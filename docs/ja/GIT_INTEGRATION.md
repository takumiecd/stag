# Git 連携

この文書は STAG の Git 連携 (MVP) の設計を定めます。`stag git ...` namespace に閉じた追加機能であり、core graph model は変更しません。

## 目的

STAG は Git が管理する artifact の変更履歴に対して、

- なぜその変更をしたのか (`PlanPayload`)
- どうなると予測したのか (`PredictionPayload`)
- 実際にどうなったのか (`ResultPayload`)
- repository 上で何が変わったのか (`GitChangePayload`)

を DAG として記録します。Git は file / commit / diff / branch の source of truth であり、STAG はその上に乗る semantic transition layer として振る舞います。

## 設計方針

- Git 連携は `stag git ...` 配下に閉じる。`plan` / `predict` / `observe` は既存 top-level command を正規のまま扱う。
- Git の変更情報は **OutputTransition に attach される `GitChangePayload`** として保存する。InputTransition には Git diff / commit log を保存しない。
- `start` 時点ではまだ結果が存在しないため、`start` は payload を作らず pending な GitSession を作るだけとする。
- `finish` で Git の変更範囲を確定し、`OutputTransition` に `GitChangePayload` を attach する。
- MVP では `transition` / `trans` namespace、`--include-dirty`、worktree、PR 連携は導入しない。

## Core model との対応

```text
input nodes
  -> InputTransition  + PlanPayload
  -> OutputTransition + ResultPayload + GitChangePayload
  -> output node
```

`GitChangePayload` は domain payload であり、`Node` / `InputTransition` / `OutputTransition` 自体には Git 用の field を増やしません。

## Payload compatibility

- `GitChangePayload` は `OutputTransition` に attach する。
- `ResultPayload` と共存できる。MVP の主用途は observed output に `ResultPayload + GitChangePayload` を共存させること。
- `PredictionPayload` との共存も技術的には許可する（将来の予測 patch / 予測 branch 用の余地）。
- 既存の `PredictionPayload` / `ResultPayload` の mutual exclusion は維持する。同一 OT に両方は attach しない。

## 用語

### GitSession

`InputTransition` に紐づく pending な作業区間。append-only graph record ではなく、run directory 配下に保存される一時状態。`stag git start` で作成し、`stag git finish` で閉じる。

### GitChangePayload

ある observed output が対応する Git 変更を説明する payload。`OutputTransition` に attach される確定 record。`ResultPayload` が「意味としての結果」を表すのに対し、`GitChangePayload` は「repository 上の変更」を表す。

## Storage

Git session と Git artifact は run directory 配下に保存します。

```text
<run_dir>/git/sessions/gs_0001.json
<run_dir>/git/current.json
<run_dir>/artifacts/git/pl_0008.patch
```

`<run_dir>` は `JsonlRunStore` / 将来の sqlite store が resolve する run-specific storage root。グローバルな `.stag/git/current.json` は使いません（同一 repository 上で複数 run を扱うときに混乱するため）。

MVP では複数 GitSession の同時存在を許可します。`<run_dir>/git/current.json` は最後に start された open session を指す convenience pointer であり、コマンド実行では session id を明示することを正とします。

## Repository root の正規化

`repo_root` は absolute path で保存します。`"."` のような CWD 依存の相対パスは保存しません。

run directory 移動可能性は MVP では追わない。将来必要なら `repo_root_rel_to_run_dir` を追加する余地を残す。

## User attribution

`started_by` / `closed_by` は既存 mutating command と同じ順序で解決します。

1. `--user`
2. `STAG_USER_ID`
3. `<store-dir>/../config.json` の `user.id`
4. `"user"`

`commit_log[].author` は Git commit の author ident であり、`started_by` / `closed_by` の STAG user id とは別概念です。両者は同じ値である必要はありません。

## Git semantics

MVP は単一作業者・単一プロセス前提です。`finish` が Git から read してから graph 保存が完了するまでの間に外部 process が commit や working tree を変更するケースは concurrency-safe に扱いません。head lock 取得は行わず、通常のローカル CLI として実装します。

`base_commit..HEAD` を範囲として、次のように固定します。

