"""Common helpers shared by RunHandle verb implementations."""

from __future__ import annotations

from optagent.core.dag import Dag
from optagent.core.schema.graph import Node
from optagent.core.schema.payloads import SnapshotPayload
from optagent.core.schema.plans import Plan


def find_plan_impl(self, plan_id: str) -> Plan:
    """Find a Plan in either the observed or predicted Dag."""
    if plan_id in self.observed_dag.plans:
        return self.observed_dag.plans[plan_id]
    if plan_id in self.predicted_dag.plans:
        return self.predicted_dag.plans[plan_id]
    raise KeyError(f"unknown plan_id: {plan_id}")


def plan_grounding_dag_impl(self, plan: Plan) -> Dag:
    """Return the Dag that owns *plan* (observed or predicted)."""
    if plan.plan_id in self.observed_dag.plans:
        return self.observed_dag
    if plan.plan_id in self.predicted_dag.plans:
        return self.predicted_dag
    raise KeyError(f"plan not registered in any Dag: {plan.plan_id}")


def get_node_snapshot_payload_impl(
    self,
    dag: Dag,
    node_id: str,
) -> SnapshotPayload:
    """Return the most recently attached SnapshotPayload for a node."""
    payloads = [
        p for p in dag.payloads_for(node_id, payload_type="snapshot")
    ]
    if not payloads:
        raise KeyError(f"no SnapshotPayload for node: {node_id}")
    snap = payloads[-1]
    assert isinstance(snap, SnapshotPayload)
    return snap


def new_node_with_snapshot_impl(
    self,
    dag: Dag,
    *,
    snapshot,
    snapshot_hash: str | None = None,
    assumptions: tuple[str, ...] = (),
    confidence: float | None = None,
    node_metadata: dict | None = None,
    payload_metadata: dict | None = None,
) -> Node:
    """Create a Node and attach its SnapshotPayload in one step."""
    node = Node(
        node_id=self._next_id("n"),
        metadata=dict(node_metadata or {}),
    )
    dag.add_node(node)
    dag.attach_payload(
        SnapshotPayload(
            payload_id=self._next_id("pl"),
            target_id=node.node_id,
            snapshot=snapshot,
            snapshot_hash=snapshot_hash or snapshot.compute_hash(),
            assumptions=assumptions,
            confidence=confidence,
            metadata=dict(payload_metadata or {}),
        )
    )
    return node
