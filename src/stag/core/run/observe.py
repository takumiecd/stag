"""RunHandle.observe implementation."""

from __future__ import annotations

from stag.core.cuts import is_inactive_transition
from stag.core.schema.graph import Edge, Node
from stag.core.schema.payloads import PredictionPayload, ResultPayload


def observe_impl(
    self,
    transition_id: str,
    result: ResultPayload,
    *,
    user_id: str | None = None,
    work_session_id: str | None = None,
) -> Node:
    """Attach an observed result payload and output node to a Transition."""
    if transition_id not in self.run_graph.transitions:
        raise KeyError(f"unknown transition_id: {transition_id}")
    if is_inactive_transition(self.run_graph, transition_id):
        raise ValueError(f"transition is inactive: {transition_id}")

    if result.matched_prediction_transition_id is not None:
        mpid = result.matched_prediction_transition_id
        if mpid not in self.run_graph.transitions:
            raise KeyError(f"unknown matched_prediction_transition_id: {mpid}")
        pred_payloads = self.run_graph.payloads_for_transition(mpid)
        if not any(isinstance(p, PredictionPayload) for p in pred_payloads):
            raise ValueError(
                f"matched_prediction_transition_id does not point to a prediction: {mpid}"
            )
        if is_inactive_transition(self.run_graph, mpid):
            raise ValueError(f"matched_prediction_transition_id is inactive: {mpid}")

    node = Node(node_id=self._next_id("n"))
    self.run_graph.add_node(node)
    edge = Edge(
        edge_id=self._next_id("e"),
        from_kind="transition",
        from_id=transition_id,
        to_kind="node",
        to_id=node.node_id,
    )
    self.run_graph.add_edge(edge)

    result_payload = ResultPayload(
        payload_id=self._next_id("pl"),
        target_id=transition_id,
        status=result.status,
        artifacts=result.artifacts,
        raw_outputs=result.raw_outputs,
        logs=result.logs,
        metrics=dict(result.metrics),
        errors=result.errors,
        actual_cost=dict(result.actual_cost),
        matched_prediction_transition_id=result.matched_prediction_transition_id,
        metadata={**dict(result.metadata), "node_id": node.node_id},
    )
    self.run_graph.attach_payload(result_payload)
    self.record_work_event(
        user_id=user_id,
        work_session_id=work_session_id,
        event_type="result_observed",
        target_kind="transition",
        target_id=transition_id,
        created_records=(node.node_id, edge.edge_id, result_payload.payload_id),
        summary=result.status,
    )
    return node