| 用途 | コマンド |
| --- | --- |
| commit log | `git log <base_commit>..HEAD` |
| diff summary | `git diff --shortstat <base_commit>..HEAD` |
| changed files | `git diff --name-only <base_commit>..HEAD` |
| patch artifact | `git diff <base_commit>..HEAD` (unified diff) |

- 三点リーダ `base...HEAD` は使わない。
- `--first-parent` は使わない。merge commit が含まれる場合も通常の log として記録する。
- patch artifact は unified diff のみ。`git format-patch` 形式は MVP では出力しない。
- `base_commit == HEAD` や差分が空の場合でも `finish` は error にしない。warning を出した上で、空の `changed_files` / 0 件の `commit_log` / 空の patch artifact を持つ `GitChangePayload` を通常通り attach する。
- finish 時の branch は start 時と同じことを要求するため、branch をまたぐ履歴は扱わない。

### Clean working tree の定義

`finish` 時の "clean" とは、tracked files に modified / staged / deleted がない状態を指します。**untracked files は MVP では許容します。** `stag git status` は untracked count を表示し、ユーザーが確認できるようにします。

## データモデル

### GitSession

GitSession は pending state であり、RunGraph の payload ではありません。

```json
{
  "session_id": "gs_0001",
  "run_id": "demo",
  "input_transition_id": "it_0001",
  "repo_root": "/home/takumi/work/stag",
  "base_commit": "abc123",
  "base_branch": "feat/git-integration",
  "base_dirty": false,
  "started_at": "2026-05-10T19:00:00+09:00",
  "started_by": "takumi",
  "closed_at": null,
  "closed_by": null,
  "output_transition_id": null,
  "metadata": {}
}
```

`base_status_hash` は MVP では持ちません。`base_commit` と `base_dirty` で十分であり、status hash の定義が曖昧になりやすいためです。

### GitChangePayload

`OutputTransition` に attach される確定 payload です。

```json
{
  "payload_id": "pl_0008",
  "payload_type": "git_change",
  "target_kind": "output_transition",
  "target_id": "ot_0003",
  "repo_root": "/home/takumi/work/stag",
  "base_commit": "abc123",
  "head_commit": "def456",
  "branch": "feat/git-integration",
  "commit_log": [
    {
      "sha": "def456",
      "subject": "Add Git integration payloads",
      "author": "takumiecd",
      "date": "2026-05-10T19:20:00+09:00"
    }
  ],
  "diff_summary": {
    "files_changed": 4,
    "insertions": 120,
    "deletions": 18
  },
  "changed_files": [
    "src/stag/cli/commands/git.py",
    "src/stag/core/schema/payloads.py",
    "docs/ja/CLI.md"
  ],
  "patch_artifact": "artifacts/git/pl_0008.patch",
  "metadata": {}
}
```

設計上の補足:

- `base_branch` / `head_branch` は持たない。branch 切替を error とするため、確定 payload には単一の `branch` を保存する。
- patch artifact は `payload_id` ベースで命名する。同一 OT に複数 GitChangePayload が attach されても artifact path が衝突しないため。
- `status_after` は MVP では持たない。dirty finish を error にするため常に clean となり、情報量がない。
- `commit_log[].date` は ISO 8601 with timezone。
- `diff_summary.insertions` / `.deletions` は `git --shortstat` 相当の数値。binary file は Git が text diff として数えた範囲のみカウントする。

## CLI

```bash
stag git start <input_transition_id>

stag git finish <session_id> [--status completed]
                             [--summary TEXT]
                             [--artifact PATH] [--raw-output PATH] [--log PATH]
                             [--metric k=v] [--error MSG]
                             [--matched-prediction <output_transition_id>]
stag git finish <session_id> --output-transition <output_transition_id>

stag git status
stag git diff <session_id>
stag git diff --output-transition <output_transition_id>
stag git log  <session_id>
stag git log  --output-transition <output_transition_id>
```

`session_id` 省略時に current session を暗黙利用することは MVP ではしません。LLM-friendly / script-friendly のため、明示的な session id を要求します。

### `stag git start`

