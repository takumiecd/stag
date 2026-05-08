"""Tests for cut/inactive replay over CutPayloads."""

from __future__ import annotations

from optagent.core.cuts import (
    cut_node_ids,
    cut_transition_ids,
    inactive_transition_ids,
    is_cut_node,
    is_cut_transition,
)
from optagent.core.dag import Dag
from optagent.core.schema.graph import Node, Transition
from optagent.core.schema.payloads import CutPayload, SnapshotPayload
from optagent.core.schema.plans import Plan
from optagent.core.schema.requirements import Requirement
from optagent.core.schema.snapshots import StateSnapshot


def _snap() -> StateSnapshot:
    return StateSnapshot(
        requirement=Requirement(requirement_id="r", target_type="t", target_id="x")
    )


def _line_dag() -> Dag:
    """a -> b -> c -> d as transitions t1, t2, t3."""
    dag = Dag(dag_id="d", metadata={"role": "observed"})
    for nid in ("a", "b", "c", "d"):
        dag.add_node(Node(node_id=nid))
        dag.attach_payload(SnapshotPayload(payload_id=f"sp_{nid}", target_id=nid, snapshot=_snap()))
    dag.add_plan(Plan(plan_id="p", grounded_node_id="a", action_type="analysis", intent=""))
    for i, (frm, to) in enumerate([("a", "b"), ("b", "c"), ("c", "d")], 1):
        dag.add_transition(Transition(transition_id=f"t{i}", parent_plan_id="p", from_node_id=frm, to_node_id=to))
    return dag


def test_no_cuts_means_empty_sets():
    dag = _line_dag()
    assert cut_transition_ids(dag) == set()
    assert cut_node_ids(dag) == set()
    assert inactive_transition_ids(dag) == set()


def test_cut_propagates_downstream():
    dag = _line_dag()
    dag.attach_payload(
        CutPayload(payload_id="cp_1", target_id="t2", cut_at="t", rewound_to_node_id="b")
    )
    assert is_cut_transition(dag, "t2")
    assert cut_transition_ids(dag) == {"t2"}
    assert cut_node_ids(dag) == {"c", "d"}
    assert is_cut_node(dag, "c")
    assert is_cut_node(dag, "d")
    # t3 originates from a cut node so it is inactive
    assert "t3" in inactive_transition_ids(dag)
    assert "t2" in inactive_transition_ids(dag)
    # t1 is upstream of cut, still active
    assert "t1" not in inactive_transition_ids(dag)
