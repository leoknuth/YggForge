# Distilled Sources

这里放 AI 或人工提炼后的中间结果。

每份条目 front matter 应设 `type: distilled-source`，并把结构化字段写进 YAML：

- `facts` — 事实
- `inferences` — 推论
- `practices` — 可复用做法
- `risks` — 风险与保留意见
- `promote_to` / `promote_rationale` — 是否建议晋升及去向

正文只保留标题与可选补充说明，不要再用 `## 事实` / `## 推论` 等重复 YAML。

新增条目时建议从：

- [../../templates/distilled-source.template.md](../../templates/distilled-source.template.md)

复制开始。权威 schema：`../../../schemas/knowledge-item.schema.yaml`（v2）。
