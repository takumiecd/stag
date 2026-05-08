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

## Commands

### `init`

```bash
optagent init <requirement_id> [--target-type code] [--target-id ID] [--run-id RID] [--store-dir DIR]
```

run を作成し、observed root `n_0000` と predicted root `n_0001` を seed します。成功時は run id を出力し、current run も更新します。

### `plan`

```bash
optagent plan --from-node n_0000 [--planner default] [--max-plans 1] [--action-type analysis] [--intent TEXT] [--input k=v]
```

observed Dag の node に grounded された `Plan` を作ります。

### `extend`

```bash
optagent extend --node-id n_0001 [--planner default] [--max-plans 1] [--action-type analysis] [--intent TEXT] [--input k=v]
```

predicted Dag の node に grounded された `Plan` を作ります。

### `predict`

```bash
optagent predict <plan_id> [--predictor default] [--max-outcomes 1]
```

predicted Dag の plan から predicted transition を作ります。

### `observe`

```bash
optagent observe --plan <plan_id> [--status completed] [--artifact PATH] [--raw-output PATH] [--log PATH] [--metric k=v] [--error MSG]
```

observed plan の実行結果を記録します。新しい observed transition に `ResultPayload` が attach されます。

### `promote-plan`

```bash
optagent promote-plan --predicted-plan <plan_id> --to-observed-node <node_id>
```

predicted Dag の plan を observed node に grounded し直します。

### `promote-transition`

```bash
optagent promote-transition --predicted-transition <transition_id> --plan <observed_plan_id> [--status completed] [--metric k=v]
```

predicted transition と実測結果を対応づけて observed transition を作ります。`promote` は `promote-transition` の alias です。

### `derive`

```bash
optagent derive <transition_id> [--type finding] [--text TEXT] [--id PAYLOAD_ID] [--confidence FLOAT]
```

observed transition に `DerivedPayload` を attach します。

### `rewind`

```bash
optagent rewind --transition <transition_id> --from-node <node_id> [--reason TEXT]
```

observed transition に `CutPayload` を attach します。既存 record は削除しません。

### `refresh`

```bash
optagent refresh --from-node <node_id>
```

predicted Dag を指定 observed node の snapshot から作り直します。

### `trace`

```bash
optagent trace --from-node <node_id> [--depth N]
```

observed node から過去の履歴を辿ります。

### `show`

```bash
optagent show [--node ID | --plan ID | --transition ID | --payload ID]
```

引数なしなら run 全体を表示します。個別 ID 指定時は observed / predicted の両 Dag を横断して探します。

### `state`

```bash
optagent state --node-id <node_id> [--add-knowledge TEXT] [--add-open-question TEXT] [--add-artifact ID:TYPE:PATH] [--add-prediction ID:SUMMARY] [--add-branch ID]
```

node の最新 `SnapshotPayload` を表示または更新します。更新時は新しい payload を append します。

### `snapshot`

```bash
optagent snapshot --node-id <node_id> [--rebuild]
```

snapshot payload を表示します。`--rebuild` 付きなら observed history から snapshot を再構築し、新しい payload として attach します。

### `list` / `current` / `use`

```bash
optagent list
optagent current [--json]
optagent use <run_id>
```

run 管理 command です。

## Storage

新形式の run directory は次のファイルを持ちます。

```text
run.json
dags.jsonl
nodes.jsonl
plans.jsonl
transitions.jsonl
payloads.jsonl
selections.jsonl
```

0.1 alpha では旧 storage schema との互換は持ちません。
