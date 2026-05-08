"""Pure DAG graph elements: Node and Transition.

Domain data (snapshots, results, derived records, etc.) is stored in
attached payloads, not on these records.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from optagent.core.types import JSONValue, to_jsonable


@dataclass(frozen=True)
class Node:
    """A pure graph node."""

    node_id: str
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]


@dataclass(frozen=True)
class Transition:
    """A pure graph edge between two nodes, grounded on a Plan."""

    transition_id: str
    parent_plan_id: str
    from_node_id: str
    to_node_id: str
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]
