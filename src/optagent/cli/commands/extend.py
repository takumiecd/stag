"""optagent CLI extend command."""

from __future__ import annotations

import argparse
import json

from optagent.cli.context import resolve_run_id_from_args
from optagent.storage.jsonl import JsonlRunStore


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("extend", help="Create a Plan grounded on a predicted node")
    parser.add_argument("--run", default=None)
    parser.add_argument("--node-id", required=True, help="Source predicted node")
    parser.add_argument("--planner", default="default")
    parser.add_argument("--max-plans", type=int, default=1)
    parser.add_argument("--action-type", default="analysis")
    parser.add_argument("--intent", default=None)
    parser.add_argument("--input", action="append")
    parser.add_argument("--store-dir", default=".optagent/runs")
    return parser


def _parse_inputs(input_list: list[str] | None) -> dict[str, str]:
    inputs: dict[str, str] = {}
    for item in input_list or []:
        if "=" not in item:
            raise ValueError(f"--input must be key=value format: {item}")
        k, v = item.split("=", 1)
        inputs[k] = v
    return inputs


def run_extend_command(
    *,
    run_id: str,
    node_id: str,
    planner: str,
    max_plans: int,
    store_dir: str,
    action_type: str = "analysis",
    intent: str | None = None,
    inputs: dict[str, str] | None = None,
) -> dict:
    store = JsonlRunStore(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    plans = handle.extend(
        node_id,
        planner=planner,
        max_plans=max_plans,
        action_type=action_type,
        intent=intent,
        inputs=inputs,
    )
    store.save_run(handle)
    return {"plans": [p.to_dict() for p in plans]}


def cli_extend(args) -> int:
    inputs = _parse_inputs(getattr(args, "input", None))
    result = run_extend_command(
        run_id=resolve_run_id_from_args(args),
        node_id=args.node_id,
        planner=args.planner,
        max_plans=args.max_plans,
        store_dir=args.store_dir,
        action_type=args.action_type,
        intent=args.intent,
        inputs=inputs,
    )
    print(json.dumps(result["plans"], ensure_ascii=False, indent=2))
    return 0
