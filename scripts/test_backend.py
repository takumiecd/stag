#!/usr/bin/env python3
"""Minimal test: call OpenCode backend directly."""

from optagent.v2.domains.code.backends import OpenCodeBackendAdapter

backend = OpenCodeBackendAdapter(
    command="/home/ware10sai/.opencode/bin/opencode",
    timeout=300.0,
)

prompt = """Optimize this Python function for speed.

```python
def slow_sum(n):
    s = 0
    for i in range(n):
        s += i
    return s
```

Return only a unified diff.
"""

print("Calling OpenCode backend...")
try:
    responses = backend.complete(prompt, n=1, temperature=0.7)
    print(f"Got {len(responses)} response(s)")
    for i, resp in enumerate(responses):
        print(f"\n--- Response {i+1} ---")
        print(resp[:1000])
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
