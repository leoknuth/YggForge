# Inbox

这里放原始投喂材料。

例如：

- 技术博文链接
- PDF
- 内部复盘
- PR 评论摘录
- 实验记录

这些材料不直接视为规则。

当前也允许归档这些材料的“原始可读副本”，例如：

- 提取后的正文文本
- 本地保存的文章导出文件

原始 HTML 不再作为默认归档格式，只在明确需要保全原网页副本时才建议保留。

建议配合：

- `ygg ingest`（实现：`scripts/cmds/pipeline/ingest.py`）

生成条目应带 `type: source`；来源元数据写在 YAML，正文为 `## 抽取正文`。再经 `ygg distill` 得到 `type: distilled-source` 草稿。
