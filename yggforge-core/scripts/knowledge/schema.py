#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 ``schemas/knowledge-item.schema.yaml`` 校验 front matter（含 type 分层）。

轻量实现：不依赖 jsonschema / PyYAML。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from lib.front_matter import as_str_list
from lib.repo_paths import CORE_ROOT

SCHEMA_PATH = CORE_ROOT / "schemas" / "knowledge-item.schema.yaml"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

KNOWN_TYPES = (
    "rule",
    "lesson",
    "reference",
    "decision",
    "template",
    "source",
    "distilled-source",
    # YggForge 内部插件类型（plugins/ 下，由 graph_scan 一并索引）
    "skill",
    "mcp-server",
    "hook",
)

_SCHEMA_CACHE: Optional[Dict[str, Any]] = None


def _parse_schema_yaml(text: str) -> Dict[str, Any]:
    """解析本仓库 schema 的最小子集（required / enums / types 字段名）。"""
    data: Dict[str, Any] = {
        "required_for_index": [],
        "recommended_when_active": [],
        "enums": {},
        "booleans": set(),
        "arrays": set(),
        "dates": set(),
        "type_fields": {t: set() for t in KNOWN_TYPES},
    }
    section = ""  # required | recommended | common | types
    current_type: Optional[str] = None
    in_type_fields = False
    current_prop: Optional[str] = None
    prop_context = ""  # common | type_field

    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped == "required_for_index:":
            section, current_type, in_type_fields, current_prop = "required", None, False, None
            continue
        if stripped == "recommended_when_active:":
            section, current_type, in_type_fields, current_prop = "recommended", None, False, None
            continue
        if stripped == "common:":
            section, current_type, in_type_fields, current_prop = "common", None, False, None
            prop_context = "common"
            continue
        if stripped == "types:":
            section, current_type, in_type_fields, current_prop = "types", None, False, None
            continue

        if section in ("required", "recommended") and stripped.startswith("- "):
            name = stripped[2:].strip()
            if section == "required":
                data["required_for_index"].append(name)
            else:
                data["recommended_when_active"].append(name)
            continue

        # types.<name>:
        if section == "types" and re.match(r"^[a-z0-9-]+:\s*$", stripped) and not line.startswith(" "):
            continue
        if section == "types" and re.match(r"^  [a-z0-9-]+:\s*$", line):
            current_type = stripped[:-1].strip()
            in_type_fields = False
            continue
        if section == "types" and current_type and stripped == "fields:":
            in_type_fields = True
            prop_context = "type_field"
            continue
        if section == "types" and current_type and stripped.startswith("body:"):
            in_type_fields = False
            continue

        # property key under common or type fields
        # common: "  id: {type: string}" or multiline "  status:"
        prop_match = re.match(r"^  ([a-z_][a-z0-9_]*)\s*:\s*(.*)$", line)
        type_prop_match = re.match(r"^      ([a-z_][a-z0-9_]*)\s*:\s*(.*)$", line)

        key = None
        rest = ""
        if section == "common" and prop_match:
            key, rest = prop_match.group(1), prop_match.group(2).strip()
            prop_context = "common"
        elif section == "types" and in_type_fields and type_prop_match and current_type:
            key, rest = type_prop_match.group(1), type_prop_match.group(2).strip()
            prop_context = "type_field"
            data["type_fields"].setdefault(current_type, set()).add(key)

        if key:
            current_prop = key
            _apply_type_hint(data, key, rest)
            # inline enum values: type: enum / values on next lines handled below
            if "enum" in rest and "values:" in rest:
                m = re.search(r"values:\s*\[([^\]]+)\]", rest)
                if m:
                    data["enums"][key] = [x.strip() for x in m.group(1).split(",") if x.strip()]
            continue

        # nested under property: type: / values:
        if current_prop and stripped.startswith("type:"):
            typ = stripped.split(":", 1)[1].strip()
            _register_prop_type(data, current_prop, typ)
            continue
        if current_prop and stripped.startswith("values:"):
            raw_vals = stripped.split(":", 1)[1].strip()
            if raw_vals.startswith("[") and raw_vals.endswith("]"):
                data["enums"][current_prop] = [
                    x.strip() for x in raw_vals[1:-1].split(",") if x.strip()
                ]
            continue

    return data


