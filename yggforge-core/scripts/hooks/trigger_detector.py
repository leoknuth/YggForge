#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YggForge 触发检测器：识别用户消息意图，路由到 ygg 记/想/思/运维各类功能。

供 Agent / 钩子调用参考，不自动执行 ygg 命令。
是否真正执行由 ygg 各命令的 behavior 门禁（ask/allow/deny）与命令自身逻辑决定。

检测器只负责「是否触发 ygg」与 `action` 路由；**综合回答策略**（模型推理 + ygg 检索 + 联网搜索）
由 agent 在作答时另行执行，见 `knowledge/rules/standing-preference.md` 与
`profiles/cursor/rules/ygg-answer-synthesis.mdc`。

也可：
    python scripts/hooks/trigger_detector.py "我以前说过路径怎么写"
"""

from __future__ import print_function

from pathlib import Path
import sys

# hooks/<script>.py → scripts/
SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
SCRIPT_DIR = SCRIPTS_ROOT

import json
import re
from typing import Dict, List, Optional, Tuple

# 否定/跳过模式：无论如何都不触发
NEGATIVE_PATTERNS = [
    r"^(你?好|在吗|在不在|hello|hi)$",
    r"今天[几号星期].*",
    r"现在[几]?点.*",
    r"^[嗯哦啊哈].*",
    r"^好的?$",
    r"^知道了?$",
    r"这次不用(查记忆|触发ygg).*",
    r"静默模式.*",
]

# 各 ygg 功能的意图模式（按 记/想/思/运维 分类）。
# 顺序即匹配优先级；命中后返回对应 action（= ygg 功能名）。
INTENT_PATTERNS: List[Tuple[str, List[str], float]] = [
    # ---- 记（录入）----
    ("remember", [
        r"[帮请]?[我]?记[住下著].*",
        r"记住[这那此].*",
        r"写进错题本.*",
        r"记(一条|一笔|下来).*",
        r"以后一直这样.*",
    ], 0.9),
    ("ingest", [
        r"把(这篇|这个|这条)(链接|文章|文件|材料)?收进知识库.*",
        r"收进知识库.*",
        r"归档(这篇|这个|这条).*",
        r"收下(这个|这篇|这条).*",
    ], 0.9),
    ("distill", [
        r"提炼(这篇|这个|来源).*",
        r"蒸馏(这个|来源).*",
        r"从(这篇|来源)提炼.*",
        r"把(这篇|来源)(提炼|蒸馏).*",
    ], 0.9),
    # ---- 想（联想检索）----
    ("recall", [
        r"我以前.*[说做提记讲].*",
        r"我之前.*[说做提记讲].*",
        r"上次[那个的]?.*",
        r"前[几天次回].*",
        r"我[有没有是].*[跟对和]?你?[说提讲].*",
        r"查一下[我的]?.*",
        r"搜索[我的]?.*记忆.*",
        r"回忆(一下|起).*",
    ], 0.9),
    ("associate", [
        r"联想[一下到].*",
        r"关联[一下到]?.*",
        r"按(标签|tag)联想.*",
    ], 0.9),
    ("tag", [
        r"加(个)?标签.*",
        r"关联标签.*",
        r"标签传播.*",
        r"(建|加)标签(关系|边).*",
        r"管理标签.*",
    ], 0.9),
    ("graph", [
        r"重建(索引|图).*",
        r"建图.*",
        r"图(检查|校验).*",
        r"graph build.*",
        r"重建(知识)?索引.*",
    ], 0.9),
    # ---- 思（反思沉淀）----
    ("dream", [
        r"扫描(候选|待晋升).*",
        r"找重复(候选)?.*",
        r"该晋升(什么|哪些).*",
        r"巩固扫描.*",
        r"dream(扫描)?.*",
    ], 0.9),
    ("promote", [
        r"升级(成|为)(规则|rule|lesson|模板|template).*",
        r"晋升(为|到)(rule|lesson|template|规则|模板).*",
        r"提升(为|到)(规则|lesson|模板).*",
        r"把这个经验升级.*",
    ], 0.9),
    # ---- 运维 ----
    ("status", [
        r"看(部署)?状态.*",
        r"部署状态.*",
        r"ygg status.*",
    ], 0.8),
    ("deploy", [
        r"部署到.*",
        r"重新部署.*",
        r"ygg deploy.*",
    ], 0.8),
    ("sync", [
        r"(多机)?同步.*",
        r"ygg (sync|push).*",
        r"推送到远程.*",
    ], 0.8),
    ("behavior", [
        r"看(当前)?(行为|策略).*",
        r"改(行为|策略)配置.*",
        r"ygg behavior.*",
    ], 0.8),
    # ---- 中置信度：选型/决策，建议 associate ----
    ("associate_suggested", [
        r"我[应该该].[选做用].*[还是或者].*",
        r"[哪哪个]个[更好更合适更优].*",
        r"[给]?我[个些]?[建议议意见].*",
        r"[有过].*[经验教训].*",
        r"[遇遇到].*[问题困难].*",
    ], 0.6),
]

def _load_chat_trigger_default() -> Optional[bool]:
    """读 behavior 配置的 features.default_trigger_on_chat。

    返回 None 表示读不到配置（按原行为，省 token）；True/False 为显式开关。
    覆盖顺序：behavior.defaults.yaml ← yggforge-runtime/config/behavior.local.yaml。
    """
    try:
        # 本文件在 hooks/；库模块在 scripts/ 根
        scripts_dir = str(Path(__file__).resolve().parents[1])
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from policies.behavior import feature_enabled

        return bool(feature_enabled("default_trigger_on_chat"))
    except Exception:
        return None

class TriggerDetector(object):
    def __init__(self) -> None:
        self.negative_patterns = [re.compile(p, re.IGNORECASE) for p in NEGATIVE_PATTERNS]
        self.intent_patterns: List[Tuple[str, List[re.Pattern], float]] = [
            (name, [re.compile(p, re.IGNORECASE) for p in pats], conf)
            for name, pats, conf in INTENT_PATTERNS
        ]

    def analyze(self, text: str, chat_default: Optional[bool] = None) -> Dict:
        text = (text or "").strip()
        if not text:
            return {"should_trigger": False, "confidence": 0, "reason": "空消息", "action": "skip"}

        if chat_default is None:
            chat_default = _load_chat_trigger_default()

        # 显式 ygg 前缀：直接路由（交给 ygg 命令解释），不依赖模式匹配
        if text.lower().startswith("ygg ") or text.lower() == "ygg":
            return {
                "should_trigger": True,
                "confidence": 1.0,
                "reason": "显式 ygg 前缀触发",
                "action": "explicit_ygg",
                "rest": text[3:].strip() if len(text) > 3 else "",
            }

        # 否定模式优先
        for pattern in self.negative_patterns:
            if pattern.search(text):
                return {
                    "should_trigger": False,
                    "confidence": 0,
                    "reason": "匹配否定/跳过模式",
                    "matched": pattern.pattern,
                    "action": "skip",
                }

        # 按优先级匹配各功能意图
        for name, patterns, conf in self.intent_patterns:
            for pattern in patterns:
                if pattern.search(text):
                    return {
                        "should_trigger": True,
                        "confidence": conf,
                        "reason": "命中 {0} 意图".format(name),
                        "matched": pattern.pattern,
                        "action": name,
                    }

        # 无具体意图：看默认开关
        if chat_default:
            return {
                "should_trigger": True,
                "confidence": 0.5,
                "reason": "默认触发开启（features.default_trigger_on_chat=true）",
                "action": "default_on",
            }

        return {
            "should_trigger": False,
            "confidence": 0.1,
            "reason": "无匹配模式",
            "action": "skip",
        }

def should_trigger_yggforge(text: str, chat_default: Optional[bool] = None) -> Dict:
    return TriggerDetector().analyze(text, chat_default=chat_default)

if __name__ == "__main__":
    # 输入优先走环境变量，原因有两层：
    # 1) Windows argv / launcher 对长中文可能截断或按系统代码页再损坏；
    # 2) Cursor hook stdin 本身会污染非 ASCII（Forum #159259 / #162295 等），
    #    pre_submit 已用 transcript_path 等修好 prompt 后，经 YGG_TRIGGER_PROMPT
    #    整段传入，避免二次经过损坏通道。详见 profiles/cursor/hooks/ygg_pre_submit.py。
    import os

    if len(sys.argv) > 1 and sys.argv[1] in ("--from-env", "--env"):
        text = os.environ.get("YGG_TRIGGER_PROMPT", "") or ""
    elif len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = os.environ.get("YGG_TRIGGER_PROMPT", "") or ""
    chat_default = _load_chat_trigger_default()
    result = should_trigger_yggforge(text, chat_default=chat_default)
    result["chat_default_trigger"] = chat_default
    print(json.dumps(result, ensure_ascii=False, indent=2))
