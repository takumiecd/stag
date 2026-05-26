Output examples/demo_tui.gif

Set FontSize 15
Set Width 1200
Set Height 800
Set Theme "Catppuccin Macchiato"
Set Padding 20
Set WindowBar Colorful

Hide
Type "export PYTHONPATH=src"
Enter
Type "clear"
Enter
Show

Type "# 1. Automatically generating a complex DAG for the demo..."
Enter
Type "./examples/generate_tui_graph.sh"
Enter
Sleep 3s

Type "clear"
Enter

Type "# 2. Open the TUI to visualize the graph"
Enter
Type "stag tui --run demo_tui"
Enter
Sleep 2.5s

# Navigate down
Type "j"
Sleep 800ms
Type "j"
Sleep 800ms
Type "k"
Sleep 1.5s

# Select node to view details (press enter in STAG TUI to view detail modal)
Type "Enter"
Sleep 2.5s
Type "Escape"
Sleep 1.5s

# Quit
Type "q"
Sleep 1.5s
