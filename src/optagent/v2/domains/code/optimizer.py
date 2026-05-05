"""§11.3 CodeOptimizer — entry point for code optimization.

Corresponds to PLANNING_AND_RL.md §11.3.

Usage:
    from optagent.v2.domains.code import CodeOptimizer

    opt = CodeOptimizer(
        source_path=Path("./my_module.py"),
        backend=OpenCodeBackend(),
    )
    result = opt.optimize(
        objective="minimize latency",
        max_rounds=5,
    )
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from optagent.v2.state import Observation
from optagent.v2.planner import DefaultPlanner
from optagent.v2.mcts import MCTSOptimizer
from optagent.v2.hybrid import HybridOptimizer
from optagent.v2.domains.code.state import CodeState, CodeArtifact
from optagent.v2.domains.code.action import EditCode, RunTests, RunBenchmark
from optagent.v2.domains.code.proposer import CodeProposer
from optagent.v2.domains.code.executor import CodeExecutor
from optagent.v2.domains.code.reward import create_code_reward_spec


class CodeOptimizer:
    """End-to-end code optimization using v2 framework."""

    def __init__(
        self,
        source_path: Path,
        backend: Any = None,
        work_dir: Optional[Path] = None,
    ):
        self.source_path = Path(source_path)
        self.backend = backend
        self.executor = CodeExecutor(work_dir=work_dir)
        self.proposer = CodeProposer(backend=backend)
        self.reward_spec = create_code_reward_spec()

    def optimize(self, objective: str, max_rounds: int = 5) -> CodeState:
        """Run optimization loop.

        Args:
            objective: natural language objective (e.g., "minimize latency")
            max_rounds: maximum optimization rounds

        Returns:
            final CodeState with best incumbent
        """
        # Read initial code
        initial_code = self.source_path.read_text()
        current_code = initial_code

        # Build initial state
        code = CodeArtifact(
            artifact_id="initial",
            source_path=self.source_path,
            content=initial_code,
        )
        state = CodeState(
            requirement={"objective": objective, "source": str(self.source_path)},
            code=code,
        )

        # Set up MCTS with minimal simulations for real backend
        mcts = MCTSOptimizer(objectives=self.reward_spec.objectives)

        # Optimization loop
        v2_state = state.to_v2_state()
        for round_idx in range(max_rounds):
            # Search for best action (minimal simulations to avoid repeated LLM calls)
            action = mcts.search(v2_state, self.proposer, n_simulations=1, max_depth=3)
            if action is None:
                break

            # Set target path for edit actions
            if isinstance(action, EditCode) and action.target_path == Path("."):
                action.target_path = self.source_path

            # Execute action
            if isinstance(action, EditCode):
                result = self.executor.apply_diff(state, action)
                obs = Observation(
                    action_id=action.apply(v2_state).artifact_id,
                    metrics={"success": 1.0 if result["success"] else 0.0},
                )
                # Update code content if patch succeeded
                if result["success"]:
                    current_code = result["patched_content"]
                    state.code.content = current_code
                    # Sync v2_state with updated content for next iteration
                    v2_state = state.to_v2_state()
            elif isinstance(action, RunTests):
                result = self.executor.run_tests(state, action)
                obs = Observation(
                    action_id=action.apply(v2_state).artifact_id,
                    metrics={"correctness": 1.0 if result["passed"] else 0.0},
                )
            elif isinstance(action, RunBenchmark):
                result = self.executor.run_benchmark(state, action)
                obs = Observation(
                    action_id=action.apply(v2_state).artifact_id,
                    metrics=result,
                )
            else:
                obs = Observation(action_id="unknown", metrics={})

            # Advance state
            v2_state = v2_state.advance(action, obs, reward_spec=self.reward_spec)
            state = CodeState.from_v2_state(v2_state)
            # Restore patched content (advance overwrites with diff)
            state.code.content = current_code

        return state
