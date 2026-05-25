"""Tests for RunGraph container."""

from __future__ import annotations

import pytest

from stag.core.cuts import inactive_node_ids, inactive_transition_ids, is_inactive_transition
from stag.core.run_graph import RunGraph
from stag.core.schema.graph import Edge, Node, Transition
from stag.core.schema.payloads import CutPayload, NotePayload, PredictionPayload, ResultPayload


def _base_graph() -> RunGraph:
    graph = RunGraph()
    graph.add_node(Node(node_id="n_a"))
    graph.add_node(Node(node_id="n_b"))
    graph.add_transition(Transition(transition_id="t_1"))
    return graph


def test_add_node_duplicate_rejected():
    graph = _base_graph()
    with pytest.raises(ValueError):
        graph.add_node(Node(node_id="n_a"))


def test_add_transition_duplicate_rejected():
    graph = _base_graph()
    with pytest.raises(ValueError):
        graph.add_transition(Transition(transition_id="t_1"))


def test_add_edge_indexes_both_directions():
    graph = _base_graph()
    graph.add_edge(
        Edge(
            edge_id="e_1",
            from_kind="node",
            from_id="n_a",
            to_kind="transition",
            to_id="t_1",
        )
    )
    assert graph.successors("node", "n_a")[0].id == "t_1"
    assert graph.predecessors("transition", "t_1")[0].id == "n_a"


def test_add_edge_unknown_ref_rejected():
    graph = _base_graph()
    with pytest.raises(KeyError):
        graph.add_edge(
            Edge(
                edge_id="e_bad",
                from_kind="node",
                from_id="n_missing",
                to_kind="transition",
                to_id="t_1",
            )
        )


def test_payloads_for_node_and_transition():
    graph = _base_graph()
    graph.attach_payload(NotePayload(payload_id="pl_n", target_id="n_a", text="hi"))
    graph.attach_payload(ResultPayload(payload_id="pl_t", target_id="t_1", status="completed"))
    assert isinstance(graph.payloads_for_node("n_a")[0], NotePayload)
    assert isinstance(graph.payloads_for_transition("t_1")[0], ResultPayload)


def test_transition_kind_classifies_payloads():
    graph = _base_graph()
    graph.attach_payload(PredictionPayload(payload_id="pl_p", target_id="t_1"))
    assert graph.transition_kind("t_1") == "prediction"

    graph.add_transition(Transition(transition_id="t_2"))
    graph.attach_payload(ResultPayload(payload_id="pl_r", target_id="t_2", status="completed"))
    assert graph.transition_kind("t_2") == "result"


def test_transition_inputs_and_outputs():
    graph = _base_graph()
    graph.add_edge(Edge("e_in", "node", "n_a", "transition", "t_1"))
    graph.add_edge(Edge("e_out", "transition", "t_1", "node", "n_b"))
    assert graph.transition_inputs("t_1") == ["n_a"]
    assert graph.transition_outputs("t_1") == ["n_b"]
    assert graph.transitions_from_node("n_a") == ["t_1"]
    assert graph.transitions_to_node("n_b") == ["t_1"]


def test_reachable_from_node_returns_nodes_transitions_payloads():
    graph = _base_graph()
    graph.add_edge(Edge("e_in", "node", "n_a", "transition", "t_1"))
    graph.add_edge(Edge("e_out", "transition", "t_1", "node", "n_b"))
    graph.attach_payload(ResultPayload(payload_id="pl_r", target_id="t_1", status="completed"))
    reachable = graph.reachable_from("n_a")
    assert reachable["node_ids"] == ["n_a", "n_b"]
    assert reachable["transition_ids"] == ["t_1"]
    assert reachable["payload_ids"] == ["pl_r"]


def test_cut_transition_cascades_to_output_node():
    graph = _base_graph()
    graph.add_edge(Edge("e_in", "node", "n_a", "transition", "t_1"))
    graph.add_edge(Edge("e_out", "transition", "t_1", "node", "n_b"))
    graph.attach_payload(
        CutPayload(
            payload_id="pl_cut",
            target_kind="transition",
            target_id="t_1",
            cut_at="now",
        )
    )
    assert inactive_transition_ids(graph) == {"t_1"}
    assert inactive_node_ids(graph) == {"n_b"}
    assert is_inactive_transition(graph, "t_1")
