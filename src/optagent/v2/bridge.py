"""Compatibility layer: v1.5 OptimizerState ↔ v2 State."""

from __future__ import annotations

from optagent.core.state_model import OptimizerState as OptimizerStateV1
from optagent.v2.state import State, ArtifactSet, Artifact, Transition, Knowledge


def state_v1_to_v2(optimizer_state: OptimizerStateV1) -> State:
    """Convert v1.5 OptimizerState to v2 State."""
    # Build artifact set from v1 artifacts
    artifacts = [
        Artifact(artifact_id=a.hypothesis_id, content=a.to_dict())
        for a in optimizer_state.algorithm.hypotheses
    ]
    artifact_set = ArtifactSet(candidates=artifacts)

    # Build trajectory from hypotheses + evidence
    trajectory = []
    for h in optimizer_state.algorithm.hypotheses:
        # Find corresponding evidence
        ev_list = [
            e for e in optimizer_state.algorithm.evidence
            if e.hypothesis_id == h.id
        ]
        for ev in ev_list:
            trajectory.append(Transition(
                action=None,  # v1 doesn't have explicit actions
                observation=None,  # TODO: map evidence to observation
                reward_contribution={"speedup": ev.speedup or 0.0},
                cost=0.0,
            ))

    return State(
        requirement=optimizer_state.algorithm.requirements,
        artifact=artifact_set,
        trajectory=trajectory,
        knowledge=Knowledge(),  # v1 has no explicit knowledge
    )


def state_v2_to_v1(state: State) -> OptimizerStateV1:
    """Convert v2 State back to v1.5 OptimizerState."""
    # TODO: implement reverse mapping
    raise NotImplementedError("Reverse bridge not yet implemented")
