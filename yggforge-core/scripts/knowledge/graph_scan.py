#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 knowledge/ 真源 Markdown 条目。"""

from __future__ import print_function

from pathlib import Path
import hashlib
from typing import List, Set, Tuple

from lib.common import normalize_tag
from lib.front_matter import as_str_list, parse_front_matter

from knowledge.graph_models import KnowledgeEntry
from knowledge.schema import (
    format_issues,
    infer_type_from_path,
    resolve_entry_type,
    validate_front_matter,
)

# 扫描真源时跳过的路径片段 / 文件名模式
SKIP_DIR_NAMES = {"inbox", "index", "graph", "__pycache__"}

# 兼容旧 import：from knowledge.graph_scan import parse_front_matter
__all__ = [
    "SKIP_DIR_NAMES",
    "parse_front_matter",
    "kind_from_path",
    "path_depth_under_knowledge",
    "should_skip_path",
    "as_str_list",
    "scan_knowledge_entries",
]


def kind_from_path(rel_posix: str) -> str:
    """根据相对路径推断条目 type（兼容旧名 kind_from_path）。"""
    return infer_type_from_path(rel_posix)


def path_depth_under_knowledge(rel_posix: str) -> int:
    """计算相对 knowledge/ 的路径深度（含文件名）。"""
    return _depth_under(rel_posix, "knowledge/")


def _depth_under(rel_posix: str, prefix: str) -> int:
    """计算相对某根目录（如 knowledge/ 或 plugins/）的路径深度（含文件名）。"""
    if not rel_posix.startswith(prefix):
        return -1
    rest = rel_posix[len(prefix):]
    return len([part for part in rest.split("/") if part])


# graph_scan 扫描的内容根：knowledge/（治理真源）+ plugins/（YggForge 内部插件）。
# 两者复用同一 front matter schema 与 KnowledgeEntry 模型，使 ygg associate 能
# 联想发现规则/经验/技能/MCP/钩子（智能插件管理器）。
SCAN_ROOTS = ("knowledge", "plugins")


def should_skip_path(path: Path, repo_root: Path) -> bool:
    """判断扫描时是否跳过该文件。"""
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return True
    parts = [part.lower() for part in rel.parts]
    if any(part in SKIP_DIR_NAMES for part in parts):
        return True
    name = path.name.lower()
    if name == "readme.md":
        return True
    if name.endswith(".template.md"):
        return True
    return False


def scan_knowledge_entries(
    repo_root: Path,
    max_depth: int,
    include_inactive: bool = False,
) -> Tuple[List[KnowledgeEntry], List[str]]:
    """扫描 knowledge/ 与 plugins/ 下正式条目，返回条目列表与警告。"""
    entries: List[KnowledgeEntry] = []
    warnings: List[str] = []
    seen_ids: Set[str] = set()

    for root_name in SCAN_ROOTS:
        content_root = repo_root / root_name
        if not content_root.exists():
            continue
        prefix = root_name + "/"
        for path in sorted(content_root.rglob("*.md")):
            if should_skip_path(path, repo_root):
                continue
            rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
            depth = _depth_under(rel, prefix)
            if depth < 0:
                continue
            if depth > max_depth:
                warnings.append("路径深度超过 {0}: {1}".format(max_depth, rel))
                continue
            text = path.read_text(encoding="utf-8-sig")
            metadata, _body = parse_front_matter(text)
            entry_type = resolve_entry_type(metadata, rel)
            schema_errors, schema_warnings = validate_front_matter(
                metadata, path=rel, kind=entry_type, require_index_fields=True
            )
            warnings.extend(format_issues(schema_errors, schema_warnings))
            status = str(metadata.get("status", "")).strip().lower()
            if entry_type == "rule" and status != "active" and not include_inactive:
                continue
            entry_id = str(metadata.get("id", "")).strip()
            if not entry_id or entry_id.startswith("<") or "slug" in entry_id:
                warnings.append("缺少有效 id，已跳过: {0}".format(rel))
                continue
            if entry_id in seen_ids:
                warnings.append("重复 id '{0}': {1}".format(entry_id, rel))
                continue
            seen_ids.add(entry_id)
            tags = [normalize_tag(t) for t in as_str_list(metadata.get("tags"))]
            tags = [t for t in tags if t and not t.startswith("<")]
            related = [str(x).strip() for x in as_str_list(metadata.get("related")) if str(x).strip()]
            related = [x for x in related if not x.startswith("<")]
            title = str(metadata.get("title") or path.stem).strip()
            priority = str(metadata.get("priority", "unset")).strip().lower() or "unset"
            entries.append(
                KnowledgeEntry(
                    id=entry_id,
                    path=rel,
                    kind=entry_type,
                    title=title,
                    tags=tags,
                    related=related,
                    priority=priority,
                    status=status,
                    confidence=str(metadata.get("confidence", "")).strip().lower(),
                    last_reviewed=str(metadata.get("last_reviewed", "")).strip(),
                    source_fingerprint=hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            )
    return entries, warnings
