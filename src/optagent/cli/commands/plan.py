"""optagent CLI plan command."""

from __future__ import annotations

import argparse
import json

from optagent.cli.context import resolve_run_id_from_args, resolve_user_id_from_args
from optagent.core.schema.payloads import PlanPayload
from optagent.storage.jsonl import JsonlRunStore


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "plan", help="Create an InputTransition from one or more nodes"
    )
    parser.add_argument("--run", default=None)
    parser.add_argument(
        "--input-node", action="append", required=True, dest="input_nodes",
        metavar="NODE_ID", help="Input node (repeatable for multi-node plans)"
    )
    parser.add_argument("--action-type", default="analysis")
    parser.add_argument("--intent", default="inspect state and propose next action")
    parser.add_argument("--input", action="append", metavar="KEY=VALUE")
    parser.add_argument("--assumption", action="append", metavar="TEXT")
    parser.add_argument("--view", default="main")
    parser.add_argument("--store-dir", default=".optagent/runs")
    parser.add_argument("--user", default=None)
    return parser


def _parse_kv(items: list[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"expected key=value format: {item!r}")
        k, v = item.split("=", 1)
        result[k] = v
    return result


def run_plan_command(
    *,
    run_id: str,
    input_node_ids: list[str],
    action_type: str,
    intent: str,
    inputs: dict | None = None,
    assumptions: list[str] | None = None,
    view: str = "main",
    store_dir: str,
    user_id: str | None = None,
) -> dict:
    store = JsonlRunStore(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    payload = PlanPayload(
        payload_id="pending",
        target_id="pending",
        intent=intent,
        action_type=action_type,  # type: ignore[arg-type]
        inputs=dict(inputs or {}),
        assumptions=tuple(assumptions or []),
    )
    it = handle.plan(input_node_ids, payload, view=view, user_id=user_id)
    store.save_run(handle)
    return {"input_transition": it.to_dict()}


def cli_plan(args) -> int:
    inputs = _parse_kv(getattr(args, "input", None))
    result = run_plan_command(
        run_id=resolve_run_id_from_args(args),
        input_node_ids=args.input_nodes,
        action_type=args.action_type,
        intent=args.intent,
        inputs=inputs,
        assumptions=getattr(args, "assumption", None) or [],
        view=args.view,
        store_dir=args.store_dir,
        user_id=resolve_user_id_from_args(args),
    )
    print(json.dumps(result["input_transition"], ensure_ascii=False, indent=2))
    return 0
