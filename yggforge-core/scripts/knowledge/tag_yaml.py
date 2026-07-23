#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tag-synonyms / tag-graph YAML 读写与无 PyYAML 兜底解析。"""

from __future__ import print_function

from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

from lib.repo_paths import CORE_ROOT

CONTENT_ROOT = CORE_ROOT
# 历史 API 名：内容根别名（非 git 仓库根）。真 git 根见 lib.repo_paths.REPO_ROOT。
REPO_ROOT = CONTENT_ROOT
DEFAULT_SYNONYMS_PATH = CONTENT_ROOT / "graph" / "tag-synonyms.yaml"
DEFAULT_TAG_GRAPH_PATH = CONTENT_ROOT / "graph" / "tag-graph.yaml"


def _parse_simple_synonyms_yaml(text: str) -> Dict[str, Any]:
    """无 PyYAML 时解析 tag-synonyms.yaml 的最小子集。"""
    data: Dict[str, Any] = {"synonyms": {}}
    current: Optional[str] = None
    in_synonyms = False
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "synonyms:":
            in_synonyms = True
            continue
        if stripped.startswith("version:"):
            continue
        if not in_synonyms:
            continue
        if line.startswith("  ") and stripped.endswith(":") and not stripped.startswith("-"):
            current = stripped[:-1].strip().strip('"')
            data["synonyms"][current] = []
            continue
        if current and stripped.startswith("-"):
            item = stripped[1:].strip().strip('"').strip("'")
            data["synonyms"][current].append(item)
    return data


def _parse_simple_tag_graph_yaml(text: str) -> Dict[str, Any]:
    """无 PyYAML 时解析 tag-graph.yaml 的最小子集（支持 weight 行内映射）。"""
    data: Dict[str, Any] = {"version": 1, "defaults": {}, "tags": {}}
    section = None
    current_tag: Optional[str] = None
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("version:"):
            data["version"] = stripped.split(":", 1)[1].strip()
            continue
        if stripped == "defaults:":
            section = "defaults"
            current_tag = None
            continue
        if stripped == "tags:":
            section = "tags"
            current_tag = None
            continue
        if section == "defaults" and ":" in stripped and not stripped.startswith("-"):
            key, val = stripped.split(":", 1)
            data["defaults"][key.strip()] = val.strip()
            continue
        if section != "tags":
            continue
        # tag key
        if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            current_tag = stripped[:-1].strip()
            data["tags"][current_tag] = {"related": []}
            continue
        if current_tag is None:
            continue
        if stripped.startswith("-"):
            item = stripped[1:].strip()
            if item.startswith("{") and "tag:" in item:
                # { tag: foo, weight: 1.0 }
                tag_name = ""
                weight = 1.0
                body = item.strip("{} ")
                for part in body.split(","):
                    if ":" not in part:
                        continue
                    k, v = part.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    if k == "tag":
                        tag_name = v
                    elif k == "weight":
                        try:
                            weight = float(v)
                        except ValueError:
                            weight = 1.0
                if tag_name:
                    data["tags"][current_tag]["related"].append({"tag": tag_name, "weight": weight})
            else:
                name = item.strip('"').strip("'")
                if name:
                    data["tags"][current_tag]["related"].append({"tag": name, "weight": 1.0})
    return data


def _dump_simple_tag_graph_yaml(data: Dict[str, Any]) -> str:
    lines = [
        "# Tag 邻接图（权威、可修改）",
        "#",
        "# 本文件由 ygg tag / remember 维护；也可人工编辑。",
        "",
        "version: {0}".format(data.get("version", 1)),
        "",
        "defaults:",
    ]
    defaults = data.get("defaults") or {}
    lines.append("  hop: {0}".format(defaults.get("hop", 2)))
    lines.append("  max_nodes: {0}".format(defaults.get("max_nodes", 64)))
    lines.append("")
    lines.append("tags:")
    for tag, body in sorted((data.get("tags") or {}).items(), key=lambda x: str(x[0])):
        lines.append("  {0}:".format(tag))
        related = []
        if isinstance(body, dict):
            related = body.get("related") or []
        if not related:
            lines.append("    related: []")
            continue
        lines.append("    related:")
        for item in related:
            if isinstance(item, dict):
                name = item.get("tag", "")
                weight = item.get("weight", 1.0)
            else:
                name = item
                weight = 1.0
            if name:
                lines.append("      - {{ tag: {0}, weight: {1} }}".format(name, weight))
    lines.append("")
    return "\n".join(lines)


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    name = path.name.lower()
    if "synonym" in name:
        return _parse_simple_synonyms_yaml(text)
    if "tag-graph" in name:
        return _parse_simple_tag_graph_yaml(text)
    raise RuntimeError("需要 PyYAML 才能读取 {0}".format(path))


def dump_yaml(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml is not None:
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
        path.write_text(text, encoding="utf-8")
        return
    if "tag-graph" in path.name.lower() or "tags" in data:
        path.write_text(_dump_simple_tag_graph_yaml(data), encoding="utf-8")
        return
    raise RuntimeError("需要 PyYAML 才能写 {0}".format(path))
