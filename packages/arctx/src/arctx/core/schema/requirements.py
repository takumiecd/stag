"""Run requirements."""

from __future__ import annotations

from dataclasses import dataclass, field

from arctx.core.types import JSONValue, to_jsonable


@dataclass(frozen=True)
class Requirement:
    """Fixed optimization or problem-solving target for a run."""

    requirement_id: str
    target_type: str
    target_id: str
    objective: dict[str, JSONValue] = field(default_factory=dict)
    constraints: dict[str, JSONValue] = field(default_factory=dict)
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]


def requirement_from_dict(data: dict[str, JSONValue]) -> Requirement:
    """Reconstruct a Requirement from its JSON dict form.

    Single source of truth shared by every storage backend so the
    deserializer cannot drift field-by-field (e.g. silently dropping
    ``objective``). Mirror every field on the dataclass here.
    """
    return Requirement(
        requirement_id=str(data["requirement_id"]),
        target_type=str(data["target_type"]),
        target_id=str(data["target_id"]),
        objective=dict(data.get("objective") or {}),
        constraints=dict(data.get("constraints") or {}),
        metadata=dict(data.get("metadata") or {}),
    )
