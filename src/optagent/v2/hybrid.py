"""§10 Plan⟷Policy Hybrid — two-tier architecture."""

from __future__ import annotations

from typing import Optional

from optagent.v2.state import Action, Observation, State
from optagent.v2.planner import Plan, Planner
from optagent.v2.mcts import MCTSOptimizer
from optagent.v2.reward import RewardSpec


class HybridOptimizer:
    """Planner generates coarse trajectory; MCTS refines local decisions."""

    def __init__(self, planner: Planner, mcts: MCTSOptimizer):
        self.planner = planner
        self.mcts = mcts

    def optimize(self, state: State, reward_spec: RewardSpec) -> State:
        # Generate coarse plan
        plan = self.planner.create_plan(state, reward_spec, horizon=5)

        while not plan.is_complete():
            # MCTS refines next step
            action = self.mcts.search(
                state,
                proposer=self.planner.proposer,
                n_simulations=20,
                budget=None,  # TODO: RolloutBudget
            )

            if action is None:
                break

            # Execute
            observation = self._execute(action)

            # Update planner and state
            plan = self.planner.update(state, plan, observation)
            state = self._advance(state, action, observation)

        return state

    def _execute(self, action: Action) -> Observation:
        # TODO: execute action in environment
        return Observation(action_id=str(action))

    def _advance(self, state: State, action: Action, observation: Observation) -> State:
        # TODO: advance state with new transition
        return state
