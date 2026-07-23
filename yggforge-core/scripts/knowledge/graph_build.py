#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识图索引构建。"""

from __future__ import print_function

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.common import deep_merge_dict, normalize_tag
from lib.repo_paths import CORE_ROOT, GENERATED_ROOT, RUNTIME_ROOT, ensure_layout

from knowledge.graph_models import KnowledgeEntry
from knowledge.graph_scan import scan_knowledge_entries
from knowledge.shard_store import SortedShardStore

CONTENT_ROOT = CORE_ROOT
# 历史 API 名：此处指内容根（yggforge-core），非 git 仓库根。真 git 根见 lib.repo_paths.REPO_ROOT。
REPO_ROOT = CONTENT_ROOT
DEFAULT_CONFIG_PATH = CORE_ROOT / "config" / "graph.defaults.json"
LOCAL_CONFIG_PATH = RUNTIME_ROOT / "config" / "graph.local.json"


def load_graph_config(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """加载 graph 默认配置与可选本机覆盖。"""
    root = repo_root or CORE_ROOT
    config: Dict[str, Any] = {}
    defaults = root / "config" / "graph.defaults.json"
    local = RUNTIME_ROOT / "config" / "graph.local.json"
    if defaults.exists():
        with defaults.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    if local.exists():
        with local.open("r", encoding="utf-8") as handle:
            config = deep_merge_dict(config, json.load(handle))
    return config


def encode_catalog_payload(entry: KnowledgeEntry) -> str:
    """把条目编码为 catalog 行的 payload（TSV 安全：用 | 连接列表）。"""
    # 字段内不用 tab；列表用 |
    tags = "|".join(entry.tags)
    related = "|".join(entry.related)
    # 标题里若有 tab/换行则替换
    title = entry.title.replace("\t", " ").replace("\n", " ")
    return "\t".join(
        [entry.path, entry.kind, title, tags, related, entry.priority]
    )


def decode_catalog_payload(entry_id: str, payload: str) -> KnowledgeEntry:
    """解码 catalog payload。"""
    parts = payload.split("\t")
    # path, kind, title, tags, related, priority
    while len(parts) < 6:
        parts.append("")
    path, kind, title, tags_s, related_s, priority = parts[:6]
    tags = [normalize_tag(t) for t in tags_s.split("|") if t]
    related = [r for r in related_s.split("|") if r]
    return KnowledgeEntry(
        id=entry_id,
        path=path,
        kind=kind,
        title=title,
        tags=tags,
        related=related,
        priority=priority or "unset",
    )


def build_indexes(
    repo_root: Optional[Path] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """扫描真源并写入 catalog / tag-inverted 有序分片索引。"""
    root = repo_root or CONTENT_ROOT
    cfg = config or load_graph_config(root)
    paths = cfg.get("paths", {})
    storage = cfg.get("storage", {})
    max_depth = int(cfg.get("max_path_depth_under_knowledge", 5))

    entries, warnings = scan_knowledge_entries(root, max_depth=max_depth)

    # 校验 related 指向是否存活
    id_set = {e.id for e in entries}
    for entry in entries:
        for rel_id in entry.related:
            if rel_id not in id_set:
                warnings.append(
                    "条目 {0} 的 related 指向不存在的 id: {1}".format(entry.id, rel_id)
                )

    catalog_records = {e.id: encode_catalog_payload(e) for e in entries}
    inverted: Dict[str, List[str]] = {}
    for entry in entries:
        for tag in entry.tags:
            inverted.setdefault(tag, []).append(entry.id)
    inverted_records = {
        tag: "|".join(sorted(ids)) for tag, ids in sorted(inverted.items())
    }

    ensure_layout()
    # 图机器索引随核心包部署（CORE_ROOT/graph/），使 associate 在部署后仍可命中。
    catalog_dir = CORE_ROOT / str(paths.get("catalog_dir", "graph/catalog"))
    tag_dir = CORE_ROOT / str(paths.get("tag_inverted_dir", "graph/tag-inverted"))

    common_kwargs = dict(
        shard_max_bytes=int(storage.get("shard_max_bytes", 8 * 1024 * 1024)),
        shard_max_lines=int(storage.get("shard_max_lines", 100000)),
        full_load_max_bytes=int(storage.get("full_load_max_bytes", 1024 * 1024 * 1024)),
        max_prefix_len=int(storage.get("max_prefix_len", 8)),
    )
    catalog_store = SortedShardStore(catalog_dir, **common_kwargs)
    tag_store = SortedShardStore(tag_dir, **common_kwargs)

    catalog_manifest = catalog_store.write_records(catalog_records)
    tag_manifest = tag_store.write_records(inverted_records)

    return {
        "entries": len(entries),
        "tags": len(inverted_records),
        "warnings": warnings,
        "catalog_manifest": catalog_manifest,
        "tag_manifest": tag_manifest,
    }
