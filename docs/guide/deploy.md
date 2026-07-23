# 部署文档

## 目录

- [1. 部署目标](#1-部署目标)
- [2. 部署模式](#2-部署模式)
  - [`link`](#link)
  - [`copy`](#copy)
  - [`render`](#render)
- [2.1 `link` 和 `render` 的直观区别](#21-link-和-render-的直观区别)
- [2.2 它们可以组合](#22-它们可以组合)
  - [`link`](#link)
  - [`render + copy`](#render-copy)
  - [`render + link`](#render-link)
- [2.3 如何选择](#23-如何选择)
- [3. 同步语义](#3-同步语义)
  - [`link` 模式](#link-模式)
  - [`copy` 模式](#copy-模式)
  - [`render` 模式](#render-模式)
- [4. `yggforge-generated/` 约定](#4-yggforge-generated-约定)
- [5. 本地秘密与不应同步的内容](#5-本地秘密与不应同步的内容)
- [6. 部署对象](#6-部署对象)
  - [Cursor](#cursor)
  - [OpenCode](#opencode)
  - [Codex](#codex)
- [7. 统一部署脚本](#7-统一部署脚本)
- [8. 路径配置](#8-路径配置)
- [9. 推荐的本地配置分层](#9-推荐的本地配置分层)
- [10. 为什么部署层要独立](#10-为什么部署层要独立)

---

## 1. 部署目标

如果你只是想先跑通安装，请先看：

- [快速开始](quickstart.md)
- [安装文档](install.md)

本项目希望支持两类全局部署：

- 针对某一个 Agent 的定制部署
- 同时面向 Cursor / OpenCode / Codex 的兼容部署

部署原则：

- 仓库是唯一真源
- 默认优先使用 `link`
- 仅在必要时退化到 `copy`
- 非真源生成物统一进入 `yggforge-generated/`
- 部署核心语义必须跨平台一致

## 2. 部署模式

### `link`

把目标 Agent 识别的文件或目录直接链接到仓库中的投影文件。

特点：

- 默认模式
- 修改天然回流到仓库
- 不需要额外“回收同步”
- 日常只需 `git add / commit / push`

更准确地说，`link` 解决的是：

- **“目标位置如何指向仓库真源”**

它不改变文件内容本身，只改变“目标位置和仓库文件之间的关系”。

也就是说：

- 目标 Agent 看到的文件
- 实际上就是仓库里的那个文件

#### `link` 的例子

例如本机 Windows 上（默认 target 为 Cursor）：

- 仓库真源（核心包）：
  - `<REPO_ROOT>\yggforge-core\`
- 用户级目标（`ygg deploy link cursor`）：
  - `~/.cursor/yggforge-core`（整包）
  - `~/.cursor/hooks/` + `~/.cursor/hooks.json`（根钩子；协议硬路径）
  - > 注：用户级不再投影 `AGENTS.md` 与 `rules/`——Cursor 原生不自动加载 `~/.cursor/AGENTS.md`、`~/.cursor/rules/`。薄规则靠 hooks + 核心包内 Read 约定；要原生自动加载请用项目级部署（见下文「项目级部署」）。

若采用 `link` 模式，最终效果是：

- `~/.cursor/yggforge-core`
  - 指向 `<REPO_ROOT>\yggforge-core\`（Windows 上目录常用 junction）
- `~/.cursor/hooks.json` / `~/.cursor/hooks/`
  - 指向 `<REPO_ROOT>\yggforge-core\profiles\cursor\hooks.json` 等

此时：

- 你改全局位置，等于改仓库文件（真正 symlink/junction/hardlink 时）
- 你改仓库文件，Agent 也立刻看到

Windows 无符号链接特权时：目录回退为 junction；单文件尝试 symlink → 硬链接（须同卷）→ 复制并提示 `copied`（edits will not auto-flow back）。跨盘（如仓库在 E:、用户目录在 C:）时 `AGENTS.md` 几乎总会 copy。开启 **Developer Mode** 可恢复文件级 symlink。

#### 什么时候适合 `link`

- 目标工具支持 symlink / junction
- 你希望仓库成为唯一真源
- 你希望改动天然回流到 git 工作树

#### `link` 不做什么

- 不帮你生成新内容
- 不帮你缩写或改写入口文件
- 不帮你把多份知识合并成一份短文档

它只是把“现成文件”直接挂到目标位置。

### `copy`

将投影文件复制到目标位置。

特点：

- 兼容性最好
- 目标位置和仓库之间不再天然同源
- 若改动发生在目标位置，需要显式 `import` 回仓库
- `ygg sync <target>` / `ygg push <target>` 会先按 deploy manifest 执行 import，再进入 git sync

### `render`

先从仓库中选取规则、模板索引和入口说明，生成 Agent 专用入口文件，再执行 link 或 copy。

特点：

- 适合固定入口格式的工具
- 渲染结果属于生成物，不属于知识真源
- 渲染产物、清单、中间文件进入 `yggforge-generated/`
- 当前实现会把渲染结果写到 `yggforge-generated/rendered/`，再复制到目标位置

更准确地说，`render` 解决的是：

- **“仓库真源内容是否需要先被整理、缩写、拼装、改写成另一份投影文件”**

它作用在**内容层**，而不是“路径指向关系”这一层。

也就是说：

- 真源文件和目标文件不一定长得一样
- 目标文件可以是从真源生成出来的“派生入口”

#### `render` 的例子

假设你不想把完整规则树直接给 Agent，而是希望给它一个短入口：

- 真源：
  - `profiles/common/behavior-packs/karpathy-guidelines.md`
  - `knowledge/rules/agent-coding-discipline.md`
  - `knowledge/rules/cpp-style.md`
  - `knowledge/rules/performance-checklist.md`
- 目标：
  - `~/.codex/AGENTS.md`

如果采用 `render`，可以先生成一份新的短入口，例如：

- `yggforge-generated/rendered/codex/agents_entry/AGENTS.md`

这份生成物里可能只保留：

- 一个简短说明
- 一组优先级
- 几个高价值入口引用

然后再把这份生成物部署到：

- `~/.codex/AGENTS.md`

#### 什么时候适合 `render`

- 目标 Agent 更适合短入口，而不是完整知识树
- 你想把多份规则/模板/行为包压缩成一个入口文件
- 你想让不同 Agent 的入口风格不同，但底层真源一致

#### `render` 不等于 `copy`

当前实现里，render 之后的部署动作是复制，所以表面上看起来像 `copy`。

但两者不是一个概念：

- `copy`
  - 直接复制已有文件
- `render`
  - 先生成新文件，再部署新文件

因此：

- `copy` 作用在“部署动作”
- `render` 作用在“内容生成”

## 2.1 `link` 和 `render` 的直观区别

可以把它们理解成两个不同问题：

- `link`
  - **这个目标文件应该指向哪里？**
- `render`
  - **这个目标文件本身应该长什么样？**

一个更直白的类比：

- `link`
  - 像是在桌面上放一个快捷方式
- `render`
  - 像是先把多份资料整理成一页 briefing，再决定把 briefing 放到哪里

## 2.2 它们可以组合

`render` 和 `link/copy` 不是互斥的概念。

理论上有三种组合：

### `link`

- 不生成新内容
- 直接把真源链接到目标位置

### `render + copy`

- 先生成新内容
- 再复制到目标位置

这是当前已经实现的 render 路径。

### `render + link`

- 先生成新内容
- 再把目标位置链接到生成物

这种方式未来也可以支持，适合：

- 想保留“生成物就是部署目标”
- 又不想每次都复制

## 2.3 如何选择

默认建议：

1. 目标工具能直接吃真源入口
   - 先选 `link`
2. 目标工具更适合短入口或特殊格式
   - 先选 `render`
3. 如果目标位置不能稳定使用链接
   - 在上面基础上退化到 `copy`

可以简单记成：

- **真源直接可用**：`link`
- **真源需要先整理成投影入口**：`render`
- **目标环境不适合链接**：再考虑 `copy`

## 3. 同步语义

### `link` 模式

同步方式就是 git：

1. Agent 修改全局生效文件
2. 实际改动直接落在仓库
3. 你执行 `git add / commit / push`

不需要额外 `import`。

若执行：

- `ygg sync <target>`
- `ygg push <target>`

则会根据 sync policy 自动判定为 `no-op import`，然后只做 git 流程。

### `copy` 模式

同步方式分两段：

1. `deploy`：仓库 -> Agent 全局目录
2. `import`：Agent 全局目录 -> 仓库

只有当 Agent 实际修改的是复制出去的副本时，才需要 `import`。

为了统一多 Agent 语义，`YggForge` 还支持：

- `ygg sync <target>`
- `ygg push <target>`

这两个命令会先读取最近 deploy manifest，再决定是否自动执行 import。

### `render` 模式

当前实现中，`render` 部署会把生成物复制到目标位置。

如果目标位置后续又被修改，则：

- 不会直接回写 canonical source
- `import` 会把修改导入到 `yggforge-generated/imports/` 供人工复核
- 复核后再决定是否晋升回 canonical source

这也是 `ygg sync <target>` / `ygg push <target>` 默认可安全执行的原因：

- 是否 import 由最近部署模式决定
- import 目标由 deploy manifest 决定
- render 模式不会直接覆盖 canonical source

## 4. `yggforge-generated/` 约定

`yggforge-generated/` 用于统一存放这些内容：

- 部署清单
- 渲染产物
- 导入中间产物
- 状态缓存
- 本机相关且不应进入知识真源的文件

这里的内容原则上：

- 不作为知识真源
- 不应被 Agent 默认整库阅读
- 只在部署、导入、状态检查时按需使用

## 5. 本地秘密与不应同步的内容

不应进入仓库真源的内容包括：

- token
- password
- secret
- api_key
- private_key
- 本机缓存
- 机器相关运行时状态

推荐原则：

- 真源中只保留模板、占位符或脱敏版本
- 敏感值只保留在本地机器
- 本地状态与生成物进入 `yggforge-generated/` 或工具自己的本地目录

## 6. 部署对象

部署分两层，避免把核心目录散落到 Agent 家目录根下：

1. **整包核心**（`core_bundle`）：把 `yggforge-core/` 链接为 `~/<agent>/yggforge-core`
2. **薄入口**：只投影工具真正识别的入口（如 `AGENTS.md`、`rules/`、`skills/`）

### Cursor

- 核心包：`~/.cursor/yggforge-core` → `yggforge-core/`
- **用户级** `~/.cursor/hooks/` + `~/.cursor/hooks.json`（随 `ygg deploy link cursor` 安装；协议硬路径）
- **用户级 skills**：`~/.cursor/skills/<name>/` ← `profiles/cursor/skills/<name>/`（按技能子目录投影，不整目录覆盖用户已有 skills）
- 用户级**不再投影** `AGENTS.md` 与 `rules/`——Cursor 原生不自动加载 `~/.cursor/` 下这两类；薄规则靠 hooks + 核心包内 Read 约定
- 要让 Cursor **原生自动加载**薄规则，用项目级部署（见下文「项目级部署」）投影到 `<repo>/.cursor/rules/*.mdc`
- 项目级同时投影 `profiles/cursor/skills/` → `<repo>/.cursor/skills/`（整目录；技能正文仍在 `plugins/`，此处仅为 stub）
- **单文件 copy 回退**：`hooks.json` 在 Windows 跨盘或无 symlink 特权时常显示 `copied`（内容一致但不自动回流）。改真源后：删掉 `~/.cursor/hooks.json` 再重跑 `ygg deploy link cursor`；或开启 Windows **Developer Mode** 后重 deploy 以争取 symlink/hardlink
- 仓库侧投影源：`yggforge-core/profiles/cursor/`
- **约定**：deploy **只投影、不现场生成**薄入口；stub 维护在 `profiles/`，协议真源在 `plugins/`（见 `profiles/cursor/skills/README.md`）

#### Cursor 规则投影注意（官方限制）

按 [Cursor Rules 文档](https://cursor.com/docs/rules.md)：

| 类型 | 官方位置 | YggForge 部署 |
| --- | --- | --- |
| Project Rules | `<repo>/.cursor/rules/*.mdc` | **项目级部署** `ygg deploy --scope project cursor` 投影到此（自动加载） |
| User Rules | Customize → Rules（Settings 纯文本） | 需人工加一条引导（见下） |
| User Hooks | `~/.cursor/hooks.json` | **已部署**（协议硬路径） |
| `~/.cursor/rules/*.mdc` | **原生不加载** | 用户级不再投影；改用项目级部署 |

**协议生效优先级（由硬到软）：**

1. 用户级 hooks（`beforeSubmitPrompt` 写 `last_trigger.json`；`sessionStart` 尽力注入，可能被 Cursor 竞态丢弃）
2. 核心包内 `profiles/cursor/AGENTS.md` 的读规则约定 + 知识真源 `knowledge/rules/default-trigger-routing.md`（会话开始主动 Read）
3. 可选：在 **Customize → Rules** 加一条 User Rule，要求会话开始用 Read 工具读取核心包内 `.mdc`
4. 项目级部署 `ygg deploy --scope project cursor` → `<repo>/.cursor/rules/*.mdc`（官方原生路径，自动加载）

领域规则（如 `cpp-style/*`）不宜长期 `alwaysApply` 全局投放；优先按需检索或项目级 globs。

#### 项目级部署（`--scope project`）

用户级部署把核心包 + 根钩子装到 `~/.<agent>/`（一次性、跨项目共享）。**项目级部署**把薄入口投影到**当前项目仓库**，让 Agent 原生自动加载：

```
# 在目标项目仓库根目录运行
ygg deploy link --scope project cursor        # → <repo>/.cursor/{rules,hooks,hooks.json}
ygg deploy link --scope project codex         # → <repo>/AGENTS.md
ygg deploy link --scope project opencode      # → <repo>/AGENTS.md
ygg deploy link --scope project claude        # → <repo>/AGENTS.md
ygg deploy link --scope project openclaw      # → <repo>/.openclaw/AGENTS.md
```

- `--project-root <path>` 可显式指定项目根（默认当前工作目录）
- 项目级**不部署整包核心**（整包留在用户级 `~/.<agent>/yggforge-core`），只投影薄入口
- Cursor 项目级会投影：`rules/`、`skills/`、`hooks/`、`hooks.json`
- 各 Agent 项目级目标见 `config/deploy.defaults.json` 的 `project_targets`
- 项目级部署是本机投影，不触发远端 git update
- 部署清单按 `<target>@project` 单独记录，与用户级清单互不覆盖

强制检索钩子（Cursor 专有，仅 cursor target 有）：

- `~/.cursor/hooks.json`（**用户级** User Hooks）注册 `beforeSubmitPrompt` + `sessionStart`
- `~/.cursor/hooks/`（junction → `yggforge-core/profiles/cursor/hooks/`）含两个脚本：`ygg_pre_submit.py`（每条消息提交前跑 `trigger_detector.py` 并落盘 `last_trigger.json`）、`ygg_session_protocol.py`（会话开始尝试注入协议；失败时以 `.mdc` / `AGENTS.md` / `last_trigger.json` 为准）
- 平台特定命令：`hooks.json` 真源按平台分两份——Windows 用 `profiles/cursor/hooks.windows.json`（命令 `py -X utf8 hooks/...`；`py` 在 `C:\Windows\py.exe`，`-X utf8` 避免 Python 按系统 GBK 再误读一层）。这是对 Cursor Windows hook stdin 编码 bug 的配套措施（[Forum #159259](https://forum.cursor.com/t/hook-stdin-pipe-double-encodes-non-ascii-on-non-utf-8-windows/159259) 等；完整链接与 `transcript_path` 主绕过见 `profiles/cursor/hooks/ygg_pre_submit.py` 模块 docstring、`hooks/README.md`、`docs/guide/install.md`）。Linux 用 `profiles/cursor/hooks.json`（命令 `python3 hooks/...`）。`deploy.defaults.json` 的 `hooks_config` mapping 用 `sources` 字段按平台选真源。不用裸 `python`，因其常在用户级 PATH（如 miniconda3），GUI 可能继承不到
- `hooks.json` 是 copy（Windows 跨盘单文件无法 symlink/junction），改它需编辑真源后重新部署；`hooks/` 是 junction，改脚本天然回流仓库
- 部署后必须重启 Cursor：Cursor 只在启动时加载 `hooks.json`，会话中途新建/修改的 hooks.json 不会自动生效（文件监视器对新建文件常不触发）。`ygg deploy link cursor` 后若 hook 不触发，先重启 Cursor
- 验证与排查：
  - 部署后重启 Cursor，打开 **Customize → Hooks** 标签，确认 `sessionStart` 与 `beforeSubmitPrompt` 两条都出现（没出现说明 hooks.json 没被加载，检查路径/编码）
  - 发一条消息后看 `~/.cursor/ygg_hook_heartbeat.txt`：时间戳随消息更新 → hook 被 Cursor 调用了；不更新 → hook 没被触发（需重启 Cursor 或检查 `py`/`python3` 是否在 GUI PATH）。行内 `prompt_ok=True/False` 与 `keys=...` 可区分「stdin 空」与「有 JSON 但字段提取失败」
  - 若 `prompt_ok=False` 且 `raw_len>0`：hook 会强制写 `~/.cursor/ygg_debug_stdin.txt`，`last_trigger.json` 带 `stdin_keys`（顶层 key:type）。官方字段是顶层 `prompt`；脚本已兼容 list/dict content blocks 与常见别名
  - 设 `YGG_DEBUG_STDIN=1` 可让每次调用都落盘 raw stdin
  - hook 执行报错看 Cursor 的 **Hooks output channel**（View → Output 选 Hooks）
  - hook 脚本已改为走 `sys.stdin.buffer.read()` 再 UTF-8 解码；detector 经环境变量 `YGG_TRIGGER_PROMPT` 传全文，避免 Windows argv 截断中文

### OpenCode

- 核心包：`~/.config/opencode/yggforge-core` → `yggforge-core/`
- 薄入口：`~/.config/opencode/AGENTS.md`
- 仓库侧投影源：`yggforge-core/profiles/opencode/`

### Codex

- 核心包：`~/.codex/yggforge-core` → `yggforge-core/`
- 薄入口：`~/.codex/AGENTS.md`（用户级）；项目级 `ygg deploy --scope project codex` → `<repo>/AGENTS.md`
- 仓库侧投影源：`yggforge-core/profiles/codex/`

### Claude Code

- 核心包：`~/.claude/yggforge-core` → `yggforge-core/`
- 薄入口：`~/.claude/AGENTS.md`（跨 Agent 标准；Claude 原生入口是 `CLAUDE.md`，可符号链接 `~/.claude/CLAUDE.md -> ~/.claude/AGENTS.md`）；项目级 `ygg deploy --scope project claude` → `<repo>/AGENTS.md`
- 仓库侧投影源：`yggforge-core/profiles/claude/`

### OpenClaw

- 核心包：`~/.openclaw/yggforge-core` → `yggforge-core/`
- 薄入口：`~/.openclaw/AGENTS.md`（OpenClaw 全局配置在 `~/.openclaw/openclaw.json`，身份在 `~/.openclaw/agents/<agent>/agent.md`；YggForge 不接管其 persona 体系）；项目级 `ygg deploy --scope project openclaw` → `<repo>/.openclaw/AGENTS.md`
- 仓库侧投影源：`yggforge-core/profiles/openclaw/`
- **无 IDE 钩子**：OpenClaw 无 `beforeSubmitPrompt`，触发检测由 Agent 读 `AGENTS.md`「KimiClaw/OpenClaw 集成 (无 IDE Hooks 环境)」内化规则静默判断（不依赖 `last_trigger.json`，等价替代 Cursor 钩子）。KimiClaw 同此机制。

## 7. 统一部署脚本

推荐入口（统一 CLI）：

```powershell
.\ygg.ps1 deploy link cursor codex claude openclaw
.\ygg.ps1 status cursor
.\ygg.ps1 deploy link --scope project cursor
.\ygg.ps1 import codex
```

```bash
./ygg.sh deploy link cursor codex claude openclaw
./ygg.sh status cursor
./ygg.sh deploy link --scope project cursor
./ygg.sh import codex
```

子命令语义：

- `ygg deploy link|copy|render [targets...]`：执行部署并记录部署清单
- `ygg import [targets...]`：仅在上一轮为 `copy` / `render` 时才有意义
- `ygg status [targets...]`：检查部署状态、目标路径和最近一次部署模式

兼容旧入口：`deploy.ps1|sh` 仍接受 `--action/--mode/--targets`（直调 `cmds/ops/deploy.py`），或新风格 `deploy.ps1 link cursor`（转发到 `ygg`）。

实现分层：

- `yggforge-core/scripts/cmds/ops/deploy.py`：跨平台核心
- `yggforge-core/scripts/cli/`：`ygg` 路由库（routes / runtime / intent）
- `yggforge-core/scripts/deploy.ps1|.sh`：兼容薄包装
- 仓库根 `ygg.sh` / `ygg.ps1`：统一 CLI 入口

运行前提：

- Windows 或 Linux
- Python 3 可用
- 目标环境支持所需的 link / copy / render 行为

## 8. 路径配置

不同工具的真实全局路径与版本行为可能不同，所以不要把它们写死在知识文档里。

统一做法：

- 默认路径写在部署配置里
- 本机覆盖写在本地配置里
- 部署脚本读取配置后执行

## 9. 推荐的本地配置分层

- 仓库默认配置：可提交
- 机器本地覆盖：不提交

例如：

- `yggforge-core/config/deploy.defaults.json`
- `yggforge-runtime/config/deploy.local.json`

## 10. 为什么部署层要独立

因为不同 Agent 的入口规则、支持的目录、是否接受链接、是否有 GUI 内置配置，都会变化。

把这些差异收束到部署层，才能避免污染知识真源。
