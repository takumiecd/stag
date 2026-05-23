"""Local/shared sync id map helpers."""

from __future__ import annotations

from pathlib import Path

from stag.core import _json as _fast_json


IdMapKey = tuple[str, str, str, str]


def idmap_key(remote: str, shared_run_id: str, kind: str, local_id: str) -> IdMapKey:
    """Return the de-duplication key for a local/shared id mapping."""
    return remote, shared_run_id, kind, local_id


def idmap_row(
    remote: str,
    shared_run_id: str,
    kind: str,
    local_id: str,
    shared_id: str,
) -> dict[str, str]:
    """Return a JSONL row for ``idmap.jsonl``."""
    return {
        "remote": remote,
        "shared_run_id": shared_run_id,
        "record_kind": kind,
        "local_id": local_id,
        "shared_id": shared_id,
    }


def read_idmap(
    *,
    run_path: Path,
    remote: str,
    shared_run_id: str,
) -> dict[IdMapKey, str]:
    """Load local id to shared id mappings for one remote/shared run."""
    path = run_path / "idmap.jsonl"
    if not path.exists():
        return {}
    result: dict[IdMapKey, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = _fast_json.loads(line)
        if row.get("remote") != remote or row.get("shared_run_id") != shared_run_id:
            continue
        key = idmap_key(
            str(row["remote"]),
            str(row["shared_run_id"]),
            str(row["record_kind"]),
            str(row["local_id"]),
        )
        result[key] = str(row["shared_id"])
    return result


def append_idmap(*, run_path: Path, rows: list[dict[str, str]]) -> None:
    """Append non-duplicate id mappings to ``idmap.jsonl``."""
    if not rows:
        return
    path = run_path / "idmap.jsonl"
    existing: set[IdMapKey] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = _fast_json.loads(line)
            existing.add(
                idmap_key(
                    str(row["remote"]),
                    str(row["shared_run_id"]),
                    str(row["record_kind"]),
                    str(row["local_id"]),
                )
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            key = idmap_key(
                row["remote"],
                row["shared_run_id"],
                row["record_kind"],
                row["local_id"],
            )
            if key in existing:
                continue
            fh.write(_fast_json.dumps(row) + "\n")
            existing.add(key)
