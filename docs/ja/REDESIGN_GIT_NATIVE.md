# STAG Git-Native 再設計 (実装仕様)

> 現在の実装では、この git-native 機能群は core ではなく標準 extension
> `stag.ext.git` に置かれている。CLI の正式形は `stag git <verb>`、
> `stag commit` などは default alias。extension 化の層構造は
> [EXTENSION_FRAMEWORK.md](EXTENSION_FRAMEWORK.md) を参照。

このドキュメントは「stag を git の上に立つ wrapper として再定義する」一連の変更の仕様書。
合意済みの設計を集約し、実装の準拠先とする。

関連: `DIRECTION.md`, `STATE_MODEL.md`, `API.md`, `CLI.md`

---

## 1. 基本方針

- stag は git の **上** に立つ。何をしたいか (intent) が先にあって、それを実現するために git 操作が起きる。`stag commit` が `git commit` を駆動する。
- 「git 操作が起きた = 何らかの intent があった」。**全ての git 操作に対応する typed payload を用意する** (commit / revert / reset / merge / amend / rebase / cherry-pick / squash …)。
- core スキーマ (`Node`, `Transition`, `RunGraph`, `GraphView`) は **構造変更しない**。新しい概念はすべて Payload / WorkEvent として追加する。
- **append-only 原則**: 過去の Transition / Payload / WorkEvent は **書き換えない**。状態の更新は常に append。
- **論理 DAG ⊥ 物理 DAG**:
  - 論理 (stag の Transition) は **意図がどう派生したか** を表す。append-only で、git の sha 変更や reorder に依存しない。
  - 物理 (git の commit graph) は **ファイル変更の実体**。`GitChangePayload` 経由で参照する。
- **1 Transition : N GitChangePayload を許す**。1 つの Transition には複数の `GitChangePayload` が時系列で append されうる。**最新の GitChangePayload が "現在の sha"**。amend / rebase は新しい GitChangePayload を既存 Transition に append することで表現する。これにより「intent は不変、物理は動く」が自然に書ける。
- **Descendant 制約**: cut されていない任意の Transition `t` について、`t.latest_GitChangePayload.head_commit` は `t.input_node_ids` 内の **すべての node の latest head_commit** の git 上の **descendant (または同一)** でなければならない。論理 DAG は git commit DAG の準同型像 (向き保存) となる。違反は `stag verify` で機械的に検出する。

## 2. 用語

- **intent**: 論理的な作業単位。stag の Transition に対応。「X を試す」「Y を戻す」など。1 intent : N commit を許す (細かい修正 commit を粗い intent でまとめられる)。
- **session**: `WorkSession`。1 つの作業端末 / worktree。並列に複数存在しうる。
- **current**: ある session の「次の transition の input になる node 集合」。1 個または複数。
- **branch**: git の branch に 1:1 対応する概念。stag では payload と event で表現する派生概念。
- **tip**: branch の現在 head node。BranchTipEvent の最新値。
- **join**: 独立した DAG を 1 つにまとめる stag 独自の transition (共通祖先なし)。
- **merge**: git の merge に対応する transition (共通祖先あり)。
- **revert**: ある transition の効果を打ち消す **新しい forward transition**。元 transition は触らない。
- **reset**: 過去の状態に物理的に戻る。new transition + 捨てた transition への CutPayload。
- **amend / rebase**: intent は不変、sha だけ動く。既存 Transition に新しい GitChangePayload を append。

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

### 5.4 `GitChangePayload` (既存、運用変更)

- フィールド: `branch`, `head_commit`, `diff_summary`, `commit_log`。
- **同一 Transition に複数 append されうる**。最新の `GitChangePayload` が現在の sha を表す。
- amend / rebase / force-push 反映時に新しい `GitChangePayload` を append する。
- 過去の `GitChangePayload` は履歴として残す (「以前は sha=X だった」)。

### 5.5 `RevertPayload(TransitionPayload)`

- `target_kind = "transition"`
- `content = {"reverted_transition": "<t_id>", "reverted_commit": "<sha>"}`
- 意味: 元 transition の効果を打ち消す **新しい forward transition** に付ける。
- **元 transition は cut しない**。「試したが戻した」という歴史を保持。
- 自分の git commit は revert commit (最新 HEAD への append)。

### 5.6 `CherryPickPayload(TransitionPayload)`

