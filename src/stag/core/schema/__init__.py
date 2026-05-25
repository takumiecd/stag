"""Schema package — pure graph primitives and attached payloads."""

from stag.core.schema.graph import Edge, GraphRecordKind, GraphRef, Node, Transition
from stag.core.schema.payloads import (
    CommitEntry,
    CutPayload,
    DiffSummary,
    GitChangePayload,
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
    "CommitEntry",
    "CutPayload",
    "DiffSummary",
    "Edge",
    "GitChangePayload",
    "GraphRecordKind",
    "GraphRef",
    "NotePayload",
    "Node",
    "Payload",
    "PayloadBase",
    "PlanPayload",
    "PredictionPayload",
    "Requirement",
    "ResultPayload",
    "TraceContext",
    "Transition",
    "payload_from_dict",
]
