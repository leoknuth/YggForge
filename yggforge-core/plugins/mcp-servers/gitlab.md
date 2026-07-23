---
id: ygg-mcp-gitlab
title: GitLab MCP 服务定义
title_refined: gitlab mcp-server
type: mcp-server
status: active
confidence: medium
source: user
scope: cross-project
channel: local
recorded_at: 2026-07-23
last_reviewed: 2026-07-23
tags:
  - git
  - mcp
  - ci
  - review
agent_targets:
  - cursor
  - claude
  - codex
transport: stdio
command: npx
args:
  - "-y"
  - "@gitlab/mcp-server"
env_placeholder: GITLAB_TOKEN
tools:
  - gitlab_list_merge_requests
  - gitlab_get_merge_request
  - gitlab_list_pipelines
  - gitlab_get_pipeline_job_output
  - gitlab_validate_ci_lint
depends_on: []
project_to:
  cursor: mcp.json:mcpServers.gitlab
  claude: .mcp.json:mcpServers.gitlab
  codex: config.toml:mcp_servers.gitlab
---
# GitLab MCP 服务

## 说明

GitLab MCP server 的 YggForge 内部定义模板。真实密钥**不进本仓库**；
部署时由用户指定的私密凭据根目录注入到各 Agent 的 mcp 配置。

## 占位符

- `env_placeholder: GITLAB_TOKEN` —— 部署时替换为本机凭据。

## 投影

由 `ygg deploy` 合并到各 Agent 的 mcp 配置：

- Cursor：`~/.cursor/mcp.json`（或项目级 `.cursor/mcp.json`）的 `mcpServers.gitlab`
- Claude：`.mcp.json` 的 `mcpServers.gitlab`
- Codex：`~/.codex/config.toml` 的 `[mcp_servers.gitlab]`

## 凭据注入

可用辅助脚本（参数为通用「secrets 根目录」，不绑定具体仓名）：

```bash
python3 scripts/cmds/ops/apply_credentials_mcp.py \
  --credentials-root <用户指定的私密凭据根目录> \
  --example profiles/cursor/mcp.json.example \
  --target ~/.cursor/mcp.json
```