- `target_kind = "transition"`
- `content = {"source_transition": "<t_id>", "source_commit": "<sha>"}`
- 意味: 他 branch の commit を持ってきた。元 transition は別 branch で生きている。
- 元 transition は触らない。新 transition が独自の `GitChangePayload` (cherry-pick で生成された新 sha) を持つ。

### 5.7 `SquashedIntoPayload(TransitionPayload)`

- `target_kind = "transition"`
- `content = {"survivor_transition": "<t_id>"}`
- 意味: rebase の squash / fixup で吸収された側の transition に付ける。
- 付与と同時に **`CutPayload` も自動付与**。
- 生存側 transition には新しい `GitChangePayload` (合成後 sha) が append される。

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

### 6.3 `AmendEvent`

- `event_type = "amend"`
- `transition_id: str`
- `old_sha: str`
- `new_sha: str`
- 用途: amend を監査用に記録。同時に対応 Transition に新 `GitChangePayload(head_commit=new_sha)` を append する。

### 6.4 `ResetEvent`

- `event_type = "reset"`
- `work_session_id: str`
- `from_node_id: str` (reset 直前の current)
- `to_node_id: str` (reset 後の current。既存 node)
- `mode: "hard" | "mixed" | "soft"`
- `discarded_transition_ids: tuple[str, ...]` (cut された transition 群)
- 用途: reset は **新しい Transition を作らない** (git の reset が commit を作らないのと同じ)。代わりにこの WorkEvent で記録する。
- 同時に `SessionPointerEvent(current_node_ids=(<to_node>,))` を append して current を巻き戻す。
- `discarded_transition_ids` の各 transition に `CutPayload` を自動付与 (mode="hard" のみ。mixed/soft は付与しない)。

### 6.5 `RebaseEvent`

- `event_type = "rebase"`
- `sha_map: dict[str, str]` (old_sha → new_sha)
- `affected_transitions: tuple[str, ...]`
- `onto: str` (rebase 先 commit)
- 用途: rebase を 1 イベントとして記録。各 affected transition には新 `GitChangePayload` が append される。
- interactive rebase の drop / squash / reword はそれぞれ別途 `CutPayload` / `SquashedIntoPayload` / 新 `GitChangePayload(commit_log=...)` で表現。

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

def current_sha(self, transition_id: str) -> str | None:
    """transition_id の最新 GitChangePayload.head_commit"""
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

すべて成功した上で commit を確定。途中失敗時はロールバック方針を別途定義 (§14)。

### 9.2 stag を経由しない commit

- pre-commit hook は `STAG_TRANSITION_GUARD` が無ければ `exit 1`。
- 緊急回避: `STAG_BYPASS=1` で warning だけ吐いて通す。後で `stag list --orphan-commits` で可視化。
- 過去 commit の救済: `stag adopt <sha>` で遡って transition 化。

### 9.3 pull で入った commit

- post-merge / post-rewrite hook が走り、未取り込み commit を **自動 adopt**。
- adopt 時の BranchPayload は元 branch 名を git ログから推定 (取れなければ unknown)。

## 10. git 操作カタログ

すべての git 操作は以下のいずれかに分類される。**過去の Transition は決して書き換えない**。差分は必ず append で表現する。

### 10.1 通常 commit

- new Transition + 各種 payload + event (§9.1)。

### 10.2 revert

- `stag revert <sha>` (または hook 経由で `git revert` を検出):
  - new Transition を append (input = current, output = new node)
  - `RevertPayload(reverted_transition=<t_old>, reverted_commit=<old_sha>)`
  - `GitChangePayload(head_commit=<revert commit sha>)`
- **元 Transition は触らない**。CutPayload も付けない。「試して戻した」を歴史として保つ。
- 図:
  ```
  n1 --t1--> n2 --t2--> n3 --t3(revert t1)--> n4
  ```
  t3 の git commit は最新 HEAD への新規 commit。

### 10.3 reset

reset は **新しい Transition を作らない**。git の reset 自体が commit を作らない (HEAD を動かすだけ) ことに忠実な意味論。代わりに:

- `stag reset --hard <sha|node>`:
  - `to_node` を解決 (引数の sha または node から逆引き)
  - `ResetEvent(from_node, to_node, mode="hard", discarded_transition_ids=[...])` を WorkEvent として append
  - `SessionPointerEvent(current_node_ids=(<to_node>,))` を append (current を巻き戻す)
  - `discarded_transition_ids` の各 transition に `CutPayload` を自動付与
  - `git reset --hard <sha>` を内部実行
