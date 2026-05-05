#!/usr/bin/env python3
"""Debug: trace optimizer step by step."""

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
""")

backend = OpenCodeBackendAdapter(
    command="/home/ware10sai/.opencode/bin/opencode",
    timeout=300.0,
)
opt = CodeOptimizer(
    source_path=source,
    backend=backend,
    work_dir=work_dir,
)

# Monkey-patch to trace
original_optimize = opt.optimize

def traced_optimize(objective, max_rounds=5):
    from optagent.v2.mcts import MCTSOptimizer
    from optagent.v2.domains.code.action import EditCode
    from optagent.v2.state import Observation
    
    initial_code = opt.source_path.read_text()
    current_code = initial_code
    
    from optagent.v2.domains.code.state import CodeArtifact, CodeState
    code = CodeArtifact(
        artifact_id="initial",
        source_path=opt.source_path,
        content=initial_code,
    )
    state = CodeState(
        requirement={"objective": objective, "source": str(opt.source_path)},
        code=code,
    )
    
    mcts = MCTSOptimizer(objectives=opt.reward_spec.objectives)
    v2_state = state.to_v2_state()
    
    for round_idx in range(max_rounds):
        print(f"\n=== Round {round_idx+1} ===")
        action = mcts.search(v2_state, opt.proposer, n_simulations=1, max_depth=3)
        print(f"Action type: {type(action).__name__}")
        if action is None:
            print("No action found")
            break
        
        if isinstance(action, EditCode):
            if action.target_path == Path("."):
                action.target_path = opt.source_path
            print(f"Diff content:\n{action.diff[:500]}")
            print("---")
            result = opt.executor.apply_diff(state, action)
            print(f"Diff success: {result['success']}")
            if result['success']:
                print(f"Patched content length: {len(result['patched_content'])}")
                print(f"Patched content preview: {result['patched_content'][:100]}...")
                current_code = result['patched_content']
                state.code.content = current_code
                v2_state = state.to_v2_state()
            else:
                print(f"Diff error: {result.get('error', '')[:200]}")
        
        # We stop after one round for debugging
        break
    
    return state

result = traced_optimize("minimize latency", max_rounds=1)
print(f"\n=== Final ===")
print(f"Final code:\n{result.code.content}")
