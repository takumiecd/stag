"""stag CLI note command."""

from __future__ import annotations

import argparse
import json

from stag.cli.context import (
    resolve_run_id_from_args,
    resolve_store,
    resolve_user_id_from_args,
    resolve_work_session_id_from_args,
)
from stag.cli.append_batch import graph_counts, maybe_append_or_save


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("note", help="Attach a lightweight memo to a node")
    parser.add_argument("--node", dest="node_id", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--tag", action="append", dest="tags")
    parser.add_argument("--run", default=None)
    parser.add_argument("--store-dir", default=".stag/runs")
    parser.add_argument("--user", default=None)
    parser.add_argument("--work-session", default=None)
    return parser


def run_note_command(
    *,
    run_id: str,
    node_id: str,
    text: str,
    tags: list[str] | None = None,
    store_dir: str,
    user_id: str | None = None,
    work_session_id: str | None = None,
) -> dict:
    store = resolve_store(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    before = graph_counts(handle)
    payload = handle.note(
        node_id,
        text,
        tags=tuple(tags or []),
        user_id=user_id,
        work_session_id=work_session_id,
    )
    maybe_append_or_save(
        store=store,
        handle=handle,
        user_id=user_id,
        work_session_id=work_session_id,
        before=before,
    )
    return {"note": payload.to_dict()}


def cli_note(args) -> int:
    result = run_note_command(
        run_id=resolve_run_id_from_args(args),
        node_id=args.node_id,
        text=args.text,
        tags=args.tags,
        store_dir=args.store_dir,
        user_id=resolve_user_id_from_args(args),
        work_session_id=resolve_work_session_id_from_args(args),
    )
    print(json.dumps(result["note"], ensure_ascii=False, indent=2))
    return 0
