# CLI

## 基本フロー

```bash
stag init req_demo --run-id demo
stag transition create --run demo --from <root_node_id> --payload-type transition_payload --field type=experiment --field lr=0.01
stag payload add --run demo --node <node_id> --payload-type node_payload --field type=note --field text="observed result"
stag cut node <node_id> --run demo --reason "不採用"
stag graph dump --run demo --format outline
```

## コマンド一覧

- `stag init <req_id>` — 新規 run 作成
- `stag list` — run 一覧
- `stag use <run_id>` / `stag current` — active run ポインタ管理

### Node

- `stag node show <node_id>` — Node を表示
- `stag node payloads <node_id>` — Node の payload を表示

### Transition

- `stag transition create --from NODE --payload-type TYPE --field key=value` — 1 Transition と 1 output Node を作成
- `stag transition show <transition_id>` — Transition を表示
- `stag transition output <transition_id>` — output Node を表示
- `stag transition inputs <transition_id>` — input Node IDs を表示
- `stag transition payloads <transition_id>` — Transition の payload を表示

複数案を作る場合は、同じ input node から `transition create` を複数回実行します。

### Payload

- `stag payload types` — 登録済み `payload_type` を表示
- `stag payload schema <payload_type>` — payload type の入力 field を表示
- `stag payload add --node NODE --payload-type TYPE --field key=value` — Node に payload を追加
- `stag payload add --transition TRANSITION --payload-type TYPE --field key=value` — Transition に payload を追加
- `stag payload list --node NODE` / `stag payload list --transition TRANSITION` — payload 一覧
- `stag payload show <payload_id>` — payload を表示

### Cut / Git

- `stag cut node <node_id>` / `stag cut transition <transition_id>` — CutPayload を追加

git 連携は標準 extension です。正式な command namespace は `stag git ...` で、
日常用の `stag commit` などは default alias として残ります。

- `stag init <req_id> --extension git` — run で git extension を有効化
- `stag git commit -m "message"` / `stag commit -m "message"` — git commit を駆動して Transition を記録
- `stag git branch list` / `stag branch list` — 記録済み branch 一覧
- `stag git branch show <name>` / `stag branch show <name>` — branch tip と member を表示
- `stag git revert --sha SHA` / `stag revert --sha SHA` — revert を駆動して記録
- `stag git cherry-pick --sha SHA` / `stag cherry-pick --sha SHA` — cherry-pick を駆動して記録
- `stag git merge --other branch:<name>` / `stag merge --other branch:<name>` — merge を駆動して記録
- `stag git reset --node NODE --mode hard` / `stag reset --node NODE --mode hard` — reset と current 移動を記録
- `stag git verify` / `stag verify` — git descendant 制約を検証
- `stag git hook install` / `stag hook install` — git hooks を install
- `stag git add --transition T --commit SHA` — Transition に commit hash を紐づける
- `stag git list --transition T` — 紐づいた commit hash を表示
- `stag git show --transition T` — GitChangePayload を表示
- `stag git worktree add <path> [branch] [--base REF] [--existing-branch]` — `git worktree add` の薄いラッパ。`branch` 省略時はパス末尾の名前で新規 branch を作成。
- `stag git worktree list` — `git worktree list --porcelain` を JSON にパースして表示。
- `stag git worktree remove <path> [--force]` — `git worktree remove` の薄いラッパ。

### Worktree attachment

- `stag work-session start --worktree PATH` / `stag work-session env --new --worktree PATH` / `stag work-session spawn --worktree PATH -- <cmd>` — 解決済み worktree path (＋ current branch / `git --git-common-dir`) を `WorkSession.metadata["worktree"]` に記録し、`STAG_GIT_WORKTREE=PATH` を export する。
- `STAG_GIT_WORKTREE` 環境変数 — セットされていると、すべての git verb (`stag git commit / revert / cherry-pick / merge / reset / verify` と post-rewrite hook) は git サブプロセスを `cwd=$STAG_GIT_WORKTREE` で実行する。`stag git worktree add` と組み合わせることで、同じ STAG run を共有しつつ各 agent に独立した checkout を渡せる。

### Graph

- `stag graph dump [--format outline|mermaid]` — graph を描画
- `stag graph trace <node_id>` — 履歴を遡る
- `stag graph reachable <node_id>` — active subgraph を表示

## 互換コマンド

`stag show`, `stag dump`, `stag trace`, `stag reachable`, `stag outcomes` は残っていますが、新しい CLI では `node` / `transition` / `payload` / `graph` namespace を優先します。

## 廃止コマンド

`stag plan`, `stag predict`, `stag observe`, `stag note` は削除済みです。
