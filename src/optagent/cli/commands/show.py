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
    parser.add_argument("--input-transition", dest="input_transition_id", default=None)
    parser.add_argument("--output-transition", dest="output_transition_id", default=None)
    parser.add_argument("--payload", dest="payload_id", default=None)
    parser.add_argument("--store-dir", default=".optagent/runs")
    return parser


def run_show_command(
    *,
    run_id: str,
    node_id: str | None,
    input_transition_id: str | None,
    output_transition_id: str | None,
    payload_id: str | None,
    store_dir: str,
) -> dict:
    store = JsonlRunStore(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    g = handle.run_graph

    if node_id is not None:
        node = g.nodes.get(node_id)
        if node is None:
            raise KeyError(f"unknown node_id: {node_id}")
        return {"node": node.to_dict()}

    if input_transition_id is not None:
        it = g.input_transitions.get(input_transition_id)
        if it is None:
            raise KeyError(f"unknown input_transition_id: {input_transition_id}")
        return {"input_transition": it.to_dict()}

    if output_transition_id is not None:
        ot = g.output_transitions.get(output_transition_id)
        if ot is None:
            raise KeyError(f"unknown output_transition_id: {output_transition_id}")
        return {"output_transition": ot.to_dict()}

    if payload_id is not None:
        payload = g.payloads.get(payload_id)
        if payload is None:
            raise KeyError(f"unknown payload_id: {payload_id}")
        return {"payload": payload.to_dict()}

    return {
        "run_id": handle.run_id,
        "requirement_id": handle.requirement.requirement_id,
        "root_node_id": handle.root_node_id,
        "node_count": len(g.nodes),
        "input_transition_count": len(g.input_transitions),
        "output_transition_count": len(g.output_transitions),
        "payload_count": len(g.payloads),
        "views": [v.name for v in handle.run_graph.views.values()],
    }


def cli_show(args) -> int:
    result = run_show_command(
        run_id=resolve_run_id_from_args(args),
        node_id=args.node_id,
        input_transition_id=args.input_transition_id,
        output_transition_id=args.output_transition_id,
        payload_id=args.payload_id,
        store_dir=args.store_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
