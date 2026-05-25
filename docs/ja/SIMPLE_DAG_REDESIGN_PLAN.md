# Simple DAG Redesign Plan

## 目的

STAG の core graph model を、現在の `Node` / `InputTransition` / `OutputTransition`
から、より単純な `Node` / `Transition` / `Edge` / `Payload` に整理する。

狙いは、DAG の骨格と意味情報をはっきり分けること。

- `Node` と `Transition` は DAG を構築するための純粋な graph record
- `Edge` は `Node` と `Transition` の接続を表す index / relation record
- `Payload` は `Node` または `Transition` に意味を付ける domain record

## 背景

現在のモデルは次の形になっている。

```text
Node
  -> InputTransition + PlanPayload
  -> OutputTransition + PredictionPayload | ResultPayload
  -> Node
```

この形は plan 側と output 側を分けられる一方、UI と概念説明では複雑に見える。
特に `InputTransition` / `OutputTransition` という分類が graph の骨格と payload の意味を
半分ずつ背負っているため、TUI や dump で綺麗に表現しづらい。

新しい方向では、graph の骨格を次に統一する。

```text
Node -> Transition -> Node -> Transition -> Node
```

`Transition` が plan なのか prediction なのか result なのかは、attach された payload が決める。

## 新しい基本モデル

### Node

`Node` は DAG 上の状態点。

```python
@dataclass(frozen=True)
class Node:
    node_id: str
    metadata: dict = field(default_factory=dict)
```

`Node` 自体は状態の意味を持たない。note、snapshot、summary などは payload として attach する。

### Transition

`Transition` は DAG 上の変化点。

```python
@dataclass(frozen=True)
class Transition:
    transition_id: str
    metadata: dict = field(default_factory=dict)
```

`Transition` 自体は plan / prediction / result などの意味を持たない。
意味は payload で付ける。

例:

```text
Transition T0 + PlanPayload
Transition T1 + PredictionPayload
Transition T2 + ResultPayload
Transition T2 + GitChangePayload
```

### Edge

`Edge` は graph record 同士の接続。

```python
@dataclass(frozen=True)
class Edge:
    edge_id: str
    from_kind: Literal["node", "transition"]
    from_id: str
    to_kind: Literal["node", "transition"]
    to_id: str
    metadata: dict = field(default_factory=dict)
```

原則として `Edge` は意味 payload を持たない。  
`Edge` は順方向 / 逆方向の探索、reachability、表示 layout のための関係 record とする。

許可する接続は次の 2 種類に限定する。

```text
Node -> Transition
Transition -> Node
```

禁止:

```text
Node -> Node
Transition -> Transition
```

この制約により、DAG は常に `Node` と `Transition` が交互に並ぶ二部グラフになる。

### Payload

`Payload` は domain meaning を attach する record。

```python
Payload(
    payload_id="pl_<opaque>",
    target_kind="node" | "transition",
    target_id="n_<opaque>" | "t_<opaque>",
    ...
)
```

`target_kind` は `node` / `transition` のみにする。  
`edge` には原則 payload を attach しない。

## 表現例

### 直線

```text
N0 -> T0 -> N1
```

```text
N0: NotePayload / SnapshotPayload
T0: PlanPayload + ResultPayload
N1: NotePayload
```

### 分岐

複数 outcome は、1 つの transition から複数 node を出すのではなく、
outcome ごとに transition を分ける。

```text
N0 -> T0 -> N1
N0 -> T1 -> N2
```

```text
T0: PlanPayload + PredictionPayload(probability=0.7)
T1: PlanPayload + PredictionPayload(probability=0.3)
```

同じ plan から派生した候補であることは、payload または metadata の `group_id` で表す。

### 合流

複数 node から 1 つの transition に入れる。

```text
N0 -> T2
N1 -> T2
T2 -> N3
```

これは現在の `InputTransition.input_node_ids` に相当する。

## 現行モデルからの対応

現在:

```text
Node
  -> InputTransition
  -> OutputTransition
  -> Node
```

新モデル:

```text
Node -> Transition -> Node
```

変換方針:

- 旧 `Node` は新 `Node`
- 旧 `OutputTransition` を新 `Transition` にする
- 旧 `InputTransition` の `PlanPayload` は、対応する新 `Transition` に attach する
- 旧 `OutputTransition` の `PredictionPayload` / `ResultPayload` も、同じ新 `Transition` に attach する
- 旧 `InputTransition.input_node_ids` は `Node -> Transition` edges に変換する
- 旧 `OutputTransition.to_node_id` は `Transition -> Node` edge に変換する

つまり、旧モデルで 1 つの `InputTransition` に複数 `OutputTransition` がぶら下がっていた場合、
新モデルでは output ごとに `Transition` を作る。

