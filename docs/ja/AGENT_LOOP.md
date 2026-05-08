# 問題解決ループ

optagent は agent そのものではありません。人間、AI、script、executor が同じ文脈を共有するために、計画、予測、実行結果、解釈を構造化して保存する基盤です。

## 基本サイクル

```text
node を見る
  -> plan を作る
  -> 必要なら prediction transition を作る
  -> optagent の外で実行する
  -> observe で結果を保存する
  -> derive で finding や decision を付ける
  -> trace で履歴を読む
  -> 必要なら branch を作って隔離した探索をする
```

## 1. node を読む

core は mutable な current pointer を持ちません。caller が起点 node を明示します。

```python
node_id = run.root_node_id
snapshot = run.state_show(node_id)
```

## 2. plan を作る

```python
plan = run.plan(node_id, intent="run benchmark")[0]
```

plan は外部 executor に渡せる計画として扱います。

## 3. 予測する

予測は同じ `RunGraph` に `kind="prediction"` の transition として記録します。

```python
predicted = run.predict(plan.plan_id, max_outcomes=3)
```

1 つの plan から複数の prediction transition を作れます。

## 4. 実行する

optagent は executor を内蔵しません。外部の script、test runner、benchmark runner、AI coding tool が実行します。

実行後、結果を `ResultPayload` として渡します。

```python
result = ResultPayload(
    payload_id="pending",
    target_kind="transition",
    target_id="pending",
    status="completed",
    raw_outputs=("raw/bench.txt",),
    metrics={"latency_ms": 1.5},
)
```

## 5. 結果を記録する

予測と対応づけない場合:

```python
observed = run.observe(plan.plan_id, result)
```

予測 transition と対応づける場合:

```python
observed = run.observe(
    plan.plan_id,
    result,
    matched_prediction_id=predicted[0].transition_id,
)
```

どちらも `kind="observed"` の `Transition` を追加します。対応づける場合は `MatchPayload` も attach されます。

## 6. derived payload を残す

事実から作った解釈や判断は `DerivedPayload` として保存します。

```python
run.derive(
    observed.transition_id,
    "finding",
    {"text": "baseline latency was 1.5 ms"},
    generator="benchmark_parser",
)
```

derived payload はあとから作り直せる解釈で、source of truth ではありません。

## 7. 履歴を読む

```python
history = run.trace(observed.to_node_id, depth=3)
```

取得できるもの:

- past node ids
- transition ids
- plan ids
- result payload ids
- matched prediction transition ids
- derived payload ids
- artifact / raw output / log refs

## 8. branch で探索する

長い仮説展開や隔離した探索をしたい場合は branch を作ります。branch は `GraphView` であり、record の実体は `RunGraph` にあります。

```python
branch = run.branch_create("exp-a", from_node_id=observed.to_node_id)
future_plan = run.plan(observed.to_node_id, branch=branch.view_id, intent="try variant")[0]
run.predict(future_plan.plan_id, branch=branch.view_id, max_outcomes=3)
```

採用したい path は branch merge で main の membership に追加します。record はコピーしません。

```python
run.branch_merge("exp-a", into="main")
```

## Rewind

間違った枝を無効化したい場合は `rewind` を使います。

```python
cut = run.rewind(
    observed.transition_id,
    from_node_id=observed.to_node_id,
    reason="wrong benchmark command",
)
```

rewind は削除ではありません。`CutPayload` を append し、active / inactive は read-time に計算します。
