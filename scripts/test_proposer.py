#!/usr/bin/env python3
"""Integration test: real backend + CodeProposer."""

import tempfile
from pathlib import Path

from optagent.v2.state import State, ArtifactSet, Artifact
from optagent.v2.domains.code.proposer import CodeProposer
from optagent.v2.domains.code.backends import OpenCodeBackendAdapter

# Create a test file
work_dir = Path(tempfile.mkdtemp(prefix="optagent_smoke_"))
source = work_dir / "slow_loop.py"
source.write_text("""\
def slow_sum(n):
    \"\"\"Sum from 0 to n-1 using a loop.\"\"\"
    s = 0
    for i in range(n):
        s += i
    return s
""")

print(f"Working dir: {work_dir}")
print(f"Source file: {source}")

backend = OpenCodeBackendAdapter(
    command="/home/ware10sai/.opencode/bin/opencode",
    timeout=300.0,
)
proposer = CodeProposer(backend=backend)

state = State(
    requirement={"objective": "minimize latency"},
    artifact=ArtifactSet(
        incumbent=Artifact(
            artifact_id="test",
            content=source.read_text(),
            metadata={},
        )
    ),
)

print("Generating actions...")
actions = proposer.generate_actions(state, n=1, temperature=0.7)
print(f"Got {len(actions)} action(s)")
for i, action in enumerate(actions):
    print(f"\n--- Action {i+1} ---")
    print(action.diff[:500])
    print("...")
