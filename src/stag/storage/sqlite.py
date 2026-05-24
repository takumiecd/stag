"""SQLite run-directory storage."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

from stag.core import _json as _fast_json
from stag.core.append import AppendBatch, AppendResult, GraphRecordEnvelope
from stag.core.cuts import is_active_node
from stag.core.graph_view import GraphView
from stag.core.run import RunHandle
from stag.core.run_graph import RunGraph
from stag.core.schema.graph import InputTransition, Node, OutputTransition
from stag.core.schema.payloads import payload_from_dict
from stag.core.schema.requirements import Requirement
from stag.core.schema.work import WorkEvent, work_event_from_dict, work_session_from_dict
from stag.storage._cache import load_cache, save_cache


class SqliteRunStore:
    """Store a run as a per-run SQLite database inside a directory tree.

    Layout (mirrors JsonlRunStore)::

        <root>/
          <run_id>/
            run.json   – manifest identical to JsonlRunStore (shared by list_runs)
            run.db     – SQLite database with all graph records

    ``run.json`` is kept intentionally identical to the JSONL implementation so
    that ``list_runs()`` can scan a mixed root directory containing both
    JsonlRunStore and SqliteRunStore runs without special-casing.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)

    # ------------------------------------------------------------------
    # Protocol: run_path
    # ------------------------------------------------------------------

    def run_path(self, run_id: str) -> Path:
        return self.root / run_id

    # ------------------------------------------------------------------
    # Protocol: list_runs
    # ------------------------------------------------------------------

    def list_runs(self) -> list[dict]:
        if not self.root.exists():
            return []
        runs: list[dict] = []
        for entry in sorted(self.root.iterdir()):
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
                    }
                )
            except (KeyError, json.JSONDecodeError):
                continue
        return runs

    # ------------------------------------------------------------------
    # Protocol: save_run
    # ------------------------------------------------------------------

    def save_run(self, run: RunHandle) -> Path:
        run_path = self.run_path(run.run_id)
        run_path.mkdir(parents=True, exist_ok=True)

        # Write manifest (same content/format as JsonlRunStore)
        _write_json(
            run_path / "run.json",
            {
                "run_id": run.run_id,
                "requirement": run.requirement.to_dict(),
                "counters": dict(run._counters),
            },
        )

        db_path = run_path / "run.db"
        con = sqlite3.connect(str(db_path))
        try:
            _setup_db(con)

            # run_meta: counters + graph metadata (INSERT OR REPLACE)
            con.execute(
                "INSERT OR REPLACE INTO run_meta(key, value) VALUES (?, ?)",
                (
                    "requirement_json",
                    _fast_json.dumps(run.requirement.to_dict()),
                ),
            )
            con.execute(
                "INSERT OR REPLACE INTO run_meta(key, value) VALUES (?, ?)",
                (
                    "counters_json",
                    _fast_json.dumps(dict(run._counters)),
                ),
            )
            con.execute(
                "INSERT OR REPLACE INTO run_meta(key, value) VALUES (?, ?)",
                (
                    "graph_metadata_json",
                    _fast_json.dumps(dict(run.run_graph.metadata)),
                ),
            )

            # Delta-insert each collection
            _delta_insert(
                con,
                table="nodes",
                id_col="node_id",
                records=list(run.run_graph.nodes.values()),
                to_dict=lambda n: n.to_dict(),
            )
            _delta_insert(
                con,
                table="input_transitions",
                id_col="input_transition_id",
                records=list(run.run_graph.input_transitions.values()),
                to_dict=lambda it: it.to_dict(),
            )
            _delta_insert(
                con,
                table="output_transitions",
                id_col="output_transition_id",
                records=list(run.run_graph.output_transitions.values()),
                to_dict=lambda ot: ot.to_dict(),
            )
            _delta_insert(
                con,
                table="payloads",
                id_col="payload_id",
                records=list(run.run_graph.payloads.values()),
                to_dict=lambda p: p.to_dict(),
            )
            _delta_insert(
                con,
                table="views",
                id_col="view_id",
                records=list(run.run_graph.views.values()),
                to_dict=lambda v: v.to_dict(),
                extra_cols={"name": lambda v: v.name},
            )
            _delta_insert(
                con,
                table="work_sessions",
                id_col="work_session_id",
                records=list(run.run_graph.work_sessions.values()),
                to_dict=lambda s: s.to_dict(),
            )
            _delta_insert(
                con,
                table="work_events",
                id_col="event_id",
                records=list(run.run_graph.work_events),
                to_dict=lambda e: e.to_dict(),
            )

            con.commit()
        finally:
            con.close()

        # Update cache with the row counts now persisted.
        row_counts = (
            len(run.run_graph.nodes),
            len(run.run_graph.input_transitions),
            len(run.run_graph.output_transitions),
            len(run.run_graph.payloads),
            len(run.run_graph.views),
            len(run.run_graph.work_sessions),
            len(run.run_graph.work_events),
        )
        save_cache(run_path, row_counts, run.run_graph)

        return run_path

    def append_batch(self, batch: AppendBatch) -> AppendResult:
        """Atomically append a small set of new records for one work event.

        This is the concurrent-writer path. SQLite serializes writers at
        ``BEGIN IMMEDIATE``; validation then runs against the latest committed
        graph before new rows are inserted.
        """
        run_path = self.run_path(batch.run_id)
        if not run_path.exists():
            raise KeyError(f"unknown run_id: {batch.run_id}")

        db_path = run_path / "run.db"
        con = sqlite3.connect(str(db_path), timeout=30.0)
        con.row_factory = sqlite3.Row
        try:
            _setup_db(con)
            con.execute("BEGIN IMMEDIATE")
            try:
                latest_graph = _load_graph_from_connection(con)
                _validate_append_batch(latest_graph, batch)
                _insert_work_session_if_needed(con, batch)
                for envelope in batch.records:
                    _insert_graph_record(con, envelope)
                event_seq = _insert_work_event(con, batch.event)
                con.commit()
            except Exception:
                con.rollback()
                raise
        finally:
            con.close()

        return AppendResult(
            event_id=batch.event.event_id,
            event_seq=event_seq,
            record_ids=tuple(envelope.record_id for envelope in batch.records),
        )

    # ------------------------------------------------------------------
    # Protocol: load_run
    # ------------------------------------------------------------------

    @staticmethod
    def _row_counts_from_db(con: sqlite3.Connection) -> tuple[int, ...]:
        """Return current row counts for the five graph tables."""
        counts = []
        for table in (
            "nodes",
            "input_transitions",
            "output_transitions",
            "payloads",
            "views",
            "work_sessions",
            "work_events",
        ):
            (n,) = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()  # type: ignore[misc]
            counts.append(n)
        return tuple(counts)

    def load_run(self, run_id: str) -> RunHandle:
        run_path = self.run_path(run_id)
        manifest = _read_json(run_path / "run.json")
        requirement = _requirement_from_dict(manifest["requirement"])

        db_path = run_path / "run.db"
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
        try:
            _setup_db(con)
            # --- Cache fast path ---
            row_counts = self._row_counts_from_db(con)
            cached_graph = load_cache(run_path, row_counts)
            if cached_graph is not None:
                return RunHandle(
                    run_id=manifest["run_id"],
                    requirement=requirement,
                    run_graph=cached_graph,
                    _counters={str(k): int(v) for k, v in manifest.get("counters", {}).items()},
                )

            # --- Full load ---
            graph = RunGraph()

            # Restore graph metadata from run_meta
            meta_row = con.execute(
                "SELECT value FROM run_meta WHERE key = 'graph_metadata_json'"
            ).fetchone()
            if meta_row:
                graph.metadata = dict(_fast_json.loads(meta_row["value"]))

            # Nodes (seq ASC preserves insertion order)
            for row in con.execute("SELECT data_json FROM nodes ORDER BY seq ASC"):
                d = _fast_json.loads(row["data_json"])
                graph.nodes[d["node_id"]] = Node(
                    node_id=d["node_id"],
                    metadata=dict(d.get("metadata") or {}),
                )

            # InputTransitions
            for row in con.execute(
                "SELECT data_json FROM input_transitions ORDER BY seq ASC"
            ):
                d = _fast_json.loads(row["data_json"])
                it = InputTransition(
                    input_transition_id=d["input_transition_id"],
                    input_node_ids=tuple(d.get("input_node_ids") or []),
                    metadata=dict(d.get("metadata") or {}),
                )
                graph.input_transitions[it.input_transition_id] = it
                for nid in it.input_node_ids:
                    graph.input_transitions_from_node.setdefault(nid, []).append(
                        it.input_transition_id
                    )

            # OutputTransitions
            for row in con.execute(
                "SELECT data_json FROM output_transitions ORDER BY seq ASC"
            ):
                d = _fast_json.loads(row["data_json"])
                ot = OutputTransition(
                    output_transition_id=d["output_transition_id"],
                    input_transition_id=d["input_transition_id"],
                    to_node_id=d["to_node_id"],
                    metadata=dict(d.get("metadata") or {}),
                )
                graph.output_transitions[ot.output_transition_id] = ot
                graph.output_transitions_from_it.setdefault(
                    ot.input_transition_id, []
                ).append(ot.output_transition_id)
                graph.output_transitions_to_node.setdefault(ot.to_node_id, []).append(
                    ot.output_transition_id
                )

            # Payloads
            for row in con.execute("SELECT data_json FROM payloads ORDER BY seq ASC"):
                d = _fast_json.loads(row["data_json"])
                payload = payload_from_dict(d)
                graph.payloads[payload.payload_id] = payload
                if payload.target_kind == "node":
                    graph.payloads_by_node.setdefault(payload.target_id, []).append(
                        payload.payload_id
                    )
                elif payload.target_kind == "input_transition":
                    graph.payloads_by_input_transition.setdefault(
                        payload.target_id, []
                    ).append(payload.payload_id)
                elif payload.target_kind == "output_transition":
                    graph.payloads_by_output_transition.setdefault(
                        payload.target_id, []
                    ).append(payload.payload_id)

            # Views
            for row in con.execute("SELECT data_json FROM views ORDER BY seq ASC"):
                d = _fast_json.loads(row["data_json"])
                v = GraphView(
                    view_id=str(d["view_id"]),
                    name=str(d["name"]),
                    root_node_id=str(d["root_node_id"]),
                    metadata=dict(d.get("metadata") or {}),
                )
                graph.views[v.name] = v

            for row in con.execute("SELECT data_json FROM work_sessions ORDER BY seq ASC"):
                session = work_session_from_dict(_fast_json.loads(row["data_json"]))
                graph.work_sessions[session.work_session_id] = session

            for row in con.execute("SELECT seq, data_json FROM work_events ORDER BY seq ASC"):
                data = _fast_json.loads(row["data_json"])
                if data.get("seq") is None:
                    data["seq"] = row["seq"]
                graph.work_events.append(work_event_from_dict(data))

            if not graph.views:
                root_node_id = str(graph.metadata.get("root_node_id") or "n_0000")
                graph.views["main"] = GraphView(
                    view_id="view_main",
                    name="main",
                    root_node_id=root_node_id,
                )

        finally:
            con.close()

        # Write cache so next load_run is fast.
        save_cache(run_path, row_counts, graph)

        return RunHandle(
            run_id=manifest["run_id"],
            requirement=requirement,
            run_graph=graph,
            _counters={str(k): int(v) for k, v in manifest.get("counters", {}).items()},
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _setup_db(con: sqlite3.Connection) -> None:
    """Create tables and enable WAL mode."""
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS run_meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS nodes (
            seq       INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id   TEXT UNIQUE,
            data_json TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS input_transitions (
            seq                  INTEGER PRIMARY KEY AUTOINCREMENT,
            input_transition_id  TEXT UNIQUE,
            data_json            TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS output_transitions (
            seq                   INTEGER PRIMARY KEY AUTOINCREMENT,
            output_transition_id  TEXT UNIQUE,
            data_json             TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS payloads (
            seq        INTEGER PRIMARY KEY AUTOINCREMENT,
            payload_id TEXT UNIQUE,
            data_json  TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS views (
            seq       INTEGER PRIMARY KEY AUTOINCREMENT,
            view_id   TEXT UNIQUE,
            name      TEXT UNIQUE,
            data_json TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS work_sessions (
            seq              INTEGER PRIMARY KEY AUTOINCREMENT,
            work_session_id  TEXT UNIQUE,
            data_json        TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS work_events (
            seq        INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id   TEXT UNIQUE,
            data_json  TEXT
        )
        """
    )


def _load_graph_from_connection(con: sqlite3.Connection) -> RunGraph:
    """Load the latest graph from an open SQLite connection."""
    graph = RunGraph()

    meta_row = con.execute(
        "SELECT value FROM run_meta WHERE key = 'graph_metadata_json'"
    ).fetchone()
    if meta_row:
        graph.metadata = dict(_fast_json.loads(meta_row["value"]))

    for row in con.execute("SELECT data_json FROM nodes ORDER BY seq ASC"):
        data = _fast_json.loads(row["data_json"])
        graph.nodes[data["node_id"]] = Node(
            node_id=data["node_id"],
            metadata=dict(data.get("metadata") or {}),
        )

    for row in con.execute("SELECT data_json FROM input_transitions ORDER BY seq ASC"):
        data = _fast_json.loads(row["data_json"])
        it = InputTransition(
            input_transition_id=data["input_transition_id"],
            input_node_ids=tuple(data.get("input_node_ids") or []),
            metadata=dict(data.get("metadata") or {}),
        )
        graph.input_transitions[it.input_transition_id] = it
        for node_id in it.input_node_ids:
            graph.input_transitions_from_node.setdefault(node_id, []).append(
                it.input_transition_id
            )

    for row in con.execute("SELECT data_json FROM output_transitions ORDER BY seq ASC"):
        data = _fast_json.loads(row["data_json"])
        ot = OutputTransition(
            output_transition_id=data["output_transition_id"],
            input_transition_id=data["input_transition_id"],
            to_node_id=data["to_node_id"],
            metadata=dict(data.get("metadata") or {}),
        )
        graph.output_transitions[ot.output_transition_id] = ot
        graph.output_transitions_from_it.setdefault(ot.input_transition_id, []).append(
            ot.output_transition_id
        )
        graph.output_transitions_to_node.setdefault(ot.to_node_id, []).append(
            ot.output_transition_id
        )

    for row in con.execute("SELECT data_json FROM payloads ORDER BY seq ASC"):
        payload = payload_from_dict(_fast_json.loads(row["data_json"]))
        graph.payloads[payload.payload_id] = payload
        if payload.target_kind == "node":
            graph.payloads_by_node.setdefault(payload.target_id, []).append(
                payload.payload_id
            )
        elif payload.target_kind == "input_transition":
            graph.payloads_by_input_transition.setdefault(payload.target_id, []).append(
                payload.payload_id
            )
        elif payload.target_kind == "output_transition":
            graph.payloads_by_output_transition.setdefault(payload.target_id, []).append(
                payload.payload_id
            )

    for row in con.execute("SELECT data_json FROM views ORDER BY seq ASC"):
        data = _fast_json.loads(row["data_json"])
        view = GraphView(
            view_id=str(data["view_id"]),
            name=str(data["name"]),
            root_node_id=str(data["root_node_id"]),
            metadata=dict(data.get("metadata") or {}),
        )
        graph.views[view.name] = view

    for row in con.execute("SELECT data_json FROM work_sessions ORDER BY seq ASC"):
        session = work_session_from_dict(_fast_json.loads(row["data_json"]))
        graph.work_sessions[session.work_session_id] = session

    for row in con.execute("SELECT seq, data_json FROM work_events ORDER BY seq ASC"):
        data = _fast_json.loads(row["data_json"])
        if data.get("seq") is None:
            data["seq"] = row["seq"]
        graph.work_events.append(work_event_from_dict(data))

    return graph


def _validate_append_batch(graph: RunGraph, batch: AppendBatch) -> None:
    if batch.work_session.work_session_id != batch.work_session_id:
        raise ValueError("batch work_session_id does not match WorkSession")
    if batch.event.work_session_id != batch.work_session_id:
        raise ValueError("batch work_session_id does not match WorkEvent")
    if batch.work_session.user_id != batch.user_id or batch.event.user_id != batch.user_id:
        raise ValueError("batch user_id does not match work records")

    existing_session = graph.work_sessions.get(batch.work_session_id)
    if existing_session is not None and existing_session.user_id != batch.user_id:
        raise ValueError(
            f"work_session_id {batch.work_session_id!r} belongs to "
            f"user {existing_session.user_id!r}, not {batch.user_id!r}"
        )

    if batch.event.event_type == "plan_created":
        input_transition = _single_batch_record(batch, "input_transition")
        if not isinstance(input_transition.record, InputTransition):
            raise ValueError("plan_created batch must contain an InputTransition")
        for node_id in input_transition.record.input_node_ids:
            if node_id not in graph.nodes:
                raise KeyError(f"unknown input node_id: {node_id}")
            if not is_active_node(graph, node_id):
                raise ValueError(
                    f"node is in a cut (inactive) branch: {node_id}; "
                    "no new plans can extend it"
                )


def _single_batch_record(
    batch: AppendBatch,
    record_kind: str,
) -> GraphRecordEnvelope:
    matches = [envelope for envelope in batch.records if envelope.record_kind == record_kind]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {record_kind} record, got {len(matches)}")
    return matches[0]


def _insert_work_session_if_needed(con: sqlite3.Connection, batch: AppendBatch) -> None:
    con.execute(
        """
        INSERT OR IGNORE INTO work_sessions(work_session_id, data_json)
        VALUES (?, ?)
        """,
        (
            batch.work_session.work_session_id,
            _fast_json.dumps(batch.work_session.to_dict()),
        ),
    )


def _insert_graph_record(con: sqlite3.Connection, envelope: GraphRecordEnvelope) -> None:
    table, id_col = _table_for_record_kind(envelope.record_kind)
    data = envelope.record.to_dict()
    if envelope.record_kind == "view":
        con.execute(
            f"INSERT INTO {table} ({id_col}, name, data_json) VALUES (?, ?, ?)",
            (envelope.record_id, data["name"], _fast_json.dumps(data)),
        )
        return
    con.execute(
        f"INSERT INTO {table} ({id_col}, data_json) VALUES (?, ?)",
        (envelope.record_id, _fast_json.dumps(data)),
    )


def _insert_work_event(con: sqlite3.Connection, event: WorkEvent) -> int:
    data = event.to_dict()
    data.pop("seq", None)
    cur = con.execute(
        "INSERT INTO work_events(event_id, data_json) VALUES (?, ?)",
        (event.event_id, _fast_json.dumps(data)),
    )
    event_seq = int(cur.lastrowid)
    seq_event = replace(event, seq=event_seq)
    con.execute(
        "UPDATE work_events SET data_json = ? WHERE event_id = ?",
        (_fast_json.dumps(seq_event.to_dict()), event.event_id),
    )
    return event_seq


def _table_for_record_kind(record_kind: str) -> tuple[str, str]:
    if record_kind == "node":
        return "nodes", "node_id"
    if record_kind == "input_transition":
        return "input_transitions", "input_transition_id"
    if record_kind == "output_transition":
        return "output_transitions", "output_transition_id"
    if record_kind == "payload":
        return "payloads", "payload_id"
    if record_kind == "view":
        return "views", "view_id"
    raise ValueError(f"unknown record_kind: {record_kind!r}")


def _delta_insert(
    con: sqlite3.Connection,
    *,
    table: str,
    id_col: str,
    records: list,
    to_dict,
    extra_cols: dict[str, Any] | None = None,
) -> None:
    """Insert only records that are new since the last save.

    Compares COUNT(*) on disk vs len(records) in memory:
    - disk == mem  → skip
    - disk <  mem  → INSERT the tail (records[disk_count:])
    - disk >  mem  → RuntimeError (external modification / corruption)
    """
    (disk_count,) = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()  # type: ignore[misc]
    mem_count = len(records)

    if disk_count > mem_count:
        raise RuntimeError(
            f"{table}: disk has {disk_count} rows but memory has {mem_count} records. "
            "The run database may be corrupt or was modified externally."
        )

    new_records = records[disk_count:]
    if not new_records:
        return

    if extra_cols:
        col_names = ", ".join([id_col, "data_json"] + list(extra_cols.keys()))
        placeholders = ", ".join(["?"] * (2 + len(extra_cols)))
        sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
        for rec in new_records:
            data = to_dict(rec)
            extra_vals = [fn(rec) for fn in extra_cols.values()]
            con.execute(
                sql,
                [data[id_col], _fast_json.dumps(data)]
                + extra_vals,
            )
    else:
        sql = f"INSERT INTO {table} ({id_col}, data_json) VALUES (?, ?)"
        for rec in new_records:
            data = to_dict(rec)
            con.execute(
                sql,
                (
                    data[id_col],
                    _fast_json.dumps(data),
                ),
            )


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _requirement_from_dict(data: dict[str, Any]) -> Requirement:
    return Requirement(
        requirement_id=data["requirement_id"],
        target_type=data["target_type"],
        target_id=data["target_id"],
        objective=dict(data.get("objective") or {}),
        constraints=dict(data.get("constraints") or {}),
        metadata=dict(data.get("metadata") or {}),
    )
