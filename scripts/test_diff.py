#!/usr/bin/env python3
"""Debug test: check diff application."""

import tempfile
from pathlib import Path

from optagent.v2.domains.code.executor import CodeExecutor
from optagent.v2.domains.code.state import CodeState, CodeArtifact
from optagent.v2.domains.code.action import EditCode

# Create a test file
work_dir = Path(tempfile.mkdtemp(prefix="optagent_debug_"))
source = work_dir / "slow_sum.py"
source.write_text("""\
def slow_sum(n):
    \"\"\"Sum from 0 to n-1 using a loop.\"\"\"
    s = 0
    for i in range(n):
        s += i
    return s
""")

print(f"Source:\n{source.read_text()}")

# Diff from OpenCode
diff = """--- a/slow_sum.py
+++ b/slow_sum.py
@@ -1,6 +1,4 @@
 def slow_sum(n):
     \"\"\"Sum from 0 to n-1 using a loop.\"\"\"
-    s = 0
-    for i in range(n):
-        s += i
-    return s
+    # O(1) arithmetic series formula.
+    return n * (n - 1) // 2
"""

state = CodeState(
    requirement={},
    code=CodeArtifact(
        artifact_id="test",
        source_path=source,
        content=source.read_text(),
    ),
)
action = EditCode(diff=diff, target_path=source)

executor = CodeExecutor(work_dir=work_dir)
result = executor.apply_diff(state, action)
print(f"\nResult: {result}")
