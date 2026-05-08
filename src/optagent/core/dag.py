"""Unified Dag container.

A Dag is a pure directed graph of nodes (`Node`) and edges (`Transition`).
It also stores Plans grounded on its nodes, Payloads attached to either
nodes or transitions, and optionally child Dags (any depth).

The observed/predicted distinction is *not* encoded on Node, Transition,
or Plan. It lives only as a tag in `Dag.metadata["role"]`. Cardinality
constraints (e.g. "1 plan -> 1 transition" on observed Dags) are enforced
by callers (RunHandle), not by Dag itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from optagent.core.schema.graph import Node, Transition
from optagent.core.schema.payloads import Payload
from optagent.core.schema.plans import Plan
from optagent.core.types import JSONValue, to_jsonable


@dataclass
class Dag:
    dag_id: str
    nodes: dict[str, Node] = field(default_factory=dict)
    transitions: dict[str, Transition] = field(default_factory=dict)
    plans: dict[str, Plan] = field(default_factory=dict)
    payloads: dict[str, Payload] = field(default_factory=dict)
    payloads_by_node: dict[str, list[str]] = field(default_factory=dict)
    payloads_by_transition: dict[str, list[str]] = field(default_factory=dict)
    child_dags: dict[str, "Dag"] = field(default_factory=dict)
    incoming_index: dict[str, list[str]] = field(default_factory=dict)
    outgoing_index: dict[str, list[str]] = field(default_factory=dict)
    plans_by_node: dict[str, list[str]] = field(default_factory=dict)
    transitions_by_plan: dict[str, list[str]] = field(default_factory=dict)
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    # ----- nodes / transitions / plans --------------------------------

    def add_node(self, node: Node) -> None:
        if node.node_id in self.nodes:
            raise ValueError(f"duplicate node_id: {node.node_id}")
        self.nodes[node.node_id] = node

    def add_transition(self, transition: Transition) -> None:
        if transition.transition_id in self.transitions:
            raise ValueError(f"duplicate transition_id: {transition.transition_id}")
        if transition.from_node_id not in self.nodes:
            raise KeyError(f"unknown from_node_id: {transition.from_node_id}")
        if transition.to_node_id not in self.nodes:
            raise KeyError(f"unknown to_node_id: {transition.to_node_id}")
        if transition.parent_plan_id not in self.plans:
            raise KeyError(f"unknown parent_plan_id: {transition.parent_plan_id}")
        self.transitions[transition.transition_id] = transition
        self.transitions_by_plan.setdefault(transition.parent_plan_id, []).append(
            transition.transition_id
        )
        self.outgoing_index.setdefault(transition.from_node_id, []).append(
            transition.transition_id
        )
        self.incoming_index.setdefault(transition.to_node_id, []).append(
            transition.transition_id
        )

    def add_plan(self, plan: Plan) -> None:
        if plan.plan_id in self.plans:
            raise ValueError(f"duplicate plan_id: {plan.plan_id}")
        if plan.grounded_node_id not in self.nodes:
            raise KeyError(f"unknown grounded_node_id: {plan.grounded_node_id}")
        self.plans[plan.plan_id] = plan
        self.plans_by_node.setdefault(plan.grounded_node_id, []).append(plan.plan_id)

    # ----- payloads ---------------------------------------------------

    def attach_payload(self, payload: Payload) -> None:
        if payload.payload_id in self.payloads:
            raise ValueError(f"duplicate payload_id: {payload.payload_id}")
        if payload.target_kind == "node":
            if payload.target_id not in self.nodes:
                raise KeyError(f"unknown target node: {payload.target_id}")
        elif payload.target_kind == "transition":
            if payload.target_id not in self.transitions:
                raise KeyError(f"unknown target transition: {payload.target_id}")
        else:
            raise ValueError(f"unknown target_kind: {payload.target_kind!r}")
        self.payloads[payload.payload_id] = payload
        if payload.target_kind == "node":
            self.payloads_by_node.setdefault(payload.target_id, []).append(
                payload.payload_id
            )
        else:
            self.payloads_by_transition.setdefault(payload.target_id, []).append(
                payload.payload_id
            )

    def payloads_for(
        self,
        target_id: str,
        *,
        target_kind: str | None = None,
        payload_type: str | None = None,
    ) -> list[Payload]:
        ids = self._payload_ids_for_target(target_id, target_kind=target_kind)
        items = [self.payloads[pid] for pid in ids]
        if payload_type is None:
            return items
        return [p for p in items if p.payload_type == payload_type]

    def payloads_for_node(
        self,
        node_id: str,
        *,
        payload_type: str | None = None,
    ) -> list[Payload]:
        return self.payloads_for(
            node_id,
            target_kind="node",
            payload_type=payload_type,
        )

    def payloads_for_transition(
        self,
        transition_id: str,
        *,
        payload_type: str | None = None,
    ) -> list[Payload]:
        return self.payloads_for(
            transition_id,
            target_kind="transition",
            payload_type=payload_type,
        )

    def _payload_ids_for_target(
        self,
        target_id: str,
        *,
        target_kind: str | None,
    ) -> list[str]:
        if target_kind == "node":
            return list(self.payloads_by_node.get(target_id, ()))
        if target_kind == "transition":
            return list(self.payloads_by_transition.get(target_id, ()))
        if target_kind is not None:
            raise ValueError(f"unknown target_kind: {target_kind!r}")

        node_ids = self.payloads_by_node.get(target_id, ())
        transition_ids = self.payloads_by_transition.get(target_id, ())
        if node_ids and transition_ids:
            raise ValueError(
                f"ambiguous payload target_id {target_id!r}; "
                "pass target_kind='node' or target_kind='transition'"
            )
        return list(node_ids or transition_ids)

    # ----- child dags -------------------------------------------------

    def add_child_dag(self, child: "Dag") -> None:
        if child.dag_id in self.child_dags:
            raise ValueError(f"duplicate child dag_id: {child.dag_id}")
        if child.dag_id == self.dag_id:
            raise ValueError("a Dag cannot contain itself")
        self.child_dags[child.dag_id] = child

    def attach(
        self,
        parent_node_id: str,
        child_dag_id: str,
        child_node_id: str,
        *,
        transition: Transition,
    ) -> None:
        """Connect a node in this Dag to a node in an already-registered child Dag.

        Adds a single transition from ``parent_node_id`` (in ``self``) to
        ``child_node_id`` (in ``self.child_dags[child_dag_id]``). The child
        Dag's internal records are not modified. The transition itself is
        stored in ``self.transitions``; its ``parent_plan_id`` must already
        exist in ``self.plans``.
        """
        if parent_node_id not in self.nodes:
            raise KeyError(f"unknown parent node: {parent_node_id}")
        if child_dag_id not in self.child_dags:
            raise KeyError(f"unknown child dag: {child_dag_id}")
        child = self.child_dags[child_dag_id]
        if child_node_id not in child.nodes:
            raise KeyError(f"unknown child node: {child_node_id}")
        if transition.from_node_id != parent_node_id:
            raise ValueError("transition.from_node_id must equal parent_node_id")
        if transition.to_node_id != child_node_id:
            raise ValueError("transition.to_node_id must equal child_node_id")
        if transition.transition_id in self.transitions:
            raise ValueError(f"duplicate transition_id: {transition.transition_id}")
        if transition.parent_plan_id not in self.plans:
            raise KeyError(f"unknown parent_plan_id: {transition.parent_plan_id}")
        # Bypass node existence check on `to_node_id` since it lives in the child.
        self.transitions[transition.transition_id] = transition
        self.transitions_by_plan.setdefault(transition.parent_plan_id, []).append(
            transition.transition_id
        )
        self.outgoing_index.setdefault(transition.from_node_id, []).append(
            transition.transition_id
        )
        self.incoming_index.setdefault(transition.to_node_id, []).append(
            transition.transition_id
        )

    # ----- topology ---------------------------------------------------

    def roots(self) -> list[str]:
        return [nid for nid in self.nodes if not self.incoming_index.get(nid)]

    def leaves(self) -> list[str]:
        return [nid for nid in self.nodes if not self.outgoing_index.get(nid)]

    def outgoing_transition_ids(self, node_id: str) -> list[str]:
        return list(self.outgoing_index.get(node_id, ()))

    def incoming_transition_ids(self, node_id: str) -> list[str]:
        return list(self.incoming_index.get(node_id, ()))

    def plan_ids_from_node(self, node_id: str) -> list[str]:
        return list(self.plans_by_node.get(node_id, ()))

    def transition_ids_for_plan(self, plan_id: str) -> list[str]:
        return list(self.transitions_by_plan.get(plan_id, ()))

    def ancestors_of(self, node_id: str) -> tuple[str, ...]:
        """BFS over incoming edges. Closest ancestor first. Excludes ``node_id`` itself."""
        seen: set[str] = set()
        order: list[str] = []
        frontier: list[str] = [node_id]
        while frontier:
            current = frontier.pop(0)
            for tid in self.incoming_index.get(current, ()):
                parent = self.transitions[tid].from_node_id
                if parent in seen:
                    continue
                seen.add(parent)
                order.append(parent)
                frontier.append(parent)
        return tuple(order)

    def descendants_of(self, node_id: str) -> tuple[str, ...]:
        """BFS over outgoing edges. Closest descendant first. Excludes ``node_id`` itself."""
        seen: set[str] = set()
        order: list[str] = []
        frontier: list[str] = [node_id]
        while frontier:
            current = frontier.pop(0)
            for tid in self.outgoing_index.get(current, ()):
                child = self.transitions[tid].to_node_id
                if child in seen:
                    continue
                seen.add(child)
                order.append(child)
                frontier.append(child)
        return tuple(order)

    def is_ancestor(self, ancestor_id: str, descendant_id: str) -> bool:
        if ancestor_id == descendant_id:
            return True
        return ancestor_id in self.ancestors_of(descendant_id)

    def to_dict(self) -> dict:
        return to_jsonable(self)  # type: ignore[return-value]
