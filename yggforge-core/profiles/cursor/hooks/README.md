# Cursor hooks（YggForge）

## 目录

- [钩子分工](#钩子分工)
- [验证本轮结果](#验证本轮结果)
- [输入与跨平台](#输入与跨平台)

## 钩子分工

- ygg_pre_submit.py：消息提交前检测；按会话和消息保存结果，完成写入后放行。
- ygg_session_protocol.py：会话开始注入路由与综合回答策略；独立部署使用核心包内 CLI。
- 上级 hooks.json 用于 Linux/macOS，hooks.windows.json 用于 Windows。

## 验证本轮结果

检测结果位于运行时 cache/triggers/，会话和消息 ID 以摘要作为路径键。
消费者使用 ygg_pre_submit.py --read-trigger，提供 conversation-id、
message-id 或本轮原文；验证会话、消息、原文摘要和默认 5 分钟有效期。
文件通过原子替换发布，不读取旧的共享 last_trigger.json。

缺少匹配身份、结果过期或原文不同，都返回 skip。
无 hooks 环境按本轮 AGENTS 约定判断或重新检测，不使用别人的缓存。
本轮显式授权仍由既有 behavior 门禁处理，不因读取缓存再增加一次确认。

协议回归见 tests/test_hooks_protocol.py；综合回答真源见
knowledge/rules/standing-preference.md。

## 输入与跨平台

两个 hooks 循环读取 stdin 到 EOF，输入上限 4 MiB。
优先采用有效的当前 prompt；仅在文本缺失/损坏且 transcript 消息身份对应时恢复，
不会因为普通问号或 Windows 平台无条件使用旧 transcript。
编码候选不要求 Linux 存在 Windows 专用 mbcs。

Windows 用 py -X utf8，Linux/macOS 用 python3。
诊断与 Cursor 上游编码问题见 docs/guide/install.md。
