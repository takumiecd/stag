# STAG Git-Native 実装計画 (vertical slices)

`REDESIGN_GIT_NATIVE.md` を実装に落とすための作業計画。
各スライスは end-to-end で動く単位に切る。完了条件を満たしたら次へ。

## 戦略

- **vertical slice**: 1 スライスごとに schema + run handle + CLI + test を揃え、動く状態を保つ。
- **alpha なので互換切ってよい**: `CLAUDE.md` の方針に従い、旧 storage / 旧 CLI の compat shim は基本作らない。
- **テスト方針**: 各スライスに schema unit test, run handle test, CLI test, (S2 以降) 実 git repo を使った integration test を最低 1 本ずつ。

## スライス一覧

### S1 — ストレージ外出し

**含むもの**:
- `STAG_HOME` env 解決 (default `${XDG_DATA_HOME:-~/.local/share}/stag`)
- `.stag-id` ファイル (UUID 1 行、git 管理下)
- run resolver の解決順: `--run` → `STAG_RUN_ID` → `.stag-id`
- `stag init` 改修: `.stag-id` 生成 + `<STAG_HOME>/runs/<uuid>/` 作成
- 旧 `.stag/` 内 storage / `current.json` 廃止

**完了条件**:
- `stag init` → `.stag-id` 生成 + `<STAG_HOME>/runs/<uuid>/` 作成
- 既存の CLI (`stag list`, `stag node`, `stag transition create`, `stag show`, `stag dump` 等) が新パスで動く
- 既存テストがすべて pass (storage パスの assertion は更新)

### S2 — 基本 git-native commit

**含むもの**:
- `BranchPayload(TransitionPayload)` 追加
- `SessionPointerEvent`, `BranchTipEvent` 追加
- session 解決ロジック (env / session ファイル)
- `stag commit -m "..."`: git commit を駆動し、Transition + BranchPayload + GitChangePayload + BranchTipEvent + SessionPointerEvent を append
- `stag branch list`, `stag branch show <name>`
- `RunGraph.ancestors_of`, `branch_members` 派生クエリ

**完了条件**:
- `stag commit -m "..."` 一発で git commit + stag transition が記録される
- `stag branch list/show` が動く
- `git log` と stag の Transition chain が対応する

### S3 — current_sha ヘルパ + show --history

**前提**: `RunGraph.attach_payload` は既に同一 transition に複数 payload を許容している (`payloads_by_transition` が list)。schema 変更は不要。S3 は薄いスライス。

**含むもの**:
- `RunGraph.current_sha(transition_id) -> str | None`: 最新の `GitChangePayload.head_commit` (リスト末尾) を返す
- `stag show transition <t>` のデフォルト表示を「最新 GitChangePayload 1 件」に
- `--history` フラグで全 GitChangePayload を時系列で出力

**完了条件**:
- 1 transition に 2 つ目の GitChangePayload を append → `current_sha` が新しい sha を返す
- `stag show transition` が最新値を default 表示
- `--history` で過去履歴が見える

### S4 — amend / rebase hook 追従

**含むもの**:
- `AmendEvent`, `RebaseEvent` 追加
- `.git/hooks/post-rewrite` install
- post-rewrite が rebase / amend を区別し、sha map を抽出
- 各 affected transition に新 `GitChangePayload(head_commit=new_sha)` を append
- interactive rebase の drop / squash / reword 検出 (後付け可能なら別スライスでも OK)
- `stag hook install [--force]`

**完了条件**:
- `git commit --amend` 後、対応 transition に新 GitChangePayload が自動 append
- `git rebase` 後、chain 全体の sha が更新される
- `AmendEvent` / `RebaseEvent` が WorkEvent として記録される

### S5 — revert / cherry-pick

**含むもの**:
- `RevertPayload`, `CherryPickPayload` 追加
- `stag revert <sha|transition>`, `stag cherry-pick <sha|transition>` コマンド
- `.git/hooks/post-commit`: revert / cherry-pick commit を検出して payload を自動付与 (fallback)

**完了条件**:
- `stag revert <sha>` で新 transition + RevertPayload が記録 (元 transition は触らない)
- `stag cherry-pick <sha>` で新 transition + CherryPickPayload が記録
- 素の `git revert` でも post-commit で自動的に RevertPayload が付く

### S6 — reset (Transition 非生成)

**含むもの**:
- `ResetEvent` 追加
- `stag reset <sha|node> [--hard|--mixed|--soft]`:
  - `ResetEvent` append、`SessionPointerEvent` で current 巻き戻し
  - mode="hard" のみ discarded transition に `CutPayload` 自動付与
  - 内部で `git reset` を実行
- Transition は **作らない**

**完了条件**:
- `stag reset --hard <node>` で current が巻き戻り、捨てた transition が cut される
- `--mixed` / `--soft` では cut されない
- §10.9 不変条件に違反しない (新 Transition がそもそも作られない)

### S7 — merge / join

**含むもの**:
- `MergePayload`, `JoinPayload` 追加
- `stag commit --merge <other-node|branch>` or `stag use --add` の UX
- multi-input transition の生成 (`input_node_ids` が 2 個以上)
- merge commit hook 連携 (`.git/hooks/post-merge` で MergePayload 付与)

**完了条件**:
- `stag commit --merge <other>` で multi-input transition + MergePayload が記録
- `git merge` 経由でも post-merge hook で MergePayload が付く
- `stag dump` で merge transition が正しく表現される

### S8 — descendant 制約検証

**含むもの**:
- `stag verify`:
  - 全 (cut でない) transition を走査
  - 各 transition について `git merge-base --is-ancestor input_head_commit output_head_commit` をチェック
  - 違反を一覧表示 (orphan / 追従漏れ / amend 不整合等)
- 違反の分類 (dead sha / non-descendant / 未追従)

**完了条件**:
- 正常な run で `stag verify` が pass
- 意図的に作った不整合 run (`STAG_BYPASS=1` で打った orphan commit 等) で違反を検出
- 違反タイプが分類されて出力される

### S9 — 並列 session ガード

**含むもの**:
- `stag commit` 時に「current_branch の最新 BranchTipEvent.tip_node_id が current_node_ids に含まれるか」検査
- 不一致なら commit 拒否 (非 fast-forward 相当)
- session_id 解決 (`STAG_WORK_SESSION_ID` env / session ファイル)

**完了条件**:
- 別 session が tip を進めた状態で commit すると拒否される
- error メッセージに「`stag pull` 相当の救済を促す」表示

### S10 — クリーンアップ

**含むもの**:
- 旧 `stag git ...` コマンド廃止 (`stag commit` / `stag adopt` に統合)
- `.stag/` 前提コード全削除
- `current.json` 全削除
- `DIRECTION.md`, `STATE_MODEL.md`, `API.md`, `CLI.md`, `AGENT_LOOP.md`, `GIT_INTEGRATION.md` 更新

**完了条件**:
- リポ全体で `.stag/` への参照 0
- 旧 `stag git attach/list/show` への参照 0
- 主要ドキュメントが新仕様と整合

## 進行管理

- 各スライスを 1 PR (or 1 commit) として進める
- スライス開始時に該当節をこの doc から読み返す
- 完了条件を満たさない状態で次に進まない
- スライス内で発見した未決事項は `REDESIGN_GIT_NATIVE.md` §14 に追記

## 役割分担方針

- ストレージ移動 / hook / sha 追従などの作業量多めの実装は **sonnet-coder agent** に投げる候補
- 設計判断やスキーマ拡張の方針確定は Opus 側で行う
- スライス着手時に「この slice は sonnet で良いか / Opus が直接書くか」を都度判断
