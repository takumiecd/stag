# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Commands

The package is usually not installed during local development. Use `PYTHONPATH=src`.

- Run all tests: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -q`
- Run one test file: `PYTHONPATH=src python3 -m pytest tests/core/test_run_api.py -q`
- CLI: `PYTHONPATH=src python3 -m optagent.cli.main <subcommand> ...`
- Optional checks configured in `pyproject.toml`: `ruff check .`, `black .`, `mypy src`

Docs are Japanese-first and should match the current implementation:

- `docs/ja/DIRECTION.md`
- `docs/ja/STATE_MODEL.md`
- `docs/ja/API.md`
- `docs/ja/CLI.md`
- `docs/ja/AGENT_LOOP.md`

## Version And Compatibility

This project is `0.1.0` alpha. Breaking changes are acceptable and expected. Do not add compatibility shims for removed APIs unless explicitly requested. Old run storage schemas do not need migration support by default.

## Architecture

optagent records the process of optimization/problem-solving. It is not a planner, executor, benchmark runner, or general agent framework.

The current core model is **pure DAG records plus attached payloads**.

- `Dag`: common graph container in `src/optagent/core/dag.py`
- `Node`: pure graph node
- `Plan`: action plan grounded on a node
- `Transition`: edge from one node to another, grounded on a plan
- `Payload`: domain data attached to a node or transition

Observed vs predicted is a property of the owning Dag, not separate dataclass families:

- `run.observed_dag`: actual history, `metadata["role"] == "observed"`
- `run.predicted_dag`: unexecuted future candidates, `metadata["role"] == "predicted"`

Avoid reintroducing `StateNode`, `ExecutionPlan`, `PredictionPlan`, `ObservedTransition`, `PredictedTransition`, `ActionResult`, or `DerivedRecord` as public compatibility aliases unless the task explicitly asks for that.

## Payloads

Payload types live under `src/optagent/core/schema/payloads.py`.

- `SnapshotPayload`: working context attached to a node
- `ResultPayload`: actual or predicted result attached to a transition
- `DerivedPayload`: interpretation such as evidence, finding, decision, summary
- `MatchPayload`: links an observed transition to a predicted transition
- `CutPayload`: append-only rewind marker attached to a transition

Snapshots are working memory, not source of truth. Facts should come from transitions and payloads.

## RunHandle

`RunHandle` is defined in `src/optagent/core/run/handle.py` and binds verb implementations from sibling modules.

Main verbs:

- `plan(from_node_id, ...)`
- `extend(node_id, ...)`
- `predict(plan_id, ...)`
- `observe(plan_id, result, ...)`
- `promote(mode="plan" | "transition", ...)`
- `derive(transition_id, ...)`
- `rewind(transition_id, from_node_id=..., ...)`
- `refresh(from_node_id=...)`
- `trace(node_id, ...)`
- `state_show(node_id)`
- `state_update(node_id=..., ...)`
- `snapshot_rebuild(node_id)`

When adding a new RunHandle method, implement it in a focused `src/optagent/core/run/<verb>.py` module and bind it in `handle.py`.

## IDs

IDs are minted through `RunHandle._next_id(prefix)`.

Current prefixes include:

- `n`
- `t`
- `plan`
- `dag`
- `pl`
- `sel`
- `promotion`

Do not hand-format new IDs except for seed roots created during `init`.

## Rewind

Rewind is append-only. It attaches a `CutPayload`; it does not delete nodes, transitions, plans, or payloads.

Activity is computed at read time in `src/optagent/core/cuts.py`.

Writers that extend observed history must reject cut nodes via `_ensure_active_observed_node(node_id)`.

## Storage

`JsonlRunStore` writes the current schema only:

- `run.json`
- `dags.jsonl`
- `nodes.jsonl`
- `plans.jsonl`
- `transitions.jsonl`
- `payloads.jsonl`
- `selections.jsonl`

Do not preserve old `states.jsonl` / `execution_plans.jsonl` compatibility unless requested.

## CLI

`src/optagent/cli/main.py` dispatches to `src/optagent/cli/commands/<name>.py`.

Commands resolve the target run in this order:

1. `--run`
2. `OPTAGENT_RUN_ID`
3. `<store-dir>/../current.json`

Mutating commands resolve user attribution in this order:

1. `--user`
2. `OPTAGENT_USER_ID`
3. `<store-dir>/../config.json` `user.id`
4. `"user"`

The `workflows/`, `domains/`, `execution/`, and `search/` packages are scaffolding unless the task explicitly wires them.
