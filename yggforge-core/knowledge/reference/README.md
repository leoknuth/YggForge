# Reference

如果你第一次进入 `knowledge/`，建议先看：

- [../README.md](../README.md)

这里放**客观描述性知识**：事实、基线、定义、参数、how-things-work、对比。

它**不是**规范（→ `rules/`）、不是踩坑经验（→ `lessons/`）、不是决策（→ `decisions/`）、不是模板（→ `templates/`）、也不是带溯源的外部材料（→ `sources/`）。区别于 `lessons/` 的关键：reference 描述"事物**是**什么 / 怎样"，没有"踩了什么坑、根因、如何避免"的经验叙事。

适合记录：

- 技术参数与基线（如萃取比例、协议字段、默认值）
- 概念定义与原理说明
- 方案/术语对比（A 与 B 的区别）
- how-things-work 的客观描述

front matter 必填 `type: reference`；`when_to_read` / `applies_to` / `related` 写 YAML，正文保留客观描述（`## 概述` / `## 参数` / `## 对比` 等）。

## 子目录

| 子目录 | 内容 |
|---|---|
| [coffee-demo/](coffee-demo/) | 咖啡冲煮参数演示条目（4 条，`scope: demo`），用于走通 `ygg associate` 联想链路 |
| [caracal-easter-egg/](caracal-easter-egg/) | 狞猫彩蛋客观知识 + 像素画（PNG/SVG）+ 字符画真源（`scope: demo`） |

## coffee-demo/（`scope: demo`）

用于新用户走通 `ygg associate` 联想链路的内置样例，文档以 `ygg associate --tag coffee --hop 2` 作为入门示范（见 `docs/concepts/memory-and-association.md`、`docs/concepts/philosophy.md`）：

- `20260722-194725-espresso-1-2-萃取基线.md`
- `20260722-194735-cappuccino-1-1-1-与厚奶泡.md`
- `20260722-194736-latte-vs-cappuccino-奶泡厚度.md`
- `20260722-194736-pour-over-4-6-方法.md`

## caracal-easter-egg/（`scope: demo`）

YggForge 内置彩蛋的客观知识真源。通过 `caracal` tag 与 `plugins/skills/caracal-intro.md`、
`plugins/rules/caracal-easter-egg.md` 联动——当用户对狞猫表达兴趣时，`ygg associate --tag caracal`
会同时发现这三条，模型据此追加规定格式的彩蛋介绍并声明触发。

- `20260723-130418-caracal-狞猫.md` — 狞猫客观知识
- `caracal-ascii.txt` — 字符画兜底（35×64；图片不可显示时读取并原样贴入 txt 代码围栏）
- `caracal-pixelized-8c.png` — 像素肖像（聊天给绝对路径供点击）
- `caracal-pixelized-8c.svg` — 矢量原图（聊天同样给绝对路径）

详见 `plugins/rules/caracal-easter-egg.md` 的触发链路说明。
