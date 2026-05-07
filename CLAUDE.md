# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

The package is not installed; tests and CLI invocations rely on `PYTHONPATH=src`.

- Run all tests: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -q`
- Run a single test file: `PYTHONPATH=src python3 -m pytest tests/core/test_run_api.py -q`
- Run a single test: `PYTHONPATH=src python3 -m pytest tests/cli/test_observe.py::test_observe_records_metric -q`
- CLI: `PYTHONPATH=src python3 -m optagent.cli.main <subcommand> ...` (or `optagent <subcommand>` once installed via `pip install -e .`)
- Lint/format/type-check (configured in `pyproject.toml`, not wired to CI): `ruff check .`, `black .`, `mypy src`

Docs are Japanese-first and authoritative; see `docs/ja/STATE_MODEL.md`, `docs/ja/AGENT_LOOP.md`, `docs/ja/CLI.md`, `docs/ja/API.md`, `docs/ja/DIRECTION.md`.

## Architecture

optagent is a state-transition framework for recording the *process* of optimization/problem-solving — not a planner or executor. The defining design choice is that **predicted futures and observed history are stored in two separate DAGs**:

- `PredictionDAG` — unexecuted future candidates (`PredictedState`, `PredictionPlan`, `PredictedTransition`). Anchored to one observed state; rebuild via `refresh()` when the anchor moves.
- `TraceDAG` — actually-happened history (`ObservedState`, `ExecutionPlan`, `ObservedTransition`, `ActionResult`, `DerivedRecord`). The source of truth.

Both DAGs are pure directed graphs (`src/optagent/core/dag.py`): nodes plus `incoming_index`/`outgoing_index`. Roots and ancestor relationships are derived from edges — no cached depth/layer index. View helpers should compute layouts on demand.

### Public API surface

`optagent.__init__` re-exports the schema dataclasses and `RunHandle` / `init`. The intentional shape:

- `init(requirement, run_id=...)` returns a `RunHandle` seeded with `s_obs_0000` (observed root) and `s_pred_0000` (predicted root anchored to it).
- `RunHandle` is defined in `src/optagent/core/run/handle.py` as a thin dataclass; its methods (`plan`, `extend`, `predict`, `select_prediction`, `promote`, `observe`, `trace`, `refresh`, `derive`, `rewind`, `state_show`, `state_update`, `snapshot_rebuild`) are attached at module load from sibling files in `src/optagent/core/run/`. When adding a new RunHandle method, add the impl in its own `run/<verb>.py` and bind it at the bottom of `handle.py` — don't grow `handle.py` itself.
- ID counters live on the handle (`_counters`) and are minted via `_next_id(prefix)`. Stable prefixes: `s_obs`, `s_pred`, `p_exec`, `p_pred`, `t_obs`, `t_pred`, `sel_pred`, `promotion`, `prediction_dag`, `cut`.

### Observed vs predicted, plan vs transition

These distinctions are load-bearing — mixing them is a bug, not a refactor opportunity:

- `ExecutionPlan` is grounded on an observed state and is what an external executor consumes. `PredictionPlan` lives in the PredictionDAG and is *not* directly executable. Convert via `promote(mode="plan")`.
- One `ExecutionPlan` → at most one `ObservedTransition`. One `PredictionPlan` → many `PredictedTransition`s (success/regression/failure outcomes).
- `observe(...)` records an execution result without matching a prediction. `promote(mode="transition", predicted_transition_id=..., ...)` records the same result *and* links it to a predicted outcome via `matched_predicted_transition_id`.
- `ActionResult` (artifacts, raw outputs, logs, metrics, errors) belongs only on `ObservedTransition`, never on `PredictedTransition`.
- `DerivedRecord` (evidence, decision, finding, summary, observation, prediction_error) is interpretation layered on top of an observed transition — explicitly not source of truth, expected to be re-derivable.

### State semantics

`StateNode` carries a `StateSnapshot` (working context for planning: requirement, current artifacts, finding refs, open questions, active branches, prediction summary, budget, metadata) plus `snapshot_hash`. The snapshot is *working memory*, not source of truth — `optagent snapshot --rebuild` reconstructs it from `TraceDAG` history. Don't add fields that try to make the snapshot authoritative; route facts through `ActionResult` / `ObservedTransition` / `DerivedRecord` instead.

### Append-only rewind

`rewind` does not delete. It appends one `TraceCut` record (`cut_id`, `cut_at`, `rewound_to_state_id`, `cut_transition_id`, `reason`, `user_id`) to the TraceDAG. The cut subtree's records remain; "is this state/transition active?" is a **read-time replay** via `trace_dag.cut_state_ids()` / `cut_transition_ids()` / `inactive_transition_ids()` / `is_cut_state(...)`.

Writers (`plan`, `promote(mode="plan")`, `observe`, `promote(mode="transition")`) must call `_ensure_active_observed_state(state_id)` before extending an observed state. Read-only APIs do not. Rewind itself only accepts transitions on the active path from `--from-state`; ancestor checks walk incoming edges, never depth.

This is the invariant: **records are immutable, the active set is computed**. Don't introduce mutation paths or cached "is_active" fields.

### Storage

`src/optagent/storage/jsonl.py` (`JsonlRunStore`) writes a run as a directory under `<store-dir>/<run_id>/`: `run.json` (metadata + requirement), and JSONL files per entity (`states.jsonl`, `execution_plans.jsonl`, `prediction_plans.jsonl`, `predicted_transitions.jsonl`, `observed_transitions.jsonl`, `derived_records.jsonl`). `run.save(store)` and `store.load_run(run_id)` round-trip the in-memory `RunHandle`.

### CLI layer

`src/optagent/cli/main.py` is a dispatcher; each subcommand has a `commands/<name>.py` module exposing `add_parser` and `cli_<name>`. Commands resolve the target run in this order: `--run` flag → `OPTAGENT_RUN_ID` env → current-run marker at `<store-dir>/../current.json` (set by `init`/`use`). User attribution: `--user` → `OPTAGENT_USER_ID` → `<store-dir>/../config.json` `user.id` → `"user"`.

Cursors (`src/optagent/cli/workspace.py`) are CLI-only view state under `<store-dir>/../workspace/cursors.json` — **core `RunHandle` writers must not read this module**. Keep that boundary.

The `workflows/`, `domains/`, `execution/`, `search/` packages are scaffolding for future planner/executor/policy integration; treat them as not-yet-wired unless the task explicitly says so.

## Conventions worth preserving

- New IDs go through `_next_id`; don't hand-format ID strings except for the seed roots (`s_obs_0000`, `s_pred_0000`).
- New entity types should follow the schema/dataclass pattern in `src/optagent/core/schema/` and round-trip through `to_jsonable` for storage.
- When a request would conflate prediction and trace data (e.g. attaching `ActionResult` to a `PredictedTransition`, caching depth on a node, mutating a cut record), push back — these are intentional invariants.
