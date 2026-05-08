"""JSONL run-directory storage."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from optagent.core.dag import Dag
from optagent.core.run import RunHandle
from optagent.core.schema.graph import Node, Transition
from optagent.core.schema.payloads import payload_from_dict
from optagent.core.schema.plans import Plan
from optagent.core.schema.requirements import Requirement
from optagent.core.schema.selections import PredictionSelection


class JsonlRunStore:
    """Store a run as a directory of JSON and JSONL files."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def run_path(self, run_id: str) -> Path:
        return self.root / run_id

    def list_runs(self) -> list[dict]:
        if not self.root.exists():
            return []
        runs: list[dict] = []
        for entry in sorted(self.root.iterdir()):
            if not entry.is_dir():
                continue
            run_json = entry / "run.json"
            if not run_json.exists():
                continue
            try:
                data = json.loads(run_json.read_text(encoding="utf-8"))
                runs.append(
                    {
                        "run_id": data["run_id"],
                        "requirement_id": data["requirement"]["requirement_id"],
                        "target_type": data["requirement"]["target_type"],
                        "target_id": data["requirement"]["target_id"],
                    }
                )
            except (KeyError, json.JSONDecodeError):
                continue
        return runs

    def save_run(self, run: RunHandle) -> Path:
        run_path = self.run_path(run.run_id)
        run_path.mkdir(parents=True, exist_ok=True)

        self._write_json(
            run_path / "run.json",
            {
                "run_id": run.run_id,
                "requirement": run.requirement.to_dict(),
                "counters": dict(run._counters),
                "observed_dag_id": run.observed_dag.dag_id,
                "predicted_dag_id": run.predicted_dag.dag_id,
            },
        )
        all_dags = list(_walk_dags(run.observed_dag))
        self._write_jsonl(
            run_path / "dags.jsonl",
            (
                {
                    "dag_id": dag.dag_id,
                    "parent_dag_id": parent_id,
                    "metadata": dict(dag.metadata),
                }
                for dag, parent_id in all_dags
            ),
        )
        self._write_jsonl(
            run_path / "nodes.jsonl",
            (
                {"dag_id": dag.dag_id, "record": node.to_dict()}
                for dag, _ in all_dags
                for node in dag.nodes.values()
            ),
        )
        self._write_jsonl(
            run_path / "plans.jsonl",
            (
                {"dag_id": dag.dag_id, "record": plan.to_dict()}
                for dag, _ in all_dags
                for plan in dag.plans.values()
            ),
        )
        self._write_jsonl(
            run_path / "transitions.jsonl",
            (
                {"dag_id": dag.dag_id, "record": tr.to_dict()}
                for dag, _ in all_dags
                for tr in dag.transitions.values()
            ),
        )
        self._write_jsonl(
            run_path / "payloads.jsonl",
            (
                {"dag_id": dag.dag_id, "record": payload.to_dict()}
                for dag, _ in all_dags
                for payload in dag.payloads.values()
            ),
        )
        self._write_jsonl(
            run_path / "selections.jsonl",
            (sel.to_dict() for sel in run.selections.values()),
        )
        return run_path

    def load_run(self, run_id: str) -> RunHandle:
        run_path = self.run_path(run_id)
        manifest = self._read_json(run_path / "run.json")
        requirement = _requirement_from_dict(manifest["requirement"])

        # Build all Dags first.
        dags: dict[str, Dag] = {}
        parent_of: dict[str, str | None] = {}
        for row in self._read_jsonl(run_path / "dags.jsonl"):
            dag = Dag(dag_id=row["dag_id"], metadata=dict(row.get("metadata") or {}))
            dags[dag.dag_id] = dag
            parent_of[dag.dag_id] = row.get("parent_dag_id")

        # Wire child relationships.
        for dag_id, parent_id in parent_of.items():
            if parent_id is not None and parent_id in dags:
                dags[parent_id].child_dags[dag_id] = dags[dag_id]

        # Nodes.
        for row in self._read_jsonl(run_path / "nodes.jsonl"):
            node = _node_from_dict(row["record"])
            dags[row["dag_id"]].add_node(node)

        # Plans (need nodes).
        for row in self._read_jsonl(run_path / "plans.jsonl"):
            plan = _plan_from_dict(row["record"])
            dags[row["dag_id"]].add_plan(plan)

        # Transitions (need nodes + plans). Use raw add (skip cardinality
        # checks that the writer would otherwise enforce — load is replay).
        for row in self._read_jsonl(run_path / "transitions.jsonl"):
            tr = _transition_from_dict(row["record"])
            dag = dags[row["dag_id"]]
            dag.transitions[tr.transition_id] = tr
            dag.transitions_by_plan.setdefault(tr.parent_plan_id, []).append(tr.transition_id)
            dag.outgoing_index.setdefault(tr.from_node_id, []).append(tr.transition_id)
            dag.incoming_index.setdefault(tr.to_node_id, []).append(tr.transition_id)

        # Payloads.
        for row in self._read_jsonl(run_path / "payloads.jsonl"):
            payload = payload_from_dict(row["record"])
            dag = dags[row["dag_id"]]
            dag.payloads[payload.payload_id] = payload
            dag.payloads_by_target.setdefault(payload.target_id, []).append(payload.payload_id)

        # Selections.
        selections: dict[str, PredictionSelection] = {}
        for row in self._read_jsonl(run_path / "selections.jsonl"):
            sel = _selection_from_dict(row)
            selections[sel.selection_id] = sel

        observed_dag = dags[manifest["observed_dag_id"]]
        predicted_dag = dags[manifest["predicted_dag_id"]]
        return RunHandle(
            run_id=manifest["run_id"],
            requirement=requirement,
            observed_dag=observed_dag,
            predicted_dag=predicted_dag,
            selections=selections,
            _counters={str(k): int(v) for k, v in manifest.get("counters", {}).items()},
        )

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _write_jsonl(path: Path, rows) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _walk_dags(dag: Dag, parent_id: str | None = None):
    yield dag, parent_id
    for child in dag.child_dags.values():
        yield from _walk_dags(child, dag.dag_id)


