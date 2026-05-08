"""Tests for the unified Dag container."""

from __future__ import annotations

import pytest

from optagent.core.dag import Dag
from optagent.core.schema.graph import Node, Transition
from optagent.core.schema.payloads import ResultPayload, SnapshotPayload
from optagent.core.schema.plans import Plan
from optagent.core.schema.requirements import Requirement
from optagent.core.schema.snapshots import StateSnapshot


def _snap() -> StateSnapshot:
    return StateSnapshot(
        requirement=Requirement(requirement_id="r", target_type="t", target_id="x")
    )


def _build_dag() -> Dag:
    dag = Dag(dag_id="d", metadata={"role": "observed"})
    dag.add_node(Node(node_id="n_a"))
    dag.attach_payload(SnapshotPayload(payload_id="pl_1", target_id="n_a", snapshot=_snap()))
    dag.add_plan(Plan(plan_id="plan_1", grounded_node_id="n_a", action_type="analysis", intent="i"))
    dag.add_node(Node(node_id="n_b"))
    dag.attach_payload(SnapshotPayload(payload_id="pl_2", target_id="n_b", snapshot=_snap()))
    return dag


def test_add_node_duplicate_rejected():
    dag = _build_dag()
    with pytest.raises(ValueError):
        dag.add_node(Node(node_id="n_a"))


def test_add_transition_indexes():
    dag = _build_dag()
    tr = Transition(transition_id="t_1", parent_plan_id="plan_1", from_node_id="n_a", to_node_id="n_b")
    dag.add_transition(tr)
    assert dag.outgoing_index["n_a"] == ["t_1"]
    assert dag.incoming_index["n_b"] == ["t_1"]
    assert dag.transition_ids_for_plan("plan_1") == ["t_1"]


def test_add_transition_unknown_node_rejected():
    dag = _build_dag()
    with pytest.raises(KeyError):
        dag.add_transition(
            Transition(transition_id="t_1", parent_plan_id="plan_1", from_node_id="n_a", to_node_id="n_missing")
        )


def test_attach_payload_unknown_target_rejected():
    dag = _build_dag()
    with pytest.raises(KeyError):
        dag.attach_payload(
            ResultPayload(payload_id="pl_x", target_id="t_missing", status="completed")
        )


def test_payloads_for_filters_by_type():
    dag = _build_dag()
    items = dag.payloads_for("n_a")
    assert len(items) == 1
    snaps = dag.payloads_for("n_a", payload_type="snapshot")
    assert len(snaps) == 1
    results = dag.payloads_for("n_a", payload_type="result")
    assert results == []


def test_payload_indexes_separate_node_and_transition_targets():
    dag = Dag(dag_id="d", metadata={"role": "observed"})
    dag.add_node(Node(node_id="same"))
    dag.attach_payload(
        SnapshotPayload(payload_id="pl_node", target_id="same", snapshot=_snap())
    )
    dag.add_plan(
        Plan(
            plan_id="plan_1",
            grounded_node_id="same",
            action_type="analysis",
            intent="i",
        )
    )
    dag.add_node(Node(node_id="n_b"))
    dag.attach_payload(
        SnapshotPayload(payload_id="pl_2", target_id="n_b", snapshot=_snap())
    )
    dag.add_transition(
        Transition(
            transition_id="same",
            parent_plan_id="plan_1",
            from_node_id="same",
            to_node_id="n_b",
        )
    )
    dag.attach_payload(
        ResultPayload(payload_id="pl_transition", target_id="same", status="completed")
    )

    assert [p.payload_id for p in dag.payloads_for_node("same")] == ["pl_node"]
    assert [p.payload_id for p in dag.payloads_for_transition("same")] == [
        "pl_transition"
    ]
    assert [p.payload_id for p in dag.payloads_for("same", target_kind="node")] == [
        "pl_node"
    ]
    assert [
        p.payload_id for p in dag.payloads_for("same", target_kind="transition")
    ] == ["pl_transition"]
    with pytest.raises(ValueError, match="ambiguous"):
        dag.payloads_for("same")


def test_roots_and_leaves():
    dag = _build_dag()
    dag.add_transition(Transition(transition_id="t_1", parent_plan_id="plan_1", from_node_id="n_a", to_node_id="n_b"))
    assert dag.roots() == ["n_a"]
    assert dag.leaves() == ["n_b"]


def test_ancestors_and_descendants():
    dag = _build_dag()
    dag.add_node(Node(node_id="n_c"))
    dag.attach_payload(SnapshotPayload(payload_id="pl_3", target_id="n_c", snapshot=_snap()))
    dag.add_transition(Transition(transition_id="t_1", parent_plan_id="plan_1", from_node_id="n_a", to_node_id="n_b"))
    dag.add_transition(Transition(transition_id="t_2", parent_plan_id="plan_1", from_node_id="n_b", to_node_id="n_c"))
    assert dag.ancestors_of("n_c") == ("n_b", "n_a")
    assert dag.descendants_of("n_a") == ("n_b", "n_c")
    assert dag.is_ancestor("n_a", "n_c") is True
    assert dag.is_ancestor("n_c", "n_a") is False


def test_child_dag_registration():
    parent = _build_dag()
    child = Dag(dag_id="d_child", metadata={"role": "predicted"})
    child.add_node(Node(node_id="n_child"))
    parent.add_child_dag(child)
    assert "d_child" in parent.child_dags


def test_attach_connects_parent_to_child_node():
    parent = _build_dag()
    child = Dag(dag_id="d_child", metadata={"role": "predicted"})
    child.add_node(Node(node_id="n_child"))
    parent.add_child_dag(child)
    transition = Transition(
        transition_id="t_attach",
        parent_plan_id="plan_1",
        from_node_id="n_a",
        to_node_id="n_child",
    )
    parent.attach(
        parent_node_id="n_a",
        child_dag_id="d_child",
        child_node_id="n_child",
        transition=transition,
    )
    assert "t_attach" in parent.transitions
    assert parent.outgoing_index["n_a"] == ["t_attach"]


def test_attach_rejects_unknown_child_node():
    parent = _build_dag()
    child = Dag(dag_id="d_child", metadata={"role": "predicted"})
    parent.add_child_dag(child)
    with pytest.raises(KeyError):
        parent.attach(
            parent_node_id="n_a",
            child_dag_id="d_child",
            child_node_id="n_missing",
            transition=Transition(
                transition_id="t_x",
                parent_plan_id="plan_1",
                from_node_id="n_a",
                to_node_id="n_missing",
            ),
        )


def test_child_dag_arbitrary_depth():
    a = Dag(dag_id="a")
    b = Dag(dag_id="b")
    c = Dag(dag_id="c")
    b.add_child_dag(c)
    a.add_child_dag(b)
    assert "b" in a.child_dags
    assert "c" in a.child_dags["b"].child_dags
