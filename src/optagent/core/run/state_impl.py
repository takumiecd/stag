"""RunHandle.state_show and state_update implementations."""

from __future__ import annotations

from optagent.core.schema.payloads import SnapshotPayload
from optagent.core.schema.snapshots import (
    ArtifactRef,
    FindingRef,
    PredictionRef,
    StateSnapshot,
)


def state_show_impl(self, node_id: str) -> SnapshotPayload:
    """Return the most recent SnapshotPayload for an observed node."""
    if node_id not in self.observed_dag.nodes:
        raise KeyError(f"unknown observed node_id: {node_id}")
    return self._get_node_snapshot_payload(self.observed_dag, node_id)


def state_update_impl(
    self,
    *,
    node_id: str,
    add_knowledge: list[str] | None = None,
    add_open_question: list[str] | None = None,
    add_artifact: list[tuple[str, str, str | None]] | None = None,
    add_prediction: list[tuple[str, str]] | None = None,
    add_branch: list[str] | None = None,
) -> SnapshotPayload:
    """Append a new SnapshotPayload that extends the latest one for *node_id*."""
    self._ensure_active_observed_node(node_id)
    old_payload = self._get_node_snapshot_payload(self.observed_dag, node_id)
    old_snap = old_payload.snapshot

    new_knowledge = list(old_snap.knowledge)
    for summary in add_knowledge or []:
        new_knowledge.append(
            FindingRef(finding_id=self._next_id("pl"), summary=summary)
        )

    new_open_questions = list(old_snap.open_questions)
    new_open_questions.extend(add_open_question or [])

    new_artifacts = list(old_snap.artifacts)
    for artifact_id, artifact_type, path in add_artifact or []:
        new_artifacts.append(
            ArtifactRef(artifact_id=artifact_id, artifact_type=artifact_type, path=path)
        )

    new_predictions = list(old_snap.predictions)
    for prediction_id, summary in add_prediction or []:
        new_predictions.append(
            PredictionRef(prediction_id=prediction_id, summary=summary)
        )

    new_branches = list(old_snap.active_branches)
    new_branches.extend(add_branch or [])

    new_snap = StateSnapshot(
        requirement=old_snap.requirement,
        artifacts=tuple(new_artifacts),
        knowledge=tuple(new_knowledge),
        open_questions=tuple(new_open_questions),
        active_branches=tuple(new_branches),
        predictions=tuple(new_predictions),
        budget=old_snap.budget,
        metadata=old_snap.metadata,
    )
    new_payload = SnapshotPayload(
        payload_id=self._next_id("pl"),
        target_id=node_id,
        snapshot=new_snap,
        snapshot_hash=new_snap.compute_hash(),
        assumptions=old_payload.assumptions,
        confidence=old_payload.confidence,
        status=old_payload.status,
        metadata={"source": "state_update"},
    )
    self.observed_dag.attach_payload(new_payload)
    return new_payload
