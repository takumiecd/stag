# STAG Extension Framework 設計 (実装仕様)

stag に extension の枠組みを導入し、git 連携機能をその上の標準 extension として置き直す。
`REDESIGN_GIT_NATIVE.md` で完成した git-native 機能群はそのまま保ち、層構造だけ正す。

関連: `REDESIGN_GIT_NATIVE.md`, `REDESIGN_IMPL_PLAN.md`, `DIRECTION.md`

## 1. 設計原則

- **依存方向は extension → core**。core は git を知らない。
- **standalone が default**。`stag init` だけでは ext は有効化されない。
- **canonical = `stag <ext> <verb>`**。`stag git commit` が正式名。
- **ショートカット = alias 層**。`stag commit` は default で `stag git commit` に解決される。
- **alpha なので breaking change OK**。旧 `RunHandle.commit` 等の直接 attr は即廃止し、`handle.git.commit` に統一する。

## 2. Extension Protocol

`src/stag/ext/base.py`:

```python
from typing import Protocol

class Violation: ...      # validate の結果型
class InitContext: ...    # on_init に渡すコンテキスト (run_id, run_dir, options)

class Extension(Protocol):
    name: str             # "git"
    version: str          # "0.1"

    # スキーマ登録 (payload class 登録、event 定数公開)
    def register_schema(self) -> None: ...

    # Python API: handle.<name>.<verb> を bind
    def register_verbs(self, handle: "RunHandle") -> None: ...

    # CLI: stag <name> <verb> を subparser に登録
    def register_cli(self, subparsers) -> None: ...

    # default の ショートカット alias
    def default_aliases(self) -> dict[str, str]:
        """例: {"commit": "git commit", "revert": "git revert"}"""

    # stag init 用のオプションを追加
    def register_init_options(self, parser) -> None: ...

    # `stag init --extension <name>` 時の副作用
    def on_init(self, ctx: "InitContext") -> None: ...

    # 整合性検査 (optional、default は空)
    def validate(self, handle: "RunHandle") -> list[Violation]: ...
```

Protocol なので abstract method 強制はない。空 default を持つ helper base class
`ExtensionBase` を別途用意して、extension 実装はそれを継承するのを推奨。

## 3. レジストリと有効化

### 3.1 built-in レジストリ

`src/stag/ext/__init__.py`:

```python
_BUILTIN: dict[str, str] = {
    "git": "stag.ext.git:GitExtension",
}

def load_extension(name: str) -> Extension: ...
def list_available() -> list[str]: ...
```

将来の third-party 対応は `entry_points` 経由で `stag.extensions` group をスキャン
してレジストリにマージする (今は実装しない)。

### 3.2 per-run 有効化

run dir に `extensions.json`:

```json
{
  "enabled": [
    {"name": "git", "version": "0.1", "config": {"repo_root": "/path/to/repo"}}
  ]
}
```

run を load すると enabled extension が auto-load される。

### 3.3 init コマンド

- `stag init <req>` — standalone (ext なし)
- `stag init <req> --extension git` — git ext を有効化、`on_init` 実行
- `stag init <req> --extension git --git-no-hooks` — ext 固有オプション

複数: `--extension git --extension jupyter` (将来)

## 4. Namespace

| レイヤ | 形式 |
|---|---|
| Python API | `handle.git.commit(...)` (ext name で namespace) |
| CLI canonical | `stag git commit` (ext name を最初の token に) |
| CLI shortcut | `stag commit` (alias で `git commit` に展開) |
| Payload type | `git_change`, `branch`, `revert`, … (フラット、衝突は register 時 error) |
| WorkEvent type | 同上 |

### 4.1 Alias 解決の優先順

```
1. user config (~/.config/stag/aliases.toml)
2. run-local config (<STAG_HOME>/runs/<uuid>/aliases.toml)
3. enabled extension の default_aliases (load 順で merge)
4. core CLI verb (init, list, current, use, …)
5. 解決失敗 → error
```

複数 ext が同じ alias 名を主張したら register 時に warning、先勝ち。ユーザは
`aliases.toml` で明示的に override。

### 4.2 alias 設定ファイル

```toml
[aliases]
c = "git commit"
ci = "git commit"
co = "git checkout"
commit = "git commit"   # default の override
```

操作 CLI: `stag alias list / add <name> <target> / remove <name>`。

