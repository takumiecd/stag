#!/usr/bin/env python3
"""End-to-end test: CodeOptimizer with real OpenCode backend."""

import tempfile
from pathlib import Path

from optagent.v2.domains.code.optimizer import CodeOptimizer
from optagent.v2.domains.code.backends import OpenCodeBackendAdapter

# Create a test file
work_dir = Path(tempfile.mkdtemp(prefix="optagent_e2e_"))
source = work_dir / "slow_sum.py"
source.write_text("""\
def slow_sum(n):
    \"\"\"Sum from 0 to n-1 using a loop.\"\"\"
    s = 0
    for i in range(n):
        s += i
    return s


def test_slow_sum():
    assert slow_sum(10) == 45
    assert slow_sum(100) == 4950
""")

print(f"Working dir: {work_dir}")
print(f"Source file: {source}")

backend = OpenCodeBackendAdapter(
    command="/home/ware10sai/.opencode/bin/opencode",
    timeout=300.0,
)
opt = CodeOptimizer(
    source_path=source,
    backend=backend,
    work_dir=work_dir,
)

print("Starting optimization...")
try:
    result = opt.optimize(objective="minimize latency", max_rounds=3)
    print("Optimization completed!")
    print(f"\nFinal code:\n{result.code.content}")
    print(f"\nTest results: {result.code.test_results}")
    print(f"\nBenchmark: {result.code.benchmark_results}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
