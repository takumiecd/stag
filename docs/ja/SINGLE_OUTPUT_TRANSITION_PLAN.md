# Single-Output Transition リファクタ計画

## 動機

現在のスキーマは `Transition` に **複数 output Node** を許している（`predict(max_outcomes=N)` が 1 Transition に N 個の output Node を生やす）。これが以下の問題を生んでいる：

1. **意味が曖昧**: 同じ Transition に `PredictionPayload` と `ResultPayload` が併存しうる。「予測されたが実行もされた」という中間状態がスキーマ上 valid になってしまう
2. **関数的でない**: 「何かをした → こうなった」を `inputs → action → output` で 1:1 に追えない。fan-out があると制御フローが追跡しづらい
3. **TUI/可視化が複雑**: Transition を畳む単位が自明でない。Tree も Flowchart も特殊ケース handling が必要

## 新スキーマ

### 原則

- **Transition は関数**: 複数 input → 1 つの action → **1 つの output**
- 予測も観測も同じ shape の Transition。違いは attach されている Payload の型のみ
- 中間 record `Edge` を廃止。`Transition` 自体が入出力 Node を直接持つ

### 型

```python
@dataclass(frozen=True)
class Node:
    node_id: str
    metadata: dict[str, JSONValue]

@dataclass(frozen=True)
class Transition:
    transition_id: str
    input_node_ids: tuple[str, ...]   # 複数 OK（multi-input join）
    output_node_id: str               # 必ず 1 つ
    metadata: dict[str, JSONValue]
```

### Payload（Transition に貼り付く）

- `PredictionPayload` — 「もしこうしたら、こうなりそう」（metrics, rationale, probability, ...）
- `ResultPayload` — 「こうしたら、こうなった」（status, metrics, errors, `matched_prediction_transition_id`）
- `CutPayload` — append-only な無効化マーク（Node または Transition）

### Node に貼り付く Payload

- `NotePayload` — Node 上のメモ
- `GitChangePayload` — そのまま

### 廃止

- `Edge` record — `Transition` が直接 input/output を持つため不要
- `PlanPayload` — 意図のみの記録は metrics 抜きの `PredictionPayload` で代替
- `plan` verb — 同上

## RunGraph 構造

```python
@dataclass
class RunGraph:
    nodes: dict[str, Node]
    transitions: dict[str, Transition]
    payloads: dict[str, Payload]
    views: dict[str, GraphView]
    work_sessions: dict[str, WorkSession]
    work_events: list[WorkEvent]
    metadata: dict[str, JSONValue]  # root_node_id 等

    # ---- 逆引きインデックス（永続化しない、ロード時に再構築） ----
    transitions_by_input_node: dict[str, list[str]]   # node_id -> [transition_id, ...]
    transition_by_output_node: dict[str, str]         # node_id -> transition_id (output は1つ)
    payloads_by_node: dict[str, list[str]]
    payloads_by_transition: dict[str, list[str]]
```

### 公開 API（lookup）

- `transitions_from_node(node_id) -> list[transition_id]`
- `transition_to_node(node_id) -> transition_id | None`（output は1つなので Transition も最大1つ）
- `transition_inputs(transition_id) -> tuple[str, ...]`
- `transition_output(transition_id) -> str`
- `transition_kind(transition_id) -> Literal["prediction", "result", "unknown"]`
- `payloads_for_node(node_id, *, payload_type=None)`
- `payloads_for_transition(transition_id, *, payload_type=None)`

## Verb

### `predict`

```python
predict(
    input_node_ids: list[str],
    payload: PredictionPayload,
    *,
    max_outcomes: int = 1,
    user_id, work_session_id,
) -> list[Transition]
```

- N 個の **sibling Transition** を生成。各 Transition は同じ `input_node_ids`、独立した output Node を 1 つ、独立した `PredictionPayload` を 1 つ
- 戻り値は作られた Transition のリスト

### `observe`

```python
observe(
    input_node_ids: list[str],
    payload: ResultPayload,
    *,
    matched_prediction_transition_id: str | None = None,
    user_id, work_session_id,
) -> Transition
```

