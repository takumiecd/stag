# プロジェクトの方向性

optagent は、問題解決や最適化の過程を構造化して保存するためのライブラリです。

コード最適化、カーネル最適化、実験、調査では、単に「最終的なコード」だけでなく、途中で何を試し、何が起き、何を学んだかが重要になります。optagent は、その過程をあとから読み返せる形で残します。

## 0.1 Alpha 方針

この段階では後方互換を優先しません。モデルが弱いまま API を固定するより、破壊的変更を許容して core を単純に保ちます。

明示的な方針:

- package version は `0.1.0` のまま進める
- 旧 API との shim は原則追加しない
- 旧 storage schema の migration は原則追加しない
- docs は現在の実装に合わせる
- テストは現在の仕様を固定するために使う

## 中心モデル

optagent は、pure な graph record と domain payload を分けます。

```text
Node / Plan / Transition
  = graph の骨格

SnapshotPayload / ResultPayload / DerivedPayload / MatchPayload / CutPayload
  = graph に attach される意味
```

observed / predicted は record の型ではなく、owning `Dag` の role で表します。

```text
observed_dag:
  実際に起きた履歴

predicted_dag:
  まだ実行していない未来候補
```

## optagent がやること

- run を作る
- observed Dag と predicted Dag を管理する
- node に grounded された plan を作る
- predicted outcome を保存する
- 実行結果を observed Dag に保存する
- 予測と実測の対応を payload として保存する
- derived payload を transition に紐づける
- rewind を append-only cut として保存する
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

1. pure-DAG + payload model を 0.1 として固める
2. CLI と JSONL storage の仕様をドキュメントと一致させる
3. branch / attach workflow の使い方を具体化する
4. prediction と observation の比較 helper を追加する
5. executor / evaluator の protocol を整える

## ドキュメント

- [状態モデル](STATE_MODEL.md)
- [API](API.md)
- [CLI](CLI.md)
- [問題解決ループ](AGENT_LOOP.md)
