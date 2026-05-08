"""Tests for JsonlRunStore round-trip."""

from __future__ import annotations

import tempfile

from optagent import init
from optagent.core.schema.graph import Node, Transition
from optagent.core.schema.payloads import ResultPayload, SnapshotPayload
from optagent.core.schema.plans import Plan
from optagent.core.schema.requirements import Requirement
from optagent.core.schema.snapshots import StateSnapshot
from optagent.storage.jsonl import JsonlRunStore


def _req() -> Requirement:
    return Requirement(requirement_id="r", target_type="task", target_id="t")


def test_round_trip_basic():
    run = init(_req(), run_id="rt_basic")
    plan = run.plan(run.root_observed_node_id, intent="x")[0]
    result = ResultPayload(payload_id="x", target_id="x", status="completed", metrics={"a": 1.0})
    run.observe(plan.plan_id, result)

    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        store.save_run(run)
        loaded = store.load_run("rt_basic")

    assert loaded.run_id == run.run_id
    assert loaded.observed_dag.dag_id == run.observed_dag.dag_id
    assert loaded.predicted_dag.dag_id == run.predicted_dag.dag_id
    assert len(loaded.observed_dag.nodes) == len(run.observed_dag.nodes)
    assert len(loaded.observed_dag.transitions) == len(run.observed_dag.transitions)
    assert len(loaded.observed_dag.payloads) == len(run.observed_dag.payloads)


def test_round_trip_with_full_flow():
    run = init(_req(), run_id="rt_full")
    plan = run.plan(run.root_observed_node_id)[0]
    result = ResultPayload(payload_id="x", target_id="x", status="completed")
    tr = run.observe(plan.plan_id, result)
    run.derive(tr.transition_id, "finding", {"text": "x"})

    pred_root = run.predicted_dag.metadata["root_node_id"]
    pplans = run.extend(pred_root)
    pred_trs = run.predict(pplans[0].plan_id, max_outcomes=2)
    run.select_prediction(predicted_transition_ids=[t.transition_id for t in pred_trs])

    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        store.save_run(run)
        loaded = store.load_run("rt_full")

    assert len(loaded.predicted_dag.transitions) == 2
    assert len(loaded.selections) == 1
    assert any(p.payload_type == "derived" for p in loaded.observed_dag.payloads.values())


def test_round_trip_preserves_separate_payload_indexes_for_colliding_target_ids():
    run = init(_req(), run_id="rt_payload_indexes")
    run.observed_dag.add_node(Node(node_id="same"))
    run.observed_dag.attach_payload(
        SnapshotPayload(
            payload_id="pl_same_node",
            target_id="same",
            snapshot=StateSnapshot(requirement=_req()),
        )
    )
    run.observed_dag.add_plan(
        Plan(
            plan_id="plan_same",
            grounded_node_id="n_0000",
            action_type="analysis",
            intent="x",
        )
    )
    run.observed_dag.add_transition(
        Transition(
            transition_id="same",
            parent_plan_id="plan_same",
            from_node_id="n_0000",
            to_node_id="same",
        )
    )
    run.observed_dag.attach_payload(
        ResultPayload(
            payload_id="pl_same_transition",
            target_id="same",
            status="completed",
        )
    )

    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        store.save_run(run)
        loaded = store.load_run("rt_payload_indexes")

    assert [
        p.payload_id for p in loaded.observed_dag.payloads_for_node("same")
    ] == ["pl_same_node"]
    assert [
        p.payload_id for p in loaded.observed_dag.payloads_for_transition("same")
    ] == ["pl_same_transition"]


def test_list_runs_returns_summaries():
    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        run = init(_req(), run_id="rt_listing")
        store.save_run(run)
        runs = store.list_runs()
        assert any(r["run_id"] == "rt_listing" for r in runs)
