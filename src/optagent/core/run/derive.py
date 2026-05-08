"""RunHandle.derive implementation."""

from __future__ import annotations

from optagent.core.schema.payloads import DerivedPayload
from optagent.core.types import JSONValue


def derive_impl(
    self,
    transition_id: str,
    derived_type: str,
    payload: dict[str, JSONValue],
    *,
    payload_id: str | None = None,
    generator: str = "cli",
    confidence: float | None = None,
    user_id: str | None = None,
) -> DerivedPayload:
    """Attach a derived interpretation payload to an observed transition."""
    if transition_id not in self.observed_dag.transitions:
        raise KeyError(f"unknown transition_id: {transition_id}")

    record = DerivedPayload(
        payload_id=payload_id or self._next_id("pl"),
        target_id=transition_id,
        derived_type=derived_type,  # type: ignore[arg-type]
        payload=dict(payload),
        generator=generator,
        confidence=confidence,
        metadata={"user_id": user_id} if user_id is not None else {},
    )
    self.observed_dag.attach_payload(record)
    return record
