"""Tests for RunGraph container."""

from __future__ import annotations

import pytest

from optagent.core.run_graph import RunGraph
from optagent.core.schema.graph import InputTransition, Node, OutputTransition
from optagent.core.schema.payloads import CutPayload, NotePayload, PredictionPayload, ResultPayload


def _base_graph() -> RunGraph:
    g = RunGraph()
    g.add_node(Node(node_id="n_a"))
    g.add_node(Node(node_id="n_b"))
    return g


def test_add_node_duplicate_rejected():
    g = _base_graph()
    with pytest.raises(ValueError):
        g.add_node(Node(node_id="n_a"))


def test_add_input_transition_indexes():
    g = _base_graph()
    it = InputTransition(input_transition_id="it_1", input_node_ids=("n_a",))
    g.add_input_transition(it)
    assert "it_1" in g.input_transitions_from_node["n_a"]


def test_add_input_transition_unknown_node_rejected():
    g = _base_graph()
    with pytest.raises(KeyError):
        g.add_input_transition(
            InputTransition(input_transition_id="it_1", input_node_ids=("n_missing",))
        )


def test_add_output_transition_indexes():
    g = _base_graph()
    it = InputTransition(input_transition_id="it_1", input_node_ids=("n_a",))
    g.add_input_transition(it)
    ot = OutputTransition(output_transition_id="ot_1", input_transition_id="it_1", to_node_id="n_b")
    g.add_output_transition(ot)
    assert "ot_1" in g.output_transitions_from_it["it_1"]
    assert "ot_1" in g.output_transitions_to_node["n_b"]


def test_add_output_transition_unknown_it_rejected():
    g = _base_graph()
    with pytest.raises(KeyError):
        g.add_output_transition(
            OutputTransition(output_transition_id="ot_1", input_transition_id="it_missing", to_node_id="n_b")
        )


def test_attach_payload_to_node():
    g = _base_graph()
    g.attach_payload(NotePayload(payload_id="pl_1", target_id="n_a", text="hi"))
    payloads = g.payloads_for_node("n_a")
    assert len(payloads) == 1
    assert payloads[0].payload_id == "pl_1"


def test_attach_payload_unknown_target_rejected():
    g = _base_graph()
    with pytest.raises(KeyError):
        g.attach_payload(NotePayload(payload_id="pl_x", target_id="n_missing", text="x"))


def test_payloads_for_output_transition():
    g = _base_graph()
    it = InputTransition(input_transition_id="it_1", input_node_ids=("n_a",))
    g.add_input_transition(it)
    ot = OutputTransition(output_transition_id="ot_1", input_transition_id="it_1", to_node_id="n_b")
    g.add_output_transition(ot)
    g.attach_payload(ResultPayload(payload_id="rp_1", target_id="ot_1", status="completed"))
    payloads = g.payloads_for_output_transition("ot_1")
    assert len(payloads) == 1
    assert isinstance(payloads[0], ResultPayload)


def test_roots():
    g = _base_graph()
    it = InputTransition(input_transition_id="it_1", input_node_ids=("n_a",))
    g.add_input_transition(it)
    ot = OutputTransition(output_transition_id="ot_1", input_transition_id="it_1", to_node_id="n_b")
    g.add_output_transition(ot)
    roots = g.roots()
    assert "n_a" in roots
    assert "n_b" not in roots


def test_multi_input_node_transition():
    g = _base_graph()
    g.add_node(Node(node_id="n_c"))
    it = InputTransition(input_transition_id="it_1", input_node_ids=("n_a", "n_b"))
    g.add_input_transition(it)
    ot = OutputTransition(output_transition_id="ot_1", input_transition_id="it_1", to_node_id="n_c")
    g.add_output_transition(ot)
    assert "it_1" in g.input_transitions_from_node["n_a"]
    assert "it_1" in g.input_transitions_from_node["n_b"]


def _graph_with_it_and_ots() -> tuple:
    """n_a → it_1 → [ot_pred → n_b, ot_result → n_c]"""
    g = RunGraph()
    for nid in ("n_a", "n_b", "n_c"):
        g.add_node(Node(node_id=nid))
    it = InputTransition(input_transition_id="it_1", input_node_ids=("n_a",))
    g.add_input_transition(it)
    ot_pred = OutputTransition(output_transition_id="ot_pred", input_transition_id="it_1", to_node_id="n_b")
    g.add_output_transition(ot_pred)
    g.attach_payload(PredictionPayload(payload_id="pl_pred", target_id="ot_pred"))
    ot_result = OutputTransition(output_transition_id="ot_result", input_transition_id="it_1", to_node_id="n_c")
    g.add_output_transition(ot_result)
    g.attach_payload(ResultPayload(payload_id="pl_result", target_id="ot_result", status="completed"))
    return g, it, ot_pred, ot_result


def test_output_kind_classifies_payloads():
    g, _, ot_pred, ot_result = _graph_with_it_and_ots()
    assert g.output_kind(ot_pred.output_transition_id) == "prediction"
    assert g.output_kind(ot_result.output_transition_id) == "result"

    # no payloads → unknown
    g2 = RunGraph()
    g2.add_node(Node(node_id="n_x"))
    g2.add_node(Node(node_id="n_y"))
    it2 = InputTransition(input_transition_id="it_x", input_node_ids=("n_x",))
    g2.add_input_transition(it2)
    ot_empty = OutputTransition(output_transition_id="ot_empty", input_transition_id="it_x", to_node_id="n_y")
    g2.add_output_transition(ot_empty)
    assert g2.output_kind("ot_empty") == "unknown"

    # both → mixed
    g.attach_payload(PredictionPayload(payload_id="pl_mix", target_id=ot_result.output_transition_id))
    assert g.output_kind(ot_result.output_transition_id) == "mixed"


def test_output_ids_for_input_filters_by_kind_and_activity():
    g, it, ot_pred, ot_result = _graph_with_it_and_ots()

    all_ids = g.output_ids_for_input(it.input_transition_id, active_only=False)
    assert set(all_ids) == {"ot_pred", "ot_result"}

    pred_ids = g.output_ids_for_input(it.input_transition_id, kind="prediction", active_only=False)
    assert pred_ids == ["ot_pred"]

    result_ids = g.output_ids_for_input(it.input_transition_id, kind="result", active_only=False)
    assert result_ids == ["ot_result"]

    # cut ot_result and check active_only filtering
    g.attach_payload(
        CutPayload(
            payload_id="cp_cut",
            target_id="ot_result",
            target_kind="output_transition",
            cut_at="2026-01-01T00:00:00Z",
        )
    )
    active_result_ids = g.output_ids_for_input(it.input_transition_id, kind="result", active_only=True)
    assert active_result_ids == []
    inactive_result_ids = g.output_ids_for_input(it.input_transition_id, kind="result", active_only=False)
    assert "ot_result" in inactive_result_ids
