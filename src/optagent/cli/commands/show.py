"""optagent CLI show command."""

from __future__ import annotations

import argparse
import json

from optagent.cli.context import resolve_run_id_from_args
from optagent.storage.jsonl import JsonlRunStore


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("show", help="Show run details")
    parser.add_argument("--run", default=None)
    parser.add_argument("--node", dest="node_id", default=None)
    parser.add_argument("--plan", dest="plan_id", default=None)
    parser.add_argument("--transition", dest="transition_id", default=None)
    parser.add_argument("--payload", dest="payload_id", default=None)
    parser.add_argument("--store-dir", default=".optagent/runs")
    return parser


def run_show_command(
    *,
    run_id: str,
    node_id: str | None,
    plan_id: str | None,
    transition_id: str | None,
    payload_id: str | None,
    store_dir: str,
) -> dict:
    store = JsonlRunStore(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)

    if node_id is not None:
        node = handle.observed_dag.nodes.get(node_id) or handle.predicted_dag.nodes.get(node_id)
        if node is None:
            raise KeyError(f"unknown node_id: {node_id}")
        return {"node": node.to_dict()}

    if plan_id is not None:
        plan = handle.observed_dag.plans.get(plan_id) or handle.predicted_dag.plans.get(plan_id)
        if plan is None:
            raise KeyError(f"unknown plan_id: {plan_id}")
        return {"plan": plan.to_dict()}

    if transition_id is not None:
        tr = handle.observed_dag.transitions.get(transition_id) or handle.predicted_dag.transitions.get(transition_id)
        if tr is None:
            raise KeyError(f"unknown transition_id: {transition_id}")
        return {"transition": tr.to_dict()}

    if payload_id is not None:
        payload = handle.observed_dag.payloads.get(payload_id) or handle.predicted_dag.payloads.get(payload_id)
        if payload is None:
            raise KeyError(f"unknown payload_id: {payload_id}")
        return {"payload": payload.to_dict()}

    return {
        "run_id": handle.run_id,
        "requirement_id": handle.requirement.requirement_id,
        "root_observed_node_id": handle.root_observed_node_id,
        "observed_dag": handle.observed_dag.to_dict(),
        "predicted_dag": handle.predicted_dag.to_dict(),
    }


def cli_show(args) -> int:
    result = run_show_command(
        run_id=resolve_run_id_from_args(args),
        node_id=args.node_id,
        plan_id=args.plan_id,
        transition_id=args.transition_id,
        payload_id=args.payload_id,
        store_dir=args.store_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