def _pick_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
    names = {field.name for field in fields(cls) if field.init}
    return {name: data[name] for name in names if name in data}


def _tuple(value: Any) -> tuple:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return (value,)


def _requirement_from_dict(data: dict[str, Any]) -> Requirement:
    return Requirement(
        requirement_id=data["requirement_id"],
        target_type=data["target_type"],
        target_id=data["target_id"],
        objective=dict(data.get("objective") or {}),
        constraints=dict(data.get("constraints") or {}),
        metadata=dict(data.get("metadata") or {}),
    )


def _node_from_dict(data: dict[str, Any]) -> Node:
    return Node(
        node_id=data["node_id"],
        metadata=dict(data.get("metadata") or {}),
    )


def _transition_from_dict(data: dict[str, Any]) -> Transition:
    return Transition(
        transition_id=data["transition_id"],
        parent_plan_id=data["parent_plan_id"],
        from_node_id=data["from_node_id"],
        to_node_id=data["to_node_id"],
        metadata=dict(data.get("metadata") or {}),
    )


def _plan_from_dict(data: dict[str, Any]) -> Plan:
    return Plan(
        plan_id=data["plan_id"],
        grounded_node_id=data["grounded_node_id"],
        action_type=data["action_type"],
        intent=data["intent"],
        inputs=dict(data.get("inputs") or {}),
        safety_policy=dict(data.get("safety_policy") or {}),
        assumptions=_tuple(data.get("assumptions")),
        confidence=data.get("confidence"),
        status=data.get("status", "active"),
        metadata=dict(data.get("metadata") or {}),
    )


def _selection_from_dict(data: dict[str, Any]) -> PredictionSelection:
    return PredictionSelection(
        selection_id=data["selection_id"],
        selected_transition_ids=_tuple(data.get("selected_transition_ids")),
        selected_path_id=data.get("selected_path_id"),
        reason=data.get("reason", ""),
        metadata=dict(data.get("metadata") or {}),
    )
