"""Tests for concurrent push/pull conflict behavior.

Covers the scenarios outlined in PLAN.md § Recommended Next Work:

1. Two workspaces independently add different transitions from the same node.
2. One workspace pulls after another workspace pushes.
3. Re-pushing the same local records is idempotent.
4. A remote record with the same record_id but different body is rejected.
"""

from __future__ import annotations

import json

import pytest

from stag.cli.commands.anchor import run_anchor_command
from stag.cli.commands.init import run_init_command
from stag.cli.commands.plan import run_plan_command
from stag.cli.commands.sync import (
    run_sync_init_command,
    run_sync_pull_command,
    run_sync_push_command,
    run_sync_status_command,
)
from stag.cli.context import resolve_store
from stag.core.run.dump import DumpOptions, dump


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init(store_dir: str, run_id: str) -> None:
    run_init_command(
        requirement_id="req",
        target_type="task",
        target_id="target",
        run_id=run_id,
        store_dir=store_dir,
    )


def _root(store_dir: str, run_id: str) -> str:
    return resolve_store(store_dir).load_run(run_id).root_node_id


def _setup_shared_pair(tmp_path, *, with_anchor: bool = True):
    """Create two local runs and a shared remote, push local_a's seed + anchor."""
    store_dir = str(tmp_path / "runs")
    remote_dir = str(tmp_path / "remotes")
    _init(store_dir, "local_a")
    _init(store_dir, "local_b")
    root_a = _root(store_dir, "local_a")

    if with_anchor:
        run_anchor_command(
            run_id="local_a",
            from_node_id=root_a,
            label="shared anchor",
            store_dir=store_dir,
        )

    run_sync_init_command(
        run_id="local_a",
        shared_run_id="sr",
        store_dir=store_dir,
        remote_dir=remote_dir,
        workspace_id="ws_a",
        actor_id="alice",
    )
    run_sync_push_command(
        run_id="local_a",
        store_dir=store_dir,
        shared_run_id="sr",
        remote_dir=remote_dir,
        workspace_id="ws_a",
        actor_id="alice",
    )
    return store_dir, remote_dir


# ---------------------------------------------------------------------------
# 1. Two workspaces independently add different transitions from the same node
# ---------------------------------------------------------------------------

