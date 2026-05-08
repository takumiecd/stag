# optagent

optagent は、問題解決や最適化の過程を DAG と JSONL で記録するための Python ライブラリです。

最終成果だけでなく、途中で立てた plan、実行前の予測、実際に起きた結果、そこから作った finding や decision を残すことを目的にしています。現在は 0.1 alpha で、後方互換よりもモデル整理を優先します。古い run 保存形式や旧 API との互換は保証しません。

## モデル

0.1 の中心は `RunGraph` です。`RunGraph` が run 全体の DAG を持ち、`GraphView` がその部分集合を表します。

```text
RunHandle
  └── graph: RunGraph

RunGraph
  ├── nodes
  ├── plans
  ├── transitions
  ├── payloads
  └── views

GraphView
  ├── view_id
  ├── root_node_id
  ├── node_ids
  ├── plan_ids
  ├── transition_ids
  └── payload_ids
```

`Node` / `Transition` / `Plan` は pure な graph record です。snapshot、result、derived note、prediction match、rewind cut などのドメイン情報は `Payload` として node または transition に attach します。

prediction は別 Dag ではなく、`kind="prediction"` の transition として同じ `RunGraph` に保存します。実測は `kind="observed"` の transition です。

`RunGraph` は append-only です。一度追加した node / plan / transition / payload は削除せず、取り消しや無効化は追加 payload と read-time の計算で表します。

## Quick Start

```python
import optagent
from optagent import Requirement, ResultPayload
from optagent.storage import JsonlRunStore

requirement = Requirement(
    requirement_id="req_kernel",
    target_type="kernel",
    target_id="csc_linear",
)

run = optagent.init(requirement, run_id="demo")

plan = run.plan(run.root_node_id, intent="run baseline benchmark")[0]
prediction = run.predict(plan.plan_id, max_outcomes=1)[0]

result = ResultPayload(
    payload_id="pending",
    target_kind="transition",
    target_id="pending",
    status="completed",
    raw_outputs=("raw/profile.txt",),
    metrics={"latency_ms": 1.5},
)

transition = run.observe(
    plan.plan_id,
    result,
    matched_prediction_id=prediction.transition_id,
)
history = run.trace(transition.to_node_id)

store = JsonlRunStore("runs")
run.save(store)
loaded = store.load_run("demo")
```

隔離した探索をしたい場合は `GraphView` を作ります。`GraphView` は global records をコピーせず、`RunGraph` の record membership だけを持ちます。

## CLI Quick Start

```bash
export PYTHONPATH=src

python3 -m optagent.cli.main init req_kernel \
  --target-type kernel \
  --target-id csc_linear \
  --run-id demo

python3 -m optagent.cli.main plan \
  --run demo \
  --from-node n_0000 \
  --intent "run baseline benchmark"

python3 -m optagent.cli.main predict \
  --run demo \
  plan_0001 \
  --max-outcomes 1

python3 -m optagent.cli.main observe \
  --run demo \
  --plan plan_0001 \
  --match-prediction t_0001 \
  --status completed \
  --raw-output raw/profile.txt \
  --metric latency_ms=1.5

python3 -m optagent.cli.main trace --run demo --from-node n_0002
python3 -m optagent.cli.main show --run demo
```

See `examples/basic_cli_loop.sh` for a complete CLI example.

## 主な用語

- `Requirement`: run の目的。
- `RunGraph`: run 全体の DAG と global records。
- `GraphView`: `RunGraph` の部分集合。
- `Node`: pure graph node。状態の中身は `SnapshotPayload` に置く。
- `Plan`: node に grounded された action plan。
- `Transition`: plan から作られる graph edge。`kind` で prediction / observed を区別する。
- `SnapshotPayload`: node に attach される working context。
- `ResultPayload`: transition に attach される実行結果または予測結果。
- `DerivedPayload`: transition に attach される finding、evidence、decision、summary などの解釈。
- `MatchPayload`: observed transition がどの prediction transition に対応したかを残す payload。
- `CutPayload`: rewind を append-only に表す payload。

## 保存形式

`JsonlRunStore` は run をディレクトリとして保存します。

```text
<store-dir>/<run-id>/
  run.json
  graph.json
  views.jsonl
  nodes.jsonl
  plans.jsonl
  transitions.jsonl
  payloads.jsonl
```

0.1 alpha では保存形式を破壊的に変える可能性があります。旧 `states.jsonl` / `execution_plans.jsonl` 形式との読み込み互換は持たせません。

## ドキュメント

- [プロジェクトの方向性](docs/ja/DIRECTION.md)
- [状態モデル](docs/ja/STATE_MODEL.md)
- [API](docs/ja/API.md)
- [CLI](docs/ja/CLI.md)
- [問題解決ループ](docs/ja/AGENT_LOOP.md)

## 開発

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -q
```

## License

MIT
