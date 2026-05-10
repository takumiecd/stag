"""Tests for incremental-append behaviour of JsonlRunStore.save_run."""

from __future__ import annotations

import tempfile

import pytest

from stag import init
from stag.core.schema.payloads import PlanPayload, ResultPayload
from stag.core.schema.requirements import Requirement
from stag.storage.jsonl import JsonlRunStore


def _req() -> Requirement:
    return Requirement(requirement_id="r", target_type="task", target_id="t")


def _plan() -> PlanPayload:
    return PlanPayload(payload_id="pending", target_id="pending", intent="x")


def _result() -> ResultPayload:
    return ResultPayload(payload_id="pending", target_id="pending", status="completed")


def test_second_save_only_appends_new_lines():
    """Second save_run must not rewrite existing lines — only append new ones."""
    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        run = init(_req(), run_id="incr_append")

        # First save: root node only
        store.save_run(run)
        nodes_path = store.run_path("incr_append") / "nodes.jsonl"

        first_lines = nodes_path.read_text(encoding="utf-8").splitlines()
        assert len(first_lines) == 1, "expected exactly one node after init"
        first_head = first_lines[0]

        # Add a node via plan+observe
        it = run.plan([run.root_node_id], _plan())
        run.observe(it.input_transition_id, _result())

        # Second save
        store.save_run(run)

        second_lines = nodes_path.read_text(encoding="utf-8").splitlines()
        assert len(second_lines) == 2, "expected two nodes after observe"

        # The first line must be identical — not rewritten
        assert second_lines[0] == first_head, (
            "First line changed on second save — full-rewrite detected instead of append"
        )


def test_second_save_file_grows_only_by_new_records():
    """Byte count of existing content must be a prefix of the file after second save."""
    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        run = init(_req(), run_id="incr_prefix")

        store.save_run(run)
        nodes_path = store.run_path("incr_prefix") / "nodes.jsonl"
        content_after_first = nodes_path.read_bytes()

        it = run.plan([run.root_node_id], _plan())
        run.observe(it.input_transition_id, _result())
        store.save_run(run)

        content_after_second = nodes_path.read_bytes()
        assert content_after_second.startswith(content_after_first), (
            "File content after second save does not start with content from first save"
        )


def test_disk_ahead_of_memory_raises():
    """If disk has more lines than memory, save_run must raise RuntimeError."""
    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        run = init(_req(), run_id="corrupt_run")
        store.save_run(run)

        nodes_path = store.run_path("corrupt_run") / "nodes.jsonl"
        # Inject a spurious extra line
        with nodes_path.open("a", encoding="utf-8") as f:
            f.write('{"node_id": "n_fake", "metadata": {}}\n')

        with pytest.raises(RuntimeError, match="nodes.jsonl"):
            store.save_run(run)


def test_disk_behind_memory_is_normal_append():
    """disk_count < mem_count is the normal incremental case — no error raised."""
    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        run = init(_req(), run_id="normal_append")

        store.save_run(run)

        it = run.plan([run.root_node_id], _plan())
        run.observe(it.input_transition_id, _result())

        # Should not raise
        store.save_run(run)

        nodes_path = store.run_path("normal_append") / "nodes.jsonl"
        assert len(nodes_path.read_text(encoding="utf-8").splitlines()) == 2
