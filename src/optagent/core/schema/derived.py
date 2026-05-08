"""Helper shapes for the contents of DerivedPayload.payload.

These are convenience dataclasses callers can construct and serialize
into the `payload` dict of a DerivedPayload. They are not stored
directly; DerivedPayload.payload is an opaque dict at the storage layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from optagent.core.types import DecisionStatus, JSONValue, to_jsonable


@dataclass(frozen=True)
class Observation:
    observation_id: str
    summary: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    raw_output_refs: tuple[str, ...] = ()
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    correctness: str = "unknown"
    eligible_scope: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    regressions: tuple[str, ...] = ()
    raw_observation_ids: tuple[str, ...] = ()
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]


@dataclass(frozen=True)
class PredictionError:
    prediction_error_id: str
    matched: tuple[str, ...] = ()
    missed: tuple[str, ...] = ()
    unexpected: tuple[str, ...] = ()
    severity: str = "unknown"
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]


@dataclass(frozen=True)
class Decision:
    decision_id: str
    status: DecisionStatus
    reason: str = ""
    policy: dict[str, JSONValue] = field(default_factory=dict)
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]


@dataclass(frozen=True)
class Finding:
    finding_id: str
    summary: str
    promising: str = ""
    avoid: str = ""
    scope: str = ""
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return to_jsonable(self)  # type: ignore[return-value]
