"""RunHandle.trace and refresh implementations."""

from __future__ import annotations

from optagent.core.dag import Dag
from optagent.core.schema.graph import Node
from optagent.core.schema.payloads import (
    DerivedPayload,
    MatchPayload,
    ResultPayload,
    SnapshotPayload,
)
from optagent.core.schema.snapshots import TraceContext


def trace_impl(
    self,
    node_id: str,
    *,
    depth: int | None = None,
    include_derived: bool = True,
    include_raw_refs: bool = True,
) -> TraceContext:
    """Walk observed history backwards from a node."""

    if node_id not in self.observed_dag.nodes:
        raise KeyError(f"unknown observed node_id: {node_id}")

    remaining = depth
    cursor = node_id
    past_node_ids: list[str] = []
    transition_ids: list[str] = []
    plan_ids: list[str] = []
    result_payload_ids: list[str] = []
    matched_transition_ids: list[str] = []
    derived_payload_ids: list[str] = []
    artifact_refs: list[str] = []

    while remaining is None or remaining > 0:
        incoming = self.observed_dag.incoming_transition_ids(cursor)
        if not incoming:
            break
        transition = self.observed_dag.transitions[incoming[-1]]
        transition_ids.append(transition.transition_id)
        plan_ids.append(transition.parent_plan_id)
        past_node_ids.append(transition.from_node_id)
        for payload in self.observed_dag.payloads_for(transition.transition_id):
            if isinstance(payload, ResultPayload):
                result_payload_ids.append(payload.payload_id)
                if include_raw_refs:
                    artifact_refs.extend(payload.artifacts)
                    artifact_refs.extend(payload.raw_outputs)
                    artifact_refs.extend(payload.logs)
            elif isinstance(payload, MatchPayload):
                matched_transition_ids.append(payload.matched_transition_id)
            elif isinstance(payload, DerivedPayload):
                if include_derived:
                    derived_payload_ids.append(payload.payload_id)
        cursor = transition.from_node_id
        if remaining is not None:
            remaining -= 1

    return TraceContext(
        current_node_id=node_id,
        past_node_ids=tuple(past_node_ids),
        transition_ids=tuple(transition_ids),
        plan_ids=tuple(plan_ids),
        result_payload_ids=tuple(result_payload_ids),
        matched_transition_ids=tuple(matched_transition_ids),
        derived_payload_ids=tuple(derived_payload_ids),
        artifact_refs=tuple(artifact_refs),
    )


def refresh_impl(self, *, from_node_id: str) -> Dag:
    """Re-anchor the predicted Dag to an observed node.

    Replaces ``self.predicted_dag`` (and its registration in
    ``self.observed_dag.child_dags``) with a fresh predicted Dag whose
    only node is a new root snapshot taken from *from_node_id*.
    """
    if from_node_id not in self.observed_dag.nodes:
        raise KeyError(f"unknown observed node_id: {from_node_id}")
    self._ensure_active_observed_node(from_node_id)

    old_pred = self.predicted_dag
    if old_pred.dag_id in self.observed_dag.child_dags:
        del self.observed_dag.child_dags[old_pred.dag_id]

    snap_payload = self._get_node_snapshot_payload(self.observed_dag, from_node_id)
    self._counters["dag"] = self._counters.get("dag", 0) + 1
    new_pred = Dag(
        dag_id=f"{self.run_id}_predicted_{self._counters['dag']}",
        metadata={"role": "predicted", "anchor_node_id": from_node_id},
    )
    root = Node(node_id=self._next_id("n"))
    new_pred.add_node(root)
    new_pred.attach_payload(
        SnapshotPayload(
            payload_id=self._next_id("pl"),
            target_id=root.node_id,
            snapshot=snap_payload.snapshot,
            snapshot_hash=snap_payload.snapshot_hash,
            metadata={"anchor_node_id": from_node_id},
        )
    )
    new_pred.metadata["root_node_id"] = root.node_id
    self.observed_dag.add_child_dag(new_pred)
    self.predicted_dag = new_pred
    return new_pred
