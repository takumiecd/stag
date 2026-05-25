"""Pure DAG records.

Node and Transition form the DAG skeleton. Edge stores directed connectivity.
Domain meaning is attached separately as payload records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from stag.core.types import JSONValue, to_jsonable

GraphRecordKind = Literal["node", "transition"]


@dataclass(frozen=True)
class GraphRef:
    """Reference to a graph record."""

    kind: GraphRecordKind
    id: str

    def key(self) -> str:
        return f"{self.kind}:{self.id}"


@dataclass(frozen=True)
class Node:
    """A pure DAG node."""

    node_id: str
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]


@dataclass(frozen=True)
class Transition:
    """A pure DAG transition."""

    transition_id: str
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]


@dataclass(frozen=True)
class Edge:
    """A directed connection between a node and a transition."""

    edge_id: str
    from_kind: GraphRecordKind
    from_id: str
    to_kind: GraphRecordKind
    to_id: str
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.from_kind == self.to_kind:
            raise ValueError("edges must connect node -> transition or transition -> node")

    def from_ref(self) -> GraphRef:
        return GraphRef(self.from_kind, self.from_id)

    def to_ref(self) -> GraphRef:
        return GraphRef(self.to_kind, self.to_id)

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]