指定された `InputTransition` に対する Git 作業区間の始点を記録します。`start` は payload を作らず、pending session を作るだけです。

動作:

1. current run / user id を解決する。
2. `InputTransition` が存在し、active であることを確認する。
3. Git repository root を検出し、absolute path に正規化する。
4. 現在の branch / commit / dirty state を取得する。
5. detached HEAD を error として弾く。
6. GitSession を作成し、`<run_dir>/git/sessions/<session_id>.json` に保存する。
7. `<run_dir>/git/current.json` を更新する。

start 時点で working tree が dirty でも error にしません。ただし「start 前から存在した未 commit 変更が後で commit されると最終 GitChangePayload に混入しうる」旨の warning を出します。

出力例:

```json
{
  "session_id": "gs_0001",
  "input_transition_id": "it_0001",
  "base_commit": "abc123",
  "branch": "feat/git-integration",
  "dirty": false,
  "warnings": [],
  "next": [
    "stag git diff gs_0001",
    "stag git finish gs_0001 --status completed"
  ]
}
```

### `stag git finish`

GitSession の始点から現在の Git 状態までを `GitChangePayload` として確定し、`OutputTransition` に attach します。2 形式があります。

#### 形式 A: OutputTransition を自動作成

```bash
stag git finish <session_id> --status completed
```

内部的に `observe` 相当の処理を行い、新しい `OutputTransition` と `ResultPayload` を作成し、その `OutputTransition` に `GitChangePayload` を attach します。

形式 A の `ResultPayload` は CLI option から次のように合成します。

| field | source | default |
| --- | --- | --- |
| `status` | `--status` | `"completed"` |
| `artifacts` | `--artifact` (繰り返し可) | `()` |
| `raw_outputs` | `--raw-output` | `()` |
| `logs` | `--log` | `()` |
| `metrics` | `--metric k=v` | `{}` |
| `errors` | `--error` | `()` |
| `matched_prediction_output_id` | `--matched-prediction` | `null` |
| `metadata.summary` | `--summary` | `null` |
| `actual_cost` | (none) | `{}` |

`--summary` は人間 / LLM 向けの短い結果説明であり、`GitChangePayload` の commit log / diff summary とは別物です。

#### 形式 B: 既存 OutputTransition に attach

```bash
stag git finish <session_id> --output-transition ot_0003
```

新しい `OutputTransition` は作成しません。既存の `OutputTransition` に `GitChangePayload` だけを attach します。

形式 B の制約:

- 対象 OT は **`ResultPayload` を持つ observed OutputTransition のみ**。Prediction-only OT への attach は将来拡張で扱う。
- `--matched-prediction` は受け付けない。既存 ResultPayload の `matched_prediction_output_id` が source of truth。
- `--status` / `--summary` / `--artifact` / `--raw-output` / `--log` / `--metric` / `--error` も受け付けない。既存 ResultPayload の意味内容を `git finish` で変更しない。

#### 整合性検証

`finish` は次の検証を必ず行います。

1. GitSession が存在する。
2. GitSession が current run に属している。
3. GitSession がまだ closed でない。
4. `session.input_transition_id` が存在する。
5. `session.input_transition_id` が active である。
6. `--matched-prediction` 指定時、その OT が存在する。
7. `--matched-prediction` 指定時、その OT が `PredictionPayload` を持つ。
8. `--matched-prediction` 指定時、その OT の `input_transition_id` が `session.input_transition_id` と一致する。
9. `--output-transition` 指定時、その OT が存在する。
10. `--output-transition` 指定時、その OT の `input_transition_id` が `session.input_transition_id` と一致する。
11. `--output-transition` 指定時、その OT が active である。
12. `--output-transition` 指定時、その OT が `ResultPayload` を持つ。
13. `--output-transition` 指定時、`--matched-prediction` が指定されていない。
14. `--output-transition` 指定時、ResultPayload 変更系 option が指定されていない。
15. 現在の repo root が `session.repo_root` と一致する。
16. 現在の branch が `session.base_branch` と一致する。
17. finish 時点の working tree が clean である（tracked files について）。
18. finish 時点が detached HEAD ではない。

#### Warning

error にせず warning に留めるケース:

