# Templates

如果你第一次进入 `knowledge/`，建议先看：

- [../README.md](../README.md)

本目录是 **知识条目模板真源**（`type: rule` / `lesson` / `decision` / `template` / `distilled-source` 的脚手架；其中实现骨架文件名为 `implementation-template.template.md`，`type` 仍为 `template`）。  
新增正式条目时从此处复制到对应目录，再改 front matter（必填 `type`）与正文。

结构化字段进 YAML；正文只留叙述。权威 schema：[../../schemas/knowledge-item.schema.yaml](../../schemas/knowledge-item.schema.yaml)。  
说明见：[../../../docs/reference/knowledge-templates.md](../../../docs/reference/knowledge-templates.md)

## 当前模板

- [rule.template.md](rule.template.md)
- [lesson.template.md](lesson.template.md)
- [decision.template.md](decision.template.md)
- [implementation-template.template.md](implementation-template.template.md)
- [distilled-source.template.md](distilled-source.template.md)

## 可选扩展

若以后要放可复用实现骨架（非「条目元数据脚手架」），建议在本目录下另开主题子目录（如 `cpp/`、`quant/`），与上列 `*.template.md` 区分开。