- 1 つの Transition + 1 つの output Node + 1 つの ResultPayload を生成
- 既存の prediction Transition と紐付けたい場合は `matched_prediction_transition_id` を payload に乗せる（予測 Transition 自体は変更しない、append-only）

### `note` / `cut`

変更なし。

### 廃止: `plan`

意図のみの記録は `predict()` を metrics/rationale なしで呼ぶ。

## ストレージ（JsonlRunStore）

新しい run directory 構造：

- `run.json` — 変更なし
- `graph.json` — RunGraph metadata + counters
- `nodes.jsonl`
- `transitions.jsonl` — `input_node_ids` と `output_node_id` を含む
- `payloads.jsonl`
- `views.jsonl`
- ~~`edges.jsonl`~~ — 削除

旧形式（`input_transitions.jsonl` / `output_transitions.jsonl` / `edges.jsonl`）の互換性は **持たない**（alpha のため）。

## CLI

- `stag plan` — **削除**
- `stag predict` — multi-outcome は内部で複数 Transition を作る
- `stag observe` — 単一 Transition + output Node
- `stag note` / `stag cut` — 変更なし
- `stag show` / `stag trace` / `stag outcomes` / `stag dump` — 新スキーマに追従
- `stag tui` — 新スキーマに追従（multi-output 表示は概念上消える）

## Cut の意味

- Node に CutPayload を貼ると、そのノード + 下流の全 Transition と output Node が inactive
- Transition に CutPayload を貼ると、その Transition + その output Node + 下流が inactive
- 「inactive」は read-time に `inactive_node_ids` / `inactive_transition_ids` で計算（現状と同じ）

## TUI への影響

Transition の output は 1 つに固定されるので：

- Tree: `T → S_out` という直線的な親子関係。fan-out は **複数の sibling Transition** として表現（兄弟ノードとして展開）。「Transition を畳む」は自然に「その Transition の output Node 以下を畳む」と等価
- Flowchart: 各 Transition は 1:N input + 1 output の標準的な diamond/box ノード。layout が単純化される

## マイグレーション

alpha なので **既存 run のマイグレーションは行わない**。新スキーマで作り直し。テストは全面書き直し。

## 影響を受けるファイル（推定）

実装フェーズで詳細化するが、ざっくり：

- `src/stag/core/schema/graph.py` — `Edge`, `GraphRef`, `GraphRecordKind` 削除、`Transition` に `input_node_ids` / `output_node_id` 追加
- `src/stag/core/schema/payloads.py` — `PlanPayload` 削除、`ResultPayload.matched_prediction_transition_id` は残す
- `src/stag/core/run_graph.py` — Edge 関連 API 削除、逆引きインデックスを `Transition.add` 時に更新
- `src/stag/core/run/plan.py` — **削除**
- `src/stag/core/run/predict.py` — N Transition を生成するよう書き直し
- `src/stag/core/run/observe.py` — 単純化（既存 Transition への attach ではなく新規生成）
- `src/stag/core/run/dump.py` — outline/mermaid を新スキーマで再実装
- `src/stag/core/run/trace.py` / `outcomes.py` / `cut.py` — 追従
- `src/stag/core/cuts.py` — `inactive_transition_ids` のロジック調整
- `src/stag/storage/jsonl.py` / `sqlite.py` — `transitions.jsonl` のフォーマット変更、`edges.jsonl` 削除
- `src/stag/cli/*` — `plan` 削除、他追従
- `src/stag/tui/*` — 追従（fan-out 表示の簡素化）
- `tests/` — 全面書き直し

## 進め方

1. 本ドキュメントに合意
2. `feat/single-output-transition` ブランチで実装
3. core schema → RunGraph → verb → storage → CLI → TUI の順で破壊的に書き直す
4. テスト全面再構築
5. CLAUDE.md と `docs/ja/{DIRECTION,STATE_MODEL,API,CLI,AGENT_LOOP}.md` 更新

## 未決の論点（実装時に決める）

- `predict` の戻り値: `list[Transition]` か `list[Node]`（output Nodes）か → 多分前者の方が情報量多い
- Transition.metadata に user_id / work_session_id を入れるか別フィールドにするか（現状は metadata）
- multi-input Transition の入力順序が意味を持つか → 持たせない（順序不問の set として扱う）
