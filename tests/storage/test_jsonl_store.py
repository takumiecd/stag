"""Tests for JsonlRunStore round-trip."""

from __future__ import annotations

import tempfile

from stag import init
from stag.core.cuts import is_inactive_transition
from stag.core.schema.payloads import NotePayload, PlanPayload, PredictionPayload, ResultPayload
from stag.core.schema.requirements import Requirement
from stag.storage.jsonl import JsonlRunStore


def _req() -> Requirement:
    return Requirement(requirement_id="r", target_type="task", target_id="t")


def _plan_payload(intent: str = "x") -> PlanPayload:
    return PlanPayload(payload_id="pending", target_id="pending", intent=intent)


def test_round_trip_basic():
    run = init(_req(), run_id="rt_basic")
    transition = run.plan([run.root_node_id], _plan_payload())
    run.observe(transition.transition_id, ResultPayload("x", "x", "completed", metrics={"a": 1.0}))

    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        store.save_run(run)
        loaded = store.load_run("rt_basic")

    assert loaded.run_id == run.run_id
    assert len(loaded.run_graph.nodes) == len(run.run_graph.nodes)
    assert len(loaded.run_graph.transitions) == len(run.run_graph.transitions)
    assert len(loaded.run_graph.edges) == len(run.run_graph.edges)
    assert len(loaded.run_graph.payloads) == len(run.run_graph.payloads)


def test_round_trip_work_history():
    run = init(_req(), run_id="rt_work")
    transition = run.plan(
        [run.root_node_id],
        _plan_payload("x"),
        user_id="alice",
        work_session_id="ws_1",
    )
    run.observe(
        transition.transition_id,
        ResultPayload("x", "x", "completed"),
        user_id="alice",
        work_session_id="ws_1",
    )

    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        store.save_run(run)
        loaded = store.load_run("rt_work")

    assert loaded.run_graph.work_sessions["ws_1"].user_id == "alice"
    assert [event.event_type for event in loaded.run_graph.work_events] == [
        "transition_planned",
        "result_observed",
    ]


def test_round_trip_with_predictions():
    run = init(_req(), run_id="rt_pred")
    run.note(run.root_node_id, "start note", tags=["setup"])
    transition = run.plan([run.root_node_id], _plan_payload())
    run.predict(transition.transition_id, max_outcomes=3)
    run.observe(transition.transition_id, ResultPayload("x", "x", "completed"))

    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        store.save_run(run)
        loaded = store.load_run("rt_pred")

    assert len(loaded.run_graph.transition_outputs(transition.transition_id)) == 4
    assert len(loaded.run_graph.payloads) == 6


def test_round_trip_preserves_views():
    run = init(_req(), run_id="rt_views")
    transition = run.plan([run.root_node_id], _plan_payload())
    node = run.observe(transition.transition_id, ResultPayload("x", "x", "completed"))
    run.view_create("exp-a", root_node_id=node.node_id)

    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        store.save_run(run)
        loaded = store.load_run("rt_views")

    assert "main" in loaded.run_graph.views
    assert "exp-a" in loaded.run_graph.views
    assert loaded.run_graph.views["exp-a"].root_node_id == node.node_id


def test_round_trip_cut_payload():
    run = init(_req(), run_id="rt_cut")
    transition = run.plan([run.root_node_id], _plan_payload())
    run.observe(transition.transition_id, ResultPayload("x", "x", "completed"))
    run.cut(transition.transition_id, target_kind="transition", reason="undo")

    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        store.save_run(run)
        loaded = store.load_run("rt_cut")

    assert is_inactive_transition(loaded.run_graph, transition.transition_id)


def test_prediction_payload_probability_round_trip():
    run = init(_req(), run_id="rt_prob")
    transition = run.plan([run.root_node_id], _plan_payload())
    run.predict(
        transition.transition_id,
        payloads=[
            PredictionPayload(
                payload_id="pending",
                target_id="pending",
                probability=0.75,
                confidence=0.9,
            )
        ],
    )

    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        store.save_run(run)
        loaded = store.load_run("rt_prob")

    payloads = loaded.run_graph.payloads_for_transition(transition.transition_id)
    pred = next(p for p in payloads if isinstance(p, PredictionPayload))
    assert pred.probability == 0.75
    assert pred.confidence == 0.9


def test_list_runs_returns_summaries():
    with tempfile.TemporaryDirectory() as td:
        store = JsonlRunStore(td)
        run = init(_req(), run_id="rt_listing")
        store.save_run(run)
        runs = store.list_runs()
        assert any(r["run_id"] == "rt_listing" for r in runs)
