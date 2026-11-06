#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一解析 Markdown YAML front matter。

所有脚本应 ``from lib.front_matter import parse_front_matter``，勿再各自实现。
只依赖标准库，可被任意叶子 CLI / 子包安全 import。

提供：
- ``parse_front_matter``：返回 ``(metadata: dict, body: str)``
- ``split_front_matter_lines``：返回 ``(front_lines|None, body)``，供 promote 行级编辑
- ``render_with_front_matter``：把 dict 或行列表与正文拼回完整文档
- ``as_str_list``：把 tags/related 等字段规范成字符串列表
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple


def _without_comment(text: str) -> str:
    """只移除引号外、由空白引出的 YAML 行尾注释。"""
    quote = ""
    escaped = False
    for idx, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if quote == '"' and char == "\\":
            escaped = True
            continue
        if char in ('"', "'"):
            if not quote:
                quote = char
            elif quote == char:
                quote = ""
        elif char == "#" and not quote and (idx == 0 or text[idx - 1].isspace()):
            return text[:idx].rstrip()
    return text.strip()


def _parse_value(text: str) -> Any:
    """解析标量与行内列表，不依赖 PyYAML。"""
    value = _without_comment(text.strip())
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        parts: List[str] = []
        start = 0
        quote = ""
        escaped = False
        depth = 0
        for idx, char in enumerate(inner):
            if escaped:
                escaped = False
                continue
            if quote == '"' and char == "\\":
                escaped = True
                continue
            if char in ('"', "'"):
                if not quote:
                    quote = char
                elif quote == char:
                    quote = ""
            elif not quote:
                if char in "[{":
                    depth += 1
                elif char in "]}":
                    depth -= 1
                elif char == "," and depth == 0:
                    parts.append(inner[start:idx])
                    start = idx + 1
        if quote or depth != 0:
            raise ValueError("无效 YAML 行内列表: {0}".format(value))
        parts.append(inner[start:])
        return [_parse_value(part) for part in parts if part.strip()]
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except ValueError:
            return value[1:-1].replace('\\"', '"')
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if value in ("{}", "null", "~"):
        return []
    return value


def parse_front_matter(text: str) -> Tuple[Dict[str, Any], str]:
    """解析开头的 YAML front matter（``---\\n ... \\n---\\n``）。

    轻量实现：支持 ``key: value``、空值开启列表、``- item`` / ``  - item`` 列表项。
    不依赖 PyYAML，与历史 graph_scan / file_backend 行为对齐。
    无 front matter 时返回 ``({}, text)``。
    """
    text = text.lstrip("\ufeff").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    metadata: Dict[str, Any] = {}
    current_list_key: Optional[str] = None
    for raw_line in text[4:end].splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if not stripped:
            current_list_key = None
            continue
        if line.startswith("  - ") or line.startswith("- "):
            item = _parse_value(stripped[2:])
            if current_list_key:
                metadata.setdefault(current_list_key, [])
                metadata[current_list_key].append(item)
            continue
        if ":" not in line:
            current_list_key = None
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            metadata[key] = []
            current_list_key = key
            continue
        metadata[key] = _parse_value(value)
        current_list_key = None
    body = text[end + 5 :]
    return metadata, body


def split_front_matter_lines(text: str) -> Tuple[Optional[List[str]], str]:
    """拆出 front matter 原始行列表（不含包围的 ---），供行级编辑。

    无 front matter 时返回 ``(None, text)``。
    """
    text = text.lstrip("\ufeff").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, text
    front = text[4:end].splitlines()
    body = text[end + 5 :]
    return front, body


def render_with_front_matter(front: Any, body: str) -> str:
    """拼回完整 Markdown。

    ``front`` 可为：
    - ``None``：只返回 body
    - ``list[str]``：已是 YAML 行
    - ``dict``：简单序列化为 YAML 子集（标量 / 字符串列表 / 布尔）
    """
    if front is None:
        return body
    if isinstance(front, list):
        return "---\n{0}\n---\n{1}".format("\n".join(front), body)
    if isinstance(front, dict):
        lines = dump_front_matter_lines(front)
        return "---\n{0}\n---\n{1}".format("\n".join(lines), body)
    raise TypeError("front must be None, list[str], or dict")


def dump_front_matter_lines(metadata: Dict[str, Any]) -> List[str]:
    """把 metadata dict 序列化为 front matter 行（YAML 子集）。"""
    lines: List[str] = []
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, bool):
            lines.append("{0}: {1}".format(key, "true" if value else "false"))
        elif isinstance(value, list):
            if not value:
                lines.append("{0}: []".format(key))
            else:
                lines.append("{0}:".format(key))
                for item in value:
                    if isinstance(item, bool):
                        lines.append("  - {0}".format("true" if item else "false"))
                    else:
                        text = str(item)
                        if any(c in text for c in (":", "#", '"', "\\", "\n", ",", "[", "]")) or text.lower() in ("true", "false", "null", "~"):
                            text = json.dumps(text, ensure_ascii=False)
                        lines.append("  - {0}".format(text))
        else:
            text = str(value)
            if any(c in text for c in (":", "#", '"', "\n", "\\", "[", "]")) or text == "" or text.lower() in ("true", "false", "null", "~"):
                text = json.dumps(text, ensure_ascii=False)
            lines.append("{0}: {1}".format(key, text))
    return lines


def as_str_list(value: Any) -> List[str]:
    """把 front matter 字段规范成非空字符串列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if text in ("[]", "{}", "null", "~"):
        return []
    return [text] if text else []
