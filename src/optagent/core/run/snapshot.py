"""RunHandle.snapshot_rebuild implementation."""

from __future__ import annotations

from optagent.core.schema.payloads import (
    DerivedPayload,
    ResultPayload,
    SnapshotPayload,
)
from optagent.core.schema.snapshots import (
    ArtifactRef,
    FindingRef,
    StateSnapshot,
)


def snapshot_rebuild_impl(self, node_id: str) -> SnapshotPayload:
    """Rebuild a node's SnapshotPayload from observed history.

    Walks backwards from *node_id* and aggregates artifacts (from
    ResultPayloads) and knowledge (from finding-like DerivedPayloads)
    into a fresh SnapshotPayload. The new payload is attached to the
    node (additional payload, not a replacement of the prior one).
    """
    if node_id not in self.observed_dag.nodes:
        raise KeyError(f"unknown observed node_id: {node_id}")
    self._ensure_active_observed_node(node_id)

    artifacts: list[ArtifactRef] = []
    knowledge: list[FindingRef] = []

    cursor = node_id
    while True:
        incoming = self.observed_dag.incoming_transition_ids(cursor)
        if not incoming:
            break
        transition = self.observed_dag.transitions[incoming[-1]]

        for payload in self.observed_dag.payloads_for_transition(
            transition.transition_id
        ):
            if isinstance(payload, ResultPayload):
                for path in payload.artifacts:
                    artifacts.append(
                        ArtifactRef(artifact_id=path, artifact_type="artifact", path=path)
                    )
                for path in payload.raw_outputs:
                    artifacts.append(
                        ArtifactRef(artifact_id=path, artifact_type="raw_output", path=path)
                    )
                for path in payload.logs:
                    artifacts.append(
                        ArtifactRef(artifact_id=path, artifact_type="log", path=path)
                    )
            elif isinstance(payload, DerivedPayload):
                if payload.derived_type in ("finding", "summary", "evidence", "decision"):
                    text = payload.payload.get("text", "")
                    summary = text if isinstance(text, str) else str(payload.payload)
                    knowledge.append(
                        FindingRef(
                            finding_id=payload.payload_id,
                            summary=summary,
                            scope=payload.derived_type,
                            metadata={"generator": payload.generator},
                        )
                    )

        cursor = transition.from_node_id

    old_snap = self._get_node_snapshot_payload(self.observed_dag, node_id).snapshot
    new_snap = StateSnapshot(
        requirement=old_snap.requirement,
        artifacts=tuple(artifacts),
        knowledge=tuple(knowledge),
        open_questions=old_snap.open_questions,
        active_branches=old_snap.active_branches,
        predictions=old_snap.predictions,
        budget=old_snap.budget,
        metadata=old_snap.metadata,
    )

    new_payload = SnapshotPayload(
        payload_id=self._next_id("pl"),
        target_id=node_id,
        snapshot=new_snap,
        snapshot_hash=new_snap.compute_hash(),
        metadata={"source": "snapshot_rebuild"},
    )
    self.observed_dag.attach_payload(new_payload)
    return new_payload
