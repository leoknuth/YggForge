# 文档总览

> 路径约定：文中 `knowledge/`、`profiles/`、`graph/`、`config/`、`scripts/` 无前缀时，默认相对 **`yggforge-core/`**。本机态见 `yggforge-runtime/`，生成物见 `yggforge-generated/`。

## 分层

| 目录 | 用途 |
| --- | --- |
| [guide/](guide/quickstart.md) | 入门：安装、部署、日常用法 |
| [concepts/](concepts/design.md) | 理念与结构：设计、布局、记忆/联想、[设计哲学](concepts/philosophy.md) |
| [reference/](reference/ygg-cli.md) | 参考：CLI、触发词、行为配置、同步 |
| [opt-plan/](opt-plan/README.md) | **仅后续优化建议**（未做项） |
| [assessments/](assessments/README.md) | 外部选型与迁移评估 |

根目录叙事与哲学见 [../README.md](../README.md)。

## 推荐阅读顺序

1. [../README.md](../README.md)  
2. [guide/quickstart.md](guide/quickstart.md)  
3. [concepts/layout.md](concepts/layout.md) · [concepts/memory-and-association.md](concepts/memory-and-association.md)  
4. [guide/usage.md](guide/usage.md) · [reference/ygg-cli.md](reference/ygg-cli.md)  
5. 需要改行为闸门 → [reference/behavior-config.md](reference/behavior-config.md)  
6. 要做能力增强 → [opt-plan/README.md](opt-plan/README.md)  

## 按目标

| 目标 | 文档 |
| --- | --- |
| 最快部署 | [guide/quickstart.md](guide/quickstart.md) · [guide/deploy.md](guide/deploy.md) |
| 理解三层目录 | [concepts/layout.md](concepts/layout.md) |
| 理解 tag ↔ 正文 id | [concepts/memory-and-association.md](concepts/memory-and-association.md) |
| 设计哲学与命名溯源 | [concepts/philosophy.md](concepts/philosophy.md) |
| 检索约定 / id 格式 | [concepts/retrieval-conventions.md](concepts/retrieval-conventions.md) |
| ask/allow/deny | [reference/behavior-config.md](reference/behavior-config.md) |
| 多机 git | [reference/sync.md](reference/sync.md) |
| 商用许可 | [reference/licensing.md](reference/licensing.md) |
| 后续优化 | [opt-plan/](opt-plan/README.md) |
