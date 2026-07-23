# 行为配置与门禁

## 目录

- [1. 文件位置](#1-文件位置)
- [2. 模式语义](#2-模式语义)
- [3. 主要操作及其默认值](#3-主要操作及其默认值)
- [4. 如何覆盖](#4-如何覆盖)
- [5. 行为决策与 `--yes` / `--no`](#5-行为决策与---yes--no)
- [6. 实现约定](#6-实现约定)

---

## 1. 文件位置

```text
yggforge-core/config/behavior.defaults.yaml      # 仓库默认（可提交）
yggforge-runtime/config/behavior.local.yaml    # 本机覆盖（不入库）
yggforge-core/config/channels.yaml               # channel 字典
```

优先级：本机 `local` > 仓库 `defaults`。

## 2. 模式语义

每个操作有一个 mode：

| 模式 | 含义 |
| --- | --- |
| `ask` | 每次询问（默认） |
| `allow` | 直接放行 |
| `deny` | 拒绝 / 跳过 |
| `warn` | 放行但警告 |
| `audit` | 放行并写入审计日志 |
| `dry_run` | 只预览 |

## 3. 主要操作及其默认值

见 `yggforge-core/config/behavior.defaults.yaml`：

| 操作 | 默认 | 说明 |
| --- | --- | --- |
| `deploy.git_sync_after` | `deny` | 部署后是否对本仓库做 `git update` |
| `git.update` | `ask` | `ygg sync` |
| `git.push` | `ask` | `ygg push` |
| `memory.record_observation` | `ask` | 写入 `yggforge-runtime/memory/raw/` |
| `memory.mirror_to_lessons_inbox` | `ask` | 镜像到 `knowledge/lessons/inbox/` |
| `memory.kinds.rule` | `deny` | **禁止静默写入 rules**（包括 `remember --as rule` / 站立偏好） |
| `memory.kinds.lesson` | `ask` | `remember --as lesson`（当前仍只写 inbox） |
| `memory.kinds.template` | `ask` | 预留 |
| `memory.kinds.decision` | `ask` | 预留 |
| `memory.kinds.distilled-source` | `ask` | 预留 |
| `promote.to_rule` | `ask` | 显式 `ygg promote ... rule` |
| `promote.auto_to_rule` | `deny` | 无站立意图的自动晋升 |
| `promote.auto_to_rule_on_standing` | `allow` | 用户显式站立偏好（如「写成规则」） |
| `promote.to_reference` | `ask` | 显式 `ygg promote ... reference` |
| `promote.auto_to_reference` | `allow` | 客观知识自动晋升到 reference（联想查重无雷同） |
| `promote.to_lesson` | `ask` | 显式 `ygg promote ... lesson` |
| `promote.auto_to_lesson` | `allow` | 经验性知识自动晋升到 lessons |
| `dream.mode` | `ask` | `ygg dream` 写报告 |
| `dream.write_report` | `ask` | `ygg dream` 写报告 |
| `core_write.operations.tag_add` | `ask` | 写 `tag-graph.yaml` |
| `core_write.operations.tag_relate` | `ask` | 写 `tag-graph.yaml` |
| `core_write.operations.tag_weight_update` | `ask` | 人工改权重 |
| `core_write.operations.tag_suggest_apply` | `ask` | 应用 tag 建议 |
| `core_write.operations.tag_weight_authority_writeback` | `deny` | 统计回写权威 weight |
| `deps.install` | `ask` | `ygg doctor --fix-deps` / `ygg deploy --install-deps` 自动 pip install 缺失依赖 |
| `features.default_trigger_on_chat` | **true** | 对话默认触发 ygg 路由（部署默认，由强制钩子执行）。`true` 时每条用户消息提交前由 `beforeSubmitPrompt` 钩子自动跑 `scripts/hooks/trigger_detector.py`，按 `action` 路由到 ygg 记/想/思/运维对应功能；`false` 时仅显式 `ygg ...` 或命中高/中置信度模式时触发（省 token）。是否真正执行由各命令 behavior 门禁决定。本机覆盖：`behavior.local.yaml` 的 `features.default_trigger_on_chat`。详见 [triggers.md](triggers.md) 第 6 节 |
| `semantic_retrieval` | false | 语义检索（预留） |
| `progressive_load` | false | 渐进加载（预留） |
| `channel_filter` | true | channel 规范化过滤 |
| `time_decay_ranking` | false | 时间衰减排序 |
| `tag_cooccur_suggest` | true | tag 共现建议（PPMI，O2） |
| `dream_community_detect` | false | dream 社区检测 |

JSON 兼容层（可忽略）：`core_write.defaults.json` / `core_write.local.json`；`authorize_core_write()` 委托 `policies/behavior.py` / `policies/core_write.py`。  
|`audit` 日志：`yggforge-runtime/cache/core_write_audit.jsonl`。

## 4. 如何覆盖

在 `yggforge-runtime/config/behavior.local.yaml` 中写：

```yaml
version: 1
deploy:
  git_sync_after: deny
git:
  update: deny
  push: deny
memory:
  record_observation: allow
  mirror_to_lessons_inbox: allow
```

## 5. 行为决策与 `--yes` / `--no`

- `--yes`：本次强制 `allow`（不持久化）
- `--no`：本次强制 `deny`（不持久化）
- 交互时 `[a]lways allow`：写入 `behavior.local.yaml`

## 6. 实现约定

- 读取入口：`scripts/policies/behavior.py`（`load_behavior_config`, `authorize`, `resolve_mode`, `feature_enabled`）
- 写入口：`scripts/cli/runtime.py`（`behavior_gate`）
- 各叶子 CLI 在写操作前调用 `authorize()` 或 `behavior_gate()`
