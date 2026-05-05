"""optagent - State-transition optimization agent framework."""

__version__ = "0.1.0"

# v1 exports
from optagent.v1.core.manager import ManagerAgent
from optagent.v1.core.models import (
    Artifact,
    Decision,
    Evidence,
    Hypothesis,
    OptimizationConfig,
    Requirement,
)
from optagent.v1.core.state import OptimizationState
from optagent.v1.core.workflow import WorkflowStep

__all__ = [
    "ManagerAgent",
    "Artifact",
    "Decision",
    "Evidence",
    "Hypothesis",
    "OptimizationConfig",
    "OptimizationState",
    "Requirement",
    "WorkflowStep",
]
