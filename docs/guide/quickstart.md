# 快速开始

## 目录

- [1. 最短路径](#1-最短路径)
- [2. 准备](#2-准备)
- [3. 配一个本机覆盖文件](#3-配一个本机覆盖文件)
- [4. 看状态](#4-看状态)
- [5. 先用 link 模式部署](#5-先用-link-模式部署)
- [6. 如果 link 失败](#6-如果-link-失败)
- [7. 验证](#7-验证)
- [8. 后续工作方式](#8-后续工作方式)
  - [link 模式](#link-模式)
  - [copy 模式](#copy-模式)
- [9. 再往下看什么](#9-再往下看什么)

---

## 1. 最短路径

如果你只想尽快把 `YggForge` 接到 Cursor（默认 target）上，按下面做。其他 Agent（Codex / OpenCode / Claude / OpenClaw）见 [deploy.md](deploy.md)。

## 2. 准备

- 已安装 Git
- 已安装 Python 3（标准库即可跑核心功能；**推荐** `pip install pyyaml`——无 PyYAML 时仅能用内置最小 YAML 解析器，复杂 `tag-graph.yaml`（带 `weight` 的边）与 `behavior.defaults.yaml` 可能解析不全）
- 缺依赖可一键补装：`.\ygg.ps1 doctor --fix-deps`（按 `requirements.txt` 自动检测并安装，经 behavior 门禁）
- 已 clone 本仓库

## 3. 配一个本机覆盖文件

新建：

- `yggforge-runtime/config/deploy.local.json`

最小示例（启用 cursor；路径用 `deploy.defaults.json` 中的平台默认值 `~/`）：

```json
{
  "cursor": {
    "enabled": true
  }
}
```

如需覆盖某条映射的目标路径，用 `mappings` 结构（与 `deploy.defaults.json` 合并）。注意 Cursor
**用户级**只投影 `hooks`（Cursor 原生不加载全局 `~/.cursor/AGENTS.md` 与 `~/.cursor/rules/`）：

```json
{
  "cursor": {
    "enabled": true,
    "mappings": [
      { "name": "hooks", "target": "~/.cursor/hooks" },
      { "name": "hooks_config", "target": "~/.cursor/hooks.json" }
    ]
  }
}
```

## 4. 看状态

Windows:

```powershell
.\ygg.ps1 status
```

Linux:

```bash
./ygg.sh status
```

（无参时默认 target 为 `cursor`。）

## 5. 先用 link 模式部署

Windows:

```powershell
.\ygg.ps1 deploy link cursor
```

Linux:

```bash
./ygg.sh deploy link cursor
```

部署 `cursor` 时会安装：

- 用户级强制钩子：`~/.cursor/hooks/` + `~/.cursor/hooks.json`（官方支持，启动时加载）
- 核心包：`~/.cursor/yggforge-core/`（link/junction，含 knowledge/profiles/scripts/graph）

> **重要（Cursor 官方限制）**：Cursor 原生只加载**项目级** `.cursor/rules/*.mdc`，不加载全局
> `~/.cursor/AGENTS.md` 与 `~/.cursor/rules/`。因此 YggForge 用户级部署对 Cursor **只投影 hooks**。
> 规则与项目入口请用项目级部署 `ygg deploy --scope project --project-root <你的仓库> cursor`
> （投影到 `<repo>/.cursor/rules/*.mdc`，Cursor 会自动加载）。详见 [deploy.md](deploy.md)「项目级部署」。

## 6. 如果 link 失败

改用：

```powershell
.\ygg.ps1 deploy copy cursor
```

## 7. 验证

1. 重启 Cursor（hooks.json 仅启动时加载）
2. **Customize → Hooks** 中看到 `beforeSubmitPrompt` 与 `sessionStart`
3. 发一条消息后检查 `~/.cursor/ygg_hook_heartbeat.txt` 是否更新
4. `.\ygg.ps1 status` 显示 cursor 映射 `target_exists: True`

可选：验证联想（咖啡教学 / 狞猫彩蛋）：

```powershell
.\ygg.ps1 associate --tag coffee --tag latte --hop 2 --json
.\ygg.ps1 associate --tag caracal --hop 2 --json
.\ygg.ps1 associate --tag 狞猫 --hop 2 --json   # 经 tag-synonyms 归并为 caracal
```

## 8. 后续工作方式

### link 模式

改仓库真源 → Agent 侧立即可见（junction/symlink 生效时）。

### copy 模式

改仓库后需再 `ygg deploy copy cursor`（或删掉已 copy 的单文件后再 `link`）。

## 9. 再往下看什么

- [install.md](install.md) — 安装与排错
- [deploy.md](deploy.md) — 部署细节与多 target
- [usage.md](usage.md) — 日常 `ygg` 用法
- [../reference/triggers.md](../reference/triggers.md) — 触发与综合回答
