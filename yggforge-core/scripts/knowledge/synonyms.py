#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tag 同义词与规范语言加载。"""

from __future__ import print_function

from pathlib import Path
from typing import Dict

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

from lib.common import normalize_tag

from knowledge.tag_yaml import DEFAULT_SYNONYMS_PATH, load_yaml


def load_tag_language(path: Path = DEFAULT_SYNONYMS_PATH, default: str = "en") -> str:
    """读取 tag 规范语言（en/zh），缺省/异常返回 default。

    配置见 graph/tag-synonyms.yaml 的 language 字段。供 agent 在生成 seed tags
    或新增 tag 前查询该用什么语言。无 PyYAML 时行扫描 language: 字段兜底。
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except Exception:
        return default
    if yaml is not None:
        try:
            raw = yaml.safe_load(text) or {}
            lang = str(raw.get("language") or "").strip().lower()
            if lang in ("en", "zh"):
                return lang
            return default
        except Exception:
            pass
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("language:"):
            val = line.split(":", 1)[1].strip().strip('"').strip("'").lower()
            if val in ("en", "zh"):
                return val
    return default


def load_synonym_map(path: Path = DEFAULT_SYNONYMS_PATH) -> Dict[str, str]:
    """返回 synonym_or_canonical -> canonical。"""
    reverse: Dict[str, str] = {}
    raw = load_yaml(path)
    synonyms = raw.get("synonyms") or {}
    for canonical, alts in synonyms.items():
        key = normalize_tag(str(canonical))
        reverse[key] = key
        if isinstance(alts, list):
            for alt in alts:
                reverse[normalize_tag(str(alt))] = key
        elif alts:
            reverse[normalize_tag(str(alts))] = key
    return reverse
