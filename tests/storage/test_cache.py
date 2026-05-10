"""Tests for the RunGraph pickle cache layer.

Covers cache hit, invalidation, corruption fallback, schema-version mismatch,
and post-save_run cache freshness.  Tests run for both JsonlRunStore and
SqliteRunStore to confirm equivalent behaviour.
"""

from __future__ import annotations

import pickle
import tempfile
import time
from pathlib import Path

import pytest

from stag import init
from stag.core.schema.payloads import PlanPayload, ResultPayload
from stag.core.schema.requirements import Requirement
from stag.storage._cache import CACHE_SCHEMA_VERSION, cache_path, load_cache, save_cache
from stag.storage.jsonl import JsonlRunStore
from stag.storage.sqlite import SqliteRunStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _req() -> Requirement:
    return Requirement(requirement_id="r", target_type="task", target_id="t")


def _plan() -> PlanPayload:
    return PlanPayload(payload_id="pending", target_id="pending", intent="x")


def _result() -> ResultPayload:
    return ResultPayload(payload_id="pending", target_id="pending", status="completed")


def _make_run(store, run_id: str = "cache_test"):
    """Create a run with two plan+observe cycles and persist it."""
    run = init(_req(), run_id=run_id)
    nid = run.root_node_id
    it = run.plan([nid], _plan())
    ot = run.observe(it.input_transition_id, _result())
    nid = ot.to_node_id
    it2 = run.plan([nid], _plan())
    run.observe(it2.input_transition_id, _result())
    store.save_run(run)
    return run


# ---------------------------------------------------------------------------
# Parameterisation: run both store backends
# ---------------------------------------------------------------------------


@pytest.fixture(params=["jsonl", "sqlite"])
def store_and_dir(request, tmp_path):
    store_cls = JsonlRunStore if request.param == "jsonl" else SqliteRunStore
    store = store_cls(tmp_path)
    return store, tmp_path


# ---------------------------------------------------------------------------
# 1. Cache hit: second load_run uses the cache
# ---------------------------------------------------------------------------


def test_cache_hit(store_and_dir):
    store, tmp_path = store_and_dir
    run = _make_run(store)
    run_id = run.run_id
    run_path = store.run_path(run_id)

    # First load: may or may not hit cache (save_run already wrote it)
    loaded1 = store.load_run(run_id)
    assert cache_path(run_path).exists(), "cache file should exist after save_run"

    # Record the mtime of the cache file before the second load
    mtime_before = cache_path(run_path).stat().st_mtime

    # Second load: should be a cache hit → cache file should NOT be rewritten
    # (save_cache is only called on a full load, not on a cache hit)
    loaded2 = store.load_run(run_id)

    mtime_after = cache_path(run_path).stat().st_mtime
    assert mtime_before == mtime_after, "cache file should not be rewritten on a cache hit"

    # Data integrity
    assert len(loaded2.run_graph.nodes) == len(loaded1.run_graph.nodes)
    assert len(loaded2.run_graph.payloads) == len(loaded1.run_graph.payloads)


# ---------------------------------------------------------------------------
# 2. Cache invalidation: adding a row externally invalidates the cache
# ---------------------------------------------------------------------------


def test_cache_invalidation_jsonl(tmp_path):
    store = JsonlRunStore(tmp_path)
    run = _make_run(store, "inv_test")
    run_id = run.run_id
    run_path = store.run_path(run_id)

    # First load primes the cache
    store.load_run(run_id)

    # Manually append a fake node line to nodes.jsonl to simulate an external write
    nodes_file = run_path / "nodes.jsonl"
    original_count = sum(1 for line in nodes_file.open() if line.strip())
    with nodes_file.open("a", encoding="utf-8") as fh:
        fh.write('{"node_id": "n_external", "metadata": {}}\n')

    # Second load must miss the cache (row count changed) and return the new node
    loaded = store.load_run(run_id)
    assert "n_external" in loaded.run_graph.nodes, "should pick up the externally appended node"
    assert len(loaded.run_graph.nodes) == original_count + 1


def test_cache_invalidation_sqlite(tmp_path):
    import sqlite3

    store = SqliteRunStore(tmp_path)
    run = _make_run(store, "inv_sqlite")
    run_id = run.run_id
    run_path = store.run_path(run_id)

    store.load_run(run_id)

    # Insert a row directly into nodes table
    db_path = run_path / "run.db"
    con = sqlite3.connect(str(db_path))
    con.execute(
        "INSERT INTO nodes (node_id, data_json) VALUES (?, ?)",
        ("n_external", '{"node_id":"n_external","metadata":{}}'),
    )
    con.commit()
    con.close()

    loaded = store.load_run(run_id)
    assert "n_external" in loaded.run_graph.nodes


# ---------------------------------------------------------------------------
# 3. Corrupt cache: falls back silently to full load
# ---------------------------------------------------------------------------


def test_corrupt_cache_fallback(store_and_dir):
    store, tmp_path = store_and_dir
    run = _make_run(store)
    run_id = run.run_id
    run_path = store.run_path(run_id)

    # Prime the cache
    store.load_run(run_id)
    assert cache_path(run_path).exists()

    # Overwrite cache with garbage bytes
    cache_path(run_path).write_bytes(b"\xff\xfe corrupt garbage \x00\x01")

    # load_run must not raise, and must return correct data
    loaded = store.load_run(run_id)
    assert len(loaded.run_graph.nodes) >= 1  # at least root node


# ---------------------------------------------------------------------------
# 4. Schema version mismatch: falls back to full load
# ---------------------------------------------------------------------------


def test_schema_version_mismatch(store_and_dir):
    store, tmp_path = store_and_dir
    run = _make_run(store)
    run_id = run.run_id
    run_path = store.run_path(run_id)

    store.load_run(run_id)  # prime cache
    assert cache_path(run_path).exists()

    # Read current cache, bump schema_version to a future value
    with cache_path(run_path).open("rb") as fh:
        data = pickle.load(fh)
    data["schema_version"] = CACHE_SCHEMA_VERSION + 99
    with cache_path(run_path).open("wb") as fh:
        pickle.dump(data, fh)

    # Must fall back silently and return correct data
    loaded = store.load_run(run_id)
    assert loaded.run_id == run_id
    assert len(loaded.run_graph.nodes) >= 1


# ---------------------------------------------------------------------------
# 5. save_run writes an up-to-date cache
# ---------------------------------------------------------------------------


def test_save_run_updates_cache(store_and_dir):
    store, tmp_path = store_and_dir
    run = _make_run(store)
    run_id = run.run_id
    run_path = store.run_path(run_id)

    # Cache should already exist right after save_run
    assert cache_path(run_path).exists(), "save_run must write the cache"

    with cache_path(run_path).open("rb") as fh:
        data = pickle.load(fh)

    assert data["schema_version"] == CACHE_SCHEMA_VERSION
    expected_row_counts = (
        len(run.run_graph.nodes),
        len(run.run_graph.input_transitions),
        len(run.run_graph.output_transitions),
        len(run.run_graph.payloads),
        len(run.run_graph.views),
    )
    assert data["row_counts"] == expected_row_counts
