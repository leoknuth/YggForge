#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Channel 规范化：读取 config/channels.yaml + behavior.channel 策略。"""

from __future__ import print_function

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib.repo_paths import CORE_ROOT

CHANNELS_PATH = CORE_ROOT / "config" / "channels.yaml"

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None


def _parse_simple_channels_yaml(text: str) -> Dict[str, Any]:
    """无 PyYAML 时解析 channels.yaml 最小子集。"""
    root: Dict[str, Any] = {"version": 1, "channels": {}}
    in_channels = False
    current: Optional[str] = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if stripped.startswith("version:"):
            continue
        if stripped == "channels:":
            in_channels = True
            current = None
            continue
        if not in_channels:
            continue
        if indent == 2 and stripped.endswith(":") and not stripped.startswith("-"):
            current = stripped[:-1].strip()
            root["channels"][current] = {"label": current, "category": "other", "aliases": []}
            continue
        if current is None:
            continue
        if stripped.startswith("label:"):
            root["channels"][current]["label"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("category:"):
            root["channels"][current]["category"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("-"):
            alias = stripped[1:].strip().strip('"').strip("'")
            if alias:
                root["channels"][current].setdefault("aliases", []).append(alias)
    return root


def load_channels_config() -> Dict[str, Any]:
    if not CHANNELS_PATH.exists():
        return {"version": 1, "channels": {}}
    text = CHANNELS_PATH.read_text(encoding="utf-8-sig")
    if yaml is not None:
        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else {"channels": {}}
    return _parse_simple_channels_yaml(text)


def _alias_index(cfg: Dict[str, Any]) -> Dict[str, str]:
    index: Dict[str, str] = {}
    channels = cfg.get("channels") or {}
    for cid, meta in channels.items():
        if not isinstance(meta, dict):
            continue
        index[str(cid).strip().lower()] = str(cid)
        for alias in meta.get("aliases") or []:
            key = str(alias).strip().lower()
            if key:
                index[key] = str(cid)
    return index




def normalize_channel(
    raw: Optional[str],
    *,
    unknown_policy: Optional[str] = None,
    default: Optional[str] = None,
) -> Tuple[Optional[str], Dict[str, Any]]:
    """返回 (canonical_or_None, meta)。

    meta.status: ok | fallback | rejected | empty
    """
    text = (raw or "").strip()
    try:
        from policies.behavior import load_behavior_config

        bcfg = load_behavior_config()
        ch = bcfg.get("channel") or {}
        policy = (unknown_policy or ch.get("unknown_policy") or "fallback").strip().lower()
        default_id = (default or ch.get("default") or "local").strip()
    except Exception:
        policy = (unknown_policy or "fallback").strip().lower()
        default_id = (default or "local").strip()

    if not text:
        return default_id or None, {"status": "empty", "input": "", "policy": policy}

    if policy == "off":
        return text, {"status": "ok", "input": text, "canonical": text, "policy": "off"}

    cfg = load_channels_config()
    index = _alias_index(cfg)
    key = text.lower()
    if key in index:
        cid = index[key]
        return cid, {"status": "ok", "input": text, "canonical": cid, "policy": policy}

    if policy == "enforce":
        return None, {
            "status": "rejected",
            "input": text,
            "policy": policy,
            "hint": "未知 channel；请使用 ygg behavior / channels.yaml 预设，或改 unknown_policy=fallback",
        }

    # fallback
    fb = "unknown" if "unknown" in (cfg.get("channels") or {}) else default_id
    return fb, {
        "status": "fallback",
        "input": text,
        "canonical": fb,
        "policy": policy,
    }
