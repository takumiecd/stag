"""Tests for pure graph schema records."""

from __future__ import annotations

import pytest

from stag.core.schema.graph import Edge, Node, Transition


def test_node_fields():
    node = Node(node_id="n_1", metadata={"role": "root"})
    assert node.to_dict()["node_id"] == "n_1"
    assert node.to_dict()["metadata"]["role"] == "root"


def test_transition_fields():
    transition = Transition(transition_id="t_1", metadata={"user": "alice"})
    assert transition.to_dict()["transition_id"] == "t_1"
    assert transition.to_dict()["metadata"]["user"] == "alice"


def test_edge_connects_node_and_transition():
    edge = Edge(
        edge_id="e_1",
        from_kind="node",
        from_id="n_1",
        to_kind="transition",
        to_id="t_1",
    )
    assert edge.from_ref().key() == "node:n_1"
    assert edge.to_ref().key() == "transition:t_1"


def test_edge_rejects_same_kind_connection():
    with pytest.raises(ValueError):
        Edge(
            edge_id="e_bad",
            from_kind="node",
            from_id="n_1",
            to_kind="node",
            to_id="n_2",
        )
