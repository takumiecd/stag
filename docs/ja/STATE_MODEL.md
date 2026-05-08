# 状態モデル

この文書は、optagent が問題解決や最適化の過程をどう記録するかを説明します。

0.1 alpha では後方互換よりもモデル整理を優先します。旧 `StateNode` / `ExecutionPlan` / `PredictionPlan` / `ObservedTransition` / `PredictedTransition` / `ActionResult` 形式は廃止し、共通の `Dag` と `Payload` に寄せています。

## 全体像

```text
RunHandle
  ├── observed_dag
  │   └── 実際に起きた履歴
  └── predicted_dag
      └── まだ実行していない未来候補

Dag
  ├── nodes: dict[str, Node]
  ├── plans: dict[str, Plan]
  ├── transitions: dict[str, Transition]
  ├── payloads: dict[str, Payload]
  ├── child_dags: dict[str, Dag]
  ├── incoming_index
  ├── outgoing_index
  ├── plans_by_node
  └── transitions_by_plan
```

observed / predicted の区別は `Node` や `Transition` 自体には持たせません。`Dag.metadata["role"]` が `observed` か `predicted` かで意味を決めます。

## Pure Graph Records

### Node

`Node` は pure な graph node です。

```python
Node(node_id="n_0000", metadata={})
```

node は状態の中身を直接持ちません。状態の working context は `SnapshotPayload` として node に attach します。

### Plan

`Plan` は node に grounded された action plan です。

```python
Plan(
    plan_id="plan_0001",
    grounded_node_id="n_0000",
    action_type="analysis",
    intent="run baseline benchmark",
)
```

observed Dag にある `Plan` は実行可能な計画として扱います。predicted Dag にある `Plan` は未来展開用の仮説として扱います。型は同じで、意味は owning Dag が決めます。

### Transition

`Transition` は node から node への edge です。

```python
Transition(
    transition_id="t_0001",
    parent_plan_id="plan_0001",
    from_node_id="n_0000",
    to_node_id="n_0002",
)
```

observed Dag では、1 つの plan から作れる transition は 1 つだけです。predicted Dag では、1 つの plan から複数の outcome transition を作れます。この cardinality は `Dag` ではなく `RunHandle` の writer が守ります。

## Payload

domain data は graph record に埋め込まず、payload として attach します。1 つの target に複数 payload を付けられます。

### SnapshotPayload

node に attach される working context です。

含めるもの:

- requirement
- artifacts
- knowledge
- open questions
- active branches
- predictions
- budget
- metadata

`StateSnapshot` は source of truth ではありません。次の plan を考えるための作業メモで、必要なら履歴から再構築します。

### ResultPayload

transition に attach される結果です。

含めるもの:

- artifacts
- raw outputs
- logs
- metrics
- errors
- actual cost

observed Dag では実際の実行結果、predicted Dag では予測 outcome の付加情報として使います。

### DerivedPayload

transition の事実から作った解釈です。

例:

- observation
- evidence
- prediction error
- decision
- finding
- summary

derived payload は source of truth ではありません。あとから別の evaluator、人間、LLM によって作り直せます。

### MatchPayload

observed transition が、どの predicted transition に対応したかを記録します。予測と実測の比較は、transition 本体ではなく payload として残します。

### CutPayload

rewind は削除ではなく `CutPayload` の append で表します。cut された transition から forward に到達できる node / transition は read-time に inactive として扱います。

## Child Dag と Attach

`Dag` は `child_dags` を持てます。将来の branch workflow では、探索を子 Dag として切り出し、あとから親 Dag の node と子 Dag の node を `Transition` で接続します。

`Dag.attach(...)` はこの接続を表す低レベル API です。子 Dag の中身はコピーせず、親 Dag 側に接続 transition を 1 本追加します。

## Rewind

`rewind` は observed Dag の transition に `CutPayload` を attach します。

重要な点:

- node / transition / plan / payload は削除しない
- active / inactive は `optagent.core.cuts` で read-time に計算する
- cut 済み subtree の node から新しい plan は作れない
- 別枝を伸ばす場合は active な node を明示して `plan(...)` する

## Storage

JSONL storage は新しい pure-DAG 形式だけを扱います。

```text
run.json
dags.jsonl
nodes.jsonl
plans.jsonl
transitions.jsonl
payloads.jsonl
selections.jsonl
```

旧形式の migration は 0.1 alpha では持ちません。
