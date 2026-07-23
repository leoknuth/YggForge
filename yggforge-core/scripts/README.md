# Scripts

## 目录

- [1. 这一层是什么](#1-这一层是什么)
- [2. 目录结构](#2-目录结构)
- [3. 核心入口](#3-核心入口)
- [4. 日常用法](#4-日常用法)

---

## 1. 这一层是什么

`yggforge-core/scripts/` 是 `YggForge` 的自动化与运维层（位于可部署核心包内）。

这里放的是：

- 部署 / 同步脚本
- 记忆层脚本
- 摄取 / 提炼 / 索引辅助脚本
- 知识图与标签管理
- 行为策略（写操作门禁）

它们服务于：

- [../knowledge/README.md](../knowledge/README.md)
- [../profiles/README.md](../profiles/README.md)

## 2. 目录结构

按职责分层：库模块入子包，叶子 CLI 入 `cmds/<领域>/`，钩子检测入 `hooks/`。

```text
scripts/
├── ygg.py                  # 统一入口（薄：解析 argv → cli.*）
├── ygg.ps1 / ygg.sh        # shell 包装（Windows 用 -X utf8）
├── deploy.{ps1,sh}         # 兼容包装：新风格→ygg；旧 --action → cmds/ops/deploy.py
├── git_sync.{ps1,sh}       # 兼容包装：→ ygg sync/push；旧 --action → cmds/ops/git_sync.py
├── cli/                    # ygg 路由器库（非叶子 CLI）
│   ├── errors.py
│   ├── runtime.py          #   subprocess / behavior 门禁 / sync 编排（经 leaf_scripts 解析）
│   ├── intent.py
│   └── routes.py
├── lib/                    # 公共基础库
│   ├── common.py
│   ├── repo_paths.py
│   ├── front_matter.py
│   └── leaf_scripts.py     #   叶子 CLI 短名 → 相对路径
├── policies/               # 治理策略
│   ├── behavior.py
│   ├── core_write.py
│   └── channel.py
├── backends/               # 记忆后端
│   ├── factory.py
│   └── file_backend.py
├── knowledge/              # 知识图与标签（库）
│   ├── graph*.py / shard_store.py / tag_*.py
│   ├── knowledge_id.py
│   └── schema.py
├── hooks/
│   └── trigger_detector.py # Cursor pre_submit 意图检测
└── cmds/                   # 叶子 CLI（被 ygg subprocess 调）
    ├── ops/                #   deploy / git_sync / git_risk_check / apply_credentials_mcp
    ├── memory/             #   remember / recall / dream
    ├── pipeline/           #   ingest / distill / promote
    ├── graph/              #   associate / graph_index / index_knowledge / tag_*
    ├── project/            #   project_mdc
    └── tools/              #   一次性迁移等（migrate_knowledge_front_matter）
```

约定：

- **库模块**被 import；调用方保证 `scripts/` 在 `sys.path`（叶子脚本用 `SCRIPTS_ROOT` 自举；`run_python` 也会设 `PYTHONPATH`）。
- **叶子 CLI** 在 `cmds/<领域>/`，由 `ygg.py` → `cli.runtime.run_python` 按短名（见 `lib/leaf_scripts.py`）拉起。
- **不要**再往 `scripts/` 根堆新的 `.py` 叶子；新命令选已有领域目录，或新增一层领域子目录并登记到 `LEAF_SCRIPTS`。

## 3. 核心入口

- 仓库根 `ygg.ps1` / `ygg.sh` → `scripts/ygg.py`（推荐唯一入口）
- `deploy.{ps1,sh}` / `git_sync.{ps1,sh}`：兼容双风格薄包装

## 4. 日常用法

```powershell
.\ygg.ps1 status cursor
.\ygg.ps1 deploy link cursor
.\ygg.ps1 associate --tag latte --json
.\ygg.ps1 tag --language
.\ygg.ps1 graph check
.\ygg.ps1 project mdc --check
```

更多：

- [../../docs/reference/ygg-cli.md](../../docs/reference/ygg-cli.md)
- [../../docs/guide/deploy.md](../../docs/guide/deploy.md)
- [../../docs/reference/sync.md](../../docs/reference/sync.md)
- [../../docs/guide/usage.md](../../docs/guide/usage.md)