def test_two_workspaces_branch_from_same_node(tmp_path):
    """DAG branching: two workspaces push different transitions from the same
    shared anchor node.  Both pushes should succeed because different
    transitions have different record IDs."""
    store_dir, remote_dir = _setup_shared_pair(tmp_path)

    # Pull shared state into local_b so it has the anchor node.
    run_sync_pull_command(
        run_id="local_b",
        store_dir=store_dir,
        shared_run_id="sr",
        remote_dir=remote_dir,
    )
    store = resolve_store(store_dir)
    store.save_run(store.load_run("local_b"))

    # Find the anchor node (the node created by anchor, not root).
    handle_a = store.load_run("local_a")
    anchor_node_ids = [
        n for n in handle_a.run_graph.nodes
        if n != handle_a.root_node_id
    ]
    assert anchor_node_ids, "expected at least one non-root node after anchor"
    anchor_node = anchor_node_ids[0]

    # Workspace A: plan from anchor node.
    run_plan_command(
        run_id="local_a",
        input_node_ids=[anchor_node],
        action_type="verification",
        intent="variant A",
        store_dir=store_dir,
    )
    push_a = run_sync_push_command(
        run_id="local_a",
        store_dir=store_dir,
        shared_run_id="sr",
        remote_dir=remote_dir,
        workspace_id="ws_a",
        actor_id="alice",
    )
    assert push_a["pushed_records"] > 0

    # Workspace B: plan from the same anchor node (different transition).
    run_plan_command(
        run_id="local_b",
        input_node_ids=[anchor_node],
        action_type="evaluation",
        intent="variant B",
        store_dir=store_dir,
    )
    push_b = run_sync_push_command(
        run_id="local_b",
        store_dir=store_dir,
        shared_run_id="sr",
        remote_dir=remote_dir,
        workspace_id="ws_b",
        actor_id="bob",
    )
    assert push_b["pushed_records"] > 0

    # Both pushes succeeded — verify the shared log has records from both.
    records_path = (
        tmp_path / "remotes" / "local-shared" / "runs" / "sr" / "records.jsonl"
    )
    batches = [
        json.loads(line)
        for line in records_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    actors = {b["actor"]["actor_id"] for b in batches}
    assert "alice" in actors
    assert "bob" in actors


# ---------------------------------------------------------------------------
# 2. One workspace pulls after another workspace pushes
# ---------------------------------------------------------------------------

def test_pull_after_other_workspace_pushes(tmp_path):
    """After workspace A pushes, workspace B can pull the new records and
    use them to continue working locally."""
    store_dir, remote_dir = _setup_shared_pair(tmp_path)

    # Pull into B.
    pulled = run_sync_pull_command(
        run_id="local_b",
        store_dir=store_dir,
        shared_run_id="sr",
        remote_dir=remote_dir,
    )
    assert pulled["pulled_records"] == 7

    store = resolve_store(store_dir)
    store.save_run(store.load_run("local_b"))

    # B can continue from the pulled graph.
    handle_b = store.load_run("local_b")
    anchor_nodes = [
        n for n in handle_b.run_graph.nodes if n != handle_b.root_node_id
    ]
    assert anchor_nodes

    it = run_plan_command(
        run_id="local_b",
        input_node_ids=[anchor_nodes[0]],
        action_type="verification",
        intent="continue from pulled state",
        store_dir=store_dir,
    )["input_transition"]
    assert it["input_transition_id"].startswith("it_")

    # Status should show B has unpushed records.
    status = run_sync_status_command(
        run_id="local_b",
        store_dir=store_dir,
        shared_run_id="sr",
        remote_dir=remote_dir,
    )
    assert status["unpushed_records"] > 0
    assert status["unpulled_records"] == 0


# ---------------------------------------------------------------------------
# 3. Re-pushing the same local records is idempotent
# ---------------------------------------------------------------------------

def test_repush_is_idempotent(tmp_path):
    """Pushing the same local records twice should not duplicate them in the
    shared log."""
    store_dir, remote_dir = _setup_shared_pair(tmp_path)

    # Push again — should be a no-op.
    second = run_sync_push_command(
        run_id="local_a",
        store_dir=store_dir,
        shared_run_id="sr",
        remote_dir=remote_dir,
        workspace_id="ws_a",
        actor_id="alice",
    )
    assert second["pushed_batches"] == 0
    assert second["pushed_records"] == 0

    # Shared log should still have exactly the same batches as the first push.
    records_path = (
        tmp_path / "remotes" / "local-shared" / "runs" / "sr" / "records.jsonl"
    )
    batches = [
        json.loads(line)
        for line in records_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(batches) == 2  # seed + anchor from the first push only


# ---------------------------------------------------------------------------
# 4. Same record_id with different body is rejected
# ---------------------------------------------------------------------------

def test_conflicting_body_rejected_on_push(tmp_path):
    """If the remote already has a record with the same identity key but a
    different body, sync_push should raise RuntimeError."""
    store_dir, remote_dir = _setup_shared_pair(tmp_path)

    # Tamper with the remote: change a node body in records.jsonl.
    records_path = (
        tmp_path / "remotes" / "local-shared" / "runs" / "sr" / "records.jsonl"
    )
    lines = records_path.read_text(encoding="utf-8").splitlines()
    new_lines = []
    for line in lines:
        if not line.strip():
            new_lines.append(line)
            continue
        batch = json.loads(line)
        for record in batch.get("records", []):
            if record["record_kind"] == "node":
                record["body"]["metadata"]["tampered"] = True
        new_lines.append(json.dumps(batch, ensure_ascii=False))
    records_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # Re-pushing local_a should fail because bodies differ.
    with pytest.raises(RuntimeError, match="differs|different body"):
        run_sync_push_command(
            run_id="local_a",
            store_dir=store_dir,
            shared_run_id="sr",
            remote_dir=remote_dir,
            workspace_id="ws_a",
            actor_id="alice",
        )


def test_conflicting_body_rejected_on_pull(tmp_path):
    """If the remote has a record whose body conflicts with the local graph,
    sync_pull should raise RuntimeError."""
    store_dir, remote_dir = _setup_shared_pair(tmp_path)

    # Pull into B so it has the shared state.
    run_sync_pull_command(
        run_id="local_b",
        store_dir=store_dir,
        shared_run_id="sr",
        remote_dir=remote_dir,
    )
    store = resolve_store(store_dir)
    store.save_run(store.load_run("local_b"))

    # Tamper with the remote: modify a node body that B already has.
    records_path = (
        tmp_path / "remotes" / "local-shared" / "runs" / "sr" / "records.jsonl"
    )
    lines = records_path.read_text(encoding="utf-8").splitlines()
    new_lines = []
    for line in lines:
        if not line.strip():
            new_lines.append(line)
            continue
        batch = json.loads(line)
        for record in batch.get("records", []):
            if record["record_kind"] == "node":
                record["body"]["metadata"]["tampered"] = True
        new_lines.append(json.dumps(batch, ensure_ascii=False))
    records_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # Pulling the tampered remote into B should fail.
    with pytest.raises(RuntimeError, match="differs"):
        run_sync_pull_command(
            run_id="local_b",
            store_dir=store_dir,
            shared_run_id="sr",
            remote_dir=remote_dir,
        )
