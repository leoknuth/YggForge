---
name: yggforge
description: >-
  YggForge 显式调用入口。在 OpenClaw 中提供 /yggforge 命令路由。
  自动触发语义：对写命令（remember/promote/deploy/sync/tag-add 等）附加 --yes
  以绕过 behavior 门禁；只读命令（status/recall/associate/graph-check）不加。
  真源：yggforge-core/plugins/skills/yggforge.md
---

# /yggforge 显式调用（OpenClaw）

当用户输入 `/yggforge <命令>` 时，按以下规则执行。

## 1. 显式调用 = 用户授权

用户主动输入 `/yggforge` 前缀，等同于声明"我要执行 YggForge 功能"。
因此：
- **对会修改状态的命令，自动附加 `--yes`**，绕过 ask/deny 门禁
- **不改状态的命令，正常执行，无需 `--yes`**
- 不等待二次确认，直接执行

安全边界：
- `--yes` 只绕过 ask/deny **行为门禁**，不改变命令本身的参数语义
- 不会把 `git push` 变成 force push
- 不会跳过用户显式指定的 `--dry-run`
- 若用户命令里已带 `--yes` 或 `--dry-run`，不再重复附加

## 2. 仓库路径

YggForge 仓库根目录：优先从环境变量 `YGGFORGE_REPO` 读取，未设置则默认：
`~/GitHub-Repositories/YggForge-local-private/`

下文命令中 `<REPO>` 均指此路径。

## 3. 命令路由表

| 用户输入 | 执行命令 | 是否需要 --yes |
|---------|---------|--------------|
| `/yggforge remember <内容>` | `cd <REPO> && ./ygg.sh remember --yes "<内容>"` | ✅ 是 |
| `/yggforge recall <查询>` | `cd <REPO> && ./ygg.sh recall "<查询>"` | ❌ 否 |
| `/yggforge associate --tag <标签>` | `cd <REPO> && ./ygg.sh associate --tag <标签>` | ❌ 否 |
| `/yggforge graph build` | `cd <REPO> && ./ygg.sh graph build` | ❌ 否 |
| `/yggforge dream` | `cd <REPO> && ./ygg.sh dream` | ❌ 否 |
| `/yggforge promote <entry> <target>` | `cd <REPO> && ./ygg.sh promote --yes <entry> <target>` | ✅ 是 |
| `/yggforge status` | `cd <REPO> && ./ygg.sh status` | ❌ 否 |
| `/yggforge deploy <target>` | `cd <REPO> && ./ygg.sh deploy --yes <target>` | ✅ 是 |
| `/yggforge sync <target>` | `cd <REPO> && ./ygg.sh sync --yes <target>` | ✅ 是 |
| `/yggforge tag --add <标签> <entry>` | `cd <REPO> && ./ygg.sh tag --add --yes <标签> <entry>` | ✅ 是 |
| `/yggforge tag --suggest <entry>` | `cd <REPO> && ./ygg.sh tag --suggest <entry>` | ❌ 否 |
| `/yggforge index --check` | `cd <REPO> && ./ygg.sh index --check` | ❌ 否 |
| `/yggforge doctor` | `cd <REPO> && ./ygg.sh doctor` | ❌ 否 |

> 若 `<REPO>` 下没有 `ygg.sh`（Windows 环境），改用 `./ygg.ps1`。

## 4. 与自动触发的关系

本 skill 只处理**显式调用**（`/yggforge` 前缀）。

AGENTS.md 中的**静默自动触发**仍然独立工作：
- 用户没说 `/yggforge`，但消息命中触发规则 → AGENTS.md 规则生效，静默执行 ygg
- 用户说了 `/yggforge` → 本 skill 接管，直接路由执行，不重复走 AGENTS.md 判定

两者互不冲突，互为补充。

## 5. 综合回答策略

当用户通过 `/yggforge` 调用且命令涉及检索（recall/associate）时：
1. 执行对应 ygg 命令获取结果
2. 结合模型自身推理
3. 必要时联网搜索
4. 综合三源作答，标注来源与置信度
