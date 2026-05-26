"""STAG path resolution for the git-native storage layout.

Run data lives outside the repo under STAG_HOME:
  ${STAG_HOME}/runs/<uuid>/

The repo only contains a single `.stag-id` file (one UUID line) that is
committed to git so that clones / worktrees share the same run.

Resolution priority for STAG_HOME:
  1. STAG_HOME env var
  2. $XDG_DATA_HOME/stag
  3. ~/.local/share/stag
"""

from __future__ import annotations

import os
from pathlib import Path


def resolve_stag_home() -> Path:
    """Resolve STAG_HOME.

    Priority:
    1. ``STAG_HOME`` env var
    2. ``$XDG_DATA_HOME/stag``
    3. ``~/.local/share/stag``
    """
    env_home = os.environ.get("STAG_HOME")
    if env_home:
        return Path(env_home)
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "stag"
    return Path.home() / ".local" / "share" / "stag"


def runs_dir() -> Path:
    """Return ``<stag_home>/runs``."""
    return resolve_stag_home() / "runs"


def stag_id_path(repo_root: Path) -> Path:
    """Return ``<repo_root>/.stag-id``."""
    return repo_root / ".stag-id"


def read_stag_id(repo_root: Path) -> str | None:
    """Read the UUID from ``.stag-id`` if present, else None."""
    path = stag_id_path(repo_root)
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text if text else None


def write_stag_id(repo_root: Path, run_id: str) -> None:
    """Write *run_id* (UUID) to ``<repo_root>/.stag-id``."""
    path = stag_id_path(repo_root)
    path.write_text(run_id + "\n", encoding="utf-8")


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from *start* (default: cwd) to find a ``.git`` directory.

    Raises
    ------
    RuntimeError
        If no ``.git`` directory is found before reaching the filesystem root.
    """
    current = (start or Path.cwd()).resolve()
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            raise RuntimeError(
                "not inside a git repository (no .git directory found). "
                "Run 'git init' first, or provide --run / STAG_RUN_ID."
            )
        current = parent


def resolve_store_dir() -> str:
    """Return the string path of ``<stag_home>/runs``.

    This is the new default store_dir replacing the old ``.stag/runs``.
    """
    return str(runs_dir())
