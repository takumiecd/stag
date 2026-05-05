"""§7 Policy: LLM as Stochastic Policy — calibration strategies."""

from __future__ import annotations

from typing import List, Protocol

from optagent.v2.state import Action, State


class Proposer(Protocol):
    """Generate and score candidate actions."""

    def generate_actions(self, state: State, n: int, temperature: float) -> List[Action]:
        ...

    def score_actions(self, state: State, actions: List[Action]) -> List[float]:
        ...


class LLMProposer:
    """Wrap LLM backend as calibrated proposer."""

    def __init__(self, backend, calibration_strategy: str = "n_sample"):
        self.backend = backend
        self.calibration_strategy = calibration_strategy

    def generate_actions(self, state: State, n: int, temperature: float) -> List[Action]:
        # TODO: call backend n times, parse actions
        return []

    def score_actions(self, state: State, actions: List[Action]) -> List[float]:
        # TODO: apply calibration strategy
        return [1.0 / len(actions)] * len(actions) if actions else []
