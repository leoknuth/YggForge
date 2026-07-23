# yggforge-runtime

**本机运行时层**（`RUNTIME_ROOT`）。机器相关、可变、默认不入库。

## 放什么

| 子目录 | 内容 |
| --- | --- |
| `memory/raw/` | `ygg remember` 写下的 observation |
| `memory/index/` | 本地索引缓存、`ygg dream` 报告等 |
| `cache/` | 其它本机缓存 |
| `config/` | `deploy.local.json` / `memory.local.json` / `sync.local.json` / `graph.local.json` / `core_write.local.json` / **`behavior.local.yaml`** |

## 与核心包的关系

- 真源与脚本在 `yggforge-core/`
- CLI 通过 `repo_paths.RUNTIME_ROOT` 读写本目录
- 晋升到 `knowledge/` 仍须 `ygg promote`（写入核心包，可提交）

本目录整树默认 gitignore；只保留本 README。
