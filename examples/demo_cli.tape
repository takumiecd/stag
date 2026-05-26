Output examples/demo_cli.gif

Set FontSize 15
Set Width 1200
Set Height 600
Set Theme "Catppuccin Macchiato"
Set Padding 20

Hide
Type "export PYTHONPATH=src"
Enter
Type "rm -rf /tmp/stag_ws_demo"
Enter
# Ensure no lingering tmux session
Type "tmux kill-server"
Enter
Type "clear"
Enter
Show

Type "tmux new -s stag_vhs"
Enter
Sleep 1.5s

Type "# 1. Initialize a new STAG run"
Enter
Type "stag init req_parallel --extension git --run-id ws_demo --store-dir /tmp/stag_ws_demo"
Enter
Sleep 1.5s

Type "# 2. Split screen to simulate two AI agents working in parallel"
Enter
# tmux split-window horizontal
Ctrl+B
Type "%"
Sleep 1s

# We are now in the right pane
Type "export PYTHONPATH=src; clear"
Enter
Sleep 500ms

Type "# [Claude's Terminal]"
Enter
Type "eval \$(stag work-session env --run ws_demo --name claude --new --store-dir /tmp/stag_ws_demo)"
Enter
Sleep 1s

Type "stag git commit -m 'Claude: trying vectorization approach'"
Enter
Sleep 1.5s

# Switch back to the left pane
Ctrl+B
Type "Left"
Sleep 1s

Type "clear"
Enter
Sleep 500ms

Type "# [Codex's Terminal]"
Enter
Type "eval \$(stag work-session env --run ws_demo --name codex --new --store-dir /tmp/stag_ws_demo)"
Enter
Sleep 1s

Type "stag git commit -m 'Codex: trying parallel map implementation'"
Enter
Sleep 1.5s

Type "# Both branches are safely isolated and tracked in STAG!"
Enter
Type "stag show --run ws_demo --store-dir /tmp/stag_ws_demo"
Enter
Sleep 6s

# Teardown
Type "exit"
Enter
Sleep 500ms
Type "exit"
Enter
Sleep 500ms
