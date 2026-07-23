---
id: 20260714144840-krm$$$-sqr$$$$$-rgvc
title: simu / quote_rate 忽略原则
type: rule
status: active
confidence: high
source: agent-profile
scope: 任意框架跑 simu 时的回放速度参数
last_reviewed: 2026-07-14
owners:
  - team
tags:
  - simu
  - troubleshooting
  - mycapital
keywords:
  - quote_rate
  - rate
  - speed
related:
  - 20260714150521-krm$$$-sbl$$$$$-exqi
priority: high
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 任意框架跑 simu / 策略 / 因子 / 模型时
  - 排查回放、崩溃、空产出等问题时
always_apply: true
projection_mode: sync
projection:
  - profiles/cursor/rules/mycapital/simu-quote-rate-ignore.mdc
---
# simu / quote_rate 忽略原则

## Rule

对**任意框架**，在使用者**没有明确要求**设置回放速度时，对 `quote_rate`（及别名 `rate`、`speed`）统一遵循：

1. **不设置**：命令行与配置都不传 `quote_rate`/`rate`/`speed`，不调用 `set_quote_speed_rate`（或等价接口），保持默认缺省即可。
2. **禁止归因**：排查 simu `status_code` 非 0、行情不回放、NDJSON 为空、H5 未落盘、策略未进入 tick、SIGSEGV 等问题时，**不得**将 `quote_rate`（含其值为 -1 或 0）列为假设或根因方向。
3. **禁止建议**：不要建议用户设置/调整 `quote_rate` 来「修复」回放或崩溃问题。

该原则与 `libbarraopt.so` / BarrOpt 相关误报同属「可忽略项」，不作为运行失败根因。

## Applies To

- 任意框架的 simu / 策略 / 因子 / 模型本地或联调运行

## Not For

- 使用者**明确要求**设置或压测回放速度的场景
