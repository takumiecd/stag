"""stag CLI predict command."""

from __future__ import annotations

import argparse
import json

from stag.cli.context import (
    resolve_run_id_from_args,
    resolve_store,
    resolve_user_id_from_args,
    resolve_work_session_id_from_args,
)


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("predict", help="Generate predicted outcomes for an InputTransition")
    parser.add_argument("input_transition_id", help="InputTransition to expand")
    parser.add_argument("--run", default=None)
    parser.add_argument("--max-outcomes", type=int, default=1)
    parser.add_argument("--store-dir", default=".stag/runs")
    parser.add_argument("--user", default=None)
    parser.add_argument("--work-session", default=None)
    return parser


def run_predict_command(
    *,
    run_id: str,
    input_transition_id: str,
    max_outcomes: int,
    store_dir: str,
    user_id: str | None = None,
    work_session_id: str | None = None,
) -> dict:
    store = resolve_store(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    predictions = handle.predict(
        input_transition_id,
        max_outcomes=max_outcomes,
        user_id=user_id,
        work_session_id=work_session_id,
    )
    store.save_run(handle)
    return {"output_transitions": [ot.to_dict() for ot in predictions]}


def cli_predict(args) -> int:
    result = run_predict_command(
        run_id=resolve_run_id_from_args(args),
        input_transition_id=args.input_transition_id,
        max_outcomes=args.max_outcomes,
        store_dir=args.store_dir,
        user_id=resolve_user_id_from_args(args),
        work_session_id=resolve_work_session_id_from_args(args),
    )
    print(json.dumps(result["output_transitions"], ensure_ascii=False, indent=2))
    return 0
