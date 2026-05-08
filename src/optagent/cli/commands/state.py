"""optagent CLI state command."""

from __future__ import annotations

import argparse
import json

from optagent.cli.context import resolve_run_id_from_args
from optagent.storage.jsonl import JsonlRunStore


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("state", help="Show or update an observed node's snapshot")
    parser.add_argument("--run", default=None)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--add-knowledge", action="append")
    parser.add_argument("--add-open-question", action="append")
    parser.add_argument("--add-artifact", action="append")
    parser.add_argument("--add-prediction", action="append")
    parser.add_argument("--add-branch", action="append")
    parser.add_argument("--store-dir", default=".optagent/runs")
    return parser


def _parse_artifact(value: str) -> tuple[str, str, str | None]:
    parts = value.split(":", 2)
    if len(parts) < 2:
        raise ValueError(f"--add-artifact must be id:type:path or id:type: {value}")
    return parts[0], parts[1], parts[2] if len(parts) > 2 and parts[2] else None


def _parse_prediction(value: str) -> tuple[str, str]:
    parts = value.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"--add-prediction must be id:summary: {value}")
    return parts[0], parts[1]


def run_state_command(
    *,
    run_id: str,
    store_dir: str,
    node_id: str,
    add_knowledge: list[str] | None,
    add_open_question: list[str] | None,
    add_artifact: list[str] | None,
    add_prediction: list[str] | None,
    add_branch: list[str] | None,
) -> dict:
    store = JsonlRunStore(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    will_update = any(
        [add_knowledge, add_open_question, add_artifact, add_prediction, add_branch]
    )
    if will_update:
        artifacts = [_parse_artifact(v) for v in add_artifact or []]
        predictions = [_parse_prediction(v) for v in add_prediction or []]
        snap = handle.state_update(
            node_id=node_id,
            add_knowledge=add_knowledge,
            add_open_question=add_open_question,
            add_artifact=artifacts or None,
            add_prediction=predictions or None,
            add_branch=add_branch,
        )
        store.save_run(handle)
    else:
        snap = handle.state_show(node_id)
    return {"snapshot": snap.to_dict()}


def cli_state(args) -> int:
    result = run_state_command(
        run_id=resolve_run_id_from_args(args),
        store_dir=args.store_dir,
        node_id=args.node_id,
        add_knowledge=getattr(args, "add_knowledge", None),
        add_open_question=getattr(args, "add_open_question", None),
        add_artifact=getattr(args, "add_artifact", None),
        add_prediction=getattr(args, "add_prediction", None),
        add_branch=getattr(args, "add_branch", None),
    )
    print(json.dumps(result["snapshot"], ensure_ascii=False, indent=2))
    return 0
