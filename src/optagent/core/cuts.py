"""Read-time replay of CutPayloads to compute cut/inactive sets.

A Dag does not track activity in its own state; it merely accumulates
``CutPayload`` records attached to transitions. Whether a node or
transition is "active" is computed by replaying those payloads here.
"""

from __future__ import annotations

from optagent.core.dag import Dag
from optagent.core.schema.payloads import CutPayload


def cut_payloads(dag: Dag) -> list[CutPayload]:
    """All CutPayloads currently attached to transitions in *dag*."""
    return [p for p in dag.payloads.values() if isinstance(p, CutPayload)]


def cut_transition_ids(dag: Dag) -> set[str]:
    """Transitions that have been directly cut (cut boundary)."""
    return {p.target_id for p in cut_payloads(dag)}


def is_cut_transition(dag: Dag, transition_id: str) -> bool:
    return transition_id in cut_transition_ids(dag)


def cut_node_ids(dag: Dag) -> set[str]:
    """All node_ids reachable forward from any cut transition.

    These nodes lie on a branch that has been rewound away, so they
    are no longer reachable from the active root via any active edge.
    """
    cut_tids = cut_transition_ids(dag)
    if not cut_tids:
        return set()
    cut_nodes: set[str] = set()
    frontier = [dag.transitions[tid].to_node_id for tid in cut_tids if tid in dag.transitions]
    while frontier:
        nid = frontier.pop()
        if nid in cut_nodes:
            continue
        cut_nodes.add(nid)
        for tid in dag.outgoing_index.get(nid, ()):
            frontier.append(dag.transitions[tid].to_node_id)
    return cut_nodes


def is_cut_node(dag: Dag, node_id: str) -> bool:
    return node_id in cut_node_ids(dag)


def inactive_transition_ids(dag: Dag) -> set[str]:
    """Every transition that is no longer on an active branch.

    Union of:
      - directly cut transitions
      - transitions that originate from a node inside a cut subtree
    """
    inactive = set(cut_transition_ids(dag))
    for nid in cut_node_ids(dag):
        inactive.update(dag.outgoing_index.get(nid, ()))
    return inactive


def is_inactive_transition(dag: Dag, transition_id: str) -> bool:
    return transition_id in inactive_transition_ids(dag)
