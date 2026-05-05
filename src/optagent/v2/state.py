"""§2 State Schema — domain-agnostic optimization state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Protocol


@dataclass
class Artifact:
    """Single candidate artifact."""
    artifact_id: str
    content: Any
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArtifactSet:
    """Collection of candidate artifacts with Pareto front tracking."""
    candidates: List[Artifact] = field(default_factory=list)
    pareto_front: List[Artifact] = field(default_factory=list)
    incumbent: Optional[Artifact] = None


@dataclass
class Observation:
    """Result of executing an action."""
    action_id: str
    metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Transition:
    """One step in the optimization trajectory."""
    action: "Action"
    observation: Observation
    reward_contribution: dict[str, float] = field(default_factory=dict)
    cost: float = 0.0
    timestamp: int = 0


@dataclass
class Knowledge:
    """Learned information accumulated during optimization."""
    ruled_out_regions: List[Any] = field(default_factory=list)
    calibration: dict[str, Any] = field(default_factory=dict)
    invariants: List[Any] = field(default_factory=list)
    surrogate_models: dict[str, Any] = field(default_factory=dict)


@dataclass
class State:
    """Optimization state X_t = (requirement, artifact, trajectory, knowledge)."""
    requirement: Any  # Domain-specific requirement spec
    artifact: ArtifactSet = field(default_factory=ArtifactSet)
    trajectory: List[Transition] = field(default_factory=list)
    knowledge: Knowledge = field(default_factory=Knowledge)


class Action(Protocol):
    """§3 Action Protocol — domain-pluggable state transition."""

    def apply(self, state: State) -> Artifact:
        """Produce a new candidate artifact (does not yet update knowledge)."""
        ...

    def cost(self, state: State) -> float:
        """Estimated cost of executing this action."""
        ...

    def observability(self) -> dict[str, str]:
        """Declares what will be observed after execution."""
        ...
