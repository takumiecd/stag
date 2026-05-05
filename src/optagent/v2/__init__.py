"""v2 domain-agnostic optimization framework.

Swap points:
  - State (state.py)
  - Action (action.py)
  - Reward (reward.py)

Algorithmic layer:
  - Planner (planner.py)
  - Rollout (rollout.py)
  - Proposer / Policy (policy.py)
  - MCTS (mcts.py)
  - Value Predictor (value.py)
  - Hybrid (hybrid.py)

Bridge:
  - v1.5 compatibility (bridge.py)
"""

__version__ = "2.0.0-alpha"
