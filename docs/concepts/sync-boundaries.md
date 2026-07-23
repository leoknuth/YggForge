﻿# 同步边界

## 目录

- [1. 目的](#1-目的)
- [2. 必须进入仓库真源的内容](#2-必须进入仓库真源的内容)
- [3. 只应保留在本地的内容](#3-只应保留在本地的内容)
- [4. `yggforge-generated/` 的定位](#4-yggforge-generated-的定位)
- [5. 不同部署模式的同步方式](#5-不同部署模式的同步方式)
  - [`link`](#link)
  - [`copy`](#copy)
  - [`render`](#render)
- [6. 哪些内容建议优先 link](#6-哪些内容建议优先-link)
- [7. 哪些内容不建议直接 link 到真源](#7-哪些内容不建议直接-link-到真源)
- [8. 实施原则](#8-实施原则)

---

## 1. 目的

本文定义 `YggForge` 中哪些内容属于知识真源，哪些内容只属于本地状态或生成物。

## 2. 必须进入仓库真源的内容

- `knowledge/` 下的规则、模板、经验、决策、来源提炼
- `profiles/` 下的 Agent 投影模板
- `scripts/` 下的跨平台部署与处理工具
- `yggforge-core/config/deploy.defaults.json`
- 可复用的 schema、索引、模板

这些内容应当：

- 可版本化
- 可 review
- 可跨机器复用

## 3. 只应保留在本地的内容

- token
- password
- secret
- api_key
- private_key
- 机器相关缓存
- 某个 Agent 运行时临时状态
- 只对本机有效的路径覆盖

这类内容不应进入知识真源。

## 4. `yggforge-generated/` 的定位

`yggforge-generated/` 用于存放：

- 部署清单
- 渲染产物
- 导入中间产物
- 本地状态缓存
- 不应默认被 Agent 检索的机器相关文件

推荐子目录：

- `deploy-manifests/`
- `rendered/`
- `imports/`
- `cache/`

其中：

- `rendered/`
  - 保存 render 模式生成的部署产物
- `imports/`
  - 保存 render 模式或需人工复核的导入结果

## 5. 不同部署模式的同步方式

### `link`

- 全局生效文件直接指向仓库
- 改动天然就在仓库
- 主同步方式是 git

### `copy`

- 全局生效文件是副本
- 副本改动不会自动回仓库
- 需要显式 `import`

### `render`

- 渲染结果是生成物
- 是否需要 `import` 取决于 render 之后是 link 还是 copy

## 6. 哪些内容建议优先 link

- `AGENTS.md`
- 稳定规则入口
- 技能说明文件
- 静态模板
- 可读文档

## 7. 哪些内容不建议直接 link 到真源

- cache
- machine-specific state
- secrets
- 工具自动生成且高频变化的临时文件

## 8. 实施原则

- 能 link 的优先 link
- 不能稳定 link 的才 copy
- 只有 copy 模式才把 `import` 作为常规流程
- 生成物和状态一律优先放进 `yggforge-generated/`
