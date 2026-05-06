"""optagent CLI list command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def add_parser(subparsers) -> argparse.ArgumentParser:
    """Register the ``list`` subcommand parser."""
    parser = subparsers.add_parser("list", help="List saved runs")
    parser.add_argument(
        "--store-dir",
        default=".optagent/runs",
        help="Directory where runs are stored (default: .optagent/runs)",
    )
    return parser


def run_list_command(*, store_dir: str) -> dict:
    """List all runs in the store directory.

    Parameters
    ----------
    store_dir:
        Directory where runs are stored.

    Returns
    -------
    dict with ``runs`` key containing a list of run summary dicts.
    """
    root = Path(store_dir)
    if not root.exists():
        return {"runs": []}

    runs: list[dict] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        run_json = entry / "run.json"
        if not run_json.exists():
            continue
        try:
            data = json.loads(run_json.read_text(encoding="utf-8"))
            runs.append(
                {
                    "run_id": data["run_id"],
                    "requirement_id": data["requirement"]["requirement_id"],
                    "target_type": data["requirement"]["target_type"],
                    "target_id": data["requirement"]["target_id"],
                    "current_observed_state_id": data.get("current_observed_state_id", ""),
                }
            )
        except (KeyError, json.JSONDecodeError):
            continue

    return {"runs": runs}


def cli_list(args) -> int:
    """Entry point for ``optagent list`` subcommand.

    Prints the list of runs as JSON to stdout.
    """
    result = run_list_command(store_dir=args.store_dir)
    print(json.dumps(result["runs"], ensure_ascii=False, indent=2))
    return 0
