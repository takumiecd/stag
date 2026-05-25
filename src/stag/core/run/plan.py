"""RunHandle.plan implementation."""

from __future__ import annotations

from stag.core.schema.graph import Edge, Transition
from stag.core.schema.payloads import PlanPayload


def plan_impl(
    self,
    input_node_ids: list[str] | tuple[str, ...],
    payload: PlanPayload,
    *,
    user_id: str | None = None,
    work_session_id: str | None = None,
) -> Transition:
    """Create a Transition from one or more input nodes with a PlanPayload."""
    for nid in input_node_ids:
        self._ensure_active_node(nid)

    transition_id = self._next_id("t")
    metadata = {}
    if user_id is not None:
        metadata["user_id"] = user_id
    if work_session_id is not None:
        metadata["work_session_id"] = work_session_id
    transition = Transition(transition_id=transition_id, metadata=metadata)
    self.run_graph.add_transition(transition)

    edge_ids = []
    for node_id in input_node_ids:
        edge = Edge(
            edge_id=self._next_id("e"),
            from_kind="node",
            from_id=node_id,
            to_kind="transition",
            to_id=transition_id,
        )
        self.run_graph.add_edge(edge)
        edge_ids.append(edge.edge_id)

    plan_payload = PlanPayload(
        payload_id=self._next_id("pl"),
        target_id=transition_id,
        intent=payload.intent,
        action_type=payload.action_type,
        inputs=dict(payload.inputs),
        constraints=dict(payload.constraints),
        assumptions=tuple(payload.assumptions),
        safety_policy=dict(payload.safety_policy),
        metadata=dict(payload.metadata),
    )
    self.run_graph.attach_payload(plan_payload)
    self.record_work_event(
        user_id=user_id,
        work_session_id=work_session_id,
        event_type="transition_planned",
        target_kind="transition",
        target_id=transition_id,
        created_records=(transition_id, *edge_ids, plan_payload.payload_id),
        summary=payload.intent,
    )
    return transition
