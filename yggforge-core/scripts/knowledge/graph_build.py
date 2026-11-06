#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识图索引构建。"""

from __future__ import print_function

import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.common import deep_merge_dict, normalize_tag
from lib.repo_paths import CORE_ROOT, RUNTIME_ROOT

from knowledge.graph_models import GraphError, KnowledgeEntry
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
        with defaults.open("r", encoding="utf-8-sig") as handle:
            config = json.load(handle)
    if local.exists():
        with local.open("r", encoding="utf-8-sig") as handle:
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
        [entry.path, entry.kind, title, tags, related, entry.priority,
         entry.status, entry.confidence, entry.last_reviewed, entry.source_fingerprint]
    )


def decode_catalog_payload(entry_id: str, payload: str) -> KnowledgeEntry:
    """解码 catalog payload。"""
    parts = payload.split("\t")
    # path, kind, title, tags, related, priority
    while len(parts) < 10:
        parts.append("")
    path, kind, title, tags_s, related_s, priority = parts[:6]
    status, confidence, last_reviewed, source_fingerprint = parts[6:10]
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
        status=status,
        confidence=confidence,
        last_reviewed=last_reviewed,
        source_fingerprint=source_fingerprint,
    )


def index_records(root: Path, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """生成预期索引内容，扫描与计算过程不写任何文件。"""
    entries, warnings = scan_knowledge_entries(
        root, max_depth=int(cfg.get("max_path_depth_under_knowledge", 5))
    )
    id_set = {entry.id for entry in entries}
    for entry in entries:
        for related_id in entry.related:
            if related_id not in id_set:
                warnings.append("条目 {0} 的 related 指向不存在的 id: {1}".format(entry.id, related_id))
    catalog = {entry.id: encode_catalog_payload(entry) for entry in entries}
    inverted: Dict[str, List[str]] = {}
    for entry in entries:
        for tag in set(entry.tags):
            inverted.setdefault(tag, []).append(entry.id)
    tag_records = {tag: "|".join(sorted(ids)) for tag, ids in sorted(inverted.items())}
    fingerprint = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item.path):
        fingerprint.update((entry.path + "\t" + entry.source_fingerprint + "\n").encode("utf-8"))
    return {"entries": entries, "warnings": warnings, "catalog": catalog,
            "tag_inverted": tag_records, "source_digest": fingerprint.hexdigest()}


def _stores(root: Path, cfg: Dict[str, Any]) -> Dict[str, SortedShardStore]:
    """按所选核心包根创建存储对象，不创建目录。"""
    paths = cfg.get("paths", {})
    storage = cfg.get("storage", {})
    kwargs = dict(
        shard_max_bytes=int(storage.get("shard_max_bytes", 8 * 1024 * 1024)),
        shard_max_lines=int(storage.get("shard_max_lines", 100000)),
        full_load_max_bytes=int(storage.get("full_load_max_bytes", 1024 * 1024 * 1024)),
        max_prefix_len=int(storage.get("max_prefix_len", 8)),
    )
    return {
        "catalog": SortedShardStore(root / str(paths.get("catalog_dir", "graph/catalog")), **kwargs),
        "tag_inverted": SortedShardStore(root / str(paths.get("tag_inverted_dir", "graph/tag-inverted")), **kwargs),
    }


def check_indexes(repo_root: Optional[Path] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """只读核对索引、源文档及源指纹的一致性。"""
    root = repo_root or CONTENT_ROOT
    cfg = config or load_graph_config(root)
    expected = index_records(root, cfg)
    warnings = list(expected["warnings"])
    consistency_errors: List[str] = []
    migration_required = False
    manifests: Dict[str, Any] = {}
    for name, store in _stores(root, cfg).items():
        try:
            manifest = store._load_manifest()
            manifests[name] = manifest
            actual = dict(store.items())
            legacy = name == "catalog" and any(len(payload.split("\t")) < 10 for payload in actual.values())
            if legacy:
                migration_required = True
                expected_records = {key: "\t".join(payload.split("\t")[:6]) for key, payload in expected[name].items()}
                actual_records = {key: "\t".join(payload.split("\t")[:6]) for key, payload in actual.items()}
            else:
                expected_records, actual_records = expected[name], actual
            if actual_records != expected_records:
                consistency_errors.append("{0} 索引与真源不一致，请执行 ygg graph build".format(name))
            if "source_digest" not in manifest:
                migration_required = True
            elif manifest["source_digest"] != expected["source_digest"]:
                consistency_errors.append("{0} 源指纹过期，请执行 ygg graph build".format(name))
        except (OSError, ValueError, KeyError, GraphError) as exc:
            consistency_errors.append("{0} 索引不可读: {1}".format(name, exc))
            manifests[name] = {"files": []}
    warnings.extend(consistency_errors)
    if migration_required:
        warnings.append("索引需要格式迁移（migration_required）：缺少状态元数据或源指纹；旧格式只能核验已有字段，不能确认正文新鲜度")
    index_status = "stale" if consistency_errors else ("migration_required" if migration_required else "consistent")
    return {"entries": len(expected["entries"]), "tags": len(expected["tag_inverted"]),
            "warnings": warnings, "catalog_manifest": manifests["catalog"],
            "tag_manifest": manifests["tag_inverted"], "source_digest": expected["source_digest"],
            "index_status": index_status, "migration_required": migration_required,
            "consistency_errors": consistency_errors,
            "source_consistency": "mismatch" if consistency_errors else ("metadata_only" if migration_required else "full")}


def build_indexes(
    repo_root: Optional[Path] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """扫描真源并写入 catalog / tag-inverted 有序分片索引。"""
    root = repo_root or CONTENT_ROOT
    cfg = config or load_graph_config(root)
    expected = index_records(root, cfg)
    manifests = {}
    for name, store in _stores(root, cfg).items():
        manifests[name] = store.write_records(expected[name], source_digest=expected["source_digest"])

    return {
        "entries": len(expected["entries"]),
        "tags": len(expected["tag_inverted"]),
        "warnings": expected["warnings"],
        "catalog_manifest": manifests["catalog"],
        "tag_manifest": manifests["tag_inverted"],
        "source_digest": expected["source_digest"],
    }
