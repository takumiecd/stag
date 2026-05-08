"""Single global graph container for a run.

RunGraph holds all nodes, input/output transitions, payloads, and views in one
place. GraphView is a lightweight label anchored to a root node; its contents
are derived at read time via reachability.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Literal

from optagent.core.graph_view import GraphView
from optagent.core.schema.graph import InputTransition, Node, OutputTransition
from optagent.core.schema.payloads import Payload, PredictionPayload, ResultPayload
from optagent.core.types import JSONValue, to_jsonable


@dataclass
class RunGraph:
    """All records for one run, stored in flat dicts with supporting indices."""

    nodes: dict[str, Node] = field(default_factory=dict)
    input_transitions: dict[str, InputTransition] = field(default_factory=dict)
    output_transitions: dict[str, OutputTransition] = field(default_factory=dict)
    payloads: dict[str, Payload] = field(default_factory=dict)
    views: dict[str, GraphView] = field(default_factory=dict)

    # payload lookup by target
    payloads_by_node: dict[str, list[str]] = field(default_factory=dict)
    payloads_by_input_transition: dict[str, list[str]] = field(default_factory=dict)
    payloads_by_output_transition: dict[str, list[str]] = field(default_factory=dict)

    # graph traversal indices
    # node_id → list[input_transition_id] where node appears in input_node_ids
    input_transitions_from_node: dict[str, list[str]] = field(default_factory=dict)
    # it_id → list[output_transition_id]
    output_transitions_from_it: dict[str, list[str]] = field(default_factory=dict)
    # to_node_id → list[output_transition_id]
    output_transitions_to_node: dict[str, list[str]] = field(default_factory=dict)

    metadata: dict[str, JSONValue] = field(default_factory=dict)

    # ----- views -----------------------------------------------------------

    def add_view(self, view: GraphView) -> None:
        if view.name in self.views:
            raise ValueError(f"duplicate view name: {view.name!r}")
        if view.root_node_id not in self.nodes:
            raise KeyError(f"unknown root_node_id: {view.root_node_id}")
        self.views[view.name] = view

    def reachable_from(self, node_id: str) -> dict:
        """BFS from node_id over active output transitions.

        Returns dict with keys node_ids, input_transition_ids,
        output_transition_ids, payload_ids — each a sorted list.
        """
        from optagent.core.cuts import (
            is_active_node,
            is_inactive_input_transition,
            is_inactive_output_transition,
        )

        visited_nodes: set[str] = set()
        visited_its: set[str] = set()
        visited_ots: set[str] = set()

        queue: deque[str] = deque()
        if node_id in self.nodes and is_active_node(self, node_id):
            queue.append(node_id)

        while queue:
            nid = queue.popleft()
            if nid in visited_nodes:
                continue
            visited_nodes.add(nid)
            for it_id in self.input_transitions_from_node.get(nid, ()):
                if is_inactive_input_transition(self, it_id):
                    continue
                visited_its.add(it_id)
                for ot_id in self.output_transitions_from_it.get(it_id, ()):
                    if is_inactive_output_transition(self, ot_id):
                        continue
                    if ot_id in visited_ots:
                        continue
                    visited_ots.add(ot_id)
                    ot = self.output_transitions[ot_id]
                    to_nid = ot.to_node_id
                    if to_nid not in visited_nodes and is_active_node(self, to_nid):
                        queue.append(to_nid)

        payload_ids: set[str] = set()
        for nid in visited_nodes:
            payload_ids.update(self.payloads_by_node.get(nid, ()))
        for it_id in visited_its:
            payload_ids.update(self.payloads_by_input_transition.get(it_id, ()))
        for ot_id in visited_ots:
            payload_ids.update(self.payloads_by_output_transition.get(ot_id, ()))

        return {
            "node_ids": sorted(visited_nodes),
            "input_transition_ids": sorted(visited_its),
            "output_transition_ids": sorted(visited_ots),
            "payload_ids": sorted(payload_ids),
        }

    # ----- mutations -------------------------------------------------------

    def add_node(self, node: Node) -> None:
        if node.node_id in self.nodes:
            raise ValueError(f"duplicate node_id: {node.node_id}")
        self.nodes[node.node_id] = node

    def add_input_transition(self, it: InputTransition) -> None:
        if it.input_transition_id in self.input_transitions:
            raise ValueError(f"duplicate input_transition_id: {it.input_transition_id}")
        for nid in it.input_node_ids:
            if nid not in self.nodes:
                raise KeyError(f"unknown input node_id: {nid}")
        self.input_transitions[it.input_transition_id] = it
        for nid in it.input_node_ids:
            self.input_transitions_from_node.setdefault(nid, []).append(it.input_transition_id)

    def add_output_transition(self, ot: OutputTransition) -> None:
        if ot.output_transition_id in self.output_transitions:
            raise ValueError(f"duplicate output_transition_id: {ot.output_transition_id}")
        if ot.input_transition_id not in self.input_transitions:
            raise KeyError(f"unknown input_transition_id: {ot.input_transition_id}")
        if ot.to_node_id not in self.nodes:
            raise KeyError(f"unknown to_node_id: {ot.to_node_id}")
        self.output_transitions[ot.output_transition_id] = ot
        self.output_transitions_from_it.setdefault(ot.input_transition_id, []).append(
            ot.output_transition_id
        )
        self.output_transitions_to_node.setdefault(ot.to_node_id, []).append(
            ot.output_transition_id
        )

    # ----- payloads --------------------------------------------------------

    def attach_payload(self, payload: Payload) -> None:
        if payload.payload_id in self.payloads:
            raise ValueError(f"duplicate payload_id: {payload.payload_id}")
        if payload.target_kind == "node":
            if payload.target_id not in self.nodes:
                raise KeyError(f"unknown target node: {payload.target_id}")
            self.payloads_by_node.setdefault(payload.target_id, []).append(payload.payload_id)
        elif payload.target_kind == "input_transition":
            if payload.target_id not in self.input_transitions:
                raise KeyError(f"unknown target input_transition: {payload.target_id}")
            self.payloads_by_input_transition.setdefault(payload.target_id, []).append(
                payload.payload_id
            )
        elif payload.target_kind == "output_transition":
            if payload.target_id not in self.output_transitions:
                raise KeyError(f"unknown target output_transition: {payload.target_id}")
            ot_id = payload.target_id
            if isinstance(payload, PredictionPayload):
                existing = self.payloads_by_output_transition.get(ot_id, [])
                if any(isinstance(self.payloads[pid], ResultPayload) for pid in existing):
                    raise ValueError(
                        f"output_transition already has a ResultPayload; "
                        f"cannot mix with PredictionPayload: {ot_id}"
                    )
            elif isinstance(payload, ResultPayload):
                existing = self.payloads_by_output_transition.get(ot_id, [])
                if any(isinstance(self.payloads[pid], PredictionPayload) for pid in existing):
                    raise ValueError(
                        f"output_transition already has a PredictionPayload; "
                        f"cannot mix with ResultPayload: {ot_id}"
                    )
            self.payloads_by_output_transition.setdefault(ot_id, []).append(
                payload.payload_id
            )
        else:
            raise ValueError(f"unknown target_kind: {payload.target_kind!r}")
        self.payloads[payload.payload_id] = payload

    def payloads_for_node(
        self, node_id: str, *, payload_type: str | None = None
    ) -> list[Payload]:
        ids = self.payloads_by_node.get(node_id, ())
        items = [self.payloads[pid] for pid in ids]
        return items if payload_type is None else [p for p in items if p.payload_type == payload_type]

    def payloads_for_input_transition(
        self, it_id: str, *, payload_type: str | None = None
    ) -> list[Payload]:
        ids = self.payloads_by_input_transition.get(it_id, ())
        items = [self.payloads[pid] for pid in ids]
        return items if payload_type is None else [p for p in items if p.payload_type == payload_type]

    def payloads_for_output_transition(
        self, ot_id: str, *, payload_type: str | None = None
    ) -> list[Payload]:
        ids = self.payloads_by_output_transition.get(ot_id, ())
        items = [self.payloads[pid] for pid in ids]
        return items if payload_type is None else [p for p in items if p.payload_type == payload_type]

    # ----- output classification -------------------------------------------

    def output_kind(self, ot_id: str) -> Literal["prediction", "result", "unknown"]:
        """Classify an OT by what payloads are attached.

        - "result": at least one ResultPayload
        - "prediction": at least one PredictionPayload
        - "unknown": neither kind present
        """
        payloads = self.payloads_for_output_transition(ot_id)
        has_result = any(isinstance(p, ResultPayload) for p in payloads)
        has_prediction = any(isinstance(p, PredictionPayload) for p in payloads)
        if has_result:
            return "result"
        if has_prediction:
            return "prediction"
        return "unknown"

    def output_ids_for_input(
        self,
        it_id: str,
        *,
        kind: Literal["prediction", "result"] | None = None,
        active_only: bool = True,
    ) -> list[str]:
        """Return OT IDs for a given IT, optionally filtered by kind and activity."""
        from optagent.core.cuts import is_inactive_output_transition

        ot_ids = self.output_transitions_from_it.get(it_id, [])
        result: list[str] = []
        for ot_id in ot_ids:
            if active_only and is_inactive_output_transition(self, ot_id):
                continue
            if kind is not None and self.output_kind(ot_id) != kind:
                continue
            result.append(ot_id)
        return result

    # ----- topology --------------------------------------------------------

    def roots(self) -> list[str]:
        """Nodes with no incoming OutputTransition."""
        has_incoming = {ot.to_node_id for ot in self.output_transitions.values()}
        return [nid for nid in self.nodes if nid not in has_incoming]

    def to_dict(self) -> dict:
        return to_jsonable(self)  # type: ignore[return-value]
