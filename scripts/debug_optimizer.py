#!/usr/bin/env python3
"""Debug test: trace CodeOptimizer step by step."""

import tempfile
from pathlib import Path

from optagent.v2.domains.code.optimizer import CodeOptimizer
from optagent.v2.domains.code.backends import OpenCodeBackendAdapter

work_dir = Path(tempfile.mkdtemp(prefix="optagent_debug_"))
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

print(f"Initial code:\n{source.read_text()}")

backend = OpenCodeBackendAdapter(
    command="/home/ware10sai/.opencode/bin/opencode",
    timeout=300.0,
)
opt = CodeOptimizer(
    source_path=source,
    backend=backend,
    work_dir=work_dir,
)

print("\n=== Starting optimization ===")
try:
    result = opt.optimize(objective="minimize latency", max_rounds=1)
    print(f"\nFinal code:\n{result.code.content}")
    print(f"Test results: {result.code.test_results}")
    print(f"Benchmark: {result.code.benchmark_results}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
