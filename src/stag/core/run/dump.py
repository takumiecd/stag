"""Dump RunGraph as outline or mermaid."""

from __future__ import annotations

from dataclasses import dataclass

from stag.core.cuts import inactive_node_ids, inactive_transition_ids
from stag.core.run.handle import RunHandle
from stag.core.run_graph import RunGraph
from stag.core.schema.payloads import (
    GitChangePayload,
    NotePayload,
    PlanPayload,
    PredictionPayload,
    ResultPayload,
)


@dataclass
class DumpOptions:
    node_id: str | None = None
    depth: int | None = None
    observed_only: bool = False
    predicted_only: bool = False
    full_payloads: bool = False


def _truncate(s: str | None, n: int) -> str:
    if not s:
        return ""
    return s if len(s) <= n else s[: n - 1] + "…"


def _node_note(graph: RunGraph, node_id: str) -> str | None:
    for payload in graph.payloads_for_node(node_id):
        if isinstance(payload, NotePayload):
            return payload.text
    return None


def _transition_summary(graph: RunGraph, transition_id: str, full: bool) -> tuple[str, str]:
    payloads = graph.payloads_for_transition(transition_id)
    parts = []
    marker = "◇"
    for payload in payloads:
        if isinstance(payload, PlanPayload):
            parts.append(f"plan:{_truncate(payload.intent, 60)}")
        elif isinstance(payload, ResultPayload):
            marker = "→"
            parts.append(f"result:{payload.status}")
            if full and payload.metrics:
                parts.append(f"metrics={payload.metrics}")
        elif isinstance(payload, PredictionPayload):
            if marker != "→":
                marker = "⇢"
            detail = "prediction"
            if payload.probability is not None:
                detail += f":p={payload.probability}"
            parts.append(detail)
        elif isinstance(payload, GitChangePayload):
            diff = payload.diff_summary
            parts.append(f"git:+{diff.insertions}/-{diff.deletions}")
    return marker, " ".join(parts) if parts else "transition"


def render_outline(handle: RunHandle, opts: DumpOptions) -> str:
    graph = handle.run_graph
    inactive_nodes = inactive_node_ids(graph)
    inactive_transitions = inactive_transition_ids(graph)
    root_id = opts.node_id or handle.root_node_id

    lines = [
        (
            f"run={handle.run_id}  nodes={len(graph.nodes)}  "
            f"transitions={len(graph.transitions)}  edges={len(graph.edges)}"
        ),
        "",
    ]
    visited_nodes: set[str] = set()
    visited_transitions: set[str] = set()

    def emit_node(node_id: str, prefix: str, is_last: bool, depth: int) -> None:
        cut = " ✂" if node_id in inactive_nodes else ""
        connector = "" if depth == 0 else ("└─" if is_last else "├─")
        if node_id in visited_nodes:
            lines.append(f"{prefix}{connector}↻ {node_id}{cut}")
            return
        visited_nodes.add(node_id)
        lines.append(f"{prefix}{connector}{node_id}{cut}")
        note = _node_note(graph, node_id)
        child_prefix = prefix + ("  " if depth == 0 or is_last else "│ ")
        if note:
            lines.append(f"{child_prefix}note: {_truncate(note, 80)}")
        if opts.depth is not None and depth >= opts.depth:
            return
        transition_ids = graph.transitions_from_node(node_id)
        for index, transition_id in enumerate(transition_ids):
            emit_transition(
                transition_id,
                child_prefix,
                index == len(transition_ids) - 1,
                depth + 1,
            )

    def emit_transition(transition_id: str, prefix: str, is_last: bool, depth: int) -> None:
        marker, summary = _transition_summary(graph, transition_id, opts.full_payloads)
        cut = " ✂" if transition_id in inactive_transitions else ""
        connector = "└─" if is_last else "├─"
        if transition_id in visited_transitions:
            lines.append(f"{prefix}{connector}↻ {transition_id}{cut}")
            return
        visited_transitions.add(transition_id)
        lines.append(f"{prefix}{connector}{marker} {transition_id}{cut}  {summary}")
        child_prefix = prefix + ("  " if is_last else "│ ")
        output_ids = graph.transition_outputs(transition_id)
        for index, node_id in enumerate(output_ids):
            emit_node(node_id, child_prefix, index == len(output_ids) - 1, depth + 1)

    emit_node(root_id, "", True, 0)
    return "\n".join(lines)


def render_mermaid(handle: RunHandle, opts: DumpOptions) -> str:
    graph = handle.run_graph
    inactive_nodes = inactive_node_ids(graph)
    inactive_transitions = inactive_transition_ids(graph)
    lines = ["```mermaid", "flowchart TD"]
    for node_id in graph.nodes:
        label = "State"
        note = _node_note(graph, node_id)
        if note:
            label = _truncate(note, 36).replace('"', "'")
        lines.append(f'  {node_id}["{label}"]')
    for transition_id in graph.transitions:
        _, summary = _transition_summary(graph, transition_id, False)
        summary = _truncate(summary, 42).replace('"', "'")
        lines.append(f'  {transition_id}{{"{summary}"}}')
    for edge in graph.edges.values():
        lines.append(f"  {edge.from_id} --> {edge.to_id}")
    if inactive_nodes:
        lines.append(f"  class {','.join(sorted(inactive_nodes))} cut")
    if inactive_transitions:
        lines.append(f"  class {','.join(sorted(inactive_transitions))} cut")
    lines.append("  classDef cut stroke:#999,stroke-dasharray: 4 4,color:#999")
    lines.append("```")
    return "\n".join(lines)


def dump(handle: RunHandle, fmt: str, opts: DumpOptions) -> str:
    if fmt == "outline":
        return render_outline(handle, opts)
    if fmt == "mermaid":
        return render_mermaid(handle, opts)
    raise ValueError(f"unknown dump format: {fmt!r}")
