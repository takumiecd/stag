# Direction

The canonical graph model is now:

```text
Node -> Transition -> Node -> Transition -> Node
```

There are no specialized transition record types. Payloads attach meaning to a
plain `Transition`.

Core is standalone and does not depend on git. Git integration is the standard
extension under `stag.ext.git`; its canonical CLI is `stag git <verb>`, with
default aliases such as `stag commit` for common workflows.

Future UI work should render the DAG visually and show payload details only for
the focused node or transition.

## Roadmap: git worktree-aware workflows

The current `work-session` isolates STAG run / session attribution only; it
does not isolate the Git working tree. To make truly concurrent multi-agent
editing first-class, the Git extension is expected to grow worktree
awareness:

- Git extension should eventually manage or attach `git worktree`s.
- `WorkSession` metadata may record workspace kind, path, branch, base ref,
  and repo root.
- This gives each agent a physical workspace while STAG keeps the logical
  graph of context, attempts, and decisions.

No implementation is committed yet; this is a direction note.
