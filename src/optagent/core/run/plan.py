"""RunHandle.plan and RunHandle.extend implementations."""

from __future__ import annotations

from optagent.core.schema.plans import Plan
from optagent.core.types import JSONValue


def plan_impl(
    self,
    from_node_id: str,
    *,
    planner: str | None = None,
    max_plans: int | None = None,
    action_type: str = "analysis",
    intent: str | None = None,
    inputs: dict[str, JSONValue] | None = None,
    user_id: str | None = None,
) -> list[Plan]:
    """Create one or more Plans grounded on an observed node."""

    self._ensure_active_observed_node(from_node_id)

    count = max(1, max_plans or 1)
    resolved_intent = intent or "inspect selected state and propose next useful action"
    resolved_planner = planner or "default"
    plans: list[Plan] = []
    for index in range(count):
        plan = Plan(
            plan_id=self._next_id("plan"),
            grounded_node_id=from_node_id,
            action_type=action_type,  # type: ignore[arg-type]
            intent=resolved_intent,
            inputs=dict(inputs or {}),
            metadata={
                "planner": resolved_planner,
                "ordinal": index,
                **({"user_id": user_id} if user_id is not None else {}),
            },
        )
        self.observed_dag.add_plan(plan)
        plans.append(plan)
    return plans


def extend_impl(
    self,
    node_id: str,
    *,
    planner: str | None = None,
    max_plans: int | None = None,
    action_type: str = "analysis",
    intent: str | None = None,
    inputs: dict[str, JSONValue] | None = None,
) -> list[Plan]:
    """Create Plans grounded on a node in the predicted Dag."""

    if node_id not in self.predicted_dag.nodes:
        raise KeyError(f"not a predicted node: {node_id}")

    count = max(1, max_plans or 1)
    resolved_intent = intent or "inspect predicted state and extend the future scenario"
    resolved_planner = planner or "default"
    plans: list[Plan] = []
    for index in range(count):
        plan = Plan(
            plan_id=self._next_id("plan"),
            grounded_node_id=node_id,
            action_type=action_type,  # type: ignore[arg-type]
            intent=resolved_intent,
            inputs=dict(inputs or {}),
            metadata={"planner": resolved_planner, "ordinal": index},
        )
        self.predicted_dag.add_plan(plan)
        plans.append(plan)
    return plans
