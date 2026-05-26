# CLI

Basic flow:

```bash
stag init req_demo --run-id demo
stag transition create --run demo --from <root_node_id> --payload-type transition_payload --field type=experiment --field lr=0.01
stag payload add --run demo --node <node_id> --payload-type node_payload --field type=note --field text="observed result"
stag cut node <node_id> --run demo --reason "discarded"
stag graph dump --run demo --format outline
```

Core commands:

- `stag init <req_id>`: create a run
- `stag list`: list runs
- `stag use <run_id>` / `stag current`: manage the active run pointer

Node:

- `stag node show <node_id>`
- `stag node payloads <node_id>`

Transition:

- `stag transition create --from NODE --payload-type TYPE --field key=value`
- `stag transition show <transition_id>`
- `stag transition output <transition_id>`
- `stag transition inputs <transition_id>`
- `stag transition payloads <transition_id>`

Each transition has exactly one output node. Create multiple sibling transitions by running `transition create` multiple times from the same input node.

Payload:

- `stag payload types`
- `stag payload schema <payload_type>`
- `stag payload add --node NODE --payload-type TYPE --field key=value`
- `stag payload add --transition TRANSITION --payload-type TYPE --field key=value`
- `stag payload list --node NODE` / `stag payload list --transition TRANSITION`
- `stag payload show <payload_id>`

Cut / Git:

- `stag cut node <node_id>` / `stag cut transition <transition_id>`

Git integration is a standard extension. The canonical command namespace is
`stag git ...`; shortcut aliases such as `stag commit` are kept for daily use.

- `stag init <req_id> --extension git`: enable the git extension for a run
- `stag git commit -m "message"` / `stag commit -m "message"`
- `stag git branch list` / `stag branch list`
- `stag git branch show <name>` / `stag branch show <name>`
- `stag git revert --sha SHA` / `stag revert --sha SHA`
- `stag git cherry-pick --sha SHA` / `stag cherry-pick --sha SHA`
- `stag git merge --other branch:<name>` / `stag merge --other branch:<name>`
- `stag git reset --node NODE --mode hard` / `stag reset --node NODE --mode hard`
- `stag git verify` / `stag verify`
- `stag git hook install` / `stag hook install`
- `stag git add --transition T --commit SHA`
- `stag git list --transition T`
- `stag git show --transition T`

Graph:

- `stag graph dump [--format outline|mermaid]`
- `stag graph trace <node_id>`
- `stag graph reachable <node_id>`

Compatibility commands such as `stag show`, `stag dump`, `stag trace`, `stag reachable`, and `stag outcomes` still exist. Prefer the `node`, `transition`, `payload`, and `graph` namespaces for new usage.
