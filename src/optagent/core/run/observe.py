"""RunHandle.observe implementation."""

from __future__ import annotations

from optagent.core.schema.graph import Transition
from optagent.core.schema.payloads import ResultPayload


def observe_impl(
    self,
    plan_id: str,
    result: ResultPayload,
    *,
    user_id: str | None = None,
) -> Transition:
    """Record a transition for a plan grounded on the observed Dag.

    *result* is a ResultPayload describing the actual execution outcome.
    Its ``target_id`` will be overwritten to point at the new transition.
    """
    plan = self.observed_dag.plans.get(plan_id)
    if plan is None:
        raise KeyError(f"unknown observed plan_id: {plan_id}")
    return self._append_observed_transition(
        plan=plan,
        result=result,
        matched_predicted_transition_id=None,
        match_status=None,
        prediction_error=None,
        user_id=user_id,
    )
