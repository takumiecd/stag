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
