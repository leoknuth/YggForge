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

from typing import Any, Dict, List, Optional, Tuple


def parse_front_matter(text: str) -> Tuple[Dict[str, Any], str]:
    """解析开头的 YAML front matter（``---\\n ... \\n---\\n``）。

    轻量实现：支持 ``key: value``、空值开启列表、``- item`` / ``  - item`` 列表项。
    不依赖 PyYAML，与历史 graph_scan / file_backend 行为对齐。
    无 front matter 时返回 ``({}, text)``。
    """
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
        if not stripped:
            current_list_key = None
            continue
        if line.startswith("  - ") or line.startswith("- "):
            item = stripped[2:].strip().strip('"').strip("'")
            if current_list_key:
                metadata.setdefault(current_list_key, [])
                # 布尔字面量
                if item.lower() in ("true", "false"):
                    metadata[current_list_key].append(item.lower() == "true")
                else:
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
        # 行内空列表
        if value in ("[]", "{}", "null", "~"):
            metadata[key] = []
            current_list_key = None
            continue
        scalar = value.strip('"').strip("'")
        if scalar.lower() in ("true", "false"):
            metadata[key] = scalar.lower() == "true"
        else:
            metadata[key] = scalar
        current_list_key = None
    body = text[end + 5 :]
    return metadata, body


def split_front_matter_lines(text: str) -> Tuple[Optional[List[str]], str]:
    """拆出 front matter 原始行列表（不含包围的 ---），供行级编辑。

    无 front matter 时返回 ``(None, text)``。
    """
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
                        if any(c in text for c in (":", "#", '"')):
                            text = '"{0}"'.format(text.replace('"', '\\"'))
                        lines.append("  - {0}".format(text))
        else:
            text = str(value)
            if any(c in text for c in (":", "#", '"', "\n")) or text == "":
                text = '"{0}"'.format(text.replace('"', '\\"'))
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
