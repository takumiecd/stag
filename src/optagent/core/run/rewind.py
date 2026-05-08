"""RunHandle.rewind implementation."""

from __future__ import annotations

from datetime import datetime, timezone

from optagent.core.cuts import cut_transition_ids
from optagent.core.schema.payloads import CutPayload


def rewind_impl(
    self,
    transition_id: str,
    *,
    from_node_id: str,
    reason: str | None = None,
    user_id: str | None = None,
) -> CutPayload:
    """Append a cut event for an observed transition."""
    transition = self.observed_dag.transitions.get(transition_id)
    if transition is None:
        raise KeyError(f"unknown observed transition_id: {transition_id}")

    if transition_id in cut_transition_ids(self.observed_dag):
        raise ValueError(f"transition already cut: {transition_id}")

    self._ensure_active_observed_node(from_node_id)
    if not _is_on_active_path_back(
        self, transition_id=transition_id, from_node_id=from_node_id
    ):
        raise ValueError(
            f"{transition_id} is not on the active path from {from_node_id}; "
            "rewind only cuts transitions reachable backwards from from_node_id."
        )

    cut = CutPayload(
        payload_id=self._next_id("pl"),
        target_id=transition_id,
        cut_at=datetime.now(timezone.utc).isoformat(),
        rewound_to_node_id=transition.from_node_id,
        reason=reason,
        user_id=user_id,
    )
    self.observed_dag.attach_payload(cut)
    return cut


def _is_on_active_path_back(self, *, transition_id: str, from_node_id: str) -> bool:
    cut_tids = cut_transition_ids(self.observed_dag)
    seen: set[str] = set()
    frontier: list[str] = [from_node_id]
    while frontier:
        nid = frontier.pop()
        if nid in seen:
            continue
        seen.add(nid)
        for tid in self.observed_dag.incoming_transition_ids(nid):
            if tid in cut_tids:
                continue
            if tid == transition_id:
                return True
            frontier.append(self.observed_dag.transitions[tid].from_node_id)
    return False