def _apply_type_hint(data: Dict[str, Any], key: str, rest: str) -> None:
    if "{type: boolean" in rest or "type: boolean" in rest:
        data["booleans"].add(key)
    if "{type: array" in rest or "type: array" in rest:
        data["arrays"].add(key)
    if "{type: date" in rest or "type: date" in rest:
        data["dates"].add(key)
    if "type: enum" in rest:
        m = re.search(r"values:\s*\[([^\]]+)\]", rest)
        if m:
            data["enums"][key] = [x.strip() for x in m.group(1).split(",") if x.strip()]


def _register_prop_type(data: Dict[str, Any], key: str, typ: str) -> None:
    if typ == "boolean":
        data["booleans"].add(key)
    elif typ == "array":
        data["arrays"].add(key)
    elif typ == "date":
        data["dates"].add(key)


def load_schema(path: Path = SCHEMA_PATH) -> Dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    if not path.exists():
        _SCHEMA_CACHE = {
            "required_for_index": ["id", "title", "status", "type"],
            "recommended_when_active": ["confidence", "last_reviewed", "tags"],
            "enums": {
                "type": list(KNOWN_TYPES),
                "status": [
                    "draft",
                    "active",
                    "deprecated",
                    "recorded",
                    "accepted",
                    "proposed",
                    "superseded",
                ],
                "confidence": ["low", "medium", "high"],
                "priority": ["low", "medium", "high", "unset"],
                "projection_mode": ["sync", "manual"],
            },
            "booleans": {"always_apply", "objective"},
            "arrays": {
                "tags",
                "keywords",
                "related",
                "owners",
                "agent_targets",
                "projection",
                "when_to_read",
                "applies_to",
                "does_not_apply_to",
                "facts",
                "inferences",
                "practices",
                "risks",
                "image_urls",
                "consequences_positive",
                "consequences_negative",
                "supersedes",
                # plugins/ 专用数组字段
                "depends_on",
                "inputs",
                "outputs",
                "tools",
                "trigger_tags",
                "args",
            },
            "dates": {"last_reviewed", "recorded_at"},
            "type_fields": {t: set() for t in KNOWN_TYPES},
        }
        return _SCHEMA_CACHE
    _SCHEMA_CACHE = _parse_schema_yaml(path.read_text(encoding="utf-8-sig"))
    # ensure type enum present
    _SCHEMA_CACHE.setdefault("enums", {})["type"] = list(KNOWN_TYPES)
    return _SCHEMA_CACHE


def reset_schema_cache() -> None:
    global _SCHEMA_CACHE
    _SCHEMA_CACHE = None


def infer_type_from_path(rel_posix: str) -> str:
    """路径缺省推断 type（写入时应显式写 type）。"""
    if rel_posix.startswith("knowledge/rules/"):
        return "rule"
    if rel_posix.startswith("knowledge/templates/"):
        return "template"
    if rel_posix.startswith("knowledge/lessons/"):
        return "lesson"
    if rel_posix.startswith("knowledge/reference/"):
        return "reference"
    if rel_posix.startswith("knowledge/decisions/"):
        return "decision"
    if rel_posix.startswith("knowledge/sources/distilled/"):
        return "distilled-source"
    if rel_posix.startswith("knowledge/sources/"):
        return "source"
    # YggForge 内部插件（plugins/ 下）
    if rel_posix.startswith("plugins/skills/"):
        return "skill"
    if rel_posix.startswith("plugins/mcp-servers/"):
        return "mcp-server"
    if rel_posix.startswith("plugins/hooks/"):
        return "hook"
    if rel_posix.startswith("plugins/rules/"):
        return "rule"
    return "unknown"