- `--mixed` / `--soft`: ResetEvent の mode で区別。CutPayload は **付与しない** (working tree / index に変更が残るため、後続 commit で再利用される可能性がある)。

これにより:
- §10.9 の Descendant 制約に違反しない (Transition を作らないので検証対象外)
- reset の事実は ResetEvent で audit 可能
- 捨てられた Transition は Cut 経由で「もう参照しない」が表現される
- 戻った先で次の `stag commit` を打つと、新 Transition の input は `to_node`、出力は新 node、head_commit は HEAD 上の新 commit となり、自然に descendant 関係が成立

### 10.4 merge

- new Transition を append (input = 複数 = 自分の tip + マージ元 tip)
- `MergePayload(merged_from=..., merged_into=...)`
- `GitChangePayload(head_commit=<merge commit>)`
- conflict 解消は merge commit に含まれる。stag は別途記録しない (必要なら commit_log で表現)。

### 10.5 cherry-pick

- new Transition を append (input = current, output = new node)
- `CherryPickPayload(source_transition=<t>, source_commit=<sha>)`
- 元 Transition は別 branch で生きている。touch しない。

### 10.6 amend

- **new Transition は作らない**。intent は変わっていない。
- 対象 Transition (= 直前の自分の Transition) に:
  - 新 `GitChangePayload(head_commit=<new sha>, ...)` を append
  - `AmendEvent(transition_id, old_sha, new_sha)` を WorkEvent として記録
- BranchTipEvent は tip_node_id を変えず、対応 sha だけ更新される (sha は GitChangePayload 側で持つので event 自体は再発行不要)。

### 10.7 rebase (interactive 含む)

ベース動作:
- **構造的に Transition は変えない**。
- `RebaseEvent(sha_map, affected_transitions, onto)` を 1 つ記録。
- 各 affected transition に新 `GitChangePayload(head_commit=<new sha>)` を append。

interactive rebase の各操作別:

| 操作 | stag での扱い |
|---|---|
| `pick` | 新 GitChangePayload を append (sha だけ更新) |
| `reword` | 新 GitChangePayload(commit_log=new message) を append |
| `drop` | 対象 Transition に **`CutPayload` を付与** |
| `squash` / `fixup` | 吸収先 Transition に新 GitChangePayload (合成後 sha)。吸収された側に `SquashedIntoPayload(survivor=<t>)` + `CutPayload` |
| `edit` | `pick` と同じ + 続けて amend が起きれば §10.6 |
| reorder | Transition の親子は変えない。git の物理順序と stag 論理 DAG は乖離する (許容) |

### 10.8 force push / 他人の rebase が降ってきた

- post-fetch / post-merge / post-rewrite hook で sha map を計算。
- 解決できれば §10.7 と同じ処理。
- 解決不能な commit は **orphan としてマーク**、`stag adopt` で手動紐付け。

### 10.9 不変条件 (まとめ)

1. **Transition は append-only**。構造は書き換えない。Cut のみ可能。
2. **GitChangePayload は append-only**。最新が「今の sha」。過去 sha は歴史として残る。
3. **論理 DAG ⊥ 物理 DAG**。reorder / rebase で物理が動いても論理依存は不変。
4. **rebase / amend で Transition は増えない**。意図が変わらない以上、論理単位を増やさない。
5. **revert で過去 Transition を書き換えない**。新 Transition + RevertPayload で表現。
6. **reset は Transition を作らない**。ResetEvent + SessionPointerEvent + (hard なら) CutPayload で表現。
7. **Descendant 制約**: cut されていない任意の Transition `t` について、`t.latest_GitChangePayload.head_commit` は `t.input_node_ids` 内の全 node の latest head_commit の git descendant (または同一) でなければならない。`stag verify` で検証する。

## 11. hook

`stag init` で自動 install:

- `.git/hooks/pre-commit`: STAG_TRANSITION_GUARD 検査
- `.git/hooks/post-commit`: revert / cherry-pick 等の自動検出 (commit message の `Revert "..."` パターン等)
- `.git/hooks/post-merge`: pull の自動 adopt、merge commit の MergePayload 付与
- `.git/hooks/post-rewrite`: rebase / amend の追従 (sha_map を取得して新 GitChangePayload を append)
- `.git/hooks/post-checkout`: branch 切替を session 側に反映 (stag を経由しない `git checkout` を吸収)

すでに hook がある場合は追記モード。`stag init --extension git --git-no-hooks`
で skip 可能。hook 再インストール: `stag git hook install [--force]`
（shortcut: `stag hook install [--force]`）。

