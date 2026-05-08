"""Tests for the RunHandle public verbs."""

from __future__ import annotations

import pytest

from optagent import init
from optagent.core.cuts import is_cut_transition
from optagent.core.schema.payloads import (
    CutPayload,
    DerivedPayload,
    MatchPayload,
    ResultPayload,
    SnapshotPayload,
)
from optagent.core.schema.requirements import Requirement


def _req() -> Requirement:
    return Requirement(requirement_id="r", target_type="task", target_id="t")


def test_init_seeds_two_dags_with_root_snapshots():
    run = init(_req(), run_id="t_init")
    assert run.observed_dag.metadata["role"] == "observed"
    assert run.predicted_dag.metadata["role"] == "predicted"
    assert run.predicted_dag.dag_id in run.observed_dag.child_dags
    obs_root = run.root_observed_node_id
    snap = run._get_node_snapshot_payload(run.observed_dag, obs_root)
    assert snap.snapshot.requirement.requirement_id == "r"


def test_plan_creates_observed_plan():
    run = init(_req(), run_id="t_plan")
    plans = run.plan(run.root_observed_node_id, intent="x")
    assert len(plans) == 1
    assert plans[0].plan_id in run.observed_dag.plans


def test_observe_appends_transition_with_result_payload():
    run = init(_req(), run_id="t_obs")
    plan = run.plan(run.root_observed_node_id)[0]
    result = ResultPayload(payload_id="x", target_id="x", status="completed", metrics={"a": 1.0})
    tr = run.observe(plan.plan_id, result)
    assert tr.parent_plan_id == plan.plan_id
    payloads = run.observed_dag.payloads_for_transition(tr.transition_id)
    assert any(isinstance(p, ResultPayload) for p in payloads)


def test_observe_enforces_one_transition_per_plan():
    run = init(_req(), run_id="t_card")
    plan = run.plan(run.root_observed_node_id)[0]
    result = ResultPayload(payload_id="x", target_id="x", status="completed")
    run.observe(plan.plan_id, result)
    with pytest.raises(ValueError):
        run.observe(plan.plan_id, result)


def test_predict_creates_multiple_predicted_transitions_for_one_plan():
    run = init(_req(), run_id="t_pred")
    pred_root = run.predicted_dag.metadata["root_node_id"]
    plans = run.extend(pred_root, intent="x")
    transitions = run.predict(plans[0].plan_id, max_outcomes=3)
    assert len(transitions) == 3
    assert all(t.parent_plan_id == plans[0].plan_id for t in transitions)


def test_promote_transition_attaches_match_payload():
    run = init(_req(), run_id="t_prom")
    pred_root = run.predicted_dag.metadata["root_node_id"]
    pplans = run.extend(pred_root)
    pred_trs = run.predict(pplans[0].plan_id, max_outcomes=1)
    obs_plan = run.plan(run.root_observed_node_id)[0]
    result = ResultPayload(payload_id="x", target_id="x", status="completed")
    tr = run.promote(
        mode="transition",
        predicted_transition_id=pred_trs[0].transition_id,
        result=result,
        plan_id=obs_plan.plan_id,
    )
    payloads = run.observed_dag.payloads_for_transition(tr.transition_id)
    assert any(isinstance(p, MatchPayload) for p in payloads)


def test_derive_attaches_derived_payload():
    run = init(_req(), run_id="t_der")
    plan = run.plan(run.root_observed_node_id)[0]
    result = ResultPayload(payload_id="x", target_id="x", status="completed")
    tr = run.observe(plan.plan_id, result)
    record = run.derive(tr.transition_id, "finding", {"text": "hi"})
    assert isinstance(record, DerivedPayload)
    assert record.target_id == tr.transition_id


def test_rewind_attaches_cut_payload_and_blocks_active_path_writes():
    run = init(_req(), run_id="t_rew")
    plan = run.plan(run.root_observed_node_id)[0]
    result = ResultPayload(payload_id="x", target_id="x", status="completed")
    tr = run.observe(plan.plan_id, result)
    cut = run.rewind(tr.transition_id, from_node_id=tr.to_node_id, reason="x")
    assert isinstance(cut, CutPayload)
    assert is_cut_transition(run.observed_dag, tr.transition_id)
    # the rewound-away node is cut, can't grow from it
    with pytest.raises(ValueError):
        run.plan(tr.to_node_id)


def test_refresh_replaces_predicted_dag():
    run = init(_req(), run_id="t_ref")
    old_id = run.predicted_dag.dag_id
    new_dag = run.refresh(from_node_id=run.root_observed_node_id)
    assert new_dag.dag_id != old_id
    assert run.predicted_dag is new_dag
    assert old_id not in run.observed_dag.child_dags


def test_state_show_returns_snapshot_payload():
    run = init(_req(), run_id="t_show")
    snap = run.state_show(run.root_observed_node_id)
    assert isinstance(snap, SnapshotPayload)


def test_state_update_appends_new_snapshot_payload():
    run = init(_req(), run_id="t_upd")
    before = len(run.observed_dag.payloads_for_node(run.root_observed_node_id))
    run.state_update(node_id=run.root_observed_node_id, add_open_question=["why?"])
    after = len(run.observed_dag.payloads_for_node(run.root_observed_node_id))
    assert after == before + 1


def test_select_prediction_records_selection():
    run = init(_req(), run_id="t_sel")
    pred_root = run.predicted_dag.metadata["root_node_id"]
    pplans = run.extend(pred_root)
    pred_trs = run.predict(pplans[0].plan_id, max_outcomes=2)
    sel = run.select_prediction(predicted_transition_ids=[t.transition_id for t in pred_trs])
    assert sel.selection_id in run.selections
    assert len(sel.selected_transition_ids) == 2
