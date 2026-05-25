"""Seed `.stag/runs` with rich sample runs for TUI exploration.

Usage:
    PYTHONPATH=src python3 scripts/seed_sample_runs.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

import stag
from stag import (
    PlanPayload,
    PredictionPayload,
    Requirement,
    ResultPayload,
)
from stag.storage.jsonl import JsonlRunStore


STORE_DIR = Path(".stag/runs")


def _wipe() -> None:
    if STORE_DIR.exists():
        shutil.rmtree(STORE_DIR)
    STORE_DIR.mkdir(parents=True, exist_ok=True)


def _scheduling_run(store: JsonlRunStore) -> None:
    """A small scheduling optimization run: linear plan → multi-input join."""
    req = Requirement("req_sched", "demo", "job_scheduling")
    run = stag.init(req, run_id="scheduling-demo")

    user = "alice"
    sess = "ws_sched"

    # P1: baseline scheduling
    t1 = run.plan(
        [run.root_node_id],
        PlanPayload("_", "_", "baseline FIFO scheduling", action_type="execution"),
        user_id=user,
        work_session_id=sess,
    )
    out1 = run.observe(
        t1.transition_id,
        ResultPayload("_", "_", "success", metrics={"makespan": 142.0, "wait_p95": 38.0}),
        user_id=user,
        work_session_id=sess,
    )

    # P2: try shortest-job-first from baseline
    t2 = run.plan(
        [out1.node_id],
        PlanPayload("_", "_", "switch to shortest-job-first", action_type="execution"),
        user_id=user,
        work_session_id=sess,
    )
    run.predict(
        t2.transition_id,
        payloads=[
            PredictionPayload(
                "_", "_",
                predicted_metrics={"makespan": 118.0, "wait_p95": 27.0},
                rationale="SJF typically improves p95 wait",
                probability=0.7,
            ),
            PredictionPayload(
                "_", "_",
                predicted_metrics={"makespan": 135.0, "wait_p95": 33.0},
                rationale="Pathological case: many long jobs first",
                probability=0.3,
            ),
        ],
        max_outcomes=2,
        user_id=user,
        work_session_id=sess,
    )
    obs2 = run.observe(
        t2.transition_id,
        ResultPayload(
            "_", "_", "success",
            metrics={"makespan": 122.0, "wait_p95": 28.5},
            matched_prediction_transition_id=t2.transition_id,
        ),
        user_id=user,
        work_session_id=sess,
    )
    run.note(obs2.node_id, "SJF wins on this workload", user_id=user, work_session_id=sess)

    # P3: parallel — try EDF from baseline (another branch)
    t3 = run.plan(
        [out1.node_id],
        PlanPayload("_", "_", "earliest-deadline-first", action_type="execution"),
        user_id=user,
        work_session_id=sess,
    )
    run.predict(
        t3.transition_id,
        payloads=[
            PredictionPayload("_", "_", predicted_metrics={"makespan": 130.0}, probability=0.5),
        ],
        max_outcomes=1,
        user_id=user,
        work_session_id=sess,
    )

    # P4: hybrid — multi-input join (combines SJF and EDF results)
    edf_outputs = run.run_graph.transition_outputs(t3.transition_id)
    if edf_outputs:
        t4 = run.plan(
            [obs2.node_id, edf_outputs[0]],
            PlanPayload("_", "_", "hybrid SJF+EDF heuristic", action_type="execution"),
            user_id=user,
            work_session_id=sess,
        )
        run.observe(
            t4.transition_id,
            ResultPayload("_", "_", "success", metrics={"makespan": 109.0, "wait_p95": 24.0}),
            user_id=user,
            work_session_id=sess,
        )

    # P5: dead-end branch we cut later
    t5 = run.plan(
        [run.root_node_id],
        PlanPayload("_", "_", "random scheduling (control)", action_type="execution"),
        user_id=user,
        work_session_id=sess,
    )
    obs5 = run.observe(
        t5.transition_id,
        ResultPayload("_", "_", "success", metrics={"makespan": 187.0}),
        user_id=user,
        work_session_id=sess,
    )
    run.cut(obs5.node_id, target_kind="node", reason="control branch, not pursuing", user_id=user, work_session_id=sess)

    run.save(store)


def _hyperparameter_run(store: JsonlRunStore) -> None:
    """A small hyperparameter search: 3 predictions, one matched observation."""
    req = Requirement("req_hp", "demo", "hyperparam_search")
    run = stag.init(req, run_id="hyperparam-demo")

    user = "bob"
    sess = "ws_hp"

    t = run.plan(
        [run.root_node_id],
        PlanPayload(
            "_", "_",
            "sweep learning_rate {1e-4, 3e-4, 1e-3}",
            action_type="execution",
            inputs={"sweep_values": [1e-4, 3e-4, 1e-3]},
        ),
        user_id=user, work_session_id=sess,
    )
    run.predict(
        t.transition_id,
        payloads=[
            PredictionPayload("_", "_", predicted_metrics={"val_loss": 0.42}, rationale="lr=1e-4 underfits", probability=0.2),
            PredictionPayload("_", "_", predicted_metrics={"val_loss": 0.31}, rationale="lr=3e-4 sweet spot",  probability=0.6),
            PredictionPayload("_", "_", predicted_metrics={"val_loss": 0.55}, rationale="lr=1e-3 diverges",   probability=0.2),
        ],
        max_outcomes=3,
        user_id=user, work_session_id=sess,
    )
    run.observe(
        t.transition_id,
        ResultPayload("_", "_", "success", metrics={"val_loss": 0.29, "lr_chosen": 3e-4}),
        user_id=user, work_session_id=sess,
    )

    run.save(store)


def _minimal_run(store: JsonlRunStore) -> None:
    """Tiny run with just a single plan + observation."""
    req = Requirement("req_mini", "demo", "minimal_example")
    run = stag.init(req, run_id="minimal-demo")

    t = run.plan(
        [run.root_node_id],
        PlanPayload("_", "_", "hello world", action_type="analysis"),
        user_id="carol",
        work_session_id="ws_mini",
    )
    run.observe(
        t.transition_id,
        ResultPayload("_", "_", "success"),
        user_id="carol",
        work_session_id="ws_mini",
    )

    run.save(store)


def main() -> None:
    _wipe()
    store = JsonlRunStore(STORE_DIR)
    _scheduling_run(store)
    _hyperparameter_run(store)
    _minimal_run(store)
    print(f"Seeded {STORE_DIR}: scheduling-demo, hyperparam-demo, minimal-demo")


if __name__ == "__main__":
    main()
