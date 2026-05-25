# STAG Git-Native 再設計 (実装仕様)

このドキュメントは「stag を git の上に立つ wrapper として再定義する」一連の変更の仕様書。
合意済みの設計を集約し、実装の準拠先とする。

関連: `DIRECTION.md`, `STATE_MODEL.md`, `API.md`, `CLI.md`

---

## 1. 基本方針

- stag は git の **上** に立つ。`stag commit` が `git commit` を駆動する。
- 「commit が起きた = transition が起きた」を厳密に対応させる。曖昧さを残さない。
- branch / merge / current などの概念は **core スキーマには載せない**。Payload と WorkEvent と派生クエリで実現する。
- core スキーマ (`Node`, `Transition`, `RunGraph`, `GraphView`) は **構造変更しない**。

## 2. 用語

- **session**: `WorkSession`。1 つの作業端末 / worktree。並列に複数存在しうる。
- **current**: ある session の「次の transition の input になる node 集合」。1 個または複数。
- **branch**: git の branch に 1:1 対応する概念。stag では payload と event で表現する派生概念。
- **tip**: branch の現在 head node。BranchTipEvent の最新値。
- **join**: 独立した DAG を 1 つにまとめる stag 独自の transition (共通祖先なし)。
- **merge**: git の merge に対応する transition (共通祖先あり)。

## 3. ストレージ

### 3.1 配置

- run データは **repo の外** に置く。default は `${XDG_DATA_HOME:-~/.local/share}/stag/runs/<uuid>/`。
- macOS でも上記 (XDG 準拠) でよい。`STAG_HOME` env で全体を上書き可能。
- `.stag/` を repo 内に作る現行運用は廃止。

### 3.2 repo との束縛

- repo root に `.stag-id` (UUID 1 行) のみを置く。これは **git 管理下にコミットする**。
- stag は `.stag-id` を読んで `<STAG_HOME>/runs/<uuid>/` を解決。
- worktree / fork / clone どこでも同じ run を指す。

### 3.3 run pointer

- `<STAG_HOME>/current.json` は廃止。理由は並列 session に耐えない (§7)。
- 「現在の run」の解決順:
  1. `--run` フラグ
  2. `STAG_RUN_ID` env
  3. `.stag-id` ファイル

## 4. core スキーマ (変更なし)

`RunGraph`, `Node`, `Transition`, `GraphView` は現在の定義のまま。
新しい概念は **すべて Payload / WorkEvent サブタイプとして追加** する。

## 5. 新規 Payload

すべて `src/stag/core/schema/payloads.py` に追加し、`register_payload_class` する。

### 5.1 `BranchPayload(TransitionPayload)`

- `target_kind = "transition"`
- `content = {"branch": "<branch_name>"}`
- 意味: **その transition が生まれた branch の歴史的記録**。不変。
- merge / pull で他 branch の commit を取り込んでも書き換えない。

### 5.2 `MergePayload(TransitionPayload)`

- `target_kind = "transition"`
- `content = {"merged_from": "<branch_name>", "merged_into": "<branch_name>"}`
- 意味: git の merge commit を表す。input は 2 個以上。

### 5.3 `JoinPayload(TransitionPayload)`

- `target_kind = "transition"`
- `content = {"joined_views": ["<view_or_branch>", ...]}`
- 意味: 独立 DAG を統合した stag 独自の合流。共通祖先なし。

### 5.4 既存 `GitChangePayload`

- そのまま使う。`branch`, `head_commit`, `diff_summary`, `commit_log` フィールド。
- 「この transition に対応する git commit はこれ」を記録。

## 6. 新規 WorkEvent サブタイプ

`src/stag/core/schema/work.py` に追加。append-only。**最新が真**。

### 6.1 `SessionPointerEvent`

- `event_type = "session_pointer"`
- `work_session_id: str`
- `current_node_ids: tuple[str, ...]` (集合表現、通常 1 要素、join/merge 直前のみ複数)
- `current_branch: str | None`
- 用途: session ごとの「現在地」を記録する。

### 6.2 `BranchTipEvent`

- `event_type = "branch_tip"`
- `branch: str`
- `tip_node_id: str`
- `work_session_id: str | None` (どの session が tip を進めたか参考、必須ではない)
- 用途: branch ごとの最新 tip を記録する。session 横断のグローバル状態。

## 7. session と current

### 7.1 current の表現

current は **node の集合**。理由:
- 通常 commit: 1 要素
- merge / join: 2 要素以上 (commit で 1 要素に潰れる)
- 「集合 → 1 transition」で merge も join も同じメカニズム

CLI:
- `stag use <node>` — current = {node}
- `stag use --add <node>` — current に追加
- `stag use --drop <node>` — current から除外

### 7.2 並列 session

- 各 session は **独立した current** を持つ (SessionPointerEvent で管理)。
- session_id は env `STAG_WORK_SESSION_ID` または `<STAG_HOME>/runs/<uuid>/sessions/<host>-<pid>.json` から解決。
- **同一 branch を複数 session が同時進行することは禁止**。
  - `stag commit` 時に「対象 branch の最新 BranchTipEvent.tip_node_id」が「自分の current に含まれる」か検査。
  - 一致しなければ拒否 (git の non-fast-forward 相当)。
  - 救済コマンドは後続 (`stag pull` 相当) で別途。

## 8. branch の実装

### 8.1 branch とは

stag における branch は **派生概念**。実体は以下 3 つの組み合わせ:

| 問い | 取得方法 |
|---|---|
| この transition はどの branch で生まれたか | `BranchPayload` (transition 付き) |
| branch X の現在 tip はどこか | `BranchTipEvent` の最新 |
| branch X に今属する node は何か | `ancestors_of(tip)` を walk |

