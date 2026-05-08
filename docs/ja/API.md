# API

この文書は、現在の Python API を説明します。0.1 alpha では破壊的変更を許容し、旧 API との互換は維持しません。

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

plan = run.plan(run.root_observed_node_id, intent="run benchmark")[0]
result = ResultPayload(
    payload_id="pending",
    target_id="pending",
    status="completed",
    raw_outputs=("raw/bench.txt",),
    metrics={"latency_ms": 1.5},
)

transition = run.observe(plan.plan_id, result)
history = run.trace(transition.to_node_id)
```

## Public Dataclasses

主な public model:

- `Requirement`
- `Dag`
- `Node`
- `Plan`
- `Transition`
- `SnapshotPayload`
- `ResultPayload`
- `DerivedPayload`
- `MatchPayload`
- `CutPayload`
- `PredictionSelection`
- `PredictionPath`
- `StateSnapshot`
- `TraceContext`

`ExecutionPlan` / `PredictionPlan` / `ObservedTransition` / `PredictedTransition` / `ActionResult` / `DerivedRecord` は現行 API では使いません。

## `optagent.init`

```python
optagent.init(requirement: Requirement, *, run_id: str | None = None) -> RunHandle
```

新しい run を作ります。

作られるもの:

- `run.observed_dag`: `metadata["role"] == "observed"`
- `run.predicted_dag`: `metadata["role"] == "predicted"`
- observed root node: `run.root_observed_node_id`
- predicted root node: `run.predicted_dag.metadata["root_node_id"]`

root node には `SnapshotPayload` が attach されます。

## `run.plan`

```python
run.plan(
    from_node_id: str,
    *,
    planner: str | None = None,
    max_plans: int | None = None,
    action_type: str = "analysis",
    intent: str | None = None,
    inputs: dict[str, JSONValue] | None = None,
    user_id: str | None = None,
) -> list[Plan]
```

observed Dag の node に grounded された plan を作ります。cut 済み subtree の node を渡すと `ValueError` です。

## `run.extend`

```python
run.extend(
    node_id: str,
    *,
    planner: str | None = None,
    max_plans: int | None = None,
    action_type: str = "analysis",
    intent: str | None = None,
    inputs: dict[str, JSONValue] | None = None,
) -> list[Plan]
```

predicted Dag の node に grounded された plan を作ります。

## `run.predict`

```python
run.predict(
    plan_id: str,
    *,
    predictor: str | None = None,
    max_outcomes: int | None = None,
) -> list[Transition]
```

predicted Dag の plan から predicted transition を作ります。各 transition には `ResultPayload` が attach されます。

## `run.observe`

```python
run.observe(
    plan_id: str,
    result: ResultPayload,
    *,
    user_id: str | None = None,
) -> Transition
```

observed Dag の plan に対して実行結果を記録します。新しい observed node と transition を追加し、渡した `ResultPayload` の内容を新 transition に attach します。

1 つの observed plan から transition は 1 つだけ作れます。同じ操作を再実行する場合は新しい plan を作ります。

`run.result(...)` は `run.observe(...)` の alias です。

## `run.promote(mode="plan")`

```python
run.promote(
    *,
    mode="plan",
    prediction_plan_id: str | None = None,
    prediction_path: PredictionPath | None = None,
    to_observed_node_id: str,
    user_id: str | None = None,
) -> list[Plan]
```

predicted Dag の plan を observed Dag の node に grounded し直します。

## `run.promote(mode="transition")`

```python
run.promote(
    *,
    mode="transition",
    predicted_transition_id: str,
    result: ResultPayload,
    plan_id: str,
    user_id: str | None = None,
) -> Transition
```

predicted transition と observed transition を対応づけて記録します。observed transition には `ResultPayload` と `MatchPayload` が attach されます。

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

observed transition に derived payload を attach します。

## `run.rewind`

```python
run.rewind(
    transition_id: str,
    *,
    from_node_id: str,
    reason: str | None = None,
    user_id: str | None = None,
) -> CutPayload
```

observed transition に `CutPayload` を attach します。既存レコードは削除しません。`transition_id` は `from_node_id` から active path を後ろ向きに辿って到達できる必要があります。

## `run.refresh`

```python
run.refresh(*, from_node_id: str) -> Dag
```

predicted Dag を、指定した observed node の snapshot を anchor にして作り直します。古い predicted Dag は `observed_dag.child_dags` から外されます。

## `run.trace`

```python
run.trace(
    node_id: str,
    *,
    depth: int | None = None,
    include_derived: bool = True,
    include_raw_refs: bool = True,
) -> TraceContext
```

observed node から過去の transition を辿ります。`run.history(...)` は alias です。

## State Snapshot Helpers

```python
run.state_show(node_id) -> SnapshotPayload
run.state_update(..., node_id=...) -> SnapshotPayload
run.snapshot_rebuild(node_id) -> SnapshotPayload
```

`state_update` は node に新しい `SnapshotPayload` を追加します。既存 payload は上書きしません。

## Storage

```python
from optagent.storage import JsonlRunStore

store = JsonlRunStore("runs")
run.save(store)
loaded = store.load_run("demo")
```

保存されるファイル:

- `run.json`
- `dags.jsonl`
- `nodes.jsonl`
- `plans.jsonl`
- `transitions.jsonl`
- `payloads.jsonl`
- `selections.jsonl`

0.1 alpha では旧 storage schema の読み込み互換はありません。
