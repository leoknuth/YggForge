#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YggForge 强制检索钩子（sessionStart）。

会话开始时由 Cursor 调用，尝试把路由协议 + 三源综合回答策略注入
``additional_context``。注意：Cursor IDE 存在已知竞态，``sessionStart`` 的
``additional_context`` 可能被静默丢弃（社区 Forum #157141 / #158452）。
因此协议硬路径是：beforeSubmitPrompt 落盘的 last_trigger.json +
AGENTS.md / knowledge 真源 / 核心包内 profiles/cursor/rules/*.mdc（或项目级
部署投影的 ``<repo>/.cursor/rules/*.mdc``），
不得只依赖本钩子的 additional_context。

协议要求 agent 在回答每条用户消息前，先 Read last_trigger.json（由
beforeSubmitPrompt 钩子每条消息自动刷新），按 action 路由到 ygg 记/想/思/运维
各类功能；作答时综合模型推理、ygg 检索与联网搜索（见 standing-preference.md）。
是否真正执行 ygg 命令由 behavior 门禁（ask/allow/deny）决定。

路径定位：兼容仓库内（yggforge-core）与部署后（~/.cursor/yggforge-core）两种环境。

编码注意（与 ygg_pre_submit.py 同源）：
  Cursor 在非 UTF-8 Windows 上污染 hook stdin（Forum #159259 / #162295 等）。
  sessionStart 不依赖 prompt 文本，但仍须二进制 drain stdin，避免管道阻塞，
  且勿用系统代码页文本模式误读。Windows 入口见 hooks.windows.json 的
  ``py -X utf8``。完整 bug 链接与绕过说明见 ygg_pre_submit.py 模块 docstring。
"""

from __future__ import print_function

import json
import os
import sys
from pathlib import Path


def _stdout_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _read_stdin() -> str:
    """稳健读取并 drain stdin（二进制 + UTF-8）。

    sessionStart 不解析 prompt，只消费掉避免管道阻塞。
    与 pre_submit 一样避免中文 Windows 文本模式按 GBK 误读
    （Cursor bug：https://forum.cursor.com/t/159259 ）。
    """
    data = b""
    try:
        data = os.read(sys.stdin.fileno(), 1 << 22)
    except Exception:
        data = b""
    if not data:
        try:
            data = sys.stdin.buffer.read() or b""
        except Exception:
            data = b""
    if not data:
        return ""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _bootstrap_core() -> Path:
    env = os.environ.get("YGGFORGE_CORE_ROOT", "").strip()
    candidates = []
    if env:
        candidates.append(Path(env).resolve())
    start = Path(__file__).resolve().parent
    for p in [start] + list(start.parents):
        candidates.append(p / "yggforge-core")
        if (p / "scripts" / "hooks" / "trigger_detector.py").exists():
            candidates.append(p)
    for cand in (Path.home() / ".cursor" / "yggforge-core", Path.home() / ".codex" / "yggforge-core"):
        candidates.append(cand)
    for cand in candidates:
        try:
            cand = cand.resolve()
        except Exception:
            continue
        if (cand / "scripts" / "hooks" / "trigger_detector.py").exists():
            scripts = str(cand / "scripts")
            if scripts not in sys.path:
                sys.path.insert(0, scripts)
            return cand
    return start


def main() -> int:
    _stdout_utf8()

    core_root = _bootstrap_core()
    cache_file = None
    ygg_cli = None
    try:
        from lib.repo_paths import RUNTIME_ROOT, REPO_ROOT
        cache_file = RUNTIME_ROOT / "cache" / "last_trigger.json"
        ygg_cli = REPO_ROOT / "ygg.ps1"
    except Exception:
        cache_file = core_root / "yggforge-runtime" / "cache" / "last_trigger.json"
        ygg_cli = core_root.parent / "ygg.ps1"

    protocol = (
        "[YggForge 强制钩子已启用——完整覆盖 记/想/思/运维]\n\n"
        "本会话启用了 ygg 强制钩子。在你回答任何用户消息之前，必须执行以下流程，不得跳过：\n\n"
        "1. 用 Read 工具读取：{cache}\n"
        "2. 按 action 路由到对应 ygg 功能（是否真正执行由 ygg 各命令的 behavior 门禁 ask/allow/deny 决定）：\n"
        "   - skip / 读不到文件 → 跳过 ygg 检索（fail open），仍执行综合回答策略："
        "模型推理 + 按需联网 → 综合作答并标注来源/置信度\n"
        "   - explicit_ygg → 按「ygg + 自然语言」解释规则路由（见 docs/reference/triggers.md 第 4 节）\n"
        "   - remember → `{ygg} remember \"<内容>\" --tags ... --title ...`\n"
        "   - ingest → `{ygg} ingest <来源>`\n"
        "   - distill → `{ygg} distill <来源>`\n"
        "   - recall → 先提炼关键词，`{ygg} recall \"<词>\" --json`；必要时 `{ygg} associate --tag ...`\n"
        "   - associate → 提炼 seed tags，`{ygg} associate --tag <t1> --tag <t2> --json`\n"
        "   - tag → `{ygg} tag --list / --add / --relate ...`\n"
        "   - graph → `{ygg} graph build`\n"
        "   - dream → `{ygg} dream --scan`\n"
        "   - promote → `{ygg} promote lesson|rule|template <entry> ...`\n"
        "   - status → `{ygg} status`\n"
        "   - deploy → `{ygg} deploy link <target>`\n"
        "   - sync → `{ygg} sync` / `{ygg} push`\n"
        "   - behavior → `{ygg} behavior`\n"
        "   - default_on → 模型先形成初步判断 → 提炼 seed tags → `{ygg} associate --tag ... --json` → "
        "Read 命中真源 → 必要时 `{ygg} recall` → 联网搜索（事实/时效类必搜）→ 综合三源作答并标注来源/置信度\n"
        "   - associate_suggested → 建议先 `{ygg} associate`，必要时 `{ygg} recall` → 综合三源作答\n"
        "3. 综合回答策略（所有问答必须执行，纯运维指令与用户声明禁网/静默除外）：\n"
        "   综合三源——ygg 检索（按 action；skip 可跳过）、模型自身推理、联网搜索（WebSearch/WebFetch）；"
        "不得仅凭 ygg 命中作答。权重：时效/事实→联网↑；仓库规范/记忆→ygg↑；推理/方案→模型↑。"
        "真源：knowledge/rules/standing-preference.md；薄规则：profiles/cursor/rules/ygg-answer-synthesis.mdc。\n"
        "4. last_trigger.json 由 beforeSubmitPrompt 钩子在每条用户消息提交前自动刷新，你读到的是最新检测结果。\n"
        "5. 检测步骤已硬性下沉到钩子，你不得凭模型自身判断跳过检测。是否触发、触发哪个功能，"
        "由 ygg 内部参数（features.default_trigger_on_chat 与 trigger_detector 模式匹配）"
        "和各命令 behavior 门禁决定，钩子只负责强制过检 + 路由建议。"
    ).format(cache=cache_file, ygg=ygg_cli)

    try:
        _read_stdin()  # drain stdin，避免管道阻塞
    except Exception:
        pass

    print(json.dumps({"additional_context": protocol}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
