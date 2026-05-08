# プロジェクトの方向性

optagent は、問題解決や最適化の過程を構造化して保存するためのライブラリです。

コード最適化、カーネル最適化、実験、調査では、単に「最終的なコード」だけでなく、途中で何を試し、何が起き、何を学んだかが重要になります。optagent は、その過程をあとから読み返せる形で残します。

## 0.1 Alpha 方針

この段階では後方互換を優先しません。モデルが弱いまま API を固定するより、破壊的変更を許容して core を単純に保ちます。

明示的な方針:

- package version は `0.1.0` のまま進める
- 旧 API との shim は原則追加しない
- 旧 storage schema の migration は原則追加しない
- docs は 0.1 の target model を固定するために使う
- テストは現在の仕様を固定するために使う

## 中心モデル

optagent は、pure な graph record と domain payload を分けます。

```text
Node / Plan / Transition
  = graph の骨格

SnapshotPayload / ResultPayload / DerivedPayload / MatchPayload / CutPayload
  = graph に attach される意味
```

run 全体の DAG は `RunGraph` です。branch や仮説展開は別の record 空間を持つ child Dag ではなく、`RunGraph` の部分集合である `GraphView` として表します。

```text
RunGraph:
  nodes / plans / transitions / payloads の global store

GraphView:
  RunGraph 内の record membership

CLI branch:
  GraphView のユーザー向け名称
```

prediction は別 Dag ではなく、`kind="prediction"` の transition です。実測は `kind="observed"` の transition です。

## optagent がやること

- run を作る
- `RunGraph` と `GraphView` を管理する
- node に grounded された plan を作る
- prediction transition を保存する
- observed transition と実行結果を保存する
- 予測と実測の対応を payload として保存する
- derived payload を transition に紐づける
- rewind を append-only cut として保存する
- branch を `GraphView` として作成、表示、merge する
- JSONL run directory に保存・読み込みする

## optagent がやらないこと

optagent は、現時点では次のものではありません。

- 汎用 chatbot framework
- LangChain 的な general agent framework
- benchmark 付き code generator
- executor を内蔵した自動最適化ツール
- 生成コードを自動で元ファイルに書き戻すツール

executor、planner、predictor、LLM、benchmark runner は外側から接続します。core は、それらが生み出す plan、prediction、result、derived payload を保存する基盤です。

## 最初に強くする領域

最初に強くする領域は、コード最適化とカーネル最適化です。

特にカーネル最適化では、次の情報を残す必要があります。

- shape family ごとの性能
- dtype / device ごとの差
- correctness
- latency
- regression
- 適用できる dispatch scope
- raw benchmark output

これらは `ResultPayload` と `DerivedPayload` が価値を出しやすい領域です。

## 近い実装予定

1. `RunGraph` + `GraphView` + payload model を 0.1 として固める
2. CLI と JSONL storage の仕様をドキュメントと一致させる
3. prediction / observation を transition kind として実装する
4. branch workflow の作成、表示、merge を具体化する
5. prediction と observation の比較 helper を追加する
6. executor / evaluator の protocol を整える

## ドキュメント

- [状態モデル](STATE_MODEL.md)
- [API](API.md)
- [CLI](CLI.md)
- [問題解決ループ](AGENT_LOOP.md)
