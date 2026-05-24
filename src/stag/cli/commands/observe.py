"""stag CLI observe command."""

from __future__ import annotations

import argparse
import json

from stag.cli.context import (
    resolve_run_id_from_args,
    resolve_store,
    resolve_user_id_from_args,
    resolve_work_session_id_from_args,
)
from stag.cli.append_batch import graph_counts, maybe_append_or_save
from stag.core.schema.payloads import ResultPayload


def _parse_metrics(metric_list: list[str] | None) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for item in metric_list or []:
        if "=" not in item:
            raise ValueError(f"--metric must be key=value format: {item}")
        key, value = item.split("=", 1)
        try:
            metrics[key] = float(value)
        except ValueError:
            raise ValueError(f"--metric value must be numeric: {item}")
    return metrics


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("observe", help="Record an observed execution result")
    parser.add_argument("input_transition_id", help="InputTransition to attach result to")
    parser.add_argument("--run", default=None)
    parser.add_argument("--status", default="completed")
    parser.add_argument("--artifact", action="append")
    parser.add_argument("--raw-output", action="append")
    parser.add_argument("--log", action="append")
    parser.add_argument("--metric", action="append")
    parser.add_argument("--error", action="append")
    parser.add_argument("--matched-prediction", default=None, dest="matched_prediction_output_id")
    parser.add_argument("--store-dir", default=".stag/runs")
    parser.add_argument("--user", default=None)
    parser.add_argument("--work-session", default=None)
    return parser


def run_observe_command(
    *,
    run_id: str,
    input_transition_id: str,
    status: str,
    artifacts: list[str] | None,
    raw_outputs: list[str] | None,
    logs: list[str] | None,
    metrics: dict[str, float] | None,
    errors: list[str] | None,
    matched_prediction_output_id: str | None = None,
    store_dir: str,
    user_id: str | None = None,
    work_session_id: str | None = None,
) -> dict:
    store = resolve_store(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    result = ResultPayload(
        payload_id="pending",
        target_id="pending",
        status=status,  # type: ignore[arg-type]
        artifacts=tuple(artifacts or []),
        raw_outputs=tuple(raw_outputs or []),
        logs=tuple(logs or []),
        metrics=dict(metrics or {}),
        errors=tuple(errors or []),
        matched_prediction_output_id=matched_prediction_output_id,
    )
    before = graph_counts(handle)
    ot = handle.observe(
        input_transition_id,
        result,
        user_id=user_id,
        work_session_id=work_session_id,
    )
    maybe_append_or_save(
        store=store,
        handle=handle,
        user_id=user_id,
        work_session_id=work_session_id,
        before=before,
    )
    return {"output_transition": ot.to_dict()}


def cli_observe(args) -> int:
    result = run_observe_command(
        run_id=resolve_run_id_from_args(args),
        input_transition_id=args.input_transition_id,
        status=args.status,
        artifacts=getattr(args, "artifact", None),
        raw_outputs=getattr(args, "raw_output", None),
        logs=getattr(args, "log", None),
        metrics=_parse_metrics(getattr(args, "metric", None)),
        errors=getattr(args, "error", None),
        matched_prediction_output_id=args.matched_prediction_output_id,
        store_dir=args.store_dir,
        user_id=resolve_user_id_from_args(args),
        work_session_id=resolve_work_session_id_from_args(args),
    )
    print(json.dumps(result["output_transition"], ensure_ascii=False, indent=2))
    return 0
