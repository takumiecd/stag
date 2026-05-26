# Git Integration

git 連携は標準 extension `stag.ext.git` として提供されます。core は git に依存せず、
git 固有の payload / event / verb / hook は extension 側にあります。

正式 CLI は `stag git <verb>` です。日常用の `stag commit`, `stag verify`,
`stag branch` などは default alias として `stag git ...` に解決されます。

```bash
stag init req_demo --extension git --run-id demo
stag git commit -m "record implementation"
stag commit -m "shortcut form"
stag git verify
```

Python API も extension namespace を使います。

```python
transition = run.git.commit(message="record implementation")
violations = run.git.verify()
```

詳細な設計背景は [EXTENSION_FRAMEWORK.md](EXTENSION_FRAMEWORK.md) と
[REDESIGN_GIT_NATIVE.md](REDESIGN_GIT_NATIVE.md) を参照してください。
