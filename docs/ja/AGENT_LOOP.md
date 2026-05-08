# 問題解決ループ

optagent は agent そのものではありません。人間、AI、script、executor が同じ文脈を共有するために、計画、予測、実行結果、解釈を構造化して保存する基盤です。

## 基本サイクル

```text
observed node を見る
  -> plan を作る
  -> 必要なら predicted Dag を伸ばす
  -> optagent の外で実行する
  -> observe / promote で結果を保存する
  -> derive で finding や decision を付ける
  -> trace で履歴を読む
  -> 必要なら refresh で predicted Dag を作り直す
```

## 1. observed node を読む

core は mutable な current pointer を持ちません。caller が起点 node を明示します。

```python
node_id = run.root_observed_node_id
snapshot = run.state_show(node_id)
```

## 2. plan を作る

```python
plan = run.plan(node_id, intent="run benchmark")[0]
```

observed Dag の plan は外部 executor に渡せる計画として扱います。

## 3. 予測する

予測は predicted Dag 側で行います。

```python
pred_root = run.predicted_dag.metadata["root_node_id"]
future_plan = run.extend(pred_root, intent="predict benchmark outcomes")[0]
predicted = run.predict(future_plan.plan_id, max_outcomes=3)
```

1 つの predicted plan から複数の outcome transition を作れます。

## 4. 実行する

optagent は executor を内蔵しません。外部の script、test runner、benchmark runner、AI coding tool が実行します。

実行後、結果を `ResultPayload` として渡します。

```python
result = ResultPayload(
    payload_id="pending",
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
observed = run.promote(
    mode="transition",
    predicted_transition_id=predicted[0].transition_id,
    plan_id=plan.plan_id,
    result=result,
)
```

どちらも observed Dag に新しい `Transition` を追加します。対応づける場合は `MatchPayload` も attach されます。

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
- matched predicted transition ids
- derived payload ids
- artifact / raw output / log refs

## 8. predicted Dag を更新する

実測結果を保存したあと、未来予測を別の observed node に anchor し直したい場合:

```python
run.refresh(from_node_id=observed.to_node_id)
```

refresh は自動では走りません。caller が必要なタイミングで明示します。

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