- **Duplicate observation (形式 A)**: 同じ `InputTransition` に active な ResultPayload 付き OT がすでに存在する。`--output-transition <existing_ot>` の利用を促す。
- **Duplicate GitChangePayload (形式 B)**: 指定 OT に既に GitChangePayload が attach されている。複数 attach は技術的に許可。
- **Parallel session**: 同じ `InputTransition` に紐づく別の open GitSession が存在する。MVP では複数 session 同時存在を許可。
- **Empty diff**: `base_commit == HEAD` または差分が空。空の payload を通常通り attach する。

#### Atomicity / write ordering

```
1. Git から log / diff / patch をすべて読み取る
2. GitChangePayload の payload_id を確保
3. <run_dir>/artifacts/git/ が無ければ作成
4. patch artifact を一時ファイルに書き込む
5. 一時 patch を <run_dir>/artifacts/git/<payload_id>.patch に atomic rename
6. graph 変更を 1 transaction として保存
   - sqlite store: DB transaction
   - jsonl store: 一括 append / save
7. graph 保存成功後に GitSession を closed として更新
8. current.json が当該 session を指していれば clear、別 session を指していれば触らない
```

GitSession 更新または `current.json` 更新が失敗しても `GitChangePayload` が source of truth です。次回 status は session と payload を照合し、closed recovery warning を出せるようにします。

形式 A の graph transaction は最低でも new Node + new OutputTransition + new ResultPayload + new GitChangePayload を含み、形式 B は new GitChangePayload のみを含みます。

#### 出力

```json
{
  "created": {
    "output_transition_id": "ot_0003",
    "result_payload_id": "pl_0007",
    "git_change_payload_id": "pl_0008"
  },
  "linked": {
    "input_transition_id": "it_0001",
    "matched_prediction_output_id": "ot_0001"
  },
  "git": {
    "base_commit": "abc123",
    "head_commit": "def456",
    "branch": "feat/git-integration",
    "commits": 2,
    "files_changed": 4,
    "patch_artifact": "artifacts/git/pl_0008.patch"
  },
  "warnings": [],
  "next": [
    "stag trace --from-node n_0003",
    "stag git diff --output-transition ot_0003"
  ]
}
```

`next` hints は JSON 出力に含めて構いません。既存 CLI の出力方針と衝突する場合は `--json` 時のみ含めるなど、実装時に既存 CLI との一貫性を優先します。

### `stag git status`

STAG run と Git repository の現在状態を同時に確認します。

出力内容:

- current run id
- active Git sessions in the current run
- current session pointer (あれば)
- repository root / branch / HEAD commit / dirty state / untracked files count
- latest GitChangePayload in the current run (あれば)

`latest GitChangePayload` は current run 内の active OutputTransition に attach された GitChangePayload のうち payload id / creation order が最も新しいものとします。MVP では `current view` に依存した status は定義しません。

### `stag git diff`

```bash
stag git diff <session_id>                       # session の base..HEAD diff (commit 済み)
stag git diff --output-transition <ot_id>        # 当該 OT に attach された patch_artifact を表示
```

1 OT に複数 GitChangePayload が attach されている場合は一覧を出し、payload id 指定を求める。MVP では dirty working tree diff は含めない。将来 `--payload <pl_id>` を追加する余地を残す。

### `stag git log`

```bash
stag git log <session_id>                        # session の base..HEAD commit log
stag git log --output-transition <ot_id>         # 当該 OT の commit_log を表示
```

複数 GitChangePayload 時の挙動は `git diff` と同じく、一覧 + payload id 指定。

## 使い方例

予測ありの標準フロー:

```bash
stag plan --input-node n_0000 --intent "add Git payload support"
stag git start it_0001
stag predict it_0001 --max-outcomes 2

# edit files
# git commit -m "Add Git integration payloads"

stag git finish gs_0001 \
  --matched-prediction ot_0001 \
  --summary "Added GitSession and GitChangePayload MVP" \
  --status completed
```

予測なしの軽量フロー:

```bash
stag plan --input-node n_0000 --intent "fix docs typo"
stag git start it_0001

# edit files
# git commit -m "Fix docs typo"

stag git finish gs_0001 --summary "Fixed typo in docs" --status completed
```

