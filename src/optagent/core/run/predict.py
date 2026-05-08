"""RunHandle.predict and select_prediction implementations."""

from __future__ import annotations

from optagent.core.schema.graph import Transition
from optagent.core.schema.payloads import ResultPayload
from optagent.core.schema.selections import PredictionSelection


def predict_impl(
    self,
    plan_id: str,
    *,
    predictor: str | None = None,
    max_outcomes: int | None = None,
) -> list[Transition]:
    """Expand the predicted Dag with predicted transitions for a plan.

    The plan must live in the predicted Dag. For each generated outcome,
    a new predicted Node is created with a SnapshotPayload that re-uses
    the from-node's snapshot, and a Transition is added with a
    ResultPayload describing the predicted result.
    """

    if plan_id not in self.predicted_dag.plans:
        raise KeyError(f"unknown predicted plan_id: {plan_id}")
    plan = self.predicted_dag.plans[plan_id]
    from_node_id = plan.grounded_node_id

    snap_payload = self._get_node_snapshot_payload(self.predicted_dag, from_node_id)

    count = max(1, max_outcomes or 1)
    transitions: list[Transition] = []
    for index in range(count):
        new_node = self._new_node_with_snapshot(
            self.predicted_dag,
            snapshot=snap_payload.snapshot,
            snapshot_hash=snap_payload.snapshot_hash,
            assumptions=tuple(plan.assumptions),
            confidence=plan.confidence,
            payload_metadata={
                "anchor_node_id": self.predicted_dag.metadata.get("anchor_node_id"),
                "source_plan_id": plan.plan_id,
                "outcome_index": index,
            },
        )
        transition = Transition(
            transition_id=self._next_id("t"),
            parent_plan_id=plan.plan_id,
            from_node_id=from_node_id,
            to_node_id=new_node.node_id,
            metadata={"ordinal": index},
        )
        self.predicted_dag.add_transition(transition)
        self.predicted_dag.attach_payload(
            ResultPayload(
                payload_id=self._next_id("pl"),
                target_id=transition.transition_id,
                status="completed",
                metadata={"predictor": predictor or "default"},
            )
        )
        transitions.append(transition)
    return transitions


def select_prediction_impl(
    self,
    *,
    predicted_transition_id: str | None = None,
    predicted_transition_ids: list[str] | None = None,
    to_predicted_node_id: str | None = None,
    reason: str = "",
) -> PredictionSelection:
    """Record a selection of predicted transitions for later promotion."""

    selected = list(predicted_transition_ids or ())
    if predicted_transition_id is not None:
        selected.append(predicted_transition_id)
    if to_predicted_node_id is not None:
        selected.extend(
            tid
            for tid, transition in self.predicted_dag.transitions.items()
            if transition.to_node_id == to_predicted_node_id
        )
    if not selected:
        raise ValueError("select_prediction requires at least one predicted transition")
    for tid in selected:
        if tid not in self.predicted_dag.transitions:
            raise KeyError(f"unknown predicted transition_id: {tid}")
    selection = PredictionSelection(
        selection_id=self._next_id("sel"),
        selected_transition_ids=tuple(dict.fromkeys(selected)),
        reason=reason,
    )
    self.selections[selection.selection_id] = selection
    return selection
