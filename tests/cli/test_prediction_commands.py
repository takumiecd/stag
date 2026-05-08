"""Tests for predict CLI commands."""

from __future__ import annotations

from optagent.cli.commands.init import run_init_command
from optagent.cli.commands.observe import run_observe_command
from optagent.cli.commands.plan import run_plan_command
from optagent.cli.commands.predict import run_predict_command
from optagent.storage.jsonl import JsonlRunStore


def _init(store_dir: str) -> str:
    run_init_command(
        requirement_id="req",
        target_type="task",
        target_id="target",
        run_id="run_a",
        store_dir=store_dir,
    )
    return "run_a"


def test_predict_adds_multiple_output_transitions_with_prediction_payloads(tmp_path):
    store_dir = str(tmp_path / "runs")
    run_id = _init(store_dir)
    it_id = run_plan_command(
        run_id=run_id,
        input_node_ids=["n_0000"],
        action_type="analysis",
        intent="x",
        store_dir=store_dir,
    )["input_transition"]["input_transition_id"]

    output_transitions = run_predict_command(
        run_id=run_id,
        input_transition_id=it_id,
        max_outcomes=3,
        store_dir=store_dir,
    )["output_transitions"]

    assert len(output_transitions) == 3
    for ot in output_transitions:
        assert ot["input_transition_id"] == it_id

    handle = JsonlRunStore(store_dir).load_run(run_id)
    for ot in output_transitions:
        pred_payloads = handle.run_graph.payloads_for_output_transition(
            ot["output_transition_id"], payload_type="prediction"
        )
        assert len(pred_payloads) == 1


def test_observe_with_matched_prediction(tmp_path):
    store_dir = str(tmp_path / "runs")
    run_id = _init(store_dir)
    it_id = run_plan_command(
        run_id=run_id,
        input_node_ids=["n_0000"],
        action_type="analysis",
        intent="x",
        store_dir=store_dir,
    )["input_transition"]["input_transition_id"]
    predictions = run_predict_command(
        run_id=run_id, input_transition_id=it_id, max_outcomes=2, store_dir=store_dir
    )["output_transitions"]
    pred_ot_id = predictions[0]["output_transition_id"]

    ot = run_observe_command(
        run_id=run_id,
        input_transition_id=it_id,
        status="completed",
        artifacts=None, raw_outputs=None, logs=None, metrics=None, errors=None,
        matched_prediction_output_id=pred_ot_id,
        store_dir=store_dir,
    )["output_transition"]

    handle = JsonlRunStore(store_dir).load_run(run_id)
    result_payloads = handle.run_graph.payloads_for_output_transition(
        ot["output_transition_id"], payload_type="result"
    )
    assert result_payloads[0].matched_prediction_output_id == pred_ot_id
