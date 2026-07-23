# andrej-karpathy-skills 评估与吸收说明

## 目录

- [目的](#目的)
- [核心判断](#核心判断)
- [为什么值得吸收进 YggForge](#为什么值得吸收进-yggforge)
- [不直接照搬的原因](#不直接照搬的原因)
- [吸收方式](#吸收方式)
  - [1. 规则层](#1-规则层)
  - [2. 通用行为包](#2-通用行为包)
- [对 YggForge 的改良意义](#对-yggforge-的改良意义)

---

## 目的

本文记录对 `multica-ai/andrej-karpathy-skills` 的评估结果，以及 `YggForge` 吸收它的具体方式。

## 核心判断

这个仓库的价值不在于复杂工具链，而在于一组极简但高强度的行为约束：

- Think Before Coding
- Simplicity First
- Surgical Changes
- Goal-Driven Execution

它的优势在于：

- 约束短
- 可重复使用
- 跨 Claude / Cursor 都容易投影
- 非常适合放在“全局控制层”

## 为什么值得吸收进 YggForge

`YggForge` 的定位不是单纯的资料库，而是部署到 Agent 全局目录附近的知识与控制层。

因此，除了“知识资产”之外，还需要一部分：

- 高复用
- 低歧义
- 低 token
- 高约束力

的行为规则。

`andrej-karpathy-skills` 正好满足这一类需求。

## 不直接照搬的原因

虽然这个仓库本身已经很简洁，但 `YggForge` 不适合把它原样当成独立子系统塞进来：

- `YggForge` 需要兼容多 Agent，而不是只围绕 Claude / Cursor
- `YggForge` 的知识真源已经按 `rules / lessons / decisions / sources` 分层
- 这份内容更适合作为 `YggForge` 的通用行为包，而不是外来单体项目

## 吸收方式

本次采用两层吸收：

### 1. 规则层

把四条原则沉淀为：

- `knowledge/rules/agent-coding-discipline.md`

作用：

- 成为 `YggForge` 的正式知识真源
- 可继续演化、扩展、与其他规则整合

### 2. 通用行为包

把同样的内容做成一个短入口包，放到：

- `profiles/common/behavior-packs/karpathy-guidelines.md`

作用：

- 可被 `render`
- 可被不同 Agent 的入口文件引用
- 更适合全局投影使用

目前已进一步接入：

- `profiles/codex/AGENTS.md`
- `profiles/cursor/AGENTS.md`
- `profiles/opencode/AGENTS.md`

## 对 YggForge 的改良意义

这次吸收让 `YggForge` 更接近“全局控制层”，而不是只做知识仓库：

- 它现在不仅能存资料
- 还能提供一组可部署的高质量行为约束

这类内容特别适合：

- 放进全局 Agent 入口
- 作为 render 的素材
- 作为不同项目共用的行为基线
