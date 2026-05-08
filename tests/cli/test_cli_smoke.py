"""Smoke tests for the CLI commands.

These exercise the run_*_command entrypoints used by each CLI parser to
make sure the new pure-DAG + Payload model is wired through end to end.
"""

from __future__ import annotations

import tempfile

import pytest

from optagent.cli.commands.derive import run_derive_command
from optagent.cli.commands.extend import run_extend_command
from optagent.cli.commands.init import run_init_command
from optagent.cli.commands.list import run_list_command
from optagent.cli.commands.observe import run_observe_command
from optagent.cli.commands.plan import run_plan_command
from optagent.cli.commands.predict import run_predict_command
from optagent.cli.commands.promote import run_promote_command, run_promote_plan_command
from optagent.cli.commands.refresh import run_refresh_command
from optagent.cli.commands.rewind import run_rewind_command
from optagent.cli.commands.show import run_show_command
from optagent.cli.commands.snapshot import run_snapshot_command
from optagent.cli.commands.state import run_state_command
from optagent.cli.commands.trace import run_trace_command


def _init(td: str, rid: str = "rid") -> str:
    run_init_command(
        requirement_id="r",
        target_type="task",
        target_id="t",
        run_id=rid,
        store_dir=td,
    )
    return rid


def test_init_creates_run():
    with tempfile.TemporaryDirectory() as td:
        rid = _init(td)
        runs = run_list_command(store_dir=td)["runs"]
        assert any(r["run_id"] == rid for r in runs)


def test_full_observed_flow():
    with tempfile.TemporaryDirectory() as td:
        rid = _init(td)
        plans = run_plan_command(
            run_id=rid,
            planner="d",
            max_plans=1,
            store_dir=td,
            from_node_id="n_0000",
            intent="x",
        )["plans"]
        plan_id = plans[0]["plan_id"]
        observed = run_observe_command(
            run_id=rid,
            plan_id=plan_id,
            status="completed",
            artifacts=["a/b"],
            raw_outputs=None,
            logs=None,
            metrics={"score": 0.5},
            errors=None,
            store_dir=td,
        )["transition"]
        tid = observed["transition_id"]
        derived = run_derive_command(
            run_id=rid,
            transition_id=tid,
            derived_type="finding",
            payload={"text": "hi"},
            payload_id=None,
            generator="cli",
            confidence=None,
            store_dir=td,
        )["record"]
        assert derived["derived_type"] == "finding"
        history = run_trace_command(run_id=rid, from_node_id=observed["to_node_id"], depth=None, store_dir=td)
        assert tid in history["history"]["transition_ids"]
        node_view = run_show_command(
            run_id=rid, node_id="n_0000", plan_id=None, transition_id=None, payload_id=None, store_dir=td
        )
        assert node_view["node"]["node_id"] == "n_0000"


def test_predict_extend_and_promote():
    with tempfile.TemporaryDirectory() as td:
        rid = _init(td)
        # extend predicted root
        pred_root = "n_0001"
        pplans = run_extend_command(
            run_id=rid, node_id=pred_root, planner="d", max_plans=1, store_dir=td
        )["plans"]
        pplan_id = pplans[0]["plan_id"]
        predictions = run_predict_command(
            run_id=rid, plan_id=pplan_id, predictor="d", max_outcomes=2, store_dir=td
        )["predictions"]
        assert len(predictions) == 2
        # promote-plan
        plans = run_promote_plan_command(
            run_id=rid, predicted_plan_id=pplan_id, to_observed_node_id="n_0000", store_dir=td
        )["plans"]
        obs_plan_id = plans[0]["plan_id"]
        # promote-transition
        tr = run_promote_command(
            run_id=rid,
            predicted_transition_id=predictions[0]["transition_id"],
            status="completed",
            plan_id=obs_plan_id,
            metrics={"x": 1.0},
            store_dir=td,
        )["transition"]
        assert tr["parent_plan_id"] == obs_plan_id


def test_rewind_and_refresh():
    with tempfile.TemporaryDirectory() as td:
        rid = _init(td)
        plans = run_plan_command(
            run_id=rid,
            planner="d",
            max_plans=1,
            store_dir=td,
            from_node_id="n_0000",
        )["plans"]
        observed = run_observe_command(
            run_id=rid,
            plan_id=plans[0]["plan_id"],
            status="completed",
            artifacts=None,
            raw_outputs=None,
            logs=None,
            metrics=None,
            errors=None,
            store_dir=td,
        )["transition"]
        tid = observed["transition_id"]
        cut = run_rewind_command(
            run_id=rid,
            transition_id=tid,
            from_node_id=observed["to_node_id"],
            reason="oops",
            store_dir=td,
        )["cut"]
        assert cut["target_id"] == tid
        # refresh
        new_dag = run_refresh_command(run_id=rid, from_node_id="n_0000", store_dir=td)["predicted_dag"]
        assert new_dag["metadata"]["role"] == "predicted"


def test_state_update_and_snapshot_rebuild():
    with tempfile.TemporaryDirectory() as td:
        rid = _init(td)
        result = run_state_command(
            run_id=rid,
            store_dir=td,
            node_id="n_0000",
            add_knowledge=["learn"],
            add_open_question=None,
            add_artifact=None,
            add_prediction=None,
            add_branch=None,
        )
        assert "snapshot" in result
        rebuilt = run_snapshot_command(
            run_id=rid, node_id="n_0000", rebuild=True, store_dir=td
        )
        assert rebuilt["target_id"] == "n_0000"
