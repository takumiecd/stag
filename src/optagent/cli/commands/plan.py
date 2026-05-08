"""optagent CLI plan command."""

from __future__ import annotations

import argparse
import json

from optagent.cli.context import resolve_run_id_from_args, resolve_user_id_from_args
from optagent.storage.jsonl import JsonlRunStore


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("plan", help="Create a Plan grounded on an observed node")
    parser.add_argument("--run", default=None, help="Run identifier (optional if current run is set)")
    parser.add_argument("--from-node", required=True, help="Source observed node")
    parser.add_argument("--planner", default="default")
    parser.add_argument("--max-plans", type=int, default=1)
    parser.add_argument("--action-type", default="analysis")
    parser.add_argument("--intent", default=None)
    parser.add_argument("--input", action="append")
    parser.add_argument("--store-dir", default=".optagent/runs")
    parser.add_argument("--user", default=None)
    return parser


def _parse_inputs(input_list: list[str] | None) -> dict[str, str]:
    inputs: dict[str, str] = {}
    for item in input_list or []:
        if "=" not in item:
            raise ValueError(f"--input must be key=value format: {item}")
        key, value = item.split("=", 1)
        inputs[key] = value
    return inputs


def run_plan_command(
    *,
    run_id: str,
    planner: str,
    max_plans: int,
    store_dir: str,
    from_node_id: str,
    action_type: str = "analysis",
    intent: str | None = None,
    inputs: dict[str, str] | None = None,
    user_id: str | None = None,
) -> dict:
    store = JsonlRunStore(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    plans = handle.plan(
        from_node_id,
        planner=planner,
        max_plans=max_plans,
        action_type=action_type,
        intent=intent,
        inputs=inputs,
        user_id=user_id,
    )
    store.save_run(handle)
    return {"plans": [p.to_dict() for p in plans]}


def cli_plan(args) -> int:
    inputs = _parse_inputs(getattr(args, "input", None))
    result = run_plan_command(
        run_id=resolve_run_id_from_args(args),
        planner=args.planner,
        max_plans=args.max_plans,
        store_dir=args.store_dir,
        from_node_id=args.from_node,
        action_type=args.action_type,
        intent=args.intent,
        inputs=inputs,
        user_id=resolve_user_id_from_args(args),
    )
    print(json.dumps(result["plans"], ensure_ascii=False, indent=2))
    return 0