先に observe してから Git payload を attach するフロー:

```bash
stag observe it_0001 --status completed
stag git finish gs_0001 --output-transition ot_0003
```

## MVP スコープ

MVP で実装するもの:

1. `GitSession` の保存と読み込み
2. `GitChangePayload` の追加
3. `stag git start` / `finish` / `status` / `diff` / `log`
4. branch 切替・detached HEAD・finish 時 dirty の error 検出
5. duplicate observation / duplicate GitChangePayload / parallel session / empty diff の warning
6. 形式 A の `ResultPayload` 合成
7. 固定された Git semantics (log / diff / patch)
8. current session pointer の cleanup

MVP で実装しないもの:

- `transition` / `trans` namespace
- `--include-dirty` / dirty diff support
- GitHub PR 連携 / worktree 連携 / branch 自動作成
- prediction patch 生成
- `plan` と `git start` の統合 shortcut
- first-parent log mode / format-patch artifact

## 将来拡張

- **`plan` + `git start` 統合**: 2 段が冗長なら `stag plan --git ...` または `stag git plan ...` を追加。
- **GitHub PR 連携**: `stag git pr create --output-transition ot_X`。
- **Worktree 連携**: STAG view と Git worktree を対応させる (`stag git worktree create --view exp-a`)。
- **GitRefPayload**: PR / remote branch / tag / release への参照を保存する payload。
- **Large commit log**: payload 内ではなく `log_artifact` に逃がす。
- **Dirty diff support**: `--include-dirty` 導入時に `status_after` や dirty patch artifact を再設計する。

## 未決事項

### 1 OT に複数 GitChangePayload を許可するか

技術的には許可します。通常は 1 つを推奨。複数 attach 時は `stag git diff --output-transition` / `stag git log --output-transition` が一覧を出し、明示的な payload id 指定を求めます。

### closed GitSession の扱い

closed session は削除しません。`closed_at` / `closed_by` / `output_transition_id` を埋めて残します。ただし closed session は GitChangePayload の source of truth ではありません。確定後の source of truth は OT に attach された GitChangePayload です。

## 合意した判断

1. Git payload は `OutputTransition` に attach する。
2. `start` は payload を作らず、pending GitSession を作る。
3. `finish` は `observe` の sugar として使える。
4. `finish --output-transition` で既存 output に Git payload だけを attach できる。
5. `finish` は session と OutputTransition / matched prediction の InputTransition 整合性を必ず検証する。
6. GitSession は run directory 配下に保存する。
7. patch artifact は payload id ベースで命名する。
8. MVP では `transition` / `trans` namespace を入れない。
9. MVP では `--include-dirty` を入れない。
10. `plan` / `predict` / `observe` は top-level command を正規として扱う。
11. MVP では branch 切替を error とする。
12. MVP では finish 時 dirty state を error とする。
13. `repo_root` は absolute path として保存する。
14. 形式 A の finish で既存 observed output がある場合は warning を出す。
15. finish は patch artifact 書き込み → graph transaction → session close の順序を守る。
16. detached HEAD は MVP では error とする。
17. 形式 B では `--matched-prediction` と ResultPayload 変更系 option を reject する。
18. Git log / diff / patch は `base_commit..HEAD` の unified diff semantics に固定する。
19. `git status` は current view に依存せず、current run 内の最新 GitChangePayload を表示する。
20. empty diff は warning として通常通り GitChangePayload を attach する。
21. clean working tree は tracked files の clean 状態を指し、untracked files は MVP では許容する。
22. 形式 B は `ResultPayload` を持つ observed OutputTransition のみに許可する。
23. finish 成功時、current pointer が当該 session を指していれば clear する。

## 設計の中心思想

Git integration は STAG の core graph を複雑にするためのものではありません。STAG が記録したいのは次の対応関係です。

```text
なぜやったか       -> PlanPayload
どうなると思ったか -> PredictionPayload
実際どうなったか   -> ResultPayload
何が変わったか     -> GitChangePayload
```

この 4 つが `InputTransition` と `OutputTransition` を通じて自然につながることを最優先にします。
