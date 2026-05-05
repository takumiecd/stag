# Optimization Agent (optagent)

`optagent` is an experimental framework for building optimization agents that treat
optimization as a sequence of state transitions:

```text
State_t -- action_t --> State_t+1
```

The project is aimed at code and kernel optimization loops where every attempt
should leave behind a useful trail: the hypothesis, the candidate artifact, the
test and benchmark evidence, the promotion decision, and the knowledge learned for
the next round.

It is not a general chatbot agent framework. It is a research prototype for
optimization workflows where correctness, measurement quality, reproducibility,
and explicit promotion gates matter.

## Current Status

This repository currently contains two related layers:

| Layer | Status | Role |
| --- | --- | --- |
| `optagent` / `optagent.v1` | Prototype, usable for deterministic workflow experiments | File-protocol workflow manager for hypothesis -> artifact -> evidence -> promotion loops |
| `optagent.v2` | Research framework, alpha | Domain-agnostic State / Action / Reward model with MCTS, rollout, value, reward, and Pareto components |
| `optagent.v2.domains.code` | Early prototype | Code optimization domain built on v2; currently best treated as a demo, not a safe production optimizer |

The strongest current use case is not "optimize anything automatically." It is:

> Manage optimization experiments as auditable state transitions, so hypotheses,
> generated candidates, measurements, failures, and promotion decisions can be
> replayed, compared, and reused.

## Core Ideas

### 1. Optimization Is State Transition Prediction

An optimization agent should not only ask "what edit should I make?" It should
predict the next useful optimization state:

- What candidate artifact should exist next?
- What should be tested or benchmarked?
- What evidence would make the candidate promotable?
- What knowledge should be retained if the attempt fails?

This gives planning and reinforcement-learning ideas a concrete target without
requiring the underlying LLM to be retrained.

### 2. State Separates Artifact, Trajectory, and Knowledge

v2 uses a state model with three distinct pieces:

- `artifact`: the current candidate or Pareto set
- `trajectory`: the ordered history of actions and observations
- `knowledge`: learned constraints, failed regions, calibration data, and reusable findings

This separation is important because two runs can have similar final scores but
very different successor states. The path and the learned constraints determine
what the agent should try next.

### 3. Promotion Is Evidence-Gated

An optimization is not accepted because it looks faster once. Promotion decisions
are based on evidence:

- correctness must pass
- the candidate must be eligible for the target scope
- regressions must be rejected or narrowed
- speedup must clear the configured threshold
- raw test and benchmark output should be preserved

This is especially important for sparse kernels and code optimization, where a
small benchmark win can hide correctness or dispatch-scope failures.

### 4. File Protocol First

The v1 manager communicates with child agents through structured files. This keeps
the system easy to inspect and makes it possible to plug in OpenClaw, Codex,
Claude Code, OpenCode, or deterministic mock agents without committing to a
distributed runtime too early.

## Installation

```bash
pip install -e ".[dev]"
```

For kernel-oriented experiments:

```bash
pip install -e ".[dev,kernel]"
```

## Quick Start: v1 Workflow Manager

This example runs one deterministic optimization round with the built-in default
hypothesis, artifact, evaluator, and promotion gate.

```python
from optagent import ManagerAgent, Requirement

agent = ManagerAgent(work_dir="./optagent_output")

requirement = Requirement(
    target_type="kernel",
    target_id="csc_linear_forward",
    objective={
        "metric": "latency_ms",
        "direction": "minimize",
        "min_speedup": 1.05,
    },
)

state = agent.optimize(requirement)

print(state.algorithm.round_index)
print(state.algorithm.hypotheses[-1].claim)
print(state.algorithm.evidence[-1].decision_recommendation)
```

State is saved under `./optagent_output/state_round_*.json`.

## Quick Start: v2 Concepts

Use `optagent.v2` when you want to work with the domain-agnostic State / Action /
Reward abstractions directly.

```python
from optagent.v2 import (
    ArtifactSet,
    Knowledge,
    Objective,
    RewardSpec,
    State,
    WeightedSum,
)

state = State(
    requirement={"target": "slow_sum", "objective": "minimize latency"},
    artifact=ArtifactSet(),
    trajectory=[],
    knowledge=Knowledge(),
)

reward = RewardSpec(
    objectives=[
        Objective(name="latency_ms", direction="minimize"),
        Objective(name="correctness", direction="maximize"),
    ],
    aggregator=WeightedSum(weights={"latency_ms": 0.7, "correctness": 0.3}),
)
```

## Repository Map

```text
src/optagent/
├── __init__.py              # v1-oriented public exports
├── v1/
│   ├── core/                # ManagerAgent, PromotionGate, state model
│   ├── backends/            # Backend interfaces and mock backend
│   ├── evaluation/          # Evaluation interfaces
│   ├── strategies/          # Domain strategy interfaces and kernel prototype
│   └── reporting/           # Batch reporting
└── v2/
    ├── state.py             # State, ArtifactSet, Transition, Knowledge
    ├── action.py            # Action protocol and action primitives
    ├── reward.py            # RewardSpec, objectives, constraints, aggregators
    ├── planner.py           # Planner abstractions
    ├── rollout.py           # Rollout simulation
    ├── policy.py            # Proposer interfaces
    ├── mcts.py              # MCTS optimizer skeleton
    ├── pareto.py            # Pareto front utilities
    └── domains/code/        # Early code optimization domain prototype
```

## What Is Not Implemented Yet

The repository is intentionally honest about its current limits:

- `optagent.v2.domains.code.CodeOptimizer` is still a narrow prototype.
- The current code-domain benchmark path is demo-oriented and not yet a general benchmark interface.
- Write-back safety, patch-only output, and isolated worktree execution need to be hardened before real projects should use automatic code modification.
- MCTS integration exists as a framework skeleton; the code-domain loop does not yet perform deep search.
- The top-level API is currently v1-oriented. v2 is available through `optagent.v2`.

## Documentation

- [Purpose and Design](docs/PURPOSE_AND_DESIGN.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Planning and Reinforcement Learning Integration](docs/PLANNING_AND_RL.md)
- [State Model](docs/STATE_MODEL.md)
- [Workflow](docs/WORKFLOW.md)

## Development

```bash
pytest tests/ -v
```

## License

MIT
