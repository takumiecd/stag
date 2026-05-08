"""Selection metadata over predicted transitions."""

from __future__ import annotations

from dataclasses import dataclass, field

from optagent.core.types import JSONValue, to_jsonable


@dataclass(frozen=True)
class PredictionStepRef:
    """Selected predicted transition inside a PredictionPath."""

    plan_id: str
    selected_transition_id: str
    from_node_id: str
    to_node_id: str

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]


@dataclass(frozen=True)
class PredictionPath:
    """Selected path through a predicted Dag."""

    path_id: str
    anchor_node_id: str
    steps: tuple[PredictionStepRef, ...]
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]


@dataclass(frozen=True)
class PredictionSelection:
    """Selection of predicted transitions to promote or compare."""

    selection_id: str
    selected_transition_ids: tuple[str, ...]
    selected_path_id: str | None = None
    reason: str = ""
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]
