"""End-to-end CLI test with STAG_STORE=sqlite."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from stag.cli.commands.init import run_init_command
from stag.cli.commands.plan import run_plan_command
from stag.cli.context import resolve_store
from stag.core.run.dump import DumpOptions, dump


def test_sqlite_init_plan_dump(monkeypatch):
    monkeypatch.setenv("STAG_STORE", "sqlite")
    with tempfile.TemporaryDirectory() as td:
        # init
        result = run_init_command(
            requirement_id="r1",
            target_type="task",
            target_id="t1",
            run_id="run_e2e",
            store_dir=td,
        )
        run_id = result["run_id"]
        root = result["root_node_id"]
        assert run_id == "run_e2e"

        # plan
        plan_result = run_plan_command(
            run_id=run_id,
            input_node_ids=[root],
            action_type="analysis",
            intent="e2e test",
            store_dir=td,
        )
        assert "input_transition" in plan_result

        # dump — outline format via underlying API
        store = resolve_store(td)
        handle = store.load_run(run_id)
        output = dump(handle, "outline", DumpOptions())
        assert root in output

        # run.db exists, nodes.jsonl does NOT
        run_dir = Path(td) / run_id
        assert (run_dir / "run.db").exists(), "run.db should exist for sqlite backend"
        assert not (run_dir / "nodes.jsonl").exists(), "nodes.jsonl should not exist for sqlite backend"


def test_sqlite_plan_uses_append_batch_for_work_events(monkeypatch):
    monkeypatch.setenv("STAG_STORE", "sqlite")
    with tempfile.TemporaryDirectory() as td:
        result = run_init_command(
            requirement_id="r1",
            target_type="task",
            target_id="t1",
            run_id="run_append",
            store_dir=td,
        )

        plan_result = run_plan_command(
            run_id=result["run_id"],
            input_node_ids=[result["root_node_id"]],
            action_type="analysis",
            intent="append plan",
            store_dir=td,
            user_id="alice",
            work_session_id="ws_agent_a",
        )

        store = resolve_store(td)
        handle = store.load_run(result["run_id"])
        it_id = plan_result["input_transition"]["input_transition_id"]
        assert it_id in handle.run_graph.input_transitions
        assert handle.run_graph.work_sessions["ws_agent_a"].user_id == "alice"
        assert len(handle.run_graph.work_events) == 1
        event = handle.run_graph.work_events[0]
        assert event.seq == 1
        assert event.event_type == "plan_created"
        assert event.target_id == it_id
