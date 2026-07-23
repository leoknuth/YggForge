# Profiles

## 目录

- [1. 这一层是什么](#1-这一层是什么)
- [2. 当前有哪些 profile](#2-当前有哪些-profile)
- [3. 使用方式](#3-使用方式)

---

## 1. 这一层是什么

`profiles/` 是面向不同 Agent 的投影层。

职责只有两件事：

- 给不同 Agent 提供它们能识别的入口文件
- 把仓库真源映射出去，而不是复制业务内容

这层不是 canonical knowledge。

真正的知识真源见：

- [../knowledge/README.md](../knowledge/README.md)

## 2. 当前有哪些 profile

- `common/`
  - 共用行为包与索引
- `cursor/`
  - Cursor 投影入口
- `codex/`
  - Codex 投影入口
- `opencode/`
  - OpenCode 投影入口

## 3. 使用方式

如果你在部署某个 Agent，通常要同时看：

1. [../../docs/guide/deploy.md](../../docs/guide/deploy.md)
2. 对应 profile 的入口文件
3. [../../docs/guide/usage.md](../../docs/guide/usage.md)
