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