## 5. core と git ext の責務分割

### 5.1 core に残す

- Node, Transition, RunGraph, GraphView, RunHandle 骨格
- `NodePayload`, `TransitionPayload` (generic), `CutPayload`
- **`JoinPayload`** — 独立 DAG 合流は git に依存しない汎用概念
- `WorkEvent` (generic), `WorkSession`, **`SessionPointerEvent`** — session / current は git なしでも有効
- 既存 verb: `transition`, `attach`, `cut`, `anchor`, `trace`, `outcomes`, `view_*`
- CLI: `init`, `list`, `current`, `use`, `node`, `payload`, `transition`, `cut`, `anchor`, `view`, `dump`, `show`, `graph`, `trace`, `reachable`, `outcomes`, `guide`, `migrate`, `sync`, `alias`, `ext`

### 5.2 git ext (`src/stag/ext/git/`) に移動

- Payloads: `GitChangePayload`, `BranchPayload`, `MergePayload`, `RevertPayload`, `CherryPickPayload`
- Event 定数: `BRANCH_TIP_EVENT`, `AMEND_EVENT`, `REBASE_EVENT`, `RESET_EVENT` + helpers
- Verbs: `commit`, `revert`, `merge`, `cherry_pick`, `reset`, `adopt_rewrite`, `verify`
- CLI: `commit`, `revert`, `cherry-pick`, `merge`, `reset`, `verify`, `branch`, `hook`
- `.stag-id` 管理 (git ext `on_init` で書く)
- Git hooks install
- Descendant 制約 (= `validate()`)

### 5.3 Run pointer の解決順 (更新)

| 優先 | source | 対象 |
|---|---|---|
| 1 | `--run <id>` | all |
| 2 | `STAG_RUN_ID` env | all |
| 3 | `.stag-id` (git ext 有効時のみ) | git mode |
| 4 | `<STAG_HOME>/last-run` (任意) | standalone |

## 6. 実装スライス

| Slice | 内容 | 完了条件 |
|---|---|---|
| **E1** | `src/stag/ext/` skeleton: `Extension` Protocol, `ExtensionBase`, registry, `Violation`, `InitContext`, `extensions.json` の persist/load helpers | unit test: dummy ext を register/load/enable/list できる |
| **E2** | core CLI に alias 解決層を入れる (alias 空でも動く)。`stag init --extension <name>` 受付、`stag ext list/show`, `stag alias list/add/remove` | core テストが全 pass、新規 alias テスト pass |
| **E3** | `src/stag/ext/git/` を作って既存 git コードを物理移動。import path 修正のみで挙動不変。テスト 394 件を保ったまま pass | 全 pass |
| **E4** | git ext を Protocol に適合: `register_schema`, `register_verbs`, `register_cli`, `default_aliases`, `register_init_options`, `on_init`, `validate` を実装 | git ext load → 既存 CLI が以前通り動く |
| **E5** | `RunHandle.git.commit(...)` namespace 化。旧 `handle.commit` は alpha なので即廃止。テストも更新 | テスト全 pass |
| **E6** | dispatcher で canonical `stag git commit` と shortcut `stag commit` の両方が動く | 両形式の CLI テスト pass |
| **E7** | doc 更新: `DIRECTION.md`, `STATE_MODEL.md`, `API.md`, `CLI.md`, `CLAUDE.md` を ext モデルに合わせる。`REDESIGN_GIT_NATIVE.md` は ext doc にリンクするだけに縮退 | doc 整合 |
| **S10** (旧) | 旧 `stag git ...` 廃止、`.stag/` 残骸削除、cleanup | リポ内に旧前提残らない |

## 7. 未決事項

- third-party ext を `entry_points` 経由で discover する仕様 (今は built-in のみ)
- ext 間の依存関係 (今は線形列挙、依存解決なし)
- ext の version 整合性チェック (alpha なので緩め)
- alias 衝突時の UX 詳細 (warning 文言、`stag alias resolve <name>` 等の診断コマンド)
- standalone モードの `stag verify` (構造整合のみ検証する core 版を作るか)

## 8. 進行管理

- 各 Slice 1 commit (or 1 PR)
- 着手前にこの doc の該当節を読み返す
- 完了条件を満たさない状態で次に進まない
- E1〜E7 を順に進め、最後に S10 (旧設計の cleanup)
