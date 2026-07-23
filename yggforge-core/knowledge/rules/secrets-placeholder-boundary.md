---
id: 20260714151437-kr$$$$-$$$$$$$$-m5c6
title: 密钥占位与私密凭据隔离
type: rule
status: active
confidence: high
scope: 本仓库与私密凭据、本机密钥落盘的边界
last_reviewed: 2026-07-14
owners:
  - team
tags:
  - secrets
  - deploy
  - mcp
keywords:
  - YOUR_TOKEN
  - 占位符
  - 私密凭据
related: []
priority: high
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 编写或审查含 token / 密码 / 内网地址的配置模板时
  - 用户要求部署并填充真实密钥时
always_apply: true
projection_mode: sync
projection:
  - profiles/cursor/rules/secrets-placeholder-boundary.mdc
---
# 密钥占位与私密凭据隔离

## Rule

1. **本仓库只保留占位符**（如 `YOUR_TOKEN`、`YOUR_PASSWORD`、`YOUR_GITLAB_HOST`），不提交真实密钥或仅本机有效的敏感地址。
2. **本仓库文档与规则不指名、不链接私密凭据仓库或其他平行工程仓库**；不把「去某某仓库取密钥」写成固定耦合说明。
3. 仅当使用者在**部署**场景明确要求填充密钥时，Agent 才按用户指定的私密凭据目录读取真实值，写入本机目标路径（例如 `~/.cursor/mcp.json`）。
4. 填充动作发生在本机运行时配置，**不回写**真实值到本仓库。
5. 对话、commit 说明、日志中不得粘贴明文密钥。

## Applies To

- MCP 模板、部署配置、文档中的敏感字段

## Not For

- 用户明确要求在私密凭据仓库本身增删改密钥条目
