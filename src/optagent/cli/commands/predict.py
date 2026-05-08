"""optagent CLI predict command."""

from __future__ import annotations

import argparse
import json

from optagent.cli.context import resolve_run_id_from_args
from optagent.storage.jsonl import JsonlRunStore


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("predict", help="Predict outcomes for a plan")
    parser.add_argument("plan_id")
    parser.add_argument("--run", default=None)
    parser.add_argument("--predictor", default="default")
    parser.add_argument("--max-outcomes", type=int, default=1)
    parser.add_argument("--store-dir", default=".optagent/runs")
    return parser


def run_predict_command(
    *,
    run_id: str,
    plan_id: str,
    predictor: str,
    max_outcomes: int,
    store_dir: str,
) -> dict:
    store = JsonlRunStore(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    predictions = handle.predict(plan_id, predictor=predictor, max_outcomes=max_outcomes)
    store.save_run(handle)
    return {"predictions": [p.to_dict() for p in predictions]}


def cli_predict(args) -> int:
    result = run_predict_command(
        run_id=resolve_run_id_from_args(args),
        plan_id=args.plan_id,
        predictor=args.predictor,
        max_outcomes=args.max_outcomes,
        store_dir=args.store_dir,
    )
    print(json.dumps(result["predictions"], ensure_ascii=False, indent=2))
    return 0
