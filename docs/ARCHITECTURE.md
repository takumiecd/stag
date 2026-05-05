# optagent Architecture

## 設計思想

optagentは「仮説駆動型の最適化エージェント」として設計されています。

### なぜ仮説駆動型か？

従来の最適化は「速くなれば良い」というアプローチが多いですが、それでは以下の問題があります：

1. **再現性がない** - なぜ速くなったのかわからない
2. **失敗から学べない** - 失敗した試行が捨てられて知見が蓄積されない
3. **安全でない** - 正確性検証なしに本番に適用される
4. **比較基準が不明確** - ベースラインが明示されていない

optagentでは、**すべての最適化は「仮説の検証」として扱われます**。

## コア原則

### 1. 仮説を先に書く

実装の前に、以下を明確に書き出します：

- **問題** - 何が遅い/悪いのか？
- **仮説** - なぜ遅いと考えるのか？（検証可能な形で）
- **対象条件** - どの条件下で有効か？
- **ベースライン** - 何と比較するのか？

### 2. 実験と本番の分離

```
実験パス    → テスト・検証のみ（declare）
本番パス    → 実運用に使用（publish/promote）
```

- `declare`: 実験用。レジストリに登録されるが、自動選択対象外
- `publish`: 本番用。auto_dispatchの対象になる

この分離により、検証中のコードが本番に影響を与えることはありません。

### 3. 証拠に基づく意思決定

最適化の承認には以下が必要です：

- ✅ 正確性検証の通過
- ✅ ベースラインとの比較ベンチマーク
- ✅ 仮説と結果の一致/不一致の記録
- ✅ 適用範囲の正当性

### 4. 知見の蓄積

成功も失敗もすべて記録されます：

- `experiments/` - 詳細な実験ログ（完全な歴史）
- `findings/` - 再利用可能な知見（集約された知識）

失敗した仮説も価値があります。「これは効かなかった」という知見は、同じ失敗を繰り返さないために重要です。

## アーキテクチャ概要

```
optagent/
├── v1/                    # Legacy v1 (hypothesis-test workflow)
│   ├── core/              # ManagerAgent, Workflow, State, Models
│   ├── backends/          # OpenCode, Claude, Mock
│   ├── evaluation/        # MultiSize benchmark
│   ├── strategies/        # Kernel, Config optimization
│   ├── artifacts/         # Artifact validation
│   └── reporting/         # Batch report generation
│
└── v2/                    # Domain-agnostic optimization framework
    ├── state.py           # §2 State, ArtifactSet, Artifact
    ├── action.py          # §3 Action protocol
    ├── reward.py          # §4 RewardSpec, Objective, Aggregator
    ├── planner.py         # §5 Plan, Planner, DefaultPlanner
    ├── rollout.py         # §6 RolloutSimulator
    ├── policy.py          # §7 Proposer, LLMProposer
    ├── mcts.py            # §8 MCTSNode, MCTSOptimizer
    ├── value.py           # §9 ValuePredictor
    ├── hybrid.py          # §10 HybridOptimizer
    ├── pareto.py          # Pareto front operations
    ├── bridge.py          # v1↔v2 compatibility
    └── domains/           # §11 Domain instantiations
        └── code/          # §11.3 Iterative Refinement
            ├── state.py      # CodeState, CodeArtifact
            ├── action.py     # EditCode, RunTests, RunBenchmark
            ├── reward.py     # create_code_reward_spec()
            ├── proposer.py   # CodeProposer (LLM prompt)
            ├── executor.py   # CodeExecutor (patch, pytest, timeit)
            ├── optimizer.py  # CodeOptimizer (main loop)
            └── backends.py   # OpenCodeBackendAdapter
```

## ワークフロー

```
1. INITIALIZE      → 戦略の初期化、環境確認
2. ANALYZE_TARGET  → 対象の分析、ベースライン取得
3. PROPOSE         → 仮説の生成（Backendが担当）
4. GENERATE        → アーティファクト生成（コード/設定）
5. EVALUATE        → 評価・ベンチマーク
6. VALIDATE        → 正確性・安全性検証
7. DECIDE          → 意思決定（承認/拒否/要検証）
8. FINALIZE        → 結果の記録、適用（任意）
```

## 状態管理

すべての最適化セッションは `OptimizationState` として管理されます：

```python
@dataclass
class OptimizationState:
    round_index: int              # 最適化ラウンド
    requirement: Requirement      # 最適化要求
    hypotheses: List[Hypothesis]  # 生成された仮説
    artifacts: List[Artifact]     # 生成されたアーティファクト
    evidence: List[Evidence]      # 評価証拠
    decisions: List[Decision]     # 意思決定履歴
```

状態はJSONとして永続化され、中断からの再開が可能です。

## マルチサイズ評価

小さいテンソルでの最適化は大きいテンソルでは逆効果になることがあります。`MultiSizeEvaluator` は以下のサイズで自動評価します：

- **small**  - 推論サイズ（batch_size=1）
- **medium** - 中間サイズ（batch_size=16）
- **large**  - 学習サイズ（batch_size=64）

速度向上率は**幾何平均**で集計され、サイズバイアスを排除します。

## 意思決定フロー

```
正確性が失敗 → 拒否（正確性が最優先）
     ↓
目標速度向上率を達成 → 承認
     ↓
未達成 → 拒否（理由を記録）
     ↓
データ不十分 → 要再検証
```

## 拡張方法

### 新しい戦略を追加

```python
class MyStrategy(Strategy):
    def analyze(self, requirement):
        # 対象分析
        pass
    
    def validate_requirement(self, requirement):
        # この戦略が対応できるか
        return requirement.target_type == "my_domain"
```

### 新しいバックエンドを追加

```python
class MyBackend(Backend):
    def propose_hypotheses(self, state, analysis):
        # 仮説生成
        pass
    
    def generate_artifact(self, hypothesis, state):
        # アーティファクト生成
        pass
```

### 新しい評価方法を追加

```python
class MyEvaluator(Evaluator):
    def evaluate(self, artifact, state):
        # 評価実行
        return Evidence(...)
```

## 使用例

### 基本的な最適化

```python
from optagent import ManagerAgent
from optagent.strategies.kernel import KernelOptimizationStrategy
from optagent.backends.opencode import OpenCodeBackend

agent = ManagerAgent(
    strategy=KernelOptimizationStrategy(),
    backend=OpenCodeBackend(model="opencode-go/kimi-k2.6"),
    evaluator=MultiSizeEvaluator(),
)

result = agent.optimize(Requirement(
    target_type="kernel",
    target_id="csc_linear_forward",
    parameters={"device": "cuda"},
))
```

### バッチ最適化

```python
from optagent.batch import BatchOptimizer

optimizer = BatchOptimizer(
    manager_factory=lambda: ManagerAgent(...),
    work_dir="./results",
    max_workers=2,
)

requirements = [
    ("csc", Requirement(...)),
    ("cscr", Requirement(...)),
    ("bsc", Requirement(...)),
]

report = optimizer.run(requirements)
report.save("./results")
```

## 設計上の制約

1. **決定論的** - 同じ入力から同じワークフローが実行される
2. **再現可能** - 状態を保存・復元できる
3. **透明性** - すべての決定に理由が記録される
4. **安全性** - 本番への適用は明示的な承認が必要

## 関連ドキュメント

- `docs/WORKFLOW.md` - 詳細なワークフロー解説
- `docs/API.md` - APIリファレンス
- `docs/EXAMPLES.md` - 使用例集
