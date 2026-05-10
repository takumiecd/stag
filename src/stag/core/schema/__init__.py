"""Schema package — pure graph primitives and attached payloads."""

from stag.core.schema.graph import InputTransition, Node, OutputTransition
from stag.core.schema.payloads import (
    CutPayload,
    NotePayload,
    Payload,
    PayloadBase,
    PlanPayload,
    PredictionPayload,
    ResultPayload,
    payload_from_dict,
)
from stag.core.schema.requirements import Requirement
from stag.core.schema.snapshots import TraceContext

__all__ = [
    "CutPayload",
    "InputTransition",
    "NotePayload",
    "Node",
    "OutputTransition",
    "Payload",
    "PayloadBase",
    "PlanPayload",
    "PredictionPayload",
    "Requirement",
    "ResultPayload",
    "TraceContext",
    "payload_from_dict",
]
