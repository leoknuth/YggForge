---
id: 20260714144840-kr$$$$-m$$$$$$$-b8kj
title: Markdown 文档规范
type: rule
status: active
confidence: high
source: agent-profile
scope: 编写或改写 Markdown 文档
last_reviewed: 2026-07-14
owners:
  - team
tags:
  - markdown
  - docs
keywords:
  - 目录导引
  - 表格空行
related: []
priority: medium
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 编写或改写 `.md`、README、技能/规则文档、报告渲染产出时
---
# Markdown 文档规范

## Rule

### 目录导引

1. 在文档头部（标题与简介之后）添加「目录」或 “Table of Contents”。
2. 目录项应覆盖文内主要章节，并使用可跳转的文内锚点链接。
3. 导引链接必须使用**纯 Markdown** 语法（`- [标题](#锚点)`），不要使用 HTML 锚点或 HTML 列表。
4. 若文档较短（仅 1-2 个小节）且用户明确不要目录，可省略；否则默认添加目录。

### 表格空行

1. **每个 Markdown 表格块**（连续以 `|` 开头的行）的**上一行**与**下一行**必须是**空行**。
2. 表格前一段落、标题、列表结束后，须先空一行再写表头。
3. 表格最后一行数据行之后，须空一行再写后续正文。
4. 由脚本生成 Markdown 时，渲染逻辑须保证上述空行。

正确示例：

```markdown
说明文字。

| 列 A | 列 B |
| --- | --- |
| 1 | 2 |

后续段落。
```

## Applies To

- 人工编写与脚本生成的 Markdown

## Not For

- 非 Markdown 格式的纯文本日志
