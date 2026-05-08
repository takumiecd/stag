"""optagent CLI derive command."""

from __future__ import annotations

import argparse
import json

from optagent.cli.context import resolve_run_id_from_args, resolve_user_id_from_args
from optagent.storage.jsonl import JsonlRunStore


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("derive", help="Attach a derived payload to an observed transition")
    parser.add_argument("transition_id")
    parser.add_argument("--run", default=None)
    parser.add_argument("--type", dest="derived_type", default="finding")
    parser.add_argument("--id", dest="payload_id", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--confidence", type=float, default=None)
    parser.add_argument("--store-dir", default=".optagent/runs")
    parser.add_argument("--user", default=None)
    return parser


def run_derive_command(
    *,
    run_id: str,
    transition_id: str,
    derived_type: str,
    payload: dict,
    payload_id: str | None,
    generator: str,
    confidence: float | None,
    store_dir: str,
    user_id: str | None = None,
) -> dict:
    store = JsonlRunStore(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    record = handle.derive(
        transition_id,
        derived_type,
        payload,
        payload_id=payload_id,
        generator=generator,
        confidence=confidence,
        user_id=user_id,
    )
    store.save_run(handle)
    return {"record": record.to_dict()}


def cli_derive(args) -> int:
    payload: dict = {}
    if args.text is not None:
        payload["text"] = args.text
    result = run_derive_command(
        run_id=resolve_run_id_from_args(args),
        transition_id=args.transition_id,
        derived_type=args.derived_type,
        payload=payload,
        payload_id=args.payload_id,
        generator="cli",
        confidence=args.confidence,
        store_dir=args.store_dir,
        user_id=resolve_user_id_from_args(args),
    )
    print(json.dumps(result["record"], ensure_ascii=False, indent=2))
    return 0
