"""stag CLI plan command."""

from __future__ import annotations

import argparse
import json

from stag.cli.context import (
    resolve_run_id_from_args,
    resolve_store,
    resolve_user_id_from_args,
    resolve_work_session_id_from_args,
)
from stag.core.append import AppendBatch, GraphRecordEnvelope
from stag.core.schema.payloads import PlanPayload


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "plan", help="Create an InputTransition from one or more nodes"
    )
    parser.add_argument("--run", default=None)
    parser.add_argument(
        "--input-node", action="append", required=True, dest="input_nodes",
        metavar="NODE_ID", help="Input node (repeatable for multi-node plans)"
    )
    parser.add_argument("--action-type", default="analysis")
    parser.add_argument("--intent", default="inspect state and propose next action")
    parser.add_argument("--input", action="append", metavar="KEY=VALUE")
    parser.add_argument("--assumption", action="append", metavar="TEXT")
    parser.add_argument("--store-dir", default=".stag/runs")
    parser.add_argument("--user", default=None)
    parser.add_argument("--work-session", default=None)
    return parser


def _parse_kv(items: list[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"expected key=value format: {item!r}")
        k, v = item.split("=", 1)
        result[k] = v
    return result


def run_plan_command(
    *,
    run_id: str,
    input_node_ids: list[str],
    action_type: str,
    intent: str,
    inputs: dict | None = None,
    assumptions: list[str] | None = None,
    store_dir: str,
    user_id: str | None = None,
    work_session_id: str | None = None,
) -> dict:
    store = resolve_store(store_dir)
    if not store.run_path(run_id).exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)
    payload = PlanPayload(
        payload_id="pending",
        target_id="pending",
        intent=intent,
        action_type=action_type,  # type: ignore[arg-type]
        inputs=dict(inputs or {}),
        assumptions=tuple(assumptions or []),
    )
    before_input_transition_ids = set(handle.run_graph.input_transitions)
    before_payload_ids = set(handle.run_graph.payloads)

    it = handle.plan(input_node_ids, payload, user_id=user_id, work_session_id=work_session_id)
    if user_id is not None and work_session_id is not None and hasattr(store, "append_batch"):
        batch = _build_plan_append_batch(
            handle,
            user_id=user_id,
            work_session_id=work_session_id,
            before_input_transition_ids=before_input_transition_ids,
            before_payload_ids=before_payload_ids,
        )
        store.append_batch(batch)
    else:
        store.save_run(handle)
    return {"input_transition": it.to_dict()}


def _build_plan_append_batch(
    handle,
    *,
    user_id: str,
    work_session_id: str,
    before_input_transition_ids: set[str],
    before_payload_ids: set[str],
) -> AppendBatch:
    new_it_ids = set(handle.run_graph.input_transitions) - before_input_transition_ids
    new_payload_ids = set(handle.run_graph.payloads) - before_payload_ids
    if len(new_it_ids) != 1:
        raise RuntimeError(f"expected one new input transition, got {len(new_it_ids)}")
    if len(new_payload_ids) != 1:
        raise RuntimeError(f"expected one new plan payload, got {len(new_payload_ids)}")
    if not handle.run_graph.work_events:
        raise RuntimeError("plan append batch requires a work event")
    event = handle.run_graph.work_events[-1]
    session = handle.run_graph.work_sessions[work_session_id]
    it_id = next(iter(new_it_ids))
    payload_id = next(iter(new_payload_ids))
    it = handle.run_graph.input_transitions[it_id]
    payload = handle.run_graph.payloads[payload_id]
    return AppendBatch(
        run_id=handle.run_id,
        user_id=user_id,
        work_session_id=work_session_id,
        work_session=session,
        event=event,
        records=(
            GraphRecordEnvelope("input_transition", it.input_transition_id, it),
            GraphRecordEnvelope("payload", payload.payload_id, payload),
        ),
    )


def cli_plan(args) -> int:
    inputs = _parse_kv(getattr(args, "input", None))
    result = run_plan_command(
        run_id=resolve_run_id_from_args(args),
        input_node_ids=args.input_nodes,
        action_type=args.action_type,
        intent=args.intent,
        inputs=inputs,
        assumptions=getattr(args, "assumption", None) or [],
        store_dir=args.store_dir,
        user_id=resolve_user_id_from_args(args),
        work_session_id=resolve_work_session_id_from_args(args),
    )
    print(json.dumps(result["input_transition"], ensure_ascii=False, indent=2))
    return 0
