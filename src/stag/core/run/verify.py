"""RunHandle.verify implementation.

Validates the Descendant constraint (REDESIGN §1, §10.9 invariant 7) over all
non-cut transitions in the run.

For each non-cut Transition t:
  1. Compute output_sha = current_sha(t). If None, record "missing_sha".
  2. For each input_node n in t.input_node_ids:
     - If n is the root node (not in transition_by_output_node), skip.
     - Let in_t = transition_by_output_node[n]; input_sha = current_sha(in_t).
     - If input_sha is None: record "missing_input_sha".
     - Else check via git: input_sha must be an ancestor-or-equal of output_sha.
       * exit 0 → OK (ancestor or equal)
       * exit 1 → "non_descendant"
       * exit 128 or object-missing → "dead_sha"

Uses subprocess to call git. cwd = repo_path or Path.cwd().
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from stag.core.run.handle import RunHandle


@dataclass(frozen=True)
class VerifyViolation:
    """One violation of the descendant constraint."""

    transition_id: str
    kind: Literal["dead_sha", "non_descendant", "missing_sha", "missing_input_sha"]
    message: str
    details: dict = field(default_factory=dict)  # type: ignore[assignment]


def _sha_exists(sha: str, repo_path: Path) -> bool:
    """Return True if sha is present as a git object in repo_path."""
    result = subprocess.run(
        ["git", "cat-file", "-e", sha],
        cwd=str(repo_path),
        capture_output=True,
    )
    return result.returncode == 0


def _is_ancestor(ancestor_sha: str, descendant_sha: str, repo_path: Path) -> Literal["ok", "non_descendant", "dead_sha"]:
    """Check whether ancestor_sha is an ancestor-or-equal of descendant_sha.

    Returns
    -------
    "ok"             : ancestor_sha is an ancestor of (or equal to) descendant_sha
    "non_descendant" : ancestor_sha is NOT an ancestor of descendant_sha
    "dead_sha"       : one or both objects are missing from the git object store
    """
    # Pre-check object existence for a cleaner dead_sha signal.
    if not _sha_exists(ancestor_sha, repo_path):
        return "dead_sha"
    if not _sha_exists(descendant_sha, repo_path):
        return "dead_sha"

    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor_sha, descendant_sha],
        cwd=str(repo_path),
        capture_output=True,
    )
    if result.returncode == 0:
        return "ok"
    if result.returncode == 1:
        return "non_descendant"
    # exit 128 = bad object; treat as dead_sha (shouldn't reach here after cat-file checks)
    return "dead_sha"


def verify_impl(
    self: "RunHandle",
    *,
    repo_path: Path | None = None,
    skip_dead_sha_check: bool = False,
) -> list[VerifyViolation]:
    """Verify the descendant constraint over all non-cut transitions.

    For each non-cut Transition t:
      1. Compute output_sha = current_sha(t). If None, record "missing_sha".
      2. For each input_node n in t.input_node_ids:
         - If n is the root node (not in transition_by_output_node), skip.
         - Let in_t = transition_by_output_node[n]; input_sha = current_sha(in_t).
         - If input_sha is None: record "missing_input_sha".
         - Else check via ``git merge-base --is-ancestor input_sha output_sha``.

    Parameters
    ----------
    repo_path:
        Path to the git repo root. Defaults to cwd.
    skip_dead_sha_check:
        If True, skip the ``git cat-file -e`` pre-check and classify
        non-zero ``merge-base`` exits as "non_descendant" rather than
        "dead_sha". Useful when running without a real git repo (tests).

    Returns
    -------
    List of VerifyViolation records (empty = all good).
    """
    from stag.core.cuts import inactive_transition_ids  # noqa: PLC0415

    graph = self.run_graph
    resolved_repo_path = repo_path or Path.cwd()

    inactive = inactive_transition_ids(graph)
    violations: list[VerifyViolation] = []

    for t_id, transition in graph.transitions.items():
        # Skip cut / inactive transitions.
        if t_id in inactive:
            continue

        output_sha = graph.current_sha(t_id)

        # 1. Check that transition has a sha at all.
        if output_sha is None:
            violations.append(
                VerifyViolation(
                    transition_id=t_id,
                    kind="missing_sha",
                    message=(
                        f"Transition {t_id} has no GitChangePayload; "
                        "cannot verify descendant constraint"
                    ),
                    details={"transition_id": t_id},
                )
            )
            continue

        # 2. For each input node, check that output_sha is a descendant of input_sha.
        for input_node_id in transition.input_node_ids:
            # Root node has no incoming transition → no sha → skip.
            if input_node_id not in graph.transition_by_output_node:
                continue

            in_t_id = graph.transition_by_output_node[input_node_id]
            input_sha = graph.current_sha(in_t_id)

            if input_sha is None:
                violations.append(
                    VerifyViolation(
                        transition_id=t_id,
                        kind="missing_input_sha",
                        message=(
                            f"Transition {t_id}: input node {input_node_id} "
                            f"has no GitChangePayload on its producing transition {in_t_id}"
                        ),
                        details={
                            "transition_id": t_id,
                            "input_node_id": input_node_id,
                            "input_transition_id": in_t_id,
                            "output_sha": output_sha,
                        },
                    )
                )
                continue

            if skip_dead_sha_check:
                # Simplified path for testing without a real git repo.
                result = subprocess.run(
                    ["git", "merge-base", "--is-ancestor", input_sha, output_sha],
                    cwd=str(resolved_repo_path),
                    capture_output=True,
                )
                if result.returncode == 0:
                    status: Literal["ok", "non_descendant", "dead_sha"] = "ok"
                elif result.returncode == 1:
                    status = "non_descendant"
                else:
                    status = "dead_sha"
            else:
                status = _is_ancestor(input_sha, output_sha, resolved_repo_path)

            if status == "ok":
                continue

            if status == "non_descendant":
                violations.append(
                    VerifyViolation(
                        transition_id=t_id,
                        kind="non_descendant",
                        message=(
                            f"Transition {t_id}: output sha {output_sha!r} is NOT "
                            f"a descendant of input sha {input_sha!r} "
                            f"(input node {input_node_id})"
                        ),
                        details={
                            "transition_id": t_id,
                            "input_node_id": input_node_id,
                            "input_sha": input_sha,
                            "output_sha": output_sha,
                        },
                    )
                )
            else:  # dead_sha
                violations.append(
                    VerifyViolation(
                        transition_id=t_id,
                        kind="dead_sha",
                        message=(
                            f"Transition {t_id}: sha {output_sha!r} or input sha "
                            f"{input_sha!r} is not present in git object store"
                        ),
                        details={
                            "transition_id": t_id,
                            "input_node_id": input_node_id,
                            "input_sha": input_sha,
                            "output_sha": output_sha,
                        },
                    )
                )

    return violations