## 12. CLI 変更まとめ

### 新規

- `stag init --extension git [--git-no-hooks]` — git extension を有効化し、hook install と `.stag-id` 生成を行う
- `stag git commit -m "..."` (`stag commit`) — git commit を駆動
- `stag git revert --sha <sha>` / `--transition <t>` (`stag revert`) — revert を駆動、RevertPayload を付与
- `stag git reset --sha <sha>` / `--node <node>` (`stag reset`) — reset を駆動、ResetEvent + SessionPointerEvent + (hard なら) 自動 Cut。**Transition は作らない**
- `stag git cherry-pick --sha <sha>` (`stag cherry-pick`) — cherry-pick を駆動、CherryPickPayload を付与
- `stag git verify` (`stag verify`) — Descendant 制約を全 Transition について git に問い合わせて検証。違反 (orphan / 追従漏れ / amend 不整合) を報告
- `stag adopt <sha>...` — 既存 commit を transition 化
- `stag checkout <branch>` — branch 切替
- `stag git branch list | show <name>` (`stag branch ...`)
- `stag git hook install [--force]` (`stag hook install [--force]`)
- `stag use --add <node>`, `stag use --drop <node>` — current 集合操作

### 変更

- `stag git ...` は正式 namespace。`stag commit` / `stag verify` 等は alias 層の shortcut。
- reachable / graph / dump 系に `--branch <name>` フィルタ追加
- `stag show transition <t>` は **最新 GitChangePayload** を default で表示。`--history` で過去 GitChangePayload 一覧。

### 廃止

- `.stag/` 内ストレージ前提のあらゆる path 解決
- `current.json` (run pointer は `.stag-id` 経由のみ)

## 13. ドキュメント更新対象

- `DIRECTION.md` — git-native 化を 1 段落追記
- `STATE_MODEL.md` — branch / session / current 集合 / 1 Transition : N GitChangePayload の節を追加
- `API.md` — 新規 verb (commit, revert, reset, cherry-pick, adopt, checkout, branch) と新規 payload / event
- `CLI.md` — 新コマンド全体
- `GIT_INTEGRATION.md` — 本ドキュメントへのリンクのみに縮退
- `AGENT_LOOP.md` — commit フローを反映

## 14. 未決事項

- commit フロー途中失敗時のロールバック方針 (git commit は成功したが BranchTipEvent append に失敗、等)
- `stag pull` の具体仕様 (session が古い tip にいる時の救済)
- multi-input transition の CLI UX (`stag use --add` で十分か、`stag commit --merge <other-tip>` を別途用意するか)
- BranchTipEvent の競合検出 (同時 commit の race)
- `.stag-id` を git に追加するタイミングの UX (init 時自動 add するか、ユーザーに委ねるか)
- interactive rebase 中の hook 連続発火を 1 つの RebaseEvent にまとめる実装方針 (rebase 開始/終了の検出)
- orphan commit (stag を経由せず作られた / 解決不能な rebase 結果) の UI 上の見せ方
- reset --soft / --mixed 後の working tree 変更を次の `stag commit` でどう扱うか (現在は CutPayload を付けず、後続 commit に自然に取り込まれる前提)
- `stag verify` 違反時の自動修復 (`stag adopt --rewrite` 等) の UX

## 15. 実装順序 (提案)

1. ストレージ外出し (`.stag-id`, `STAG_HOME`, run 解決ロジック)
2. 新 Payload / WorkEvent サブタイプ追加 (Branch / Merge / Join / Revert / CherryPick / SquashedInto / Amend / Rebase / Reset)
3. `ancestors_of` / `branch_members` / `current_sha` 派生クエリ
4. `stag commit` (hook なし、手動駆動) と `stag adopt`
5. `stag revert` / `stag reset` / `stag cherry-pick` の手動駆動版
6. hook install と `stag init` 改修 (pre-commit / post-commit / post-merge / post-rewrite / post-checkout)
7. `stag checkout` / `stag branch` / `stag use --add`
8. amend / rebase の sha 追従 (1 Transition : N GitChangePayload の運用確立)
9. `stag verify` (Descendant 制約検証)
10. 既存 `stag git ...` の整理 / 廃止
11. ドキュメント更新

各段階で既存テストを通しつつ進める。schema 変更ではないので migration コードは不要 (alpha なので過去 run の互換も切ってよい)。
