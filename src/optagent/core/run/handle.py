"""Run handle definition and initialization."""

from __future__ import annotations

from dataclasses import dataclass, field

from optagent.core.cuts import is_cut_node
from optagent.core.dag import Dag
from optagent.core.ids import sequential_id, slugify, timestamp_id
from optagent.core.schema.graph import Node
from optagent.core.schema.payloads import SnapshotPayload
from optagent.core.schema.requirements import Requirement
from optagent.core.schema.selections import PredictionSelection
from optagent.core.schema.snapshots import StateSnapshot


@dataclass
class RunHandle:
    """In-memory handle for one optimization/problem-solving run."""

    run_id: str
    requirement: Requirement
    observed_dag: Dag
    predicted_dag: Dag
    selections: dict[str, PredictionSelection] = field(default_factory=dict)
    _counters: dict[str, int] = field(default_factory=dict)

    def _next_id(self, prefix: str) -> str:
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return sequential_id(prefix, self._counters[prefix])

    @property
    def root_observed_node_id(self) -> str:
        roots = self.observed_dag.roots()
        if len(roots) != 1:
            raise KeyError(f"expected exactly one observed root, got {roots}")
        return roots[0]

    def _ensure_active_observed_node(self, node_id: str) -> None:
        """Reject node IDs that are unknown or sit inside a cut subtree."""
        if node_id not in self.observed_dag.nodes:
            raise KeyError(f"unknown observed node_id: {node_id}")
        if is_cut_node(self.observed_dag, node_id):
            raise ValueError(
                f"node is in a cut branch: {node_id}; "
                "rewind cut this subtree, so no new plans/observations can extend it"
            )

    def save(self, store) -> object:
        return store.save_run(self)


def init(requirement: Requirement, *, run_id: str | None = None) -> RunHandle:
    """Create a new in-memory run with seeded observed/predicted Dags."""

    rid = run_id or timestamp_id(f"run_{slugify(requirement.requirement_id)}")
    initial_snapshot = StateSnapshot(requirement=requirement)

    observed_dag = Dag(dag_id=f"{rid}_observed", metadata={"role": "observed"})
    predicted_dag = Dag(
        dag_id=f"{rid}_predicted",
        metadata={"role": "predicted"},
    )

    obs_root = Node(node_id="n_0000")
    observed_dag.add_node(obs_root)
    observed_dag.attach_payload(
        SnapshotPayload(
            payload_id="pl_0000",
            target_id=obs_root.node_id,
            snapshot=initial_snapshot,
            snapshot_hash=initial_snapshot.compute_hash(),
        )
    )

    pred_root = Node(node_id="n_0001")
    predicted_dag.add_node(pred_root)
    predicted_dag.attach_payload(
        SnapshotPayload(
            payload_id="pl_0001",
            target_id=pred_root.node_id,
            snapshot=initial_snapshot,
            snapshot_hash=initial_snapshot.compute_hash(),
            metadata={"anchor_node_id": obs_root.node_id},
        )
    )
    predicted_dag.metadata["anchor_node_id"] = obs_root.node_id
    predicted_dag.metadata["root_node_id"] = pred_root.node_id

    observed_dag.add_child_dag(predicted_dag)

    return RunHandle(
        run_id=rid,
        requirement=requirement,
        observed_dag=observed_dag,
        predicted_dag=predicted_dag,
        _counters={
            "n": 1,
            "t": 0,
            "plan": 0,
            "dag": 0,
            "pl": 1,
            "sel": 0,
            "promotion": 0,
        },
    )


# Bind verb implementations.
from optagent.core.run.helpers import (  # noqa: E402
    find_plan_impl as _find_plan,
    get_node_snapshot_payload_impl as _get_node_snapshot_payload,
    new_node_with_snapshot_impl as _new_node_with_snapshot,
    plan_grounding_dag_impl as _plan_grounding_dag,
)
from optagent.core.run.observe import observe_impl as _observe_impl  # noqa: E402
from optagent.core.run.plan import (  # noqa: E402
    extend_impl as _extend_impl,
    plan_impl as _plan_impl,
)
from optagent.core.run.predict import (  # noqa: E402
    predict_impl as _predict_impl,
    select_prediction_impl as _select_prediction_impl,
)
from optagent.core.run.promote import (  # noqa: E402
    _append_observed_transition as _append_observed_transition_impl,
    promote_impl as _promote_impl,
)
from optagent.core.run.trace import refresh_impl as _refresh_impl, trace_impl as _trace_impl  # noqa: E402
from optagent.core.run.derive import derive_impl as _derive_impl  # noqa: E402
from optagent.core.run.rewind import rewind_impl as _rewind_impl  # noqa: E402
from optagent.core.run.snapshot import snapshot_rebuild_impl as _snapshot_rebuild_impl  # noqa: E402
from optagent.core.run.state_impl import (  # noqa: E402
    state_show_impl as _state_show_impl,
    state_update_impl as _state_update_impl,
)

RunHandle._find_plan = _find_plan
RunHandle._plan_grounding_dag = _plan_grounding_dag
RunHandle._get_node_snapshot_payload = _get_node_snapshot_payload
RunHandle._new_node_with_snapshot = _new_node_with_snapshot
RunHandle._append_observed_transition = _append_observed_transition_impl
RunHandle.plan = _plan_impl
RunHandle.extend = _extend_impl
RunHandle.predict = _predict_impl
RunHandle.select_prediction = _select_prediction_impl
RunHandle.promote = _promote_impl
RunHandle.observe = _observe_impl
RunHandle.result = _observe_impl
RunHandle.trace = _trace_impl
RunHandle.history = _trace_impl
RunHandle.refresh = _refresh_impl
RunHandle.derive = _derive_impl
RunHandle.rewind = _rewind_impl
RunHandle.state_show = _state_show_impl
RunHandle.state_update = _state_update_impl
RunHandle.snapshot_rebuild = _snapshot_rebuild_impl
