# Cursor skills 投影层

本目录存放 **Cursor 原生可发现的薄入口**（`SKILL.md` stub），不是技能正文。

| 层 | 位置 | 职责 |
|---|---|---|
| 真源 | `yggforge-core/plugins/skills/*.md` | 完整协议与步骤 |
| 投影源（本目录） | `profiles/cursor/skills/<name>/SKILL.md` | 短 stub：触发描述 + Read 真源 |
| 部署目标 | `~/.cursor/skills/` 或 `<repo>/.cursor/skills/` | `ygg deploy` link/copy |

约定：

- **deploy 只投影、不生成内容**；改 stub 在本目录，改协议在 `plugins/`。
- 插件增多后可用单独的 project/render 步骤把 stub **生成进本目录**（可审 diff），再 deploy；不要在 Agent 家目录现场造文件。
- 与 `profiles/cursor/rules/*.mdc` 对称。
