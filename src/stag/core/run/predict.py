"""RunHandle.predict implementation."""

from __future__ import annotations

from stag.core.cuts import is_inactive_transition
from stag.core.schema.graph import Edge, Node
from stag.core.schema.payloads import PredictionPayload
from stag.core.types import JSONValue


def predict_impl(
    self,
    transition_id: str,
    *,
    payloads: list[PredictionPayload] | None = None,
    max_outcomes: int | None = None,
    user_id: str | None = None,
    work_session_id: str | None = None,
) -> list[Node]:
    """Attach predicted outcome payloads and output nodes to a Transition."""
    if transition_id not in self.run_graph.transitions:
        raise KeyError(f"unknown transition_id: {transition_id}")
    if is_inactive_transition(self.run_graph, transition_id):
        raise ValueError(f"transition is inactive: {transition_id}")

    count = max(1, max_outcomes or 1)
    template_payloads = list(payloads or [])

    output_nodes: list[Node] = []
    created_records: list[str] = []
    for index in range(count):
        node = Node(node_id=self._next_id("n"))
        self.run_graph.add_node(node)

        edge_meta: dict[str, JSONValue] = {"ordinal": index}
        edge = Edge(
            edge_id=self._next_id("e"),
            from_kind="transition",
            from_id=transition_id,
            to_kind="node",
            to_id=node.node_id,
            metadata=edge_meta,
        )
        self.run_graph.add_edge(edge)

        if index < len(template_payloads):
            tmpl = template_payloads[index]
            pred_payload = PredictionPayload(
                payload_id=self._next_id("pl"),
                target_id=transition_id,
                predicted_artifacts=tmpl.predicted_artifacts,
                predicted_metrics=dict(tmpl.predicted_metrics),
                rationale=tmpl.rationale,
                probability=tmpl.probability,
                confidence=tmpl.confidence,
                predictor=tmpl.predictor,
                metadata={**dict(tmpl.metadata), "ordinal": index, "node_id": node.node_id},
            )
        else:
            pred_payload = PredictionPayload(
                payload_id=self._next_id("pl"),
                target_id=transition_id,
                metadata={"ordinal": index, "node_id": node.node_id},
            )
        self.run_graph.attach_payload(pred_payload)
        output_nodes.append(node)
        created_records.extend((node.node_id, edge.edge_id, pred_payload.payload_id))

    self.record_work_event(
        user_id=user_id,
        work_session_id=work_session_id,
        event_type="prediction_created",
        target_kind="transition",
        target_id=transition_id,
        created_records=tuple(created_records),
        summary=f"{len(output_nodes)} predicted outcome(s)",
    )
    return output_nodes
