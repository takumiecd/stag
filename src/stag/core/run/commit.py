"""RunHandle.commit implementation.

Drives a git commit and records the corresponding stag Transition with
BranchPayload, GitChangePayload, BranchTipEvent, and SessionPointerEvent.

S2 scope: single-input commit only (merge / join is S7).
Parallel-session guard (§7.2) is TODO for S9.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from stag.core.schema.graph import Transition
from stag.core.run._forward_transition import (
    capture_git_info,
    record_forward_transition,
    resolve_current_branch,
    resolve_current_node_ids,
)


def commit_impl(
    self,
    *,
    message: str,
    branch: str | None = None,
    repo_path: Path | None = None,
    user_id: str | None = None,
    work_session_id: str | None = None,
    head_commit: str | None = None,
    dry_run: bool = False,
) -> Transition:
    """Drive a git commit and record the corresponding stag Transition.

    Steps (per REDESIGN §9.1):
    1. Resolve current_node_ids from the latest SessionPointerEvent.
       Falls back to (root_node,) if no SessionPointerEvent exists yet.
    2. Resolve current_branch (argument → git current branch).
    3. Run ``git commit -m message`` (unless dry_run=True).
    4. Capture head_commit, diff_summary, commit_log from git.
    5. Append:
       - new Node + Transition(input=current_node_ids, output=new Node)
       - BranchPayload(transition, branch=current_branch)
       - GitChangePayload(transition, branch, head_commit, diff_summary, commit_log)
       - BranchTipEvent(branch=current_branch, tip_node_id=<new node>)
       - SessionPointerEvent(current_node_ids=(<new node>,), current_branch=current_branch)
    6. Return the new Transition.

    Parameters
    ----------
    message:
        Commit message passed to ``git commit -m``.
    branch:
        Override the branch name. If None, inferred from git.
    repo_path:
        Path to the git repo root. Defaults to cwd.
    user_id:
        User ID for attribution. If None, work events are not recorded.
    work_session_id:
        Work session ID. If None, work events are not recorded.
    head_commit:
        Override the HEAD commit SHA (for testing / dry-run). If None
        and dry_run is False, git is queried for the HEAD SHA after commit.
    dry_run:
        If True, skip the actual ``git commit`` call. Useful for testing
        without a real git repository.

    Returns
    -------
    The newly created Transition.

    Notes
    -----
    TODO (S9): Add parallel-session guard. Before committing, verify that
    the latest BranchTipEvent.tip_node_id for current_branch is in
    current_node_ids. If not, reject with a non-fast-forward error.
    """
    resolved_repo_path: Path = repo_path or Path.cwd()

    # ------------------------------------------------------------------
    # 1. Resolve current_node_ids.
    # ------------------------------------------------------------------
    current_node_ids = resolve_current_node_ids(self, work_session_id)

    # S2: single-input only. Multi-input is S7.
    if len(current_node_ids) != 1:
        raise NotImplementedError(
            "S2 supports single-input commits only. "
            "Multi-input (merge/join) is implemented in S7."
        )

    for nid in current_node_ids:
        self._ensure_active_node(nid)

    # ------------------------------------------------------------------
    # 2. Resolve current_branch.
    # ------------------------------------------------------------------
    current_branch = resolve_current_branch(
        branch=branch,
        dry_run=dry_run,
        repo_path=resolved_repo_path,
    )

    # ------------------------------------------------------------------
    # 3. Run git commit (unless dry_run).
    # ------------------------------------------------------------------
    if not dry_run:
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(resolved_repo_path),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                ["git", "commit", "-m", message],
                result.stdout,
                result.stderr,
            )

    # ------------------------------------------------------------------
    # 4. Capture git info.
    # ------------------------------------------------------------------
    if head_commit is None:
        if dry_run:
            head_commit = "dry_run_sha_" + self._next_id("sha")
        else:
            from stag.core.git import repo as git_repo  # noqa: PLC0415
            head_commit = git_repo.current_commit(resolved_repo_path)

    diff_summary, commit_log = capture_git_info(
        head_commit=head_commit,
        dry_run=dry_run,
        repo_path=resolved_repo_path,
    )

    # ------------------------------------------------------------------
    # 5. Append graph records.
    # ------------------------------------------------------------------
    return record_forward_transition(
        self,
        current_node_ids=current_node_ids,
        current_branch=current_branch,
        head_commit=head_commit,
        diff_summary=diff_summary,
        commit_log=commit_log,
        extra_payloads=[],
        event_type="commit_created",
        event_summary=message,
        event_data={
            "message": message,
            "branch": current_branch,
            "head_commit": head_commit,
        },
        user_id=user_id,
        work_session_id=work_session_id,
    )
