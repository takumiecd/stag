"""Depth-oriented prediction and evidence trees."""

from __future__ import annotations

from dataclasses import dataclass, field

from optagent.core.schema import ActionSpec, StateNode, TransitionRecord


@dataclass(frozen=True)
class PlannedTransition:
    """Predicted edge in a PredictionTree."""

    transition_id: str
    from_state_id: str
    to_predicted_state_id: str
    action_spec: ActionSpec
    depth: int
    branch_id: str = "main"
    assumptions: tuple[str, ...] = ()
    confidence: float | None = None


@dataclass
class PredictionTree:
    """Future state tree grouped by depth."""

    tree_id: str
    nodes: dict[str, StateNode] = field(default_factory=dict)
    node_depths: dict[str, int] = field(default_factory=dict)
    nodes_by_depth: dict[int, list[str]] = field(default_factory=dict)
    planned_transitions: dict[str, PlannedTransition] = field(default_factory=dict)
    outgoing_index: dict[str, list[str]] = field(default_factory=dict)
    incoming_index: dict[str, list[str]] = field(default_factory=dict)

    def add_node(self, node: StateNode, depth: int) -> None:
        self.nodes[node.state_id] = node
        self.node_depths[node.state_id] = depth
        self.nodes_by_depth.setdefault(depth, []).append(node.state_id)

    def add_transition(self, transition: PlannedTransition) -> None:
        self.planned_transitions[transition.transition_id] = transition
        self.outgoing_index.setdefault(transition.from_state_id, []).append(
            transition.transition_id
        )
        self.incoming_index.setdefault(transition.to_predicted_state_id, []).append(
            transition.transition_id
        )

    def depth(self, depth: int) -> list[StateNode]:
        return [self.nodes[state_id] for state_id in self.nodes_by_depth.get(depth, ())]

    def future_transition_ids(self, state_id: str) -> list[str]:
        return list(self.outgoing_index.get(state_id, ()))


@dataclass
class EvidenceTree:
    """Observed transition tree grouped by depth."""

    tree_id: str
    nodes: dict[str, StateNode] = field(default_factory=dict)
    node_depths: dict[str, int] = field(default_factory=dict)
    nodes_by_depth: dict[int, list[str]] = field(default_factory=dict)
    transitions: dict[str, TransitionRecord] = field(default_factory=dict)
    outgoing_index: dict[str, list[str]] = field(default_factory=dict)
    incoming_index: dict[str, list[str]] = field(default_factory=dict)

    def add_node(self, node: StateNode, depth: int) -> None:
        self.nodes[node.state_id] = node
        self.node_depths[node.state_id] = depth
        self.nodes_by_depth.setdefault(depth, []).append(node.state_id)

    def append_transition(self, transition: TransitionRecord) -> None:
        self.transitions[transition.transition_id] = transition
        self.outgoing_index.setdefault(transition.from_state_id, []).append(
            transition.transition_id
        )
        self.incoming_index.setdefault(transition.to_state_id, []).append(
            transition.transition_id
        )

    def depth(self, depth: int) -> list[StateNode]:
        return [self.nodes[state_id] for state_id in self.nodes_by_depth.get(depth, ())]

    def past_transition_ids(self, state_id: str) -> list[str]:
        return list(self.incoming_index.get(state_id, ()))

    def next_transition_ids(self, state_id: str) -> list[str]:
        return list(self.outgoing_index.get(state_id, ()))
