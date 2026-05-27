# Direction

正準グラフモデル:

```text
Node -> Transition -> Node -> Transition -> Node
```

`Transition` は必ず 1 つの output Node を持ちます（single-output）。
fan-out は sibling Transitions（同じ input から複数の Transition）で表現します。

Transition の種類・意味は attached payload の `type` フィールドで区別します。
`transition_kind()` メソッドも専用の record type も持ちません。

core は standalone で、git には依存しません。git 連携は標準 extension
`stag.ext.git` が提供します。正式 CLI は `stag git <verb>` で、`stag commit`
などの日常用 command は default alias として解決されます。

今後の UI は DAG を図として表示し、選択した node / transition の
payload だけを詳細表示する方針です。

## Roadmap: git worktree-aware な workflow

現在の `work-session` が分離するのは STAG run / session の attribution のみで、
Git の working tree 自体は分離しません。本格的に複数 agent が同時編集する
ワークフローを first-class にするため、Git extension 側に worktree awareness
を持たせる予定です:

- Git extension が最終的に `git worktree` を管理 / attach する。
- `WorkSession` の metadata に workspace の種別・path・branch・base ref・
  repo root を記録できるようにする。
- これにより、各 agent には物理的な workspace が割り当てられつつ、STAG は
  context / 試行 / 決定の論理グラフを引き続き保持する。

実装はまだコミットされていません。あくまで方向性メモです。