```text
旧:
N0 -> IT0 -> OT0 -> N1
          -> OT1 -> N2

新:
N0 -> T0 -> N1
N0 -> T1 -> N2
```

`T0` と `T1` は同じ plan 由来であることを payload / metadata で共有する。

## RunGraph の新しい形

```text
RunGraph
  ├── nodes: dict[str, Node]
  ├── transitions: dict[str, Transition]
  ├── edges: dict[str, Edge]
  ├── payloads: dict[str, Payload]
  ├── views: dict[str, GraphView]
  ├── outgoing_edges_by_node
  ├── incoming_edges_by_node
  ├── outgoing_edges_by_transition
  ├── incoming_edges_by_transition
  ├── payloads_by_node
  └── payloads_by_transition
```

便利 API:

```python
graph.successors(kind, id) -> list[GraphRef]
graph.predecessors(kind, id) -> list[GraphRef]
graph.payloads_for_node(node_id) -> list[Payload]
graph.payloads_for_transition(transition_id) -> list[Payload]
graph.transition_inputs(transition_id) -> list[str]  # node ids
graph.transition_outputs(transition_id) -> list[str] # node ids
```

## append-only 方針

append-only は維持する。

- `Node` / `Transition` / `Edge` / `Payload` は削除しない
- 無効化は `CutPayload` などを `Node` または `Transition` に attach して表す
- `Edge` を無効化したい場合も、原則として edge payload ではなく、接続先の `Transition` を cut する
- view は root node からの reachability で計算する

## UI への影響

TUI / dump はかなり単純になる。

図の中心は常に:

```text
[Node] -> (Transition) -> [Node]
```

payload は graph 上に直接表示しない。
focus した `Node` / `Transition` の payload を detail pane に表示する。

表示ラベル:

```text
Node:       S0, S1, S2
Transition: T0, T1, T2
```

意味ラベルは payload summary から補助的に出す。

```text
T0  plan: try smaller lr
T1  prediction: success
T2  result: failed tests
```

## 実装フェーズ

### Phase 1: 設計と adapter

- 新 schema の草案を追加する
- 既存 `RunGraph` から新しい normalized graph view を作る adapter を追加する
- TUI / dump で adapter を読む実験をする
- storage format はまだ変えない

### Phase 2: core API の新モデル化

- `RunGraph.nodes`
- `RunGraph.transitions`
- `RunGraph.edges`
- `payloads_by_transition`
- `add_transition`
- `add_edge`
- `attach_payload`

を追加する。

この段階では旧 `InputTransition` / `OutputTransition` も並存させるか、migration branch 内で一気に置換するかを決める。

### Phase 3: operations の再定義

既存 API を新モデルに対応させる。

- `plan`: `Node -> Transition -> Node` を作るか、transition だけを作るかを決める
- `predict`: prediction payload を持つ transition を作る
- `observe`: result payload を持つ transition を作る
- `note`: node payload のまま
- `cut`: node / transition target に統一

重要な設計判断:

- plan と result を同じ transition に attach するか
- plan transition と result transition を分けるか
- 複数 prediction を plan group としてどう表すか

現時点の推奨:

```text
1 outcome = 1 transition
```

同じ plan 由来の複数 transition は `group_id` でまとめる。

### Phase 4: storage migration

- JSONL / SQLite の新テーブル・ファイル構成を追加
- 旧 run を新モデルへ migrate するコマンドを用意
- 0.1 alpha では後方互換よりモデル整理を優先するが、既存テストデータを失わない変換は用意する

### Phase 5: docs / CLI / TUI 更新

- `STATE_MODEL.md` を置き換える
- `CONCEPT.md` の説明を `Node -> Transition -> Node` に寄せる
- CLI の表示名を `input_transition` / `output_transition` から `transition` に寄せる
- TUI は `Node` / `Transition` focus model にする

## 未決定事項

1. `PlanPayload` と `ResultPayload` を同じ transition に attach するか
2. prediction と result の対応をどう表すか
   - `ResultPayload.matched_prediction_transition_id`
   - または `group_id`
3. 同じ plan 由来の複数 transition の grouping を payload に持つか metadata に持つか
4. `Edge` を record として永続化するか、transition の input/output node ids から index として生成するか
5. `CutPayload` の target を `node` / `transition` のみに限定して十分か

## 暫定結論

core model は次の形へ方向転換する。

```text
Node -> Transition -> Node
```

意味は payload が付ける。

```text
Node / Transition = DAG skeleton
Payload = meaning
Edge = connection and traversal index
```

この方針により、保存モデル、TUI、dump、説明文がすべて単純になる。
