"""stag CLI note command."""

from __future__ import annotations

import argparse
import json

from stag.cli.context import resolve_store, resolve_run_id_from_args, resolve_user_id_from_args


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("note", help="Attach a lightweight memo to a node")
    parser.add_argument("--node", dest="node_id", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--tag", action="append", dest="tags")
    parser.add_argument("--run", default=None)
    parser.add_argument("--store-dir", default=".stag/runs")
    parser.add_argument("--user", default=None)
    return parser


def run_note_command(
    *,
    run_id: str,
    node_id: str,
    text: str,
    tags: list[str] | None = None,
    store_dir: str,
    user_id: str | None = None,
) -> dict:
    store = resolve_store(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    payload = handle.note(node_id, text, tags=tuple(tags or []), user_id=user_id)
    store.save_run(handle)
    return {"note": payload.to_dict()}


def cli_note(args) -> int:
    result = run_note_command(
        run_id=resolve_run_id_from_args(args),
        node_id=args.node_id,
        text=args.text,
        tags=args.tags,
        store_dir=args.store_dir,
        user_id=resolve_user_id_from_args(args),
    )
    print(json.dumps(result["note"], ensure_ascii=False, indent=2))
    return 0
