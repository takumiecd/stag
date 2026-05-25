"""Tests for the RunHandle public verbs."""

from __future__ import annotations

import pytest

from stag import init
from stag.core.cuts import is_active_node, is_inactive_transition
from stag.core.schema.graph import Node, Transition
from stag.core.schema.payloads import (
    CutPayload,
    NotePayload,
    PlanPayload,
    PredictionPayload,
    ResultPayload,
)
from stag.core.schema.requirements import Requirement


def _req() -> Requirement:
    return Requirement(requirement_id="r", target_type="task", target_id="t")


def _plan_payload(intent: str = "test") -> PlanPayload:
    return PlanPayload(payload_id="pending", target_id="pending", intent=intent)


def _result(status: str = "completed") -> ResultPayload:
    return ResultPayload(payload_id="pending", target_id="pending", status=status)


def test_init_seeds_root_node_and_main_view():
    run = init(_req(), run_id="t_init")
    assert run.root_node_id.startswith("n_")
    assert run.root_node_id in run.run_graph.nodes
    assert "main" in run.run_graph.views


def test_plan_creates_transition_with_plan_payload():
    run = init(_req(), run_id="t_plan")
    transition = run.plan([run.root_node_id], _plan_payload("x"))
    assert isinstance(transition, Transition)
    assert transition.transition_id in run.run_graph.transitions
    assert run.run_graph.transition_inputs(transition.transition_id) == [run.root_node_id]
    payloads = run.run_graph.payloads_for_transition(transition.transition_id)
    assert any(isinstance(p, PlanPayload) for p in payloads)


def test_anchor_creates_scope_refinement_output_node():
    run = init(_req(), run_id="t_anchor")
    node = run.anchor(run.root_node_id, "common benchmark setup")
    assert isinstance(node, Node)
    assert node.node_id in run.run_graph.nodes

    transition_id = run.run_graph.transitions_to_node(node.node_id)[0]
    payloads = run.run_graph.payloads_for_transition(transition_id)
    plan = next(p for p in payloads if isinstance(p, PlanPayload))
    result = next(p for p in payloads if isinstance(p, ResultPayload))
    assert plan.intent == "common benchmark setup"
    assert plan.action_type == "scope_refinement"
    assert result.status == "completed"


def test_plan_multi_input_nodes():
    run = init(_req(), run_id="t_plan_multi")
    t1 = run.plan([run.root_node_id], _plan_payload())
    second_node = run.observe(t1.transition_id, _result())
    t2 = run.plan([run.root_node_id, second_node.node_id], _plan_payload("merge"))
    assert run.run_graph.transition_inputs(t2.transition_id) == [
        run.root_node_id,
        second_node.node_id,
    ]


def test_observe_creates_output_node_with_result_payload():
    run = init(_req(), run_id="t_obs")
    transition = run.plan([run.root_node_id], _plan_payload())
    node = run.observe(
        transition.transition_id, ResultPayload("x", "x", "completed", metrics={"a": 1.0})
    )
    assert node.node_id in run.run_graph.nodes
    assert node.node_id in run.run_graph.transition_outputs(transition.transition_id)
    payloads = run.run_graph.payloads_for_transition(transition.transition_id)
    assert any(isinstance(p, ResultPayload) for p in payloads)


def test_predict_creates_prediction_output_nodes():
    run = init(_req(), run_id="t_pred")
    transition = run.plan([run.root_node_id], _plan_payload())
    nodes = run.predict(transition.transition_id, max_outcomes=3)
    assert len(nodes) == 3
    assert {n.node_id for n in nodes} == set(
        run.run_graph.transition_outputs(transition.transition_id)
    )
    payloads = run.run_graph.payloads_for_transition(transition.transition_id)
    assert any(isinstance(p, PredictionPayload) for p in payloads)


def test_note_attaches_to_node():
    run = init(_req(), run_id="t_note")
    note = run.note(run.root_node_id, "baseline setup", tags=["context"])
    assert isinstance(note, NotePayload)
    assert note.target_id == run.root_node_id


def test_cut_transition_cuts_transition_and_output_nodes():
    run = init(_req(), run_id="t_cut_transition")
    transition = run.plan([run.root_node_id], _plan_payload())
    node = run.observe(transition.transition_id, _result())
    cut = run.cut(transition.transition_id, target_kind="transition", reason="undo")
    assert isinstance(cut, CutPayload)
    assert cut.target_kind == "transition"
    assert is_inactive_transition(run.run_graph, transition.transition_id)
    assert not is_active_node(run.run_graph, node.node_id)


def test_cut_node_cascades_forward():
    run = init(_req(), run_id="t_cut_node")
    transition = run.plan([run.root_node_id], _plan_payload())
    node = run.observe(transition.transition_id, _result())
    run.cut(node.node_id, target_kind="node")
    with pytest.raises(ValueError):
        run.plan([node.node_id], _plan_payload())


def test_cut_already_cut_raises():
    run = init(_req(), run_id="t_cut_dup")
    transition = run.plan([run.root_node_id], _plan_payload())
    run.cut(transition.transition_id, target_kind="transition")
    with pytest.raises(ValueError):
        run.cut(transition.transition_id, target_kind="transition")


def test_trace_walks_backwards():
    run = init(_req(), run_id="t_trace")
    transition = run.plan([run.root_node_id], _plan_payload())
    node = run.observe(transition.transition_id, _result())
    ctx = run.trace(node.node_id)
    assert ctx.current_node_id == node.node_id
    assert run.root_node_id in ctx.past_node_ids
    assert transition.transition_id in ctx.transition_ids


def test_trace_includes_predictions_when_requested():
    run = init(_req(), run_id="t_trace_pred")
    transition = run.plan([run.root_node_id], _plan_payload())
    run.predict(transition.transition_id, max_outcomes=2)
    node = run.observe(transition.transition_id, _result())
    ctx = run.trace(node.node_id, include_predictions=True)
    assert ctx.prediction_payload_ids


def test_view_reachable_from():
    run = init(_req(), run_id="t_view_reach")
    t1 = run.plan([run.root_node_id], _plan_payload())
    node1 = run.observe(t1.transition_id, _result())
    t2 = run.plan([node1.node_id], _plan_payload("branch"))
    node2 = run.observe(t2.transition_id, _result())

    reachable = run.run_graph.reachable_from(run.root_node_id)
    assert reachable["node_ids"] == sorted([run.root_node_id, node1.node_id, node2.node_id])
    assert reachable["transition_ids"] == sorted([t1.transition_id, t2.transition_id])


def test_outcomes_returns_output_nodes():
    run = init(_req(), run_id="t_outcomes")
    transition = run.plan([run.root_node_id], _plan_payload())
    nodes = run.predict(transition.transition_id, max_outcomes=2)
    out = run.outcomes(transition.transition_id)
    assert out["transition_id"] == transition.transition_id
    assert set(out["output_node_ids"]) == {node.node_id for node in nodes}


def test_observe_matched_prediction_valid_passes():
    run = init(_req(), run_id="t_mpid_valid")
    transition = run.plan([run.root_node_id], _plan_payload())
    run.predict(transition.transition_id, max_outcomes=1)

    result = ResultPayload(
        payload_id="r1",
        target_id="r1",
        status="completed",
        matched_prediction_transition_id=transition.transition_id,
    )
    node = run.observe(transition.transition_id, result)
    payloads = run.run_graph.payloads_for_transition(transition.transition_id)
    rp = next(p for p in payloads if isinstance(p, ResultPayload))
    assert node.node_id in run.run_graph.nodes
    assert rp.matched_prediction_transition_id == transition.transition_id
