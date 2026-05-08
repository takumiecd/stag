#!/usr/bin/env bash
# Basic CLI loop example for optagent 0.1 alpha.
#
# Demonstrates:
#   init -> plan -> observe -> derive -> trace -> extend -> predict -> refresh -> show -> list

set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=src

RUN_ID="demo_loop"
STORE_DIR="${STORE_DIR:-/tmp/optagent_demo_runs}"

rm -rf "$STORE_DIR/$RUN_ID"

echo "=== 1. init ==="
python3 -m optagent.cli.main init \
  "req_optimize_kernel" \
  --target-type "kernel" \
  --target-id "matmul_v1" \
  --run-id "$RUN_ID" \
  --store-dir "$STORE_DIR"

echo ""
echo "=== 2. plan on observed root ==="
PLAN_RESULT=$(python3 -m optagent.cli.main plan \
  --from-node n_0000 \
  --planner default \
  --max-plans 1 \
  --intent "run baseline benchmark" \
  --store-dir "$STORE_DIR")
echo "$PLAN_RESULT"
PLAN_ID=$(echo "$PLAN_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['plan_id'])")

echo ""
echo "=== 3. observe result ==="
OBS_RESULT=$(python3 -m optagent.cli.main observe \
  --plan "$PLAN_ID" \
  --status completed \
  --artifact "build.log" \
  --raw-output "benchmark.txt" \
  --log "stderr.log" \
  --metric "speedup=1.15" \
  --store-dir "$STORE_DIR")
echo "$OBS_RESULT"
OBS_NODE_ID=$(echo "$OBS_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['to_node_id'])")
OBS_TRANSITION_ID=$(echo "$OBS_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['transition_id'])")

echo ""
echo "=== 4. derive finding ==="
python3 -m optagent.cli.main derive "$OBS_TRANSITION_ID" \
  --type finding \
  --text "baseline run completed with speedup metric" \
  --store-dir "$STORE_DIR"

echo ""
echo "=== 5. trace ==="
python3 -m optagent.cli.main trace \
  --from-node "$OBS_NODE_ID" \
  --store-dir "$STORE_DIR"

echo ""
echo "=== 6. extend predicted root ==="
PPLAN_RESULT=$(python3 -m optagent.cli.main extend \
  --node-id n_0001 \
  --intent "predict likely benchmark outcomes" \
  --store-dir "$STORE_DIR")
echo "$PPLAN_RESULT"
PPLAN_ID=$(echo "$PPLAN_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['plan_id'])")

echo ""
echo "=== 7. predict ==="
python3 -m optagent.cli.main predict \
  "$PPLAN_ID" \
  --max-outcomes 2 \
  --store-dir "$STORE_DIR"

echo ""
echo "=== 8. refresh predicted dag ==="
python3 -m optagent.cli.main refresh \
  --from-node "$OBS_NODE_ID" \
  --store-dir "$STORE_DIR"

echo ""
echo "=== 9. show run ==="
python3 -m optagent.cli.main show \
  --store-dir "$STORE_DIR"

echo ""
echo "=== 10. list ==="
python3 -m optagent.cli.main list \
  --store-dir "$STORE_DIR"

echo ""
echo "Done. Run directory: $STORE_DIR/$RUN_ID"
