"""optagent CLI rewind command."""

from __future__ import annotations

import argparse
import json

from optagent.cli.context import resolve_run_id_from_args, resolve_user_id_from_args
from optagent.storage.jsonl import JsonlRunStore


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("rewind", help="Cut an observed transition")
    parser.add_argument("--transition", dest="transition_id", required=True)
    parser.add_argument("--from-node", required=True)
    parser.add_argument("--run", default=None)
    parser.add_argument("--reason", default=None)
    parser.add_argument("--store-dir", default=".optagent/runs")
    parser.add_argument("--user", default=None)
    return parser


def run_rewind_command(
    *,
    run_id: str,
    transition_id: str,
    from_node_id: str,
    reason: str | None,
    store_dir: str,
    user_id: str | None = None,
) -> dict:
    store = JsonlRunStore(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    cut = handle.rewind(
        transition_id,
        from_node_id=from_node_id,
        reason=reason,
        user_id=user_id,
    )
    store.save_run(handle)
    return {"cut": cut.to_dict()}


def cli_rewind(args) -> int:
    result = run_rewind_command(
        run_id=resolve_run_id_from_args(args),
        transition_id=args.transition_id,
        from_node_id=args.from_node,
        reason=args.reason,
        store_dir=args.store_dir,
        user_id=resolve_user_id_from_args(args),
    )
    print(json.dumps(result["cut"], ensure_ascii=False, indent=2))
    return 0
