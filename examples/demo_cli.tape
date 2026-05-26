Output examples/demo_cli.gif

Set Shell "bash"
Set FontSize 15
Set Width 1200
Set Height 600
Set Theme "Catppuccin Macchiato"
Set Padding 20
Set WindowBar Colorful

Hide
Type "source examples/demo_env.sh"
Enter
Type "tmux kill-server 2>/dev/null; true"
Enter
Type "clear"
Enter
Show

Type "tmux new -s stag_vhs"
Enter
Sleep 1.5s

Type "# 1. Initialize a new STAG run"
Enter
Type "stag init req_parallel --extension git --run-id ws_demo"
Enter
Sleep 1.5s

Type "# 2. Split screen to simulate two AI agents working in parallel"
Enter
Ctrl+B
Type "%"
Sleep 1s

# Right pane = Claude
Type "clear"
Enter
Sleep 300ms
Type "# [Claude's Terminal]"
Enter
Type `eval $(stag work-session env --run ws_demo --new --user claude)`
Enter
Sleep 800ms

Type "git checkout -b claude/vec"
Enter
Sleep 500ms
Type "echo 'def claude_vec(xs): return [x*2 for x in xs]' > claude.py"
Enter
Type "git add claude.py"
Enter
Type "stag git commit -m 'Claude: vectorization approach'"
Enter
Sleep 1.8s

# Back to left pane = Codex
Ctrl+B
Left
Sleep 800ms

Type "clear"
Enter
Sleep 300ms
Type "# [Codex's Terminal]"
Enter
Type `eval $(stag work-session env --run ws_demo --new --user codex)`
Enter
Sleep 800ms

Type "git checkout main && git checkout -b codex/map"
Enter
Sleep 500ms
Type "echo 'def codex_map(xs): return list(map(lambda x: x*2, xs))' > codex.py"
Enter
Type "git add codex.py"
Enter
Type "stag git commit -m 'Codex: parallel map implementation'"
Enter
Sleep 1.8s

Type "# Both branches are safely isolated and tracked in STAG!"
Enter
Type "stag dump --run ws_demo --format outline"
Enter
Sleep 5s

Hide
Type "tmux kill-server 2>/dev/null; true"
Enter
