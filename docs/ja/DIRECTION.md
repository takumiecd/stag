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
