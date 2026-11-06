# -*- coding: utf-8 -*-
"""将简单自然语言意图路由为有参数的 CLI 调用。"""

from __future__ import annotations

import re
from typing import List, Tuple

from cli.errors import YggError
from cli.runtime import KNOWN_TARGETS


def extract_first_url(text: str) -> str:
    match = re.search(r"https?://[^\s<>]+", text)
    return match.group(0).rstrip("，。；、,.;!）)]\"'") if match else ""


def infer_intent(text: str) -> Tuple[str, List[str]]:
    intent = text.strip()
    if not intent:
        raise YggError("ygg requires an explicit action or a natural-language intent.")
    # 简单指令保留正文；说明性问题优先只读查询。
    intent = re.sub(r"^(?:请帮我|请你|麻烦你|帮我|请)\s*", "", intent)
    lowered = intent.lower()
    targets = [target for target in KNOWN_TARGETS if target in lowered]

    note = re.match(r"^(?:记住|记一下|写进错题本|经验记下来|错题本|remember)\s*[:：]?\s*(.*)$", intent, re.I)
    if note:
        return "remember", [note.group(1)] if note.group(1) else []
    query = re.match(r"^(?:回忆|搜索记忆|查一下我的|recall|search[- ]memory)\s*[:：]?\s*(.*)$", intent, re.I)
    if query:
        return "recall", [query.group(1)] if query.group(1) else []
    tags = re.match(r"^(?:按标签)?(?:联想|关联检索|associate|tag\s+联想)\s*[:：]?\s*(.*)$", intent, re.I)
    if tags:
        arguments: List[str] = []
        for tag in re.split(r"[\s,，]+", tags.group(1).strip()):
            if tag:
                arguments.extend(["--tag", tag])
        return "associate", arguments

    destinations = {"规则": "rule", "经验": "lesson", "模板": "template", "参考知识": "reference", "决策": "decision"}
    promotion = re.match(r"^(?:晋升|升级)\s*(.+?)\s*(?:为|成)\s*(规则|经验|模板|参考知识|决策)$", intent)
    if promotion:
        return "promote", [destinations[promotion.group(2)], promotion.group(1).strip()]
    promotion = re.match(r"^(?:升级成|晋升为)(规则|经验|模板|参考知识|决策)\s+(.+)$", intent)
    if promotion:
        return "promote", [destinations[promotion.group(1)], promotion.group(2).strip()]

    url = extract_first_url(intent)
    if url and (lowered.startswith(("http://", "https://")) or any(word in intent for word in ("收进知识库", "归档", "收录", "入库", "链接"))):
        return "ingest", [url]

    if any(word in lowered for word in ("部署", "deploy")):
        negated = re.search(r"(?:不要|不需要|不必|禁止|勿|别|不是要)\s*(?:(?:实际|真实|直接|现在|再次|执行|进行)\s*)?(?:部署|deploy)|(?:do not|don't)\s+deploy", lowered)
        if negated:
            return "deploy", ["--no"] + (targets or ["cursor"])
        if any(word in lowered for word in ("怎么", "如何", "是否", "是不是", "状态", "了吗", "how ", "what ", "is ")):
            return "status", targets or ["cursor"]
        flags = re.findall(r"(?<!\S)--[\w-]+(?:=[^\s]+)?", intent)
        if re.findall(r"--[\w-]+(?:=[^\s]+)?", intent) != flags:
            raise YggError("控制参数必须独立分词；复杂意图请使用显式 ygg deploy 命令。")
        allowed_flags = {"--yes", "--no", "--dry-run", "--backup", "--install-deps"}
        if any(flag not in allowed_flags for flag in flags):
            raise YggError("复杂部署参数请使用显式 ygg deploy 命令，不能省略控制参数。")
        modes = [mode for mode in ("link", "copy", "render") if mode in lowered]
        if len(modes) > 1:
            raise YggError("部署意图包含多个模式，请明确选择 link、copy 或 render。")
        return "deploy", modes + (targets or ["cursor"]) + flags
    if any(word in lowered for word in ("状态", "status", "是不是link", "is it link")):
        return "status", targets or ["cursor"]
    if any(word in lowered for word in ("导入", "导回", "import")):
        return "import", targets or ["cursor"]
    if any(word in lowered for word in ("推上去", "推送", "push")):
        return "push", targets
    if any(word in lowered for word in ("同步", "update", "拉最新", "pull latest")):
        return "sync", targets
    if any(word in lowered for word in ("提炼", "distill")):
        value = re.sub(r"^(?:提炼|distill)\s*[:：]?\s*", "", intent, flags=re.I)
        return "distill", [value] if value and value != intent else []
    if any(word in lowered for word in ("做梦", "dream", "整理记忆", "consolidate memory")):
        return "dream", []
    if any(word in lowered for word in ("建图", "graph build", "重建知识图", "重建索引")):
        return "graph", ["build"]
    if any(word in lowered for word in ("索引", "index")):
        return "index", []
    addition = re.match(r"^(?:加标签|添加标签)\s+(.+)$", intent)
    if addition:
        return "tag", ["--add"] + re.split(r"[\s,，]+", addition.group(1))
    if any(word in lowered for word in ("标签", "tag list", "管理标签")):
        return "tag", ["--list"]
    if any(word in lowered for word in ("体检", "健康检查", "doctor", "health check")):
        return "doctor", []
    raise YggError("Could not infer a YggForge action; use an explicit command for complex arguments.")