def resolve_entry_type(metadata: Dict[str, Any], rel_posix: str = "") -> str:
    """优先 front matter ``type``，否则路径推断。不使用已弃用的 ``kind`` 字段。"""
    raw = metadata.get("type")
    text = str(raw or "").strip().lower()
    if text in KNOWN_TYPES:
        return text
    if rel_posix:
        return infer_type_from_path(rel_posix)
    return "unknown"


def validate_front_matter(
    metadata: Dict[str, Any],
    *,
    path: str = "",
    kind: str = "",
    require_index_fields: bool = True,
) -> Tuple[List[str], List[str]]:
    """校验 metadata，返回 ``(errors, warnings)``。"""
    schema = load_schema()
    errors: List[str] = []
    warnings: List[str] = []
    loc = path or "<memory>"

    def note(level: str, msg: str) -> None:
        text = "{0}: {1}".format(loc, msg)
        if level == "error":
            errors.append(text)
        else:
            warnings.append(text)

    entry_type = resolve_entry_type(metadata, path)
    if kind and kind != entry_type and entry_type != "unknown":
        # kind 参数仅作提示
        pass
    if entry_type == "unknown":
        note("error", "无法解析 type（请设置 type: rule|lesson|…）")
    elif "type" not in metadata:
        note("warn", "缺少显式 type 字段（当前按路径推断为 '{0}'）".format(entry_type))

    if require_index_fields:
        for key in schema.get("required_for_index", []):
            if key == "type":
                if entry_type == "unknown":
                    continue
                if "type" not in metadata:
                    continue  # already warned
                continue
            val = metadata.get(key)
            if val is None or val == "" or val == []:
                note("warn", "缺少索引必需字段 '{0}'".format(key))
            elif isinstance(val, str) and (val.startswith("<") or "slug" in val):
                note("warn", "字段 '{0}' 仍是模板占位".format(key))

    status = str(metadata.get("status") or "").strip().lower()
    if status == "active" and entry_type in ("rule", "lesson", "decision", ""):
        for key in schema.get("recommended_when_active", []):
            val = metadata.get(key)
            if val is None or val == "" or val == []:
                note("warn", "active 条目建议提供 '{0}'".format(key))

    for key, allowed in schema.get("enums", {}).items():
        if key not in metadata:
            continue
        val = metadata.get(key)
        if val is None or val == "":
            continue
        text = str(val).strip().lower()
        if text.startswith("<"):
            continue
        allowed_l = [a.lower() for a in allowed]
        if text not in allowed_l:
            note("error", "字段 '{0}' 值 '{1}' 不在 {2}".format(key, val, allowed))

    for key in schema.get("booleans", set()):
        if key not in metadata:
            continue
        val = metadata[key]
        if isinstance(val, bool):
            continue
        if isinstance(val, str) and val.strip().lower() in ("true", "false", ""):
            continue
        note("error", "字段 '{0}' 应为布尔，实际为 {1}".format(key, type(val).__name__))

    for key in schema.get("dates", set()):
        if key not in metadata:
            continue
        val = str(metadata.get(key) or "").strip().strip('"')
        if not val or val.startswith("<") or "YYYY" in val:
            continue
        if not DATE_RE.match(val):
            note("error", "字段 '{0}' 日期格式应为 YYYY-MM-DD，实际 '{1}'".format(key, val))

    if metadata.get("always_apply") in (True, "true", "True"):
        mode = str(metadata.get("projection_mode") or "").strip().lower()
        if mode and mode not in ("sync", "manual"):
            note("error", "projection_mode 应为 sync|manual")

    # front matter 禁止 kind（用 type）；catalog/CLI 的 kind 是另一层命名
    if "kind" in metadata:
        note("error", "front matter 请使用 type，不要使用 kind")

    return errors, warnings


def format_issues(errors: List[str], warnings: List[str]) -> List[str]:
    out = ["schema_error  : {0}".format(e) for e in errors]
    out.extend("schema_warn   : {0}".format(w) for w in warnings)
    return out
