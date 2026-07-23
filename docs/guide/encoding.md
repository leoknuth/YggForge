# 编码说明

## 目录

- [目标](#目标)
- [约定](#约定)
- [为什么核心文档使用 BOM](#为什么核心文档使用-bom)
- [编辑建议](#编辑建议)
- [Git 与编辑器策略](#git-与编辑器策略)

---

## 目标

这个仓库希望同时兼顾：

- 人类在 Windows / macOS / Linux 上直接阅读
- Cursor / OpenCode / Codex 等 Agent 稳定读取
- Git 差异干净
- PowerShell 不把中文误显示为乱码

## 约定

- 所有文本文件统一使用 UTF-8
- 核心 Markdown 文档和 `AGENTS.md` 使用 `UTF-8 with BOM`
- JSON 文件默认使用 `UTF-8` 无 BOM
- 行尾统一使用 LF

## 为什么核心文档使用 BOM

在 Windows PowerShell 5.x 下，`Get-Content` 读取无 BOM 的 UTF-8 文件时，容易按本地代码页解释，从而把中文显示成乱码。

对这个仓库来说，`README.md`、`AGENTS.md`、`docs/*.md` 和 `profiles/*/AGENTS.md` 都属于高频查看文件，因此统一保存为 `UTF-8 with BOM` 更稳。

## 编辑建议

- 编辑器默认保存为 UTF-8
- 对核心 Markdown 文件，优先保存为 `UTF-8 with BOM`
- 避免在不同编辑器之间来回切换编码
- 若发现中文乱码，先检查文件编码，而不是先怀疑内容损坏

## Git 与编辑器策略

- `.editorconfig` 用于约束常见编辑器行为
- `.gitattributes` 用于统一换行和文本文件处理
- 若未来引入格式化或校验脚本，可以把编码检查并入 CI

## CLI argv 与 `-X utf8`

Windows PowerShell 5.x 在中文系统代码页（CP936/GBK）下，把中文参数经 argv 传给 Python 子进程时，可能把非 ASCII 字符替换成 `?`，导致 `ygg associate --tag 拿铁` 这类命令的中文 tag 被损坏、检索落空（与 hook stdin 的双重编码 bug 同源，见 `docs/guide/install.md` 第 9 节）。

本仓库 `yggforge-core/scripts/ygg.ps1` 调用 Python 时统一加 `-X utf8`（启用 Python UTF-8 模式），让 argv/stdout 按 UTF-8 处理，避免中文 CLI 参数损坏。配合 `graph/tag-synonyms.yaml` 的查询侧归并（`associate` 把中文 seed tag 映射到 canonical 英文 tag），中文 tag 既能正确传入又能命中已有英文索引。

若自行直接调用 `python scripts/ygg.py ...` 传中文参数，建议同样加 `-X utf8`，或改用 `ygg.ps1` 入口。
