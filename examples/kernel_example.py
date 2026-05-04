#!/usr/bin/env python3
"""Example: Kernel optimization using optagent."""

import sys
from pathlib import Path

# Add src to path for example
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from optagent import ManagerAgent, OptimizationConfig
from optagent.core.models import Requirement
from optagent.strategies.kernel import KernelOptimizationStrategy
from optagent.backends.mock import MockBackend
from optagent.core.models import Hypothesis
from optagent.evaluation.base import Evaluator
from optagent.core.models import Evidence


class SimpleEvaluator(Evaluator):
    """Simple evaluator for demonstration."""
    
    def evaluate(self, artifact, state):
        # Simulate evaluation
        return Evidence(
            hypothesis_id=artifact.hypothesis_id,
            artifact_id=artifact.artifact_type,
            speedup=1.5,  # Simulated speedup
            is_correct=True,
            is_eligible=True,
        )
    
    def is_available(self):
        return True


def main():
    """Run kernel optimization example."""
    print("Kernel Optimization Example")
    print("=" * 40)
    
    # Configure strategy
    strategy = KernelOptimizationStrategy(
        formats=["CSC", "CSCR"],
        operations=["linear_forward"],
    )
    
    # Configure backend with demo hypotheses
    backend = MockBackend(hypotheses=[
        Hypothesis(id="h1", description="Optimize loop ordering", strategy_type="mock")
    ])
    
    # Configure evaluator
    evaluator = SimpleEvaluator()
    
    # Create optimizer
    config = OptimizationConfig(
        target_speedup=1.2,
        max_rounds=1,
    )
    
    agent = ManagerAgent(
        strategy=strategy,
        backend=backend,
        evaluator=evaluator,
        config=config,
        work_dir="./optagent_output",
    )
    
    # Define requirement
    requirement = Requirement(
        target_type="kernel",
        target_id="csc_linear_forward",
        parameters={
            "in_features": 512,
            "out_features": 512,
            "batch_size": 32,
            "device": "cuda",
        },
        objective={
            "metric": "latency_ms",
            "direction": "minimize",
        },
    )
    
    # Run optimization
    print(f"Optimizing: {requirement.target_id}")
    state = agent.optimize(requirement)
    
    # Print results
    print(f"\nResults (Round {state.round_index}):")
    if state.decisions:
        decision = state.decisions[-1]
        print(f"  Decision: {'Accepted' if decision.accepted else 'Rejected'}")
        print(f"  Reason: {decision.reason}")
    
    if state.evidence:
        for evidence in state.evidence:
            if evidence.speedup:
                print(f"  Speedup: {evidence.speedup:.2f}x")
    
    print(f"\nState saved to: {state.work_dir}")


if __name__ == "__main__":
    main()
