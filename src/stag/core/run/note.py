"""RunHandle.note implementation."""

from __future__ import annotations

from stag.core.schema.payloads import NotePayload


def note_impl(
    self,
    node_id: str,
    text: str,
    *,
    tags: list[str] | tuple[str, ...] = (),
    user_id: str | None = None,
    work_session_id: str | None = None,
) -> NotePayload:
    """Attach a lightweight memo to a node."""
    if node_id not in self.run_graph.nodes:
        raise KeyError(f"unknown node_id: {node_id}")

    payload = NotePayload(
        payload_id=self._next_id("pl"),
        target_id=node_id,
        text=text,
        author=user_id,
        tags=tuple(tags),
    )
    self.run_graph.attach_payload(payload)
    self.record_work_event(
        user_id=user_id,
        work_session_id=work_session_id,
        event_type="note_added",
        target_kind="node",
        target_id=node_id,
        created_records=(payload.payload_id,),
        summary=text,
    )
    return payload
