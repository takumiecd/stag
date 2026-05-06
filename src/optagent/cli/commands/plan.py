"""optagent CLI plan command."""

from __future__ import annotations

from optagent.storage.jsonl import JsonlRunStore


def run_plan_command(
    *,
    run_id: str,
    planner: str,
    max_plans: int,
    store_dir: str,
) -> dict:
    """Create plans from the current observed state of an existing run.

    Parameters
    ----------
    run_id:
        Identifier of the run to plan against.
    planner:
        Name of the planner to use.
    max_plans:
        Maximum number of plans to create.
    store_dir:
        Directory where runs are stored.

    Returns
    -------
    dict with ``plans`` key containing a list of plan dicts.

    Raises
    ------
    KeyError
        If the run_id does not exist in the store.
    """
    store = JsonlRunStore(store_dir)
    run_path = store.run_path(run_id)
    if not run_path.exists():
        raise KeyError(f"unknown run_id: {run_id}")
    handle = store.load_run(run_id)

    plans = handle.plan(
        state_id=handle.current_observed_state_id,
        planner=planner,
        max_plans=max_plans,
    )

    store.save_run(handle)
    return {"plans": [plan.to_dict() for plan in plans]}


def cli_plan(args) -> int:
    """Entry point for ``optagent plan`` subcommand.

    Prints the created plans as JSON to stdout.
    """
    import json

    result = run_plan_command(
        run_id=args.run_id,
        planner=args.planner,
        max_plans=args.max_plans,
        store_dir=args.store_dir,
    )
    print(json.dumps(result["plans"], ensure_ascii=False, indent=2))
    return 0
