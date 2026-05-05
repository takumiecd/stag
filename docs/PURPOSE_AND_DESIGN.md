# optagent の目的と設計

## 一言でいうと

optagent は、コード・カーネル最適化の試行錯誤を
**状態遷移として記録し、証拠に基づいて次の一手と昇格可否を決めるための研究基盤**です。

目指しているのは、LangChain のような汎用エージェントフレームワークではありません。
対象はもっと狭く、以下のような optimization loop です。

1. 仮説を立てる
2. 候補アーティファクトを作る
3. テスト・ベンチマークする
4. 証拠を残す
5. promotion gate で採否を決める
6. 失敗も知識として残し、次の状態に進む

このループを `State_t -> Action_t -> State_{t+1}` として扱うことで、
LLM 生成、MCTS、Pareto 最適化、報酬設計、実験ログを同じ設計面に乗せます。

## 設計の中心命題

### 最適化は「編集」ではなく「状態遷移」

LLM にコードを書かせるだけでは、最適化エージェントにはなりません。
optagent では、各ラウンドの価値を「最終コードが速いか」だけでなく、
次の状態がどれだけ良い探索状態になったかで捉えます。

状態には以下を分けて持たせます。

| 要素 | 意味 |
| --- | --- |
| `artifact` | 現在保持している候補、または Pareto front |
| `trajectory` | どの仮説・編集・評価を辿ったか |
| `knowledge` | 失敗パターン、制約、校正データ、再利用可能な知見 |

この分離により、「速くならなかった試行」も探索空間を狭める情報として扱えます。

### 安全性は後付けではなく、promotion の前提

optagent のゴールは、候補を自動で本番投入することではありません。
候補を promotion してよいかを判断できるだけの証拠を残すことです。

最低限見るべきものは以下です。

- 正確性が通ったか
- 対象 dispatch / workload に対して eligible か
- regression がないか
- baseline と比較した speedup が閾値を超えたか
- 生ログや benchmark 出力が追跡可能か

このため、`PromotionGate` は設計の中心コンポーネントです。

### v1 と v2 の位置づけ

| 層 | 役割 |
| --- | --- |
| v1 | ファイルプロトコルで hypothesis -> artifact -> evidence -> decision を回す実用寄りのワークフロー |
| v2 | State / Action / Reward を差し替え可能にした研究寄りの抽象フレームワーク |
| code domain | v2 上の初期デモ。まだ安全な汎用コード最適化器ではない |

当面の方針は、v1 の堅い実験管理と v2 の抽象モデルを接続し、
「ちゃんと動く研究基盤」として育てることです。

## なぜ作られたのか

### 元々の問題

odsa-sparse-runtime の `kernel_optimizer` は特定のドメイン（疎行列カーネル）に特化していました。これは有効なアプローチですが、以下の制約がありました：

1. **ドメインに依存** - カーネル専用のコードが散在し、他の最適化に流用できない
2. **LLMバックエンドが固定** - OpenCode前提で、Claudeや他のモデルへの切り替えが困難
3. **評価が単一サイズ** - 小さいテンソルでのベンチマークのみで、実際のワークロードでの性能が不明
4. **実験管理が手動** - 複数の最適化を一括実行・比較する仕組みがない

### 解決したいこと

optagent はこれらを一般化し、以下を実現します：

1. **最適化ループの再利用** - カーネル、設定パラメータ、コード改善などで同じ hypothesis/evidence/promotion 構造を使う
2. **バックエンドの選択肢** - OpenCode、Claude、ローカルモデルなど、要件に応じた選択
3. **公正な評価** - 複数サイズでの自動ベンチマークと統計的な集計
4. **再現性** - すべての最適化プロセスを記録し、後から検証可能に

## どういう仕組みで動くのか

### 全体の流れ

