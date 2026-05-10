"""stag CLI use command."""

from __future__ import annotations

import argparse

from stag.cli.context import save_current_run
from stag.storage.jsonl import JsonlRunStore


def add_parser(subparsers) -> argparse.ArgumentParser:
    """Register the ``use`` subcommand parser."""
    parser = subparsers.add_parser("use", help="Set the current run")
    parser.add_argument("run_id", help="Run identifier")
    parser.add_argument(
        "--store-dir",
        default=".stag/runs",
        help="Directory where runs are stored (default: .stag/runs)",
    )
    return parser


def run_use_command(
    *,
    run_id: str,
    store_dir: str,
) -> dict:
    """Set the current run.

    Parameters
    ----------
    run_id:
        Identifier of the run.
    store_dir:
        Directory where runs are stored.

    Returns
    -------
    dict with ``run_id`` key.

    Raises
    ------
    KeyError
        If the run_id does not exist.
    """
    store = JsonlRunStore(store_dir)
    run_path = store.run_path(run_id)
    if not run_path.exists():
        raise KeyError(f"unknown run_id: {run_id}")
    save_current_run(run_id, store_dir)
    return {"run_id": run_id}


def cli_use(args) -> int:
    """Entry point for ``stag use`` subcommand."""
    result = run_use_command(
        run_id=args.run_id,
        store_dir=args.store_dir,
    )
    print(result["run_id"])
    return 0
