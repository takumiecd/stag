"""stag git subcommand — attach commit hashes to transitions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from stag.cli.context import (
    resolve_run_id_from_args,
    resolve_store,
    resolve_user_id_from_args,
    resolve_work_session_id_from_args,
)
from stag.cli.append_batch import graph_counts, maybe_append_or_save

# ---------------------------------------------------------------------------
# Parser registration
# ---------------------------------------------------------------------------


def add_parser(subparsers) -> argparse.ArgumentParser:
    git_parser = subparsers.add_parser("git", help="Git integration commands")
    git_sub = git_parser.add_subparsers(dest="git_command", required=True)

    sp_list = git_sub.add_parser("list", help="List git_change payloads for a Transition")
    sp_list.add_argument("--transition", required=True, dest="transition_id")
    sp_list.add_argument("--run", default=None)
    sp_list.add_argument("--store-dir", default=None)

    sp_add = git_sub.add_parser("add", help="Attach explicit Git commits to a Transition")
    sp_add.add_argument("--transition", required=True, dest="transition_id")
    sp_add.add_argument("--commit", action="append", required=True, dest="commits")
    sp_add.add_argument("--run", default=None)
    sp_add.add_argument("--store-dir", default=None)
    sp_add.add_argument("--user", default=None)
    sp_add.add_argument("--work-session", default=None)

    sp_show = git_sub.add_parser("show", help="Show git_change payloads for a Transition")
    sp_show.add_argument("--transition", required=True, dest="transition_id")
    sp_show.add_argument("--run", default=None)
    sp_show.add_argument("--store-dir", default=None)

    return git_parser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_dir(store: object, run_id: str) -> Path:
    return store.run_path(run_id)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def cli_git(args) -> int:
    if args.git_command == "add":
        return _cli_git_attach(args)
    if args.git_command == "list":
        return _cli_git_list(args)
    if args.git_command == "show":
        return _cli_git_show(args)
    print(f"unknown git subcommand: {args.git_command}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# attach
# ---------------------------------------------------------------------------


def _git_payloads_for_transition(args) -> tuple[object, list]:
    store = resolve_store(args.store_dir)
    run_id = resolve_run_id_from_args(args)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    if args.transition_id not in handle.run_graph.transitions:
        raise KeyError(f"unknown transition_id: {args.transition_id}")
    payloads = handle.run_graph.payloads_for_transition(
        args.transition_id,
        payload_type="git_change",
    )
    return handle, payloads


def _cli_git_list(args) -> int:
    try:
        _, payloads = _git_payloads_for_transition(args)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    commits: list[str] = []
    for payload in payloads:
        for entry in getattr(payload, "commit_log", ()):
            sha = getattr(entry, "sha", None)
            if sha is not None:
                commits.append(str(sha))
    print(
        json.dumps(
            {
                "transition_id": args.transition_id,
                "commits": commits,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _cli_git_show(args) -> int:
    try:
        _, payloads = _git_payloads_for_transition(args)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps([p.to_dict() for p in payloads], ensure_ascii=False, indent=2))
    return 0


def _cli_git_attach(args) -> int:
    store = resolve_store(args.store_dir)
    run_id = resolve_run_id_from_args(args)
    user_id = resolve_user_id_from_args(args)
    work_session_id = resolve_work_session_id_from_args(args)

    if not store.run_path(run_id).exists():
        print(f"error: unknown run_id: {run_id}", file=sys.stderr)
        return 1

    handle = store.load_run(run_id)
    run_dir = _run_dir(store, run_id)

    from stag.ext.git.helpers.attach import attach_commits_to_transition

    try:
        before = graph_counts(handle)
        result = attach_commits_to_transition(
            handle,
            run_dir,
            args.transition_id,
            tuple(args.commits),
            user_id=user_id,
            work_session_id=work_session_id,
        )
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    maybe_append_or_save(
        store=store,
        handle=handle,
        user_id=user_id,
        work_session_id=work_session_id,
        before=before,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
