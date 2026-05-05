"""§6 Rollout: Horizon vs Branching — virtual future expansion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from optagent.v2.state import Action, State


@dataclass
class RolloutBudget:
    """Budget for rollout simulation."""
    max_total_cost: float = 100.0
    max_depth: int = 3
    max_branching_per_node: int = 3
    pruning: Any = None  # TODO: PruningPolicy


@dataclass
class FuturePath:
    """One possible future path."""
    actions: List[Action] = field(default_factory=list)
    expected_value: float = 0.0
    expected_cost: float = 0.0


@dataclass
class RolloutResult:
    """Result of rollout simulation."""
    paths: List[FuturePath] = field(default_factory=list)
    best_path: FuturePath | None = None
    expected_value: float = 0.0
    expected_cost: float = 0.0
    confidence: float = 0.0


class RolloutSimulator:
    """Simulate future paths from current state."""

    def simulate(self, state: State, action: Action, depth: int, budget: RolloutBudget) -> RolloutResult:
        # TODO: cost-bounded expansion
        # TODO: knowledge-pruned skipping
        # TODO: value-pruned skipping
        return RolloutResult()
