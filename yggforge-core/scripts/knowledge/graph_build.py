#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识图索引构建。"""

from __future__ import print_function

import json
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.common import deep_merge_dict, normalize_tag
from lib.repo_paths import CORE_ROOT, HOST_RUNTIME_ROOT, host_generated_root

from knowledge.graph_models import GraphError, KnowledgeEntry
from knowledge.graph_scan import scan_knowledge_entries
from knowledge.shard_store import SortedShardStore
from knowledge.space_lock import graph_lock

CONTENT_ROOT = CORE_ROOT
# 历史 API 名：此处指内容根（yggforge-core），非 git 仓库根。真 git 根见 lib.repo_paths.REPO_ROOT。
REPO_ROOT = CONTENT_ROOT
DEFAULT_CONFIG_PATH = CORE_ROOT / "config" / "graph.defaults.json"
LOCAL_CONFIG_PATH = HOST_RUNTIME_ROOT / "config" / "graph.local.json"


def load_graph_config(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """加载 graph 默认配置与可选本机覆盖。"""
    root = repo_root or CORE_ROOT
    config: Dict[str, Any] = {}
    defaults = root / "config" / "graph.defaults.json"
    local = HOST_RUNTIME_ROOT / "config" / "graph.local.json"
    if defaults.exists():
        with defaults.open("r", encoding="utf-8-sig") as handle:
            config = json.load(handle)
    if local.exists():
        with local.open("r", encoding="utf-8-sig") as handle:
            config = deep_merge_dict(config, json.load(handle))
    config.setdefault("space_id", "shared")
    config.setdefault("staging_root", str(host_generated_root(root.parent) / "scratch/graphs"))
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
        root, max_depth=int(cfg.get("max_path_depth_under_knowledge", 5)),
        content_roots=cfg.get("content_roots"), allowed_paths=cfg.get("allowed_paths"),
        include_inbox=bool(cfg.get("include_inbox", False)), space_id=str(cfg.get("space_id", "shared")),
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
    if cfg.get("owner_role"):
        from lib.front_matter import source_text_fingerprint
        for key in ("tag_graph", "tag_synonyms"):
            relative = cfg.get("paths", {}).get(key, "graph/tag-graph.yaml" if key == "tag_graph" else "graph/tag-synonyms.yaml")
            path = root / relative
            if path.is_file():
                fingerprint.update((relative + "\t" + source_text_fingerprint(path.read_bytes()) + "\n").encode("utf-8"))
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


def _check_indexes(repo_root: Optional[Path] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
            if manifest.get("space_id", "shared") != str(cfg.get("space_id", "shared")):
                consistency_errors.append("{0} 索引知识空间身份不一致".format(name))
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
    space=None,
) -> Dict[str, Any]:
    """扫描真源并写入 catalog / tag-inverted 有序分片索引。"""
    root = space.root if space is not None else repo_root or CONTENT_ROOT
    cfg = space.config if space is not None else config or load_graph_config(root)
    if cfg.get("allowed_paths") is not None and not cfg.get("owner_role"):
        raise GraphError("授权共享视图只读，不能用它覆盖全局索引；请构建完整共享空间。")
    with graph_lock(root, cfg):
        expected = index_records(root, cfg)
        manifests = {}
        paths = cfg.get("paths", {})
        destinations = {"catalog": root / str(paths.get("catalog_dir", "graph/catalog")), "tag_inverted": root / str(paths.get("tag_inverted_dir", "graph/tag-inverted"))}
        graph_root = destinations["catalog"].parent
        graph_root.mkdir(parents=True, exist_ok=True)
        staging_root = Path(cfg.get("staging_root", graph_root))
        staging_root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".graph-build-", dir=str(staging_root)))
        replaced = []
        try:
            staging_config = dict(cfg, paths={"catalog_dir": "catalog", "tag_inverted_dir": "tag-inverted"})
            for name, store in _stores(staging, staging_config).items():
                manifests[name] = store.write_records(expected[name], source_digest=expected["source_digest"])
                manifests[name]["space_id"] = str(cfg.get("space_id", "shared"))
                with store.manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
                    json.dump(manifests[name], handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
            for name, destination in destinations.items():
                destination.parent.mkdir(parents=True, exist_ok=True)
                old = staging / (name + "-previous")
                if destination.exists():
                    os.replace(str(destination), str(old))
                replaced.append((destination, old))
                os.replace(str(staging / ("catalog" if name == "catalog" else "tag-inverted")), str(destination))
        except Exception:
            for destination, old in reversed(replaced):
                if destination.exists():
                    shutil.rmtree(str(destination))
                if old.exists():
                    os.replace(str(old), str(destination))
            raise
        finally:
            shutil.rmtree(str(staging), ignore_errors=True)

    return {
        "entries": len(expected["entries"]),
        "tags": len(expected["tag_inverted"]),
        "warnings": expected["warnings"],
        "catalog_manifest": manifests["catalog"],
        "tag_manifest": manifests["tag_inverted"],
        "source_digest": expected["source_digest"],
        "space_id": str(cfg.get("space_id", "shared")),
    }


def check_indexes(repo_root: Optional[Path] = None, config: Optional[Dict[str, Any]] = None, space=None) -> Dict[str, Any]:
    """在同一空间锁内校验，两组分片不会被并发构建拆开读取。"""
    root = space.root if space is not None else repo_root or CONTENT_ROOT
    cfg = space.config if space is not None else config or load_graph_config(root)
    with graph_lock(root, cfg):
        result = _check_indexes(root, cfg)
        result["space_id"] = str(cfg.get("space_id", "shared"))
        return result