```
┌─────────────────────────────────────────────────────────────┐
│                    最適化要求 (Requirement)                    │
│  "cuda上のCSC linear_forwardを最適化したい"                      │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│              1. 戦略による分析 (Strategy.analyze)              │
│  - 対象の特性を把握                                           │
│  - ベースラインを取得                                         │
│  - 最適化の余地を特定                                          │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│           2. 仮説の生成 (Backend.propose_hypotheses)          │
│  LLMによる仮説：                                              │
│  "Pythonループのオーバーヘッドが大きい。                       │
│   ベクトル化または並列化で改善できるはず"                      │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│          3. アーティファクト生成 (Backend.generate_artifact)    │
│  LLMが最適化コードを生成：                                     │
│  ```python                                                    │
│  class OptimizedCSCForward(KernelSpec):                       │
│      ...                                                      │
│  ```                                                          │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│            4. 評価 (Evaluator.evaluate)                       │
│  - smallサイズ (batch=1) で計測                               │
│  - mediumサイズ (batch=16) で計測                             │
│  - largeサイズ (batch=64) で計測                              │
│  - 正確性チェック                                              │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│            5. 意思決定 (Decision)                             │
│  - 全サイズで正確？ → Yes                                     │
│  - 幾何平均速度向上 >= 目標値？ → Yes                          │
│  → 承認 (Accepted)                                            │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│            6. 記録と適用                                      │
│  - 実験ログを保存                                             │
│  - 知見をfindingsに追加                                       │
│  - (オプション) 本番に適用                                     │
└─────────────────────────────────────────────────────────────┘
```

### 各コンポーネントの役割

#### ManagerAgent（指揮官）

ManagerAgent は全体の指揮をとりますが、**具体的な最適化手法は知りません**。代わりに、Strategy・Backend・Evaluator に委譲します。

これにより：
- 新しい戦略を追加してもManagerAgentの変更が不要
- バックエンドを切り替えてもワークフローは同じ
- 評価方法を変えても他の部分に影響なし

#### Strategy（戦略家）

最適化対象のドメイン知識を持ちます。

例えば `KernelOptimizationStrategy` は：
- どのフォーマット（CSC, CSCR, BSC...）があるか知っている
- 各フォーマットの特性（メモリアクセスパターン、並列化のしやすさ）を知っている
- どこに最適化の余地があるかを特定できる

#### Backend（生成エンジン）

LLMやその他の生成エンジンと連携します。

`OpenCodeBackend` の場合：
1. 仮説を自然言語で生成
2. 最適化コードを生成（プロンプトにドキュメントを注入）
3. 出力をパースしてアーティファクトとして格納

#### Evaluator（測定官）

公正な評価を行います。

`MultiSizeEvaluator` の特徴：
- **複数サイズで測定** - 小さい入力だけでなく、実用的なサイズも測定
- **幾何平均** - 算術平均ではなく幾何平均を使用し、極端な値の影響を抑制
- **統合評価** - 複数サイズの結果を1つの指標に集約

なぜ幾何平均か？
- サイズAで10倍速くても、サイズBで0.5倍（遅くなる）なら採用すべきではない
- 幾何平均は「全体として改善しているか」を正しく反映する

### 状態管理の詳細

すべての最適化プロセスは `OptimizationState` に記録されます：

```python
state = OptimizationState(
    round_index=1,
    requirement=Requirement(...),
    hypotheses=[Hypothesis(id="h1", description="loop fusion")],
    artifacts=[Artifact(content="optimized code...")],
    evidence=[Evidence(speedup=1.5, is_correct=True)],
    decisions=[Decision(accepted=True, reason="1.5x speedup")],
)
```

この状態はJSONとして保存され、後から：
- 再現（同じ条件でもう一度実行）
- 検証（第三者が結果を確認）
- 中断からの再開

が可能になります。

## 典型的な使用シナリオ

### シナリオ1: 単一カーネルの最適化

```python
# 1. 要求を定義
req = Requirement(
    target_type="kernel",
    target_id="csc_linear_forward",
    parameters={
        "device": "cuda",
        "dtype": "float32",
        "in_features": 1024,
        "out_features": 1024,
    },
    objective={"metric": "latency_ms", "direction": "minimize"},
)

# 2. 最適化実行
agent = ManagerAgent(strategy=..., backend=..., evaluator=...)
state = agent.optimize(req)

# 3. 結果確認
if state.decisions[-1].accepted:
    print(f"成功: {state.evidence[-1].speedup:.2f}x 速度向上")
else:
    print(f"失敗: {state.decisions[-1].reason}")
```

### シナリオ2: 複数フォーマットの一括評価

```python
# 複数の要件を定義
requirements = [
    ("csc_linear", Requirement(target_type="kernel", target_id="csc_linear", ...)),
    ("cscr_linear", Requirement(target_type="kernel", target_id="cscr_linear", ...)),
    ("bsc_conv", Requirement(target_type="kernel", target_id="bsc_conv", ...)),
]

# バッチ実行
optimizer = BatchOptimizer(manager_factory=..., work_dir="./results")
report = optimizer.run(requirements)

# レポート出力
print(report.to_markdown())
# → どのフォーマットが最も改善余地があるか一目でわかる
```

