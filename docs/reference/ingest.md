# 来源提炼与 ingest

## 目录

- [1. 目的](#1-目的)
- [2. 推荐流程](#2-推荐流程)
- [3. 当前最小实现](#3-当前最小实现)
- [4. 当前支持的来源](#4-当前支持的来源)
- [5. 例子](#5-例子)
- [6. 关于图片](#6-关于图片)

---

## 1. 目的

`ingest` 用来把原始来源材料变成 `YggForge` 中可归档、可检索、可晋升的内容。

典型输入：

- URL
- 本地 HTML
- Markdown / TXT
- PDF
- 聊天记录
- review 结论

## 2. 推荐流程

1. 把原始材料归档到 `yggforge-core/knowledge/sources/inbox/`
2. 提炼出结构化结论，放到 `yggforge-core/knowledge/sources/distilled/`
3. 视质量和稳定性决定是否晋升到：
   - `knowledge/rules/`
   - `knowledge/lessons/`
   - `knowledge/templates/`

## 3. 当前最小实现

当前仓库已经有一个最小原型：

- `scripts/cmds/pipeline/ingest.py`

当前支持：

- `--url`
- `--slug`

当前能力：

- 抓取 URL
- 识别当前支持的来源类型
- 默认归档提取后的文本到 `yggforge-core/knowledge/sources/inbox/assets/`
- 抽取正文文本
- 生成一份 inbox Markdown：`type: source`，来源元数据（`source_url` / `author` / `image_urls` / `asset_path` 等）在 YAML，正文为 `## 抽取正文`
- 如有需要，可额外保存原始 HTML 作为可选备份

配套的第一版 distilled 生成器：

- `scripts/cmds/pipeline/distill.py`

可以把 `inbox` 条目转成 `yggforge-core/knowledge/sources/distilled/` 下的初稿（`type: distilled-source`；`facts` / `inferences` / `practices` / `risks` 写在 YAML）。

## 4. 当前支持的来源

- WeChat 文章 URL

后续可以继续扩展：

- 本地 HTML
- Markdown / TXT
- PDF
- 更多站点规则

## 5. 例子

```powershell
.\ygg.ps1 ingest --url "https://mp.weixin.qq.com/s/..." --slug "example-article"
```

生成结果通常包括：

- `yggforge-core/knowledge/sources/inbox/<date>-<slug>.md`
- `yggforge-core/knowledge/sources/inbox/assets/<date>-<slug>.txt`

如需额外保留网页原始副本：

```powershell
.\ygg.ps1 ingest --url "https://..." --slug "example-article" --save-raw-html
```

## 6. 关于图片

当前 ingest 会保留图片 URL 列表。

处理原则：

- 无意义装饰图可以忽略
- 承载核心信息的图片应进一步解析
- 若后续具备 OCR 或图像理解能力，可再补自动识别
