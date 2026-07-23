# 安装文档

## 目录

- [1. 适用范围](#1-适用范围)
- [2. 前置要求](#2-前置要求)
  - [通用要求](#通用要求)
  - [若使用 `link` 模式](#若使用-link-模式)
- [3. 获取仓库](#3-获取仓库)
- [4. 配置部署目标](#4-配置部署目标)
- [5. 选择部署模式](#5-选择部署模式)
  - [推荐：`link`](#推荐-link)
  - [兼容：`copy`](#兼容-copy)
  - [特殊：`render`](#特殊-render)
- [6. 执行安装与部署](#6-执行安装与部署)
  - [Windows](#windows)
  - [Linux](#linux)
- [7. 验证是否生效](#7-验证是否生效)
- [8. copy 模式下如何回收](#8-copy-模式下如何回收)
- [9. 常见问题](#9-常见问题)
  - [链接创建失败](#链接创建失败)
  - [改了全局文件但仓库里没变化](#改了全局文件但仓库里没变化)
  - [`status` 显示路径不对](#status-显示路径不对)
- [10. 推荐首次安装顺序](#10-推荐首次安装顺序)

---

## 1. 适用范围

本文说明如何在 Windows 或 Linux 上安装并部署 `YggForge`。

目标包括：

- 把仓库放在本机一个固定位置
- 为 Cursor / Codex / OpenCode / Claude / OpenClaw 配置入口
- 选择合适的部署模式（用户级 `--scope user` 或项目级 `--scope project`）
- 验证部署是否生效

## 2. 前置要求

### 通用要求

- Git
- Python 3
- **推荐** `pip install pyyaml`：无 PyYAML 时仅用内置最小 YAML 解析器，复杂 `tag-graph.yaml`（带 `weight` 的边）与 `behavior.defaults.yaml` 可能解析不全
- 可用的命令行环境

> **自动检测与补装**：`ygg doctor` 会按 `yggforge-core/scripts/requirements.txt` 逐条检测依赖并报黄/绿。缺失时一键补装：
>
> ```powershell
> .\ygg.ps1 doctor --fix-deps            # 经 behavior 门禁 deps.install（默认 ask）
> .\ygg.ps1 doctor --fix-deps --yes      # 非交互直接补装（CI 友好）
> ```
>
> 也可在部署时顺带补装：
>
> ```powershell
> .\ygg.ps1 deploy link cursor --install-deps   # 部署前检测并补装缺失依赖
> ```
>
> 依赖清单见 `yggforge-core/scripts/requirements.txt`；新增依赖只需加一行，`doctor` 自动覆盖。
  - Windows: PowerShell 或 PowerShell Core
  - Linux: Bash

### 若使用 `link` 模式

还需要：

- 目标平台支持符号链接
- 当前用户对目标路径有写权限

Windows 下如果链接创建失败，常见原因包括：

- 当前 PowerShell 没有足够权限
- 系统未启用开发者模式
- 某些目录策略限制了 symlink 创建

这时可以先退回 `copy` 模式验证链路。

## 3. 获取仓库

```bash
git clone <YOUR_GIT_HOST>/<YOUR_NAMESPACE>/yggforge.git
cd yggforge
```

把仓库放在固定工作目录即可，例如：

- Windows: `C:\work\YggForge` 或任意盘符下的路径
- Linux: `~/work/YggForge`

## 4. 配置部署目标

默认配置文件：

- `yggforge-core/config/deploy.defaults.json`

本机覆盖配置：

- `yggforge-runtime/config/deploy.local.json`

建议做法：

- 不直接改 `deploy.defaults.json`
- 在 `deploy.local.json` 中只写本机差异

最小示例（启用 cursor，路径用默认平台值 `~/`）：

```json
{
  "cursor": {
    "enabled": true
  }
}
```

如需覆盖目标路径，用 `mappings` 结构（与默认配置合并）。注意 Cursor **用户级**不再投影
`AGENTS.md` 与 `rules/`（Cursor 原生不加载全局 `~/.cursor/AGENTS.md` 与 `~/.cursor/rules/`），
仅投影 `hooks`（官方支持）。规则与项目入口请用项目级部署（见 [deploy.md](deploy.md)）。

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

Linux 下 `~/` 展开与 Windows 相同（由 deploy 脚本 `expanduser`）。多目标（Codex/OpenCode/Claude/OpenClaw）见 [deploy.md](deploy.md)。

## 5. 选择部署模式

### 推荐：`link`

适用于：

- 目标工具能稳定读取符号链接
- 你希望所有修改直接回到仓库

优点：

- 同步最简单
- 不需要额外 `import`

### 兼容：`copy`

适用于：

- 链接权限受限
- 工具对 symlink 支持不稳定

缺点：

- 如果改动发生在全局副本里，要显式 `import`

### 特殊：`render`

适用于：

- 某个 Agent 需要短入口或专用渲染格式

当前它还是基础实现，后续可以继续增强。

## 6. 执行安装与部署

### Windows

查看状态：

```powershell
.\ygg.ps1 status
```

执行 link 部署：

```powershell
.\ygg.ps1 deploy link cursor
```

执行 copy 部署：

```powershell
.\ygg.ps1 deploy copy cursor
```

> 兼容旧入口：`deploy.ps1 --action status --targets cursor` 仍可用（薄包装会识别旧旗标并直调 `cmds/ops/deploy.py`）。推荐统一用 `ygg`。

### Linux

查看状态：

```bash
./ygg.sh status
```

执行 link 部署：

```bash
./ygg.sh deploy link cursor
```

执行 copy 部署：

```bash
./ygg.sh deploy copy cursor
```

## 7. 验证是否生效

建议检查三件事：

1. `status` 是否能显示正确的 `source` 和 `target`
2. 目标路径是否真实存在
3. 若为 `link` 模式，目标路径是否真的是链接

还可以直接打开目标 Agent 的全局目录，确认入口文件已经出现。

部署 `cursor` target 时额外验证：

- `~/.cursor/hooks.json` 与 `~/.cursor/hooks/` 是否就位（**用户级** hooks，官方支持）
- 用户级**不再**投影 `AGENTS.md` 与 `rules/`（Cursor 原生不加载全局 `~/.cursor/AGENTS.md` 与 `~/.cursor/rules/`）；规则与项目入口请用项目级部署 `ygg deploy --scope project cursor`（投影到 `<repo>/.cursor/rules/*.mdc`，见 [deploy.md](deploy.md)「项目级部署」）
- 推荐依赖：`pip install pyyaml`（无 PyYAML 时复杂 `tag-graph.yaml` / `behavior.defaults.yaml` 可能解析不全，见第 2 节）
- 新开会话后 Cursor **Hooks** 设置页显示 `beforeSubmitPrompt` 与 `sessionStart`

验证链接类型（PowerShell，用户级 hooks）：

```powershell
Get-Item $env:USERPROFILE\.cursor\hooks, $env:USERPROFILE\.cursor\yggforge-core |
  Select-Object Name, LinkType, Target
```

- `hooks`、`yggforge-core` 期望 `Junction` 或 `SymbolicLink`

项目级部署验证（PowerShell）：

```powershell
ygg deploy --scope project --project-root <你的仓库> cursor
Get-Item <你的仓库>\.cursor\rules, <你的仓库>\.cursor\hooks |
  Select-Object Name, LinkType, Target
```

## 8. copy 模式下如何回收

只有在 `copy` 或 `render + copy` 时才需要：

```powershell
.\ygg.ps1 import cursor
```

或：

```bash
./ygg.sh import cursor
```

如果最近一次部署模式是 `link`，执行 `import` 会直接提示 `no-op`。

## 9. 常见问题

### 链接创建失败

先确认：

- 当前用户是否对目标目录有写权限
- 系统是否允许创建 symlink
- 目标路径是否已存在普通文件

必要时先切换到 `copy` 模式。

### Cursor 用户级看不到 AGENTS.md / rules

这是**预期行为**。Cursor 原生不加载全局 `~/.cursor/AGENTS.md` 与 `~/.cursor/rules/`，因此 YggForge
用户级部署对 Cursor **只投影 hooks**（官方支持）。规则与项目入口请用项目级部署：

```powershell
ygg deploy --scope project --project-root <你的仓库> cursor
```

投影到 `<repo>/.cursor/rules/*.mdc`（Cursor 会自动加载项目级 rules）与 `<repo>/.cursor/hooks`。
详见 [deploy.md](deploy.md)「项目级部署」。

### 改了全局文件但仓库里没变化

通常说明你当前不是 `link` 模式，或者目标路径不是链接。

先运行：

```bash
status
```

确认最近一次部署模式，再决定是否需要 `import`。

### `status` 显示路径不对

优先检查：

- `yggforge-core/config/deploy.defaults.json`
- `yggforge-runtime/config/deploy.local.json`

### hook 中文乱码（Cursor Windows 已知 bug）

本机若 `chcp` 为 936（GBK）且未开系统 UTF-8，Cursor 把 hook 的 stdin JSON 按系统代码页写入，中文会双重编码或变成 `?`。这是 Cursor 官方/社区已确认的问题，不是 YggForge 脚本单独的问题：

| 现象 | 论坛帖 |
| --- | --- |
| 双重编码（UTF-8→GBK→UTF-8 乱码） | [Forum #159259](https://forum.cursor.com/t/hook-stdin-pipe-double-encodes-non-ascii-on-non-utf-8-windows/159259)（官方建议 Beta UTF-8 或 `pwsh`） |
| stdin 污染、建议读 `transcript_path` | [Forum #162295](https://forum.cursor.com/t/windows-cursor-hooks-stdin-corrupts-utf-8-text-before-hook-script-receives-it/162295) |
| 中文被换成 `?` | [Forum #142878](https://forum.cursor.com/t/windows-cursor-hooks-corrupt-chinese-utf-8-characters-in-stdin-replaced-with-question-marks/142878) |
| execution.log 正确、stdin 已是 `?` | [Forum #146604](https://forum.cursor.com/t/on-windows-chinese-prompt-in-hooks-stdin-becomes-while-execution-log-shows-correct-text/146604) |

**推荐绕过（任选）：**

1. **系统 UTF-8（最彻底）**：`Win+R` → `intl.cpl` → 管理 → 更改系统区域设置 → 勾选「Beta：使用 Unicode UTF-8 提供全球语言支持」→ **重启电脑**。
2. **安装 PowerShell 7**：把 `pwsh` 放进 PATH；Cursor 会优先用它跑 hook，I/O 默认 UTF-8（个别版本仍无效，可再试方案 1）。
3. **本仓库已做代码绕过**：`ygg_pre_submit.py` 在 Windows 上优先从 stdin 里的 `transcript_path`（ASCII 路径）读取 JSONL 中最近 `<user_query>`（文件本身是合法 UTF-8，见 #162295），不再依赖被污染的 `prompt` 字段；并保留 mbcs 回环作为兜底。Windows 入口用 `py -X utf8`（`hooks.windows.json`）。实现注释见脚本模块 docstring 与 `profiles/cursor/hooks/README.md`。

验证：发中文消息后看 `last_trigger.json` 的 `prompt` 与 `prompt_field`（应为 `transcript_path` 或正确中文）。

### hook 取不到 prompt（`last_trigger.json` 恒为 skip 或不刷新）

若 `yggforge-runtime/cache/last_trigger.json` 恒为 `{"action":"skip","reason":"hook 未取到 prompt","prompt":""}`，或文件时间戳不随消息提交更新，说明 hook 没被 Cursor 真正调用，或被调用了但 stdin 没拿到内容。

排查步骤（按顺序）：

1. **重启 Cursor**。Cursor 只在启动时加载 `hooks.json`，会话中途新建/修改的不会自动生效。这是最常见的根因。
2. 重启后打开 **Customize → Hooks** 标签，确认 `sessionStart` 与 `beforeSubmitPrompt` 两条都出现。没出现说明 `hooks.json` 没被加载（检查 `~/.cursor/hooks.json` 是否存在、是否带 BOM——JSON 不应带 BOM）。
3. 发一条消息后看 `~/.cursor/ygg_hook_heartbeat.txt`：
   - 时间戳随消息更新 → hook 被 Cursor 调用了，继续下一步
   - 不更新 → hook 没被触发。Windows 上多半是 `py`/`python` 不在 Cursor GUI 进程的 PATH；本项目已改用 `py` launcher（`C:\Windows\py.exe`，系统级），若仍不生效检查 `py` 是否可执行
4. 看 heartbeat 行内容：
   - `raw_len=0` → stdin 为空（Cursor 没把 payload 喂进来）
   - `raw_len>0` 且 `prompt_ok=False` → JSON 有内容但字段提取失败。此时 hook 会强制写 `~/.cursor/ygg_debug_stdin.txt`，且 `last_trigger.json` 的 `stdin_keys` 会列出顶层 key:type。对照官方字段应是顶层 `prompt`（字符串）；若类型是 `list`/`dict`，脚本已尝试 coerce，仍失败则把 debug 文件里的结构反馈给维护者
   - `prompt_ok=True` → 提取成功，继续看 `last_trigger.json` 的 `action`
5. 也可设 `YGG_DEBUG_STDIN=1` 让每次调用都落盘 raw stdin（默认仅提取失败时落盘）
6. hook 执行报错看 Cursor 的 **Hooks output channel**（View → Output 选 Hooks）

hook 脚本已改为走 `sys.stdin.buffer.read()` 再 UTF-8 解码，并兼容 list/dict 形态的 `prompt`；传给 `trigger_detector` 时用环境变量 `YGG_TRIGGER_PROMPT`，避免 Windows argv 截断中文。Windows 用 `py` launcher、Linux 用 `python3`（见 `deploy.md` 第 6 节）。

## 10. 推荐首次安装顺序

1. clone 仓库
2. 配置 `deploy.local.json`
3. 先运行 `status`
4. 优先尝试 `link` 模式
5. 若失败，再切到 `copy`
6. 验证目标文件和 Agent 行为
