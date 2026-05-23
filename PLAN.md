# PLAN.md

## Current Branch Handoff: Sync ID Simplification

Branch: `feature/local-sync-store`

This branch currently includes:

- `anchor` support already merged into `main`.
- `git attach --output-transition <ot> --commit <sha> ...` already merged into `main`.
- File-backed local/shared DAG sync prototype on this branch:
  - `src/stag/core/sync/local.py`
  - `src/stag/core/sync/records.py`
  - `src/stag/core/sync/idmap.py`
  - `src/stag/core/sync/shared_store.py`
  - `src/stag/cli/commands/sync.py`
- Opaque graph record IDs:
  - `RunHandle._next_id(prefix)` now returns `opaque_id(prefix)`.
  - Root node is no longer `n_0000`; it is stored in `RunGraph.metadata["root_node_id"]`.
  - `run_init_command()` returns `{"run_id": ..., "root_node_id": ...}`.
- Tests passed after the opaque ID changes:
  - `PYTHONPATH=src pytest`
  - 217 passed.

## Design Decision

Sync should use a Git-like object identity model.

- Every graph record ID is already globally unique enough for practical use.
- The same ID should be used in local and remote stores.
- Sync should push and pull records without ID translation.
- `idmap.jsonl`, `shared_id`, and `global_id` are no longer part of the intended design.
- Remote records should identify records by the same ID already present in their body.

Git analogy:

- Git commits keep the same hash locally and remotely.
- STAG records should similarly keep the same opaque ID locally and remotely.
- Collision probability for UUID-backed opaque IDs is negligible for this project.

## Next Task

Remove the now-unnecessary sync ID mapping layer.

Concrete steps:

1. Delete `src/stag/core/sync/idmap.py`.
2. Remove `idmap.jsonl` reads/writes from `src/stag/core/sync/local.py`.
3. Remove `shared_id` from sync record envelopes.
4. In remote `records.jsonl`, each record should look roughly like:

   ```json
   {
     "record_kind": "node",
     "record_id": "n_<uuid>",
     "body": {
       "node_id": "n_<uuid>",
       "metadata": {}
     }
   }
   ```

   For each kind:

   - node: `record_id == body["node_id"]`
   - input_transition: `record_id == body["input_transition_id"]`
   - output_transition: `record_id == body["output_transition_id"]`
   - payload: `record_id == body["payload_id"]`
   - view: `record_id == body["view_id"]`

5. Keep batch envelopes:

   ```json
   {
     "seq": 1,
     "batch_id": "batch_<uuid>",
     "operation": "anchor",
     "records": [ ... ],
     "actor": { ... },
     "origin": { ... },
     "created_at": "..."
   }
   ```

6. Update `src/stag/core/sync/records.py`:
   - Rename helper names toward `record_id`.
   - `flatten_batches()` should expose `record_id`, not `shared_id`.
   - Backward compatibility for old `shared_id` is not required unless it is trivial.

7. Update `tests/cli/test_sync.py`:
   - Remove assertions for `idmap.jsonl`.
   - Assert each remote record has `record_id`.
   - Assert no remote record has `shared_id`.
   - Keep the local A -> shared -> local B round-trip.

8. Run:

   ```bash
   PYTHONPATH=src pytest
   ```

9. Commit this as a focused change, for example:

   ```bash
   git commit -m "Simplify sync record identity"
   ```

## Constraints

- Do not reintroduce sequential IDs.
- Do not add a compatibility shim for `n_0000` or old sequential IDs.
- Keep sync file-backed and local-only for now; do not add HTTP/Postgres yet.
- Keep `SharedRunStore` as the backend boundary.
- Prefer small commits. The current branch already has multiple focused commits, so continue that style.
