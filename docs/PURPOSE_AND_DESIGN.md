# optagent の目的と設計

## なぜ作られたのか

### 元々の問題

odsa-sparse-runtime の `kernel_optimizer` は特定のドメイン（疎行列カーネル）に特化していました。これは有効なアプローチですが、以下の制約がありました：

1. **ドメインに依存** - カーネル専用のコードが散在し、他の最適化に流用できない
2. **LLMバックエンドが固定** - OpenCode前提で、Claudeや他のモデルへの切り替えが困難
3. **評価が単一サイズ** - 小さいテンソルでのベンチマークのみで、実際のワークロードでの性能が不明
4. **実験管理が手動** - 複数の最適化を一括実行・比較する仕組みがない

### 解決したいこと

optagent はこれらを一般化し、以下を実現します：

1. **ドメイン非依存** - カーネル、設定パラメータ、データベースクエリなど、あらゆる最適化対象に対応
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
