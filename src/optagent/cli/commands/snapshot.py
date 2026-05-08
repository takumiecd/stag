"""optagent CLI snapshot command."""

from __future__ import annotations

import argparse
import json

from optagent.cli.context import resolve_run_id_from_args
from optagent.storage.jsonl import JsonlRunStore


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("snapshot", help="Show or rebuild a node's snapshot payload")
    parser.add_argument("--run", default=None)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--store-dir", default=".optagent/runs")
    return parser


def run_snapshot_command(*, run_id: str, node_id: str, rebuild: bool, store_dir: str) -> dict:
    store = JsonlRunStore(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    if rebuild:
        snap = handle.snapshot_rebuild(node_id)
        store.save_run(handle)
    else:
        snap = handle.state_show(node_id)
    return snap.to_dict()


def cli_snapshot(args) -> int:
    result = run_snapshot_command(
        run_id=resolve_run_id_from_args(args),
        node_id=args.node_id,
        rebuild=args.rebuild,
        store_dir=args.store_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
