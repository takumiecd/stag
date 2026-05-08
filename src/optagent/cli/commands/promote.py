"""optagent CLI promote command."""

from __future__ import annotations

import argparse
import json

from optagent.cli.context import resolve_run_id_from_args, resolve_user_id_from_args
from optagent.core.schema.payloads import ResultPayload
from optagent.storage.jsonl import JsonlRunStore


def add_parser(subparsers) -> argparse.ArgumentParser:
    legacy = subparsers.add_parser("promote", help="Alias for promote-transition")
    _add_transition_args(legacy)

    transition = subparsers.add_parser(
        "promote-transition", help="Promote a predicted transition into an observed transition"
    )
    _add_transition_args(transition)

    plan = subparsers.add_parser(
        "promote-plan", help="Promote a predicted plan into an observed plan"
    )
    plan.add_argument("--run", default=None)
    plan.add_argument(
        "--predicted-plan",
        dest="predicted_plan_id",
        required=True,
    )
    plan.add_argument("--to-observed-node", required=True)
    plan.add_argument("--store-dir", default=".optagent/runs")
    plan.add_argument("--user", default=None)
    return transition


def _add_transition_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run", default=None)
    parser.add_argument(
        "--predicted-transition",
        dest="predicted_transition_id",
        required=True,
    )
    parser.add_argument("--status", default="completed")
    parser.add_argument(
        "--plan",
        dest="plan_id",
        required=True,
        help="Observed plan id this transition is grounded on",
    )
    parser.add_argument("--metric", action="append")
    parser.add_argument("--store-dir", default=".optagent/runs")
    parser.add_argument("--user", default=None)


def _parse_metrics(metric_list: list[str] | None) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for item in metric_list or []:
        if "=" not in item:
            raise ValueError(f"--metric must be key=value format: {item}")
        key, value = item.split("=", 1)
        metrics[key] = float(value)
    return metrics


def run_promote_command(
    *,
    run_id: str,
    predicted_transition_id: str,
    status: str,
    plan_id: str,
    metrics: dict[str, float] | None,
    store_dir: str,
    user_id: str | None = None,
) -> dict:
    store = JsonlRunStore(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    result = ResultPayload(
        payload_id="pending",
        target_id="pending",
        status=status,  # type: ignore[arg-type]
        metrics=dict(metrics or {}),
    )
    transition = handle.promote(
        mode="transition",
        predicted_transition_id=predicted_transition_id,
        result=result,
        plan_id=plan_id,
        user_id=user_id,
    )
    store.save_run(handle)
    return {"transition": transition.to_dict()}


def run_promote_plan_command(
    *,
    run_id: str,
    predicted_plan_id: str,
    to_observed_node_id: str,
    store_dir: str,
    user_id: str | None = None,
) -> dict:
    store = JsonlRunStore(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    plans = handle.promote(
        mode="plan",
        prediction_plan_id=predicted_plan_id,
        to_observed_node_id=to_observed_node_id,
        user_id=user_id,
    )
    store.save_run(handle)
    return {"plans": [p.to_dict() for p in plans]}


def cli_promote_transition(args) -> int:
    result = run_promote_command(
        run_id=resolve_run_id_from_args(args),
        predicted_transition_id=args.predicted_transition_id,
        status=args.status,
        plan_id=args.plan_id,
        metrics=_parse_metrics(getattr(args, "metric", None)),
        store_dir=args.store_dir,
        user_id=resolve_user_id_from_args(args),
    )
    print(json.dumps(result["transition"], ensure_ascii=False, indent=2))
    return 0


def cli_promote_plan(args) -> int:
    result = run_promote_plan_command(
        run_id=resolve_run_id_from_args(args),
        predicted_plan_id=args.predicted_plan_id,
        to_observed_node_id=args.to_observed_node,
        store_dir=args.store_dir,
        user_id=resolve_user_id_from_args(args),
    )
    print(json.dumps(result["plans"], ensure_ascii=False, indent=2))
    return 0


cli_promote = cli_promote_transition
