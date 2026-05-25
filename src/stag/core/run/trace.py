"""RunHandle.trace implementation."""

from __future__ import annotations

from collections import deque

from stag.core.cuts import is_inactive_transition
from stag.core.schema.payloads import NotePayload, PredictionPayload, ResultPayload
from stag.core.schema.snapshots import TraceContext


def trace_impl(
    self,
    node_id: str,
    *,
    depth: int | None = None,
    include_predictions: bool = False,
    include_raw_refs: bool = True,
) -> TraceContext:
    """Walk observed history backwards from a node via transition edges."""
    if node_id not in self.run_graph.nodes:
        raise KeyError(f"unknown node_id: {node_id}")

    past_node_ids: set[str] = set()
    transition_ids: list[str] = []
    result_payload_ids: list[str] = []
    prediction_payload_ids: list[str] = []
    note_payload_ids: list[str] = []
    artifact_refs_seen: dict[str, None] = {}

    for payload in self.run_graph.payloads_for_node(node_id):
        if isinstance(payload, NotePayload):
            note_payload_ids.append(payload.payload_id)

    queue: deque[tuple[str, int | None]] = deque()
    queue.append((node_id, depth))
    visited_nodes: set[str] = {node_id}

    while queue:
        current, remaining = queue.popleft()
        if remaining is not None and remaining <= 0:
            continue

        for transition_id in self.run_graph.transitions_to_node(current):
            if is_inactive_transition(self.run_graph, transition_id):
                continue
            payloads = self.run_graph.payloads_for_transition(transition_id)
            result_payloads = [p for p in payloads if isinstance(p, ResultPayload)]
            if not result_payloads:
                continue

            transition_ids.append(transition_id)
            for payload in result_payloads:
                result_payload_ids.append(payload.payload_id)
                if include_raw_refs:
                    for ref in payload.artifacts:
                        artifact_refs_seen[ref] = None
                    for ref in payload.raw_outputs:
                        artifact_refs_seen[ref] = None
                    for ref in payload.logs:
                        artifact_refs_seen[ref] = None

            if include_predictions:
                for payload in payloads:
                    if isinstance(payload, PredictionPayload):
                        prediction_payload_ids.append(payload.payload_id)

            next_remaining = None if remaining is None else remaining - 1
            for parent_id in self.run_graph.transition_inputs(transition_id):
                if parent_id in visited_nodes:
                    continue
                visited_nodes.add(parent_id)
                past_node_ids.add(parent_id)
                for payload in self.run_graph.payloads_for_node(parent_id):
                    if isinstance(payload, NotePayload):
                        note_payload_ids.append(payload.payload_id)
                queue.append((parent_id, next_remaining))

    return TraceContext(
        current_node_id=node_id,
        past_node_ids=tuple(sorted(past_node_ids)),
        transition_ids=tuple(sorted(set(transition_ids))),
        result_payload_ids=tuple(sorted(set(result_payload_ids))),
        prediction_payload_ids=tuple(sorted(set(prediction_payload_ids))),
        note_payload_ids=tuple(sorted(set(note_payload_ids))),
        artifact_refs=tuple(artifact_refs_seen.keys()),
    )
