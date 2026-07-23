---
id: 20260701163140-kr$$$$-pc$$$$$$-pi14
title: Performance Checklist
type: rule
status: active
confidence: high
scope: Benchmark design, performance analysis, and regression checks
last_reviewed: 2026-07-01
owners:
  - team
tags:
  - performance
  - hpc
keywords:
  - benchmark
  - latency
  - throughput
  - numa
  - tail latency
related:
  - 20260701163140-kr$$$$-csb$$$$$-vhsf
priority: high
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 当任务涉及 benchmark、性能分析、吞吐延迟结论、性能回归判断时优先加载
---
# Performance Checklist

初始占位规则。后续建议补充：

- benchmark 需要固定输入与环境
- 区分吞吐、延迟、尾延迟
- 避免把日志与 I/O 干扰混入基准
- 明确编译选项、CPU 特性、NUMA 与线程绑定
- 性能结论必须附带可复现实验条件

## Applies To

- benchmark 设计
- 性能回归检查
- 性能结论回报

## Not For

- 纯功能正确性规则