### 8.2 派生クエリ

`RunGraph` に追加:

```python
def ancestors_of(self, node_id: str) -> set[str]:
    """node_id から transition_by_output_node を辿って祖先 node 集合を返す"""
```

新しい高レベル API:

```python
def branch_members(self, branch: str) -> set[str]:
    """latest BranchTipEvent(branch).tip_node_id の ancestors"""
```

CLI:
- `stag branch list`
- `stag branch show <name>` — tip, members, BranchPayload 付き transitions
- reachable / graph 系コマンドに `--branch <name>` フィルタを追加

### 8.3 checkout

- `stag checkout <branch>`:
  1. 対象 branch の最新 BranchTipEvent.tip_node_id を取得
  2. 現 session に SessionPointerEvent(current_node_ids=(tip,), current_branch=branch) を append
  3. `git checkout <branch>` を内部実行 (失敗したら stag 側もロールバック)

## 9. commit フロー

### 9.1 `stag commit -m "..."` の手順

1. session を解決 (env または session ファイル)
2. session の最新 SessionPointerEvent から current_node_ids と current_branch を取得
3. current_branch の最新 BranchTipEvent.tip_node_id が current_node_ids に含まれるか検査 (並列禁止ガード §7.2)
4. `git commit` を環境変数 `STAG_TRANSITION_GUARD=<token>` 付きで実行
5. pre-commit hook が `STAG_TRANSITION_GUARD` を検出 → 通過
6. commit 成功後、以下を append:
   - new `Node` (output)
   - new `Transition(input_node_ids=current_node_ids, output_node_id=<new node>)`
   - `BranchPayload(transition, branch=current_branch)`
   - merge/join なら `MergePayload` / `JoinPayload`
   - `GitChangePayload(transition, branch, head_commit, diff_summary, commit_log)`
   - `BranchTipEvent(branch=current_branch, tip_node_id=<new node>)`
   - `SessionPointerEvent(current_node_ids=(<new node>,), current_branch=current_branch)`

すべて成功した上で commit を確定。途中失敗時はロールバック方針を別途定義 (§13)。

### 9.2 stag を経由しない commit

- pre-commit hook は `STAG_TRANSITION_GUARD` が無ければ `exit 1`。
- 緊急回避: `STAG_BYPASS=1` で warning だけ吐いて通す。後で `stag list --orphan-commits` で可視化。
- 過去 commit の救済: `stag adopt <sha>` で遡って transition 化。

### 9.3 pull で入った commit

- post-merge / post-rewrite hook が走り、未取り込み commit を **自動 adopt**。
- adopt 時の BranchPayload は元 branch 名を git ログから推定 (取れなければ unknown)。

## 10. hook

`stag init` で自動 install:

- `.git/hooks/pre-commit`: STAG_TRANSITION_GUARD 検査
- `.git/hooks/post-merge`: pull の自動 adopt
- `.git/hooks/post-rewrite`: rebase / amend の追従

すでに hook がある場合は追記モード。`stag init --no-hooks` で skip 可能。
hook 再インストール: `stag hook install [--force]`。

## 11. CLI 変更まとめ

### 新規

- `stag init [--no-hooks] [--no-stag-id-commit]` — 仕様変更 (storage 外出し、hook install、`.stag-id` 生成)
- `stag commit -m "..."` — git commit を駆動
- `stag adopt <sha>...` — 既存 commit を transition 化
- `stag checkout <branch>` — branch 切替
- `stag branch list | show <name>`
- `stag hook install [--force]`
- `stag use --add <node>`, `stag use --drop <node>` — current 集合操作

### 変更

- `stag git ...` 系は廃止または `stag commit` / `stag adopt` に統合
- reachable / graph / dump 系に `--branch <name>` フィルタ追加

### 廃止

- `.stag/` 内ストレージ前提のあらゆる path 解決
- `current.json` (run pointer は `.stag-id` 経由のみ)

## 12. ドキュメント更新対象

- `DIRECTION.md` — git-native 化を 1 段落追記
- `STATE_MODEL.md` — branch / session / current 集合の節を追加
- `API.md` — 新規 verb (commit, adopt, checkout, branch) と新規 payload / event
- `CLI.md` — 新コマンド全体
- `GIT_INTEGRATION.md` — 本ドキュメントへのリンクのみに縮退
- `AGENT_LOOP.md` — commit フローを反映

## 13. 未決事項

- commit フロー途中失敗時のロールバック方針 (git commit は成功したが BranchTipEvent append に失敗、等)
- `stag pull` の具体仕様 (session が古い tip にいる時の救済)
- multi-input transition の CLI UX (`stag use --add` で十分か、`stag commit --merge <other-tip>` を別途用意するか)
- BranchTipEvent の競合検出 (同時 commit の race)
- `.stag-id` を git に追加するタイミングの UX (init 時自動 add するか、ユーザーに委ねるか)

## 14. 実装順序 (提案)

1. ストレージ外出し (`.stag-id`, `STAG_HOME`, run 解決ロジック)
2. 新 Payload / WorkEvent サブタイプ追加
3. `ancestors_of` / `branch_members` 派生クエリ
4. `stag commit` (hook なし、手動駆動) と `stag adopt`
5. hook install と `stag init` 改修
6. `stag checkout` / `stag branch` / `stag use --add`
7. 既存 `stag git ...` の整理 / 廃止
8. ドキュメント更新

各段階で既存テストを通しつつ進める。schema 変更ではないので migration コードは不要 (alpha なので過去 run の互換も切ってよい)。
