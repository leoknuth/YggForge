# Cursor hooks（YggForge）

- `ygg_pre_submit.py` — `beforeSubmitPrompt`：检测意图并写 `last_trigger.json`
- `ygg_session_protocol.py` — `sessionStart`：注入路由协议 + 三源综合回答策略

注册文件在上一级：

- `hooks.json` — Linux / macOS（`python3 hooks/...`）
- `hooks.windows.json` — Windows（`py -X utf8 hooks/...`）

## 钩子分工

| 钩子 | 时机 | 作用 |
| --- | --- | --- |
| `beforeSubmitPrompt` | 每条用户消息提交前 | 跑 `trigger_detector.py`，落盘 `last_trigger.json`（`action` / `should_trigger`） |
| `sessionStart` | 会话开始 | 向 agent 注入完整协议：ygg 路由 + **三源综合回答**（模型推理 + ygg 检索 + 联网搜索） |

Agent 回答前必须先 Read `last_trigger.json`，再按 `action` 路由；无论 `action` 为何，问答场景须综合三源作答（纯运维指令与用户声明禁网/静默除外）。真源见 `knowledge/rules/standing-preference.md`；薄规则见 `profiles/cursor/rules/ygg-answer-synthesis.mdc`。

## 为何 Windows 用 `py -X utf8`

Cursor 在系统代码页非 UTF-8（如 CP936）的 Windows 上，会经 PowerShell 把 hook stdin JSON 的非 ASCII 字段双重编码或换成 `?`。这是 Cursor 侧已知问题，不是本仓库脚本单独的 bug。

`py -X utf8` 让 Python 进程默认用 UTF-8，避免在已污染的管道上再叠加一层 GBK 误读。真正可靠的 prompt 来源仍是 `ygg_pre_submit.py` 里对 `transcript_path` 的读取。

## Cursor bug 链接（请同步看 `ygg_pre_submit.py` 模块 docstring）

- https://forum.cursor.com/t/hook-stdin-pipe-double-encodes-non-ascii-on-non-utf-8-windows/159259
- https://forum.cursor.com/t/windows-cursor-hooks-stdin-corrupts-utf-8-text-before-hook-script-receives-it/162295
- https://forum.cursor.com/t/windows-cursor-hooks-corrupt-chinese-utf-8-characters-in-stdin-replaced-with-question-marks/142878
- https://forum.cursor.com/t/on-windows-chinese-prompt-in-hooks-stdin-becomes-while-execution-log-shows-correct-text/146604

系统侧绕过与排查：`docs/guide/install.md`（「hook 中文乱码」一节）。
