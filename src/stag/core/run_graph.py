"""Single global DAG container for a run."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Literal

from stag.core.graph_view import GraphView
from stag.core.schema.graph import Edge, GraphRecordKind, GraphRef, Node, Transition
from stag.core.schema.payloads import Payload, PredictionPayload, ResultPayload
from stag.core.schema.work import WorkEvent, WorkSession
from stag.core.types import JSONValue, to_jsonable


@dataclass
class RunGraph:
    """Append-only graph records for one run."""

    nodes: dict[str, Node] = field(default_factory=dict)
    transitions: dict[str, Transition] = field(default_factory=dict)
    edges: dict[str, Edge] = field(default_factory=dict)
    payloads: dict[str, Payload] = field(default_factory=dict)
    views: dict[str, GraphView] = field(default_factory=dict)
    work_sessions: dict[str, WorkSession] = field(default_factory=dict)
    work_events: list[WorkEvent] = field(default_factory=list)

    payloads_by_node: dict[str, list[str]] = field(default_factory=dict)
    payloads_by_transition: dict[str, list[str]] = field(default_factory=dict)

    outgoing_edges: dict[str, list[str]] = field(default_factory=dict)
    incoming_edges: dict[str, list[str]] = field(default_factory=dict)

    metadata: dict[str, JSONValue] = field(default_factory=dict)

    # ----- views -----------------------------------------------------------

    def add_view(self, view: GraphView) -> None:
        if view.name in self.views:
            raise ValueError(f"duplicate view name: {view.name!r}")
        if view.root_node_id not in self.nodes:
            raise KeyError(f"unknown root_node_id: {view.root_node_id}")
        self.views[view.name] = view

    def add_work_session(self, session: WorkSession) -> None:
        if session.work_session_id in self.work_sessions:
            existing = self.work_sessions[session.work_session_id]
            if existing.user_id != session.user_id:
                raise ValueError(
                    f"work_session_id {session.work_session_id!r} belongs to "
                    f"user {existing.user_id!r}, not {session.user_id!r}"
                )
            return
        self.work_sessions[session.work_session_id] = session

    def add_work_event(self, event: WorkEvent) -> None:
        if event.work_session_id not in self.work_sessions:
            raise KeyError(f"unknown work_session_id: {event.work_session_id}")
        if any(existing.event_id == event.event_id for existing in self.work_events):
            raise ValueError(f"duplicate work_event_id: {event.event_id}")
        self.work_events.append(event)

    # ----- mutations -------------------------------------------------------

    def add_node(self, node: Node) -> None:
        if node.node_id in self.nodes:
            raise ValueError(f"duplicate node_id: {node.node_id}")
        self.nodes[node.node_id] = node

    def add_transition(self, transition: Transition) -> None:
        if transition.transition_id in self.transitions:
            raise ValueError(f"duplicate transition_id: {transition.transition_id}")
        self.transitions[transition.transition_id] = transition

    def add_edge(self, edge: Edge) -> None:
        if edge.edge_id in self.edges:
            raise ValueError(f"duplicate edge_id: {edge.edge_id}")
        self._ensure_ref(edge.from_kind, edge.from_id)
        self._ensure_ref(edge.to_kind, edge.to_id)
        if edge.from_kind == edge.to_kind:
            raise ValueError("edges must connect node -> transition or transition -> node")
        self.edges[edge.edge_id] = edge
        self.outgoing_edges.setdefault(edge.from_ref().key(), []).append(edge.edge_id)
        self.incoming_edges.setdefault(edge.to_ref().key(), []).append(edge.edge_id)

    def attach_payload(self, payload: Payload) -> None:
        if payload.payload_id in self.payloads:
            raise ValueError(f"duplicate payload_id: {payload.payload_id}")
        if payload.target_kind == "node":
            if payload.target_id not in self.nodes:
                raise KeyError(f"unknown target node: {payload.target_id}")
            self.payloads_by_node.setdefault(payload.target_id, []).append(payload.payload_id)
        elif payload.target_kind == "transition":
            if payload.target_id not in self.transitions:
                raise KeyError(f"unknown target transition: {payload.target_id}")
            self.payloads_by_transition.setdefault(payload.target_id, []).append(payload.payload_id)
        else:
            raise ValueError(f"unknown target_kind: {payload.target_kind!r}")
        self.payloads[payload.payload_id] = payload

    # ----- lookup ----------------------------------------------------------

    def _ensure_ref(self, kind: GraphRecordKind, record_id: str) -> None:
        if kind == "node":
            if record_id not in self.nodes:
                raise KeyError(f"unknown node_id: {record_id}")
        elif kind == "transition":
            if record_id not in self.transitions:
                raise KeyError(f"unknown transition_id: {record_id}")
        else:
            raise ValueError(f"unknown graph record kind: {kind!r}")

    def successors(self, kind: GraphRecordKind, record_id: str) -> list[GraphRef]:
        self._ensure_ref(kind, record_id)
        refs = []
        for edge_id in self.outgoing_edges.get(GraphRef(kind, record_id).key(), ()):
            refs.append(self.edges[edge_id].to_ref())
        return refs

    def predecessors(self, kind: GraphRecordKind, record_id: str) -> list[GraphRef]:
        self._ensure_ref(kind, record_id)
        refs = []
        for edge_id in self.incoming_edges.get(GraphRef(kind, record_id).key(), ()):
            refs.append(self.edges[edge_id].from_ref())
        return refs

    def payloads_for_node(self, node_id: str, *, payload_type: str | None = None) -> list[Payload]:
        ids = self.payloads_by_node.get(node_id, ())
        items = [self.payloads[pid] for pid in ids]
        return (
            items if payload_type is None else [p for p in items if p.payload_type == payload_type]
        )

    def payloads_for_transition(
        self, transition_id: str, *, payload_type: str | None = None
    ) -> list[Payload]:
        ids = self.payloads_by_transition.get(transition_id, ())
        items = [self.payloads[pid] for pid in ids]
        return (
            items if payload_type is None else [p for p in items if p.payload_type == payload_type]
        )

    def transition_inputs(self, transition_id: str) -> list[str]:
        return [
            ref.id for ref in self.predecessors("transition", transition_id) if ref.kind == "node"
        ]

    def transition_outputs(self, transition_id: str) -> list[str]:
        return [
            ref.id for ref in self.successors("transition", transition_id) if ref.kind == "node"
        ]

    def transitions_from_node(self, node_id: str) -> list[str]:
        return [ref.id for ref in self.successors("node", node_id) if ref.kind == "transition"]

    def transitions_to_node(self, node_id: str) -> list[str]:
        return [ref.id for ref in self.predecessors("node", node_id) if ref.kind == "transition"]

    # ----- classification --------------------------------------------------

    def transition_kind(self, transition_id: str) -> Literal["prediction", "result", "unknown"]:
        payloads = self.payloads_for_transition(transition_id)
        has_result = any(isinstance(p, ResultPayload) for p in payloads)
        has_prediction = any(isinstance(p, PredictionPayload) for p in payloads)
        if has_result:
            return "result"
        if has_prediction:
            return "prediction"
        return "unknown"

    # ----- topology --------------------------------------------------------

    def reachable_from(self, node_id: str) -> dict:
        """BFS from node_id over active transitions."""
        from stag.core.cuts import is_active_node, is_inactive_transition

        visited_nodes: set[str] = set()
        visited_transitions: set[str] = set()

        queue: deque[GraphRef] = deque()
        if node_id in self.nodes and is_active_node(self, node_id):
            queue.append(GraphRef("node", node_id))

        while queue:
            ref = queue.popleft()
            if ref.kind == "node":
                if ref.id in visited_nodes:
                    continue
                visited_nodes.add(ref.id)
                for next_ref in self.successors("node", ref.id):
                    if next_ref.kind == "transition" and not is_inactive_transition(
                        self, next_ref.id
                    ):
                        queue.append(next_ref)
            else:
                if ref.id in visited_transitions:
                    continue
                if is_inactive_transition(self, ref.id):
                    continue
                visited_transitions.add(ref.id)
                for next_ref in self.successors("transition", ref.id):
                    if next_ref.kind == "node" and is_active_node(self, next_ref.id):
                        queue.append(next_ref)

        payload_ids: set[str] = set()
        for nid in visited_nodes:
            payload_ids.update(self.payloads_by_node.get(nid, ()))
        for tid in visited_transitions:
            payload_ids.update(self.payloads_by_transition.get(tid, ()))

        return {
            "node_ids": sorted(visited_nodes),
            "transition_ids": sorted(visited_transitions),
            "payload_ids": sorted(payload_ids),
        }

    def roots(self) -> list[str]:
        """Nodes with no incoming transition."""
        return [nid for nid in self.nodes if not self.transitions_to_node(nid)]

    def to_dict(self) -> dict:
        return to_jsonable(self)  # type: ignore[return-value]
