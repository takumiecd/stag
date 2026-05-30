#!/usr/bin/env bash
# Example: Benchmark-driven optimization with ARCTX
#
# This script demonstrates how ARCTX records the reasoning history
# behind a performance optimization: try variant A, measure, cut it,
# try variant B, measure — the whole story stays in the graph.
#
# Run inside a git repository with arctx-cli installed.

set -e

# Clean up any previous run
rm -rf .arctx-id
rm -rf /tmp/arctx-bench-demo

# 1. Initialize the run
arctx init optimize --extension git --run-id bench-demo

# 2. Baseline — a naive implementation
cat > work.py <<'PY'
def sum_list(data):
    total = 0
    for x in data:
        total += x
    return total
PY
git add work.py && arctx git commit -m "baseline: naive loop"

# 3. Hypothesis A — add a cache layer (spoiler: it gets slower)
git checkout -b feat/cache
cat > work.py <<'PY'
_cache = {}

def sum_list(data):
    key = id(data)
    if key in _cache:
        return _cache[key]
    total = 0
    for x in data:
        total += x
    _cache[key] = total
    return total
PY
git add work.py && arctx git commit -m "hypothesis A: add cache layer"

# Attach benchmark result — slower than baseline
LATEST_T=$(arctx show --latest transition | grep transition_id | awk '{print $2}')
arctx payload add --target "transition:${LATEST_T}" \
  --payload-type benchmark \
  --field elapsed_ms=1200 \
  --field note="slower than baseline — cache overhead dominates"

# 4. Cut hypothesis A — it stays in the graph, just marked inactive
arctx cut transition "${LATEST_T}"

# 5. Hypothesis B — vectorize with built-in sum (faster!)
git checkout main && git checkout -b feat/vectorize
cat > work.py <<'PY'
def sum_list(data):
    return sum(data)
PY
git add work.py && arctx git commit -m "hypothesis B: use built-in sum"

# Attach benchmark result — much faster
LATEST_T=$(arctx show --latest transition | grep transition_id | awk '{print $2}')
arctx payload add --target "transition:${LATEST_T}" \
  --payload-type benchmark \
  --field elapsed_ms=180 \
  --field note="5x faster than baseline"

# 6. Show the story

echo ""
echo "=== The graph tells the whole story ==="
arctx graph dump --format outline --run bench-demo

echo ""
echo "=== Or as Mermaid ==="
arctx graph dump --format mermaid --run bench-demo
