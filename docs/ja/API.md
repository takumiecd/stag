# API

この文書は、0.1 alpha で目指す Python API を説明します。破壊的変更を許容し、旧 API との互換は維持しません。

## 最小例

```python
import optagent
from optagent import Requirement, ResultPayload

requirement = Requirement(
    requirement_id="req_kernel",
    target_type="kernel",
    target_id="csc_linear",
)

run = optagent.init(requirement, run_id="demo")

plan = run.plan(run.root_node_id, intent="run benchmark")[0]
prediction = run.predict(plan.plan_id, max_outcomes=1)[0]

result = ResultPayload(
    payload_id="pending",
    target_kind="transition",
    target_id="pending",
    status="completed",
    raw_outputs=("raw/bench.txt",),
    metrics={"latency_ms": 1.5},
)

transition = run.observe(
    plan.plan_id,
    result,
    matched_prediction_id=prediction.transition_id,
)
history = run.trace(transition.to_node_id)
```

## Public Dataclasses

主な public model:

- `Requirement`
- `RunGraph`
- `GraphView`
- `Node`
- `Plan`
- `Transition`
- `PayloadBase`
- `SnapshotPayload`
- `ResultPayload`
- `DerivedPayload`
- `MatchPayload`
- `CutPayload`
- `StateSnapshot`
- `TraceContext`

`Dag` は全体 graph を表す名前としては使わず、`RunGraph` に置き換えます。部分集合は `GraphView` です。

`ExecutionPlan` / `PredictionPlan` / `ObservedTransition` / `PredictedTransition` / `ActionResult` / `DerivedRecord` は現行 API では使いません。

## `optagent.init`

```python
optagent.init(requirement: Requirement, *, run_id: str | None = None) -> RunHandle
```

新しい run を作ります。

作られるもの:

- `run.graph`: run 全体の `RunGraph`
- `run.graph.views["main"]`: default `GraphView`
- root node: `run.root_node_id`

root node には `SnapshotPayload` が attach されます。

## `run.plan`

```python
run.plan(
    from_node_id: str,
    *,
    branch: str = "main",
    planner: str | None = None,
    max_plans: int | None = None,
    action_type: str = "analysis",
    intent: str | None = None,
    inputs: dict[str, JSONValue] | None = None,
    user_id: str | None = None,
) -> list[Plan]
```

node に grounded された plan を作ります。作成した plan は指定 branch の membership に追加されます。cut 済み subtree の node を渡すと `ValueError` です。

## `run.predict`

```python
run.predict(
    plan_id: str,
    *,
    branch: str = "main",
    predictor: str | None = None,
    max_outcomes: int | None = None,
) -> list[Transition]
```

`kind="prediction"` の transition を作ります。各 transition には `ResultPayload` が attach されます。

## `run.observe`

```python
run.observe(
    plan_id: str,
    result: ResultPayload,
    *,
    branch: str = "main",
    matched_prediction_id: str | None = None,
    user_id: str | None = None,
) -> Transition
```

実行結果を `kind="observed"` の transition として記録します。新しい transition に `ResultPayload` を attach します。

`matched_prediction_id` を指定すると、observed transition に `MatchPayload` も attach します。

1 つの plan から prediction transition は複数作れます。observed transition は原則 1 つだけです。同じ操作を再実行する場合は新しい plan を作ります。

`run.result(...)` は `run.observe(...)` の alias です。

## `run.derive`

```python
run.derive(
    transition_id: str,
    derived_type: DerivedType,
    payload: dict[str, JSONValue],
    *,
    payload_id: str | None = None,
    generator: str = "default",
    confidence: float | None = None,
    user_id: str | None = None,
) -> DerivedPayload
```

transition に derived payload を attach します。

## `run.rewind`

```python
run.rewind(
    transition_id: str,
    *,
    from_node_id: str,
    branch: str = "main",
    reason: str | None = None,
    user_id: str | None = None,
) -> CutPayload
```

transition に `CutPayload` を attach します。既存レコードは削除しません。`transition_id` は `from_node_id` から active path を後ろ向きに辿って到達できる必要があります。

## `run.trace`

```python
run.trace(
    node_id: str,
    *,
    branch: str = "main",
    depth: int | None = None,
    include_predictions: bool = False,
    include_derived: bool = True,
    include_raw_refs: bool = True,
) -> TraceContext
```

node から過去の transition を辿ります。`include_predictions=False` の場合は observed transition を中心に履歴を作ります。`run.history(...)` は alias です。

## Branch API

```python
run.branch_create(name: str, *, from_node_id: str) -> GraphView
run.branch_list() -> list[GraphView]
run.branch_show(name: str) -> GraphView
run.branch_merge(name: str, *, into: str = "main", to_node_id: str | None = None) -> GraphView
```

branch は `GraphView` です。record の実体は `RunGraph` にあり、merge は record copy ではなく membership の追加です。

## State Snapshot Helpers

```python
run.state_show(node_id) -> SnapshotPayload
run.state_update(..., node_id=...) -> SnapshotPayload
run.snapshot_rebuild(node_id) -> SnapshotPayload
```

`state_update` は node に新しい `SnapshotPayload` を追加します。既存 payload は上書きしません。prediction は snapshot ではなく transition として保存します。

## Storage

```python
from optagent.storage import JsonlRunStore

store = JsonlRunStore("runs")
run.save(store)
loaded = store.load_run("demo")
```

保存されるファイル:

- `run.json`
- `graph.json`
- `views.jsonl`
- `nodes.jsonl`
- `plans.jsonl`
- `transitions.jsonl`
- `payloads.jsonl`

0.1 alpha では旧 storage schema の読み込み互換はありません。
