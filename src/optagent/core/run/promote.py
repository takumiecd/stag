"""RunHandle.promote and shared observed-transition append helper."""

from __future__ import annotations

from typing import Literal

from optagent.core.schema.graph import Transition
from optagent.core.schema.payloads import MatchPayload, ResultPayload
from optagent.core.schema.plans import Plan
from optagent.core.schema.selections import PredictionPath


def promote_impl(
    self,
    *,
    mode: Literal["plan", "transition"],
    prediction_plan_id: str | None = None,
    prediction_path: PredictionPath | None = None,
    to_observed_node_id: str | None = None,
    predicted_transition_id: str | None = None,
    result: ResultPayload | None = None,
    plan_id: str | None = None,
    user_id: str | None = None,
) -> list[Plan] | Transition:
    """Promote prediction-side records into observed-side grounded records."""

    if mode == "plan":
        if to_observed_node_id is None:
            raise ValueError("promote(mode='plan') requires to_observed_node_id")
        return _promote_plan(
            self,
            prediction_plan_id,
            prediction_path,
            to_observed_node_id,
            user_id=user_id,
        )
    if mode == "transition":
        if predicted_transition_id is None or result is None:
            raise ValueError(
                "promote(mode='transition') requires predicted_transition_id and result"
            )
        return _promote_transition(
            self,
            predicted_transition_id=predicted_transition_id,
            result=result,
            plan_id=plan_id,
            user_id=user_id,
        )
    raise ValueError(f"unsupported promote mode: {mode}")


def _promote_plan(
    self,
    prediction_plan_id: str | None,
    prediction_path: PredictionPath | None,
    to_observed_node_id: str,
    *,
    user_id: str | None = None,
) -> list[Plan]:
    self._ensure_active_observed_node(to_observed_node_id)

    plan_ids: list[str] = []
    selected_by_plan: dict[str, str] = {}
    source_path_id: str | None = None
    if prediction_path is not None:
        source_path_id = prediction_path.path_id
        for step in prediction_path.steps:
            plan_ids.append(step.plan_id)
            selected_by_plan[step.plan_id] = step.selected_transition_id
    if prediction_plan_id is not None:
        plan_ids.append(prediction_plan_id)
    if not plan_ids:
        raise ValueError("promote(mode='plan') requires prediction_plan_id or prediction_path")

    promoted: list[Plan] = []
    for pid in plan_ids:
        source = self.predicted_dag.plans.get(pid)
        if source is None:
            raise KeyError(f"unknown predicted plan_id: {pid}")
        new_plan = Plan(
            plan_id=self._next_id("plan"),
            grounded_node_id=to_observed_node_id,
            action_type=source.action_type,
            intent=source.intent,
            inputs=dict(source.inputs),
            safety_policy=dict(source.safety_policy),
            assumptions=tuple(source.assumptions),
            metadata={
                **source.metadata,
                "source_predicted_plan_id": source.plan_id,
                "source_prediction_path_id": source_path_id,
                "selected_predicted_transition_id": selected_by_plan.get(pid),
                "promotion_id": self._next_id("promotion"),
                **({"user_id": user_id} if user_id is not None else {}),
            },
        )
        self.observed_dag.add_plan(new_plan)
        promoted.append(new_plan)
    return promoted


def _promote_transition(
    self,
    *,
    predicted_transition_id: str,
    result: ResultPayload,
    plan_id: str | None,
    user_id: str | None,
) -> Transition:
    predicted_transition = self.predicted_dag.transitions.get(predicted_transition_id)
    if predicted_transition is None:
        raise KeyError(f"unknown predicted_transition_id: {predicted_transition_id}")
    if plan_id is None:
        raise ValueError("promote(mode='transition') requires plan_id")
    plan = self.observed_dag.plans.get(plan_id)
    if plan is None:
        raise KeyError(f"unknown observed plan_id: {plan_id}")
    return _append_observed_transition(
        self,
        plan=plan,
        result=result,
        matched_predicted_transition_id=predicted_transition.transition_id,
        match_status="compatible",
        prediction_error={},
        user_id=user_id,
    )


def _append_observed_transition(
    self,
    *,
    plan: Plan,
    result: ResultPayload,
    matched_predicted_transition_id: str | None,
    match_status: str | None,
    prediction_error: dict | None,
    user_id: str | None = None,
) -> Transition:
    """Append a transition to the observed Dag, enforcing 1-plan-1-transition."""
    self._ensure_active_observed_node(plan.grounded_node_id)
    if self.observed_dag.transition_ids_for_plan(plan.plan_id):
        raise ValueError(
            "an observed plan can have only one transition; "
            "create a new plan to rerun the same operation"
        )
    snap_payload = self._get_node_snapshot_payload(self.observed_dag, plan.grounded_node_id)
    next_node = self._new_node_with_snapshot(
        self.observed_dag,
        snapshot=snap_payload.snapshot,
        snapshot_hash=snap_payload.snapshot_hash,
    )
    transition = Transition(
        transition_id=self._next_id("t"),
        parent_plan_id=plan.plan_id,
        from_node_id=plan.grounded_node_id,
        to_node_id=next_node.node_id,
        metadata={"user_id": user_id} if user_id is not None else {},
    )
    self.observed_dag.add_transition(transition)
    # Re-attach the result payload pointing at the new transition.
    result_payload = ResultPayload(
        payload_id=self._next_id("pl"),
        target_id=transition.transition_id,
        status=result.status,
        artifacts=result.artifacts,
        raw_outputs=result.raw_outputs,
        logs=result.logs,
        metrics=dict(result.metrics),
        errors=result.errors,
        actual_cost=dict(result.actual_cost),
        metadata=dict(result.metadata),
    )
    self.observed_dag.attach_payload(result_payload)
    if matched_predicted_transition_id is not None:
        self.observed_dag.attach_payload(
            MatchPayload(
                payload_id=self._next_id("pl"),
                target_id=transition.transition_id,
                matched_transition_id=matched_predicted_transition_id,
                match_status=match_status or "compatible",  # type: ignore[arg-type]
                prediction_error=dict(prediction_error or {}),
            )
        )
    return transition
