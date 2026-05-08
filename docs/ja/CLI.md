# CLI

optagent CLI は Python API の薄いラッパーです。各 command は `JsonlRunStore` を通じて run をディスクに保存します。

実行例:

```bash
PYTHONPATH=src python3 -m optagent.cli.main <subcommand> ...
```

editable install 後は `optagent <subcommand>` でも実行できます。

## 共通仕様

`--store-dir` の既定値は `.optagent/runs` です。

`init` / `use` 以外の command は run を次の順に解決します。

1. `--run`
2. `OPTAGENT_RUN_ID`
3. `<store-dir>/../current.json`

mutating command の user attribution は次の順に解決します。

1. `--user`
2. `OPTAGENT_USER_ID`
3. `<store-dir>/../config.json` の `user.id`
4. `"user"`

`RunGraph` は run 全体の DAG です。`GraphView` はその部分集合で、CLI では `branch` と呼びます。通常の command は `main` branch を対象にします。branch を明示できる command は `--branch` を受け取ります。

## Commands

### `init`

```bash
optagent init <requirement_id> [--target-type code] [--target-id ID] [--run-id RID] [--store-dir DIR]
```

run を作成し、`RunGraph` と `main` branch を seed します。root node は `n_0000` です。成功時は run id を出力し、current run も更新します。

### `plan`

```bash
optagent plan --from-node n_0000 [--branch main] [--planner default] [--max-plans 1] [--action-type analysis] [--intent TEXT] [--input k=v]
```

node に grounded された `Plan` を作ります。作成した plan は指定 branch の membership に追加されます。

### `predict`

```bash
optagent predict <plan_id> [--branch main] [--predictor default] [--max-outcomes 1]
```

同じ `RunGraph` に `kind="prediction"` の transition を作ります。各 transition には `ResultPayload` が attach されます。1 つの plan から複数の prediction transition を作れます。

### `observe`

```bash
optagent observe --plan <plan_id> [--branch main] [--match-prediction <transition_id>] [--status completed] [--artifact PATH] [--raw-output PATH] [--log PATH] [--metric k=v] [--error MSG]
```

実行結果を `kind="observed"` の transition として記録します。新しい transition に `ResultPayload` が attach されます。

`--match-prediction` を指定すると、observed transition に `MatchPayload` も attach します。これは旧 `promote-transition` の代替です。

### `derive`

```bash
optagent derive <transition_id> [--type finding] [--text TEXT] [--id PAYLOAD_ID] [--confidence FLOAT]
```

transition に `DerivedPayload` を attach します。

### `rewind`

```bash
optagent rewind --transition <transition_id> --from-node <node_id> [--branch main] [--reason TEXT]
```

transition に `CutPayload` を attach します。既存 record は削除しません。

### `trace`

```bash
optagent trace --from-node <node_id> [--branch main] [--depth N] [--include-predictions]
```

node から過去の履歴を辿ります。デフォルトでは observed transition を中心に読む想定です。prediction transition も含めたい場合は `--include-predictions` を使います。

### `show`

```bash
optagent show [--branch main] [--node ID | --plan ID | --transition ID | --payload ID]
```

引数なしなら run 全体を表示します。出力は `graph` と `branches` を含みます。個別 ID 指定時は `RunGraph` の global records から探します。

### `branch create`

```bash
optagent branch create --from-node <node_id> --name <branch_id>
```

指定 node を root とする `GraphView` を作ります。新しい branch は global records をコピーしません。

### `branch list`

```bash
optagent branch list
```

run 内の branch を一覧します。

### `branch show`

```bash
optagent branch show <branch_id>
```

branch の membership と metadata を表示します。

### `branch merge`

```bash
optagent branch merge <branch_id> --into main [--to-node <node_id>]
```

branch の選択した path を別 branch の membership に追加します。record の実体は `RunGraph` にあるため、merge は copy ではありません。

### `state`

```bash
optagent state --node-id <node_id> [--add-knowledge TEXT] [--add-open-question TEXT] [--add-artifact ID:TYPE:PATH] [--add-branch ID]
```

node の最新 `SnapshotPayload` を表示または更新します。更新時は新しい payload を append します。prediction は `state` ではなく `predict` で transition として記録します。

### `snapshot`

```bash
optagent snapshot --node-id <node_id> [--rebuild]
```

snapshot payload を表示します。`--rebuild` 付きなら履歴から snapshot を再構築し、新しい payload として attach します。

### `list` / `current` / `use`

```bash
optagent list
optagent current [--json]
optagent use <run_id>
```

run 管理 command です。

## Removed Commands

0.1 の単一 `RunGraph` モデルでは、次の command は廃止します。

```bash
optagent extend
optagent refresh
optagent promote
optagent promote-plan
optagent promote-transition
```

`extend` は `plan --branch ...` に統合します。`refresh` は predicted Dag がなくなるため不要です。`promote-transition` は `observe --match-prediction ...` に置き換えます。

## Storage

新形式の run directory は次のファイルを持ちます。

```text
run.json
graph.json
views.jsonl
nodes.jsonl
plans.jsonl
transitions.jsonl
payloads.jsonl
```

0.1 alpha では旧 storage schema との互換は持ちません。
