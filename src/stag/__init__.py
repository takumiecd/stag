"""stag: records the process of optimization and problem-solving."""

from stag.core.graph_view import GraphView
from stag.core.run import RunHandle, init
from stag.core.run_graph import RunGraph
from stag.core.schema import (
    CommitEntry,
    CutPayload,
    DiffSummary,
    Edge,
    GitChangePayload,
    GraphRecordKind,
    GraphRef,
    NotePayload,
    Node,
    Payload,
    PayloadBase,
    PlanPayload,
    PredictionPayload,
    Requirement,
    ResultPayload,
    TraceContext,
    Transition,
)
from stag.core.types import (
    ActionType,
    PayloadType,
    ResultStatus,
    TargetKind,
)

__version__ = "0.1.0"

__all__ = [
    "ActionType",
    "CommitEntry",
    "CutPayload",
    "DiffSummary",
    "Edge",
    "GitChangePayload",
    "GraphView",
    "GraphRecordKind",
    "GraphRef",
    "NotePayload",
    "Node",
    "Payload",
    "PayloadBase",
    "PayloadType",
    "PlanPayload",
    "PredictionPayload",
    "Requirement",
    "ResultPayload",
    "ResultStatus",
    "RunGraph",
    "RunHandle",
    "TargetKind",
    "TraceContext",
    "Transition",
    "init",
]