### シナリオ3: A/Bテスト（Backend比較）

```python
# OpenCodeで最適化
agent_oc = ManagerAgent(backend=OpenCodeBackend(model="kimi-k2.6"), ...)
state_oc = agent_oc.optimize(req)

# Claudeで最適化
agent_claude = ManagerAgent(backend=ClaudeBackend(model="claude-sonnet"), ...)
state_claude = agent_claude.optimize(req)

# 比較
print(f"OpenCode: {state_oc.evidence[-1].speedup:.2f}x")
print(f"Claude: {state_claude.evidence[-1].speedup:.2f}x")
```

### シナリオ4: コード最適化（v2 Iterative Refinement）

```python
from pathlib import Path
from optagent.v2.domains.code import CodeOptimizer
from optagent.v2.domains.code.backends import OpenCodeBackendAdapter

# 1. バックエンド設定
backend = OpenCodeBackendAdapter(
    command="/home/ware10sai/.opencode/bin/opencode",
    timeout=300.0,
)

# 2. 最適化実行
opt = CodeOptimizer(
    source_path=Path("./slow_module.py"),
    backend=backend,
)
result = opt.optimize(objective="minimize latency", max_rounds=3)

# 3. 結果確認
print(f"最適化後のコード:\n{result.code.content}")
print(f"テスト結果: {result.code.test_results}")
print(f"ベンチマーク: {result.code.benchmark_results}")
```

v2 のコード最適化は以下の流れで動作します：
1. 元のコードをベンチマーク（baseline）
2. LLM に最適化コードを生成させる
3. 生成コードを適用してテスト実行
4. テスト通過ならベンチマーク計測
5. 改善があればベストとして記録
6. 現行実装では全ラウンド終了後、ベストなコードをファイルに書き戻す

注意: シナリオ4は v2 の概念デモです。現状の `CodeOptimizer` はまだ
安全な汎用コード最適化器ではありません。実用化する前に、write-back の
デフォルト無効化、patch 出力、worktree 隔離、外部指定 benchmark が必要です。

## 失敗パターンと対処法

### パターン1: 小さいテンソルでは速いが、大きいテンソルでは遅い

**原因**: Pythonループのオーバーヘッドが支配的で、実際の計算時間を隠蔽している

**対処**: MultiSizeEvaluator が自動検出。幾何平均が1未満になれば拒否。

### パターン2: 正確性が失敗

**原因**: 最適化により数値誤差が増大、またはアルゴリズム的に間違い

**対処**: 正確性チェックが必須。失敗した場合、性能に関わらず拒否。

### パターン3: LLMがドキュメントを無視して間違ったコードを生成

**原因**: LLMが訓練データの標準的なCSR/CSCレイアウトを前提としている

**対処**: 
- Storage/Adapter APIドキュメントをプロンプトに注入
- ドキュメント検証テストでカバレッジ確認
- 生成されたコードに対する構文・安全性チェック

### パターン4: ベースラインが不明確

**原因**: 何と比較しているのかが曖昧

**対処**: 
- 明示的なベースライン指定が必須
- `auto_dispatch` または named spec を使用
- 比較対象は実験ログに記録

## 設計上のトレードオフ

### 柔軟性 vs 型安全性

optagent は `typing.Any` を多用して柔軟性を確保しています。これは：

- ✅ 新しい戦略/バックエンドの追加が容易
- ✅ 異なるドメイン間でのコード共有が可能
- ❌ コンパイル時の型チェックが弱い
- ❌ IDEの補完が効きにくい

トレードオフとして、実行時の検証とテストカバレッジを重視しています。

### 抽象化 vs パフォーマンス

抽象化レイヤー（Strategy, Backend, Evaluator）の間でのデータ変換にはオーバーヘッドがあります。しかし：

- 最適化プロセス自体は人間のレビューやLLMの応答待ちが支配的
- データ変換のコストは無視できるレベル
- 保守性と拡張性の方が重要

## 将来の拡張予定

1. **分散評価** - 複数マシンでの並列ベンチマーク
2. **ベイズ最適化** - LLM生成ではなく、パラメータ空間の探索
3. **自動戦略選択** - 対象に応じて最適なStrategyを自動選択
4. **継続的最適化** - 本番環境のメトリクスをフィードバックとして使用
