"""Action plan record."""

from __future__ import annotations

from dataclasses import dataclass, field

from optagent.core.types import ActionType, JSONValue, PlanStatus, to_jsonable


@dataclass(frozen=True)
class Plan:
    """An action plan grounded on a node.

    The grounding node's containing Dag determines whether this plan is
    directly executable (observed Dag) or hypothetical (predicted Dag).
    Plan itself does not encode that distinction.
    """

    plan_id: str
    grounded_node_id: str
    action_type: ActionType
    intent: str
    inputs: dict[str, JSONValue] = field(default_factory=dict)
    safety_policy: dict[str, JSONValue] = field(default_factory=dict)
    assumptions: tuple[str, ...] = ()
    confidence: float | None = None
    status: PlanStatus = "active"
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]
