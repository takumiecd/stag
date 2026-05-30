#!/usr/bin/env bash
# Example: Debugging trace with ARCTX
#
# This script demonstrates how ARCTX records every hypothesis while
# chasing a bug, so you can walk the trace backwards once you find
# the root cause.
#
# Run inside a git repository with arctx-cli installed.

set -e

# Clean up any previous run
rm -rf .arctx-id
rm -rf /tmp/arctx-debug-demo

# 1. Initialize the run
arctx init debug --extension git --run-id bug-42-demo

# 2. Reproduction script
cat > repro.py <<'PY'
def process(items):
    result = []
    for i in range(len(items)):
        result.append(items[i] * 2)
    return result

# Bug: should be i + 1, not i
PY
git add repro.py && arctx git commit -m "reproduction script: demonstrates off-by-one"

# 3. Hypothesis 1: race condition in cache (wrong — still flaky)
git checkout -b try/race-fix
cat > repro.py <<'PY'
import threading
_lock = threading.Lock()

def process(items):
    with _lock:
        result = []
        for i in range(len(items)):
            result.append(items[i] * 2)
        return result
PY
git add repro.py && arctx git commit -m "hypothesis: add lock around cache"

LATEST_T=$(arctx show --latest transition | grep transition_id | awk '{print $2}')
arctx payload add --target "transition:${LATEST_T}" \
  --payload-type observation \
  --field result="still flaky — lock didn't help"

# 4. Hypothesis 2: off-by-one in loop bound (correct!)
git checkout main && git checkout -b try/index-fix
cat > repro.py <<'PY'
def process(items):
    result = []
    for i in range(len(items) - 1):  # Bug fix: off-by-one
        result.append(items[i] * 2)
    return result
PY
git add repro.py && arctx git commit -m "fix: correct loop bound"

LATEST_T=$(arctx show --latest transition | grep transition_id | awk '{print $2}')
arctx payload add --target "transition:${LATEST_T}" \
  --payload-type observation \
  --field result="bug gone — 3 consecutive green runs"

# 5. Show the trace

echo ""
echo "=== The debugging trace ==="
arctx graph dump --format outline --run bug-42-demo

echo ""
echo "=== Walk backwards from the fix ==="
LATEST_NODE=$(arctx show --latest node | grep node_id | awk '{print $2}')
arctx trace "${LATEST_NODE}" --run bug-42-demo
