# 状態モデル

この文書は、optagent 0.1 alpha で目指す状態モデルを説明します。

0.1 alpha では後方互換よりもモデル整理を優先します。旧 `StateNode` / `ExecutionPlan` / `PredictionPlan` / `ObservedTransition` / `PredictedTransition` / `ActionResult` 形式は廃止し、run 全体の graph record と payload に寄せます。

## 全体像

```text
RunHandle
  └── graph: RunGraph

RunGraph
  ├── nodes: dict[str, Node]
  ├── plans: dict[str, Plan]
  ├── transitions: dict[str, Transition]
  ├── payloads: dict[str, Payload]
  ├── views: dict[str, GraphView]
  ├── incoming_index
  ├── outgoing_index
  ├── plans_by_node
  ├── transitions_by_plan
  ├── payloads_by_node
  └── payloads_by_transition

GraphView
  ├── view_id: str
  ├── root_node_id: str
  ├── node_ids: set[str]
  ├── plan_ids: set[str]
  ├── transition_ids: set[str]
  ├── payload_ids: set[str]
  └── metadata
```

`RunGraph` が run 全体の DAG です。`Node` / `Plan` / `Transition` / `Payload` の ID は run 内で global に一意です。

`GraphView` は `RunGraph` の部分集合です。CLI では主に `branch` と呼びます。`main` も特別な `GraphView` の 1 つです。

## なぜ GraphView にするか

parent Dag / child Dag がそれぞれ `nodes` や `transitions` を持つと、別 Dag 間で同じ ID が使われたときに意味が壊れます。さらに、親の transition が子の node を指すような横断参照は index や storage を曖昧にします。

そのため、record の実体は `RunGraph` に集約します。branch / 実験 / 仮説展開は、record をコピーせず `GraphView` の membership で表します。

```text
RunGraph
  nodes = {n_0000, n_0001, n_0100}
  transitions = {t_0000, t_0100}

GraphView main
  node_ids = {n_0000, n_0001}
  transition_ids = {t_0000}

GraphView exp-a
  node_ids = {n_0001, n_0100}
  transition_ids = {t_0100}
```

同じ node は複数の view に所属できます。merge は record のコピーではなく、選択した node / transition / plan / payload の ID を別 view の membership に追加する操作です。

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

plan 自体に observed / predicted の区別はありません。どの view に属しているか、どの transition を生むかで workflow 上の意味が決まります。

### Transition

`Transition` は node から node への edge です。

```python
Transition(
    transition_id="t_0001",
    parent_plan_id="plan_0001",
    from_node_id="n_0000",
    to_node_id="n_0002",
    kind="prediction",
)
```

`kind` は transition の意味を表します。

- `prediction`: 実行前の予測 outcome
- `observed`: 実際に起きた outcome

1 つの plan から prediction transition は複数作れます。observed transition は原則 1 つです。この cardinality は `RunGraph` の低レベル操作ではなく `RunHandle` の writer が守ります。

## Payload

domain data は graph record に埋め込まず、payload として attach します。1 つの target に複数 payload を付けられます。

payload は `target_kind` と `target_id` を持ちます。

```python
SnapshotPayload(
    payload_id="pl_0001",
    target_kind="node",
    target_id="n_0000",
    ...
)
```

### SnapshotPayload

node に attach される working context です。

含めるもの:

- requirement
- artifacts
- knowledge
- open questions
- active branches
- budget
- metadata

prediction は snapshot の手書きメモではなく、`kind="prediction"` の transition として表します。

### ResultPayload

transition に attach される結果です。

含めるもの:

- artifacts
- raw outputs
- logs
- metrics
- errors
- actual cost

prediction transition では予測 outcome の付加情報として、observed transition では実測結果として使います。

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

observed transition が、どの prediction transition に対応したかを記録します。予測と実測の比較は、transition 本体ではなく payload として残します。

### CutPayload

rewind は削除ではなく `CutPayload` の append で表します。cut された transition から forward に到達できる node / transition は read-time に inactive として扱います。

## Branch と GraphView

CLI では `GraphView` を `branch` と呼びます。

軽い未来予測は main view に prediction transition を追加するだけで十分です。長い仮説展開、隔離した探索、試験的な変更は別 branch を作ります。

```text
main
  n_0000 --observed--> n_0001

exp-a
  n_0001 --prediction--> n_0100 --prediction--> n_0101
```

branch merge は、選択した path の record ID を main view に追加します。record の実体は `RunGraph` にあるため、copy / attach / ID 衝突の問題を避けます。

## Rewind

`rewind` は transition に `CutPayload` を attach します。

重要な点:

- node / transition / plan / payload は削除しない
- active / inactive は read-time に計算する
- cut 済み subtree の node から新しい plan は作れない
- 別枝を伸ばす場合は active な node を明示して `plan(...)` する

## Storage

JSONL storage は run graph 形式だけを扱います。

```text
run.json
graph.json
views.jsonl
nodes.jsonl
plans.jsonl
transitions.jsonl
payloads.jsonl
```

旧形式の migration は 0.1 alpha では持ちません。
