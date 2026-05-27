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

## Git worktree-aware workflows

The Git extension is worktree-aware. A `WorkSession` can be attached to
a specific `git worktree`, and STAG commands inside that session run
their git subprocesses inside the linked working tree:

- `STAG_GIT_WORKTREE` overrides the cwd for every git verb
  (`stag git commit / revert / cherry-pick / merge / reset / verify`).
- `stag work-session start / env / spawn --worktree PATH` records the
  resolved path (plus current branch and `git --git-common-dir`) on
  `WorkSession.metadata["worktree"]` and exports `STAG_GIT_WORKTREE`
  for downstream processes.
- `stag git worktree {add,list,remove}` is a thin wrapper around the
  upstream `git worktree` plumbing. Lifecycle stays in git so that
  worktrees created outside STAG can still be attached.

Possible follow-ups:

- Surface the worktree path in `stag work-session list` / TUI views.
- Record a per-transition workspace path when an agent moves between
  worktrees during a single session.
- Auto-create a worktree when `work-session env --new --worktree PATH`
  points at a missing directory.
