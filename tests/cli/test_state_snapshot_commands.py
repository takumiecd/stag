"""Tests for note and view CLI commands."""

from __future__ import annotations

from optagent.cli.commands.init import run_init_command
from optagent.cli.commands.note import run_note_command
from optagent.cli.commands.observe import run_observe_command
from optagent.cli.commands.plan import run_plan_command
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


def test_note_attaches_to_node(tmp_path):
    store_dir = str(tmp_path / "runs")
    run_id = _init(store_dir)

    note = run_note_command(
        run_id=run_id,
        node_id="n_0000",
        text="baseline setup",
        tags=["context", "setup"],
        store_dir=store_dir,
        user_id="alice",
    )["note"]

    assert note["text"] == "baseline setup"
    assert note["target_id"] == "n_0000"
    assert note["payload_type"] == "note"
    assert set(note["tags"]) == {"context", "setup"}

    handle = JsonlRunStore(store_dir).load_run(run_id)
    note_payloads = handle.run_graph.payloads_for_node("n_0000", payload_type="note")
    assert len(note_payloads) == 1
    assert note_payloads[0].text == "baseline setup"


def test_note_shows_in_trace(tmp_path):
    store_dir = str(tmp_path / "runs")
    run_id = _init(store_dir)

    run_note_command(run_id=run_id, node_id="n_0000", text="root note", store_dir=store_dir)
    it_id = run_plan_command(
        run_id=run_id, input_node_ids=["n_0000"], action_type="analysis",
        intent="x", store_dir=store_dir,
    )["input_transition"]["input_transition_id"]
    ot = run_observe_command(
        run_id=run_id, input_transition_id=it_id, status="completed",
        artifacts=None, raw_outputs=None, logs=None, metrics=None, errors=None,
        store_dir=store_dir,
    )["output_transition"]

    from optagent.cli.commands.trace import run_trace_command
    history = run_trace_command(
        run_id=run_id, from_node_id=ot["to_node_id"], depth=None, store_dir=store_dir
    )["history"]
    assert len(history["note_payload_ids"]) >= 1
