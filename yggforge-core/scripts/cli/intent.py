# -*- coding: utf-8 -*-
"""Ygg CLI 自然语言意图推断（``infer_intent``）。

与钩子侧 ``trigger_detector`` 是独立模式集：本模块只服务 ``ygg`` 命令行入口。
"""

from __future__ import annotations

from typing import List, Tuple

from cli.errors import YggError
from cli.runtime import KNOWN_TARGETS


def infer_intent(text: str) -> Tuple[str, List[str]]:
    lowered = text.strip().lower()

    if not lowered:
        raise YggError("`ygg` requires either an explicit action or a natural-language intent.")

    if lowered.startswith("http://") or lowered.startswith("https://"):
        return "ingest", [text.strip()]

    if ("http://" in text or "https://" in text) and any(
        word in text for word in ["收进知识库", "归档", "收录", "入库", "链接"]
    ):
        url = extract_first_url(text)
        if url:
            return "ingest", [url]

    if any(word in lowered for word in ["部署", "deploy"]):
        targets = [candidate for candidate in KNOWN_TARGETS if candidate in lowered]
        return "deploy", targets or ["cursor"]

    if any(word in lowered for word in ["状态", "status", "怎么部署", "是不是link", "is it link"]):
        targets = [candidate for candidate in KNOWN_TARGETS if candidate in lowered]
        return "status", targets or ["cursor"]

    if any(word in lowered for word in ["导入", "导回", "import"]):
        targets = [candidate for candidate in KNOWN_TARGETS if candidate in lowered]
        return "import", targets or ["cursor"]

    if any(word in lowered for word in ["同步", "update", "拉最新", "pull latest"]):
        if any(word in lowered for word in ["推上去", "push"]):
            return "push", []
        return "sync", []

    if any(word in lowered for word in ["提炼", "distill"]):
        return "distill", []

    if any(word in lowered for word in ["做梦", "dream", "整理记忆", "consolidate memory"]):
        return "dream", []

    if any(word in lowered for word in ["回忆", "recall", "搜索记忆", "search memory", "search-memory"]):
        return "recall", []

    if any(word in lowered for word in ["错题本", "记住", "remember", "经验记下来"]):
        return "remember", []

    if any(word in lowered for word in ["升级成规则", "晋升", "promote"]):
        return "promote", []

    if any(word in lowered for word in ["索引", "index"]):
        return "index", []

    if any(word in lowered for word in ["建图", "graph build", "重建知识图"]):
        return "graph", ["build"]

    if any(word in lowered for word in ["联想", "associate", "关联检索", "tag 联想"]):
        return "associate", []

    if any(word in lowered for word in ["标签", "tag list", "tag propagate", "管理标签"]):
        return "tag", []

    if any(word in lowered for word in ["体检", "健康检查", "doctor", "health check"]):
        return "doctor", []

    raise YggError("Could not infer a YggForge action from the provided intent.")


def extract_first_url(text: str) -> str:
    for token in text.split():
        if token.startswith("http://") or token.startswith("https://"):
            return token
    return ""


