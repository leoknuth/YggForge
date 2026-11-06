#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识图索引查询。"""

from __future__ import print_function

from pathlib import Path
import hashlib
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from lib.common import normalize_tag
from lib.front_matter import as_str_list, parse_front_matter

from knowledge.graph_build import (
    REPO_ROOT,
    decode_catalog_payload,
    load_graph_config,
)
from knowledge.graph_models import AssociateHit, KnowledgeEntry
from knowledge.schema import resolve_entry_type
from knowledge.shard_store import SortedShardStore
from knowledge.tag_graph import TagExpandInfo, TagGraph


class KnowledgeGraphIndex(object):
    """已构建索引上的查询入口。"""

    def __init__(self, repo_root: Optional[Path] = None, config: Optional[Dict[str, Any]] = None) -> None:
        self.repo_root = repo_root or REPO_ROOT
        self.config = config or load_graph_config(self.repo_root)
        paths = self.config.get("paths", {})
        storage = self.config.get("storage", {})
        self.tag_graph = TagGraph.load(
            self.repo_root / str(paths.get("tag_graph", "graph/tag-graph.yaml")),
            self.config,
        )
        self.catalog = SortedShardStore(
            self.repo_root / str(paths.get("catalog_dir", "graph/catalog")),
            shard_max_bytes=int(storage.get("shard_max_bytes", 8 * 1024 * 1024)),
            shard_max_lines=int(storage.get("shard_max_lines", 100000)),
            full_load_max_bytes=int(storage.get("full_load_max_bytes", 1024 * 1024 * 1024)),
            max_prefix_len=int(storage.get("max_prefix_len", 8)),
        )
        self.tag_inverted = SortedShardStore(
            self.repo_root / str(paths.get("tag_inverted_dir", "graph/tag-inverted")),
            shard_max_bytes=int(storage.get("shard_max_bytes", 8 * 1024 * 1024)),
            shard_max_lines=int(storage.get("shard_max_lines", 100000)),
            full_load_max_bytes=int(storage.get("full_load_max_bytes", 1024 * 1024 * 1024)),
            max_prefix_len=int(storage.get("max_prefix_len", 8)),
        )
        self._synonym_map = self._load_synonym_map()
        self._entry_cache: Dict[str, Optional[KnowledgeEntry]] = {}
        self._missing_entries: Set[str] = set()

    def _load_synonym_map(self) -> Dict[str, str]:
        """加载 tag-synonyms.yaml 的 synonym→canonical 映射（查询侧归并用）。"""
        try:
            from knowledge.synonyms import load_synonym_map
            paths = self.config.get("paths", {})
            return load_synonym_map(self.repo_root / str(paths.get("tag_synonyms", "graph/tag-synonyms.yaml")))
        except Exception:
            return {}

    def _canonical_tag(self, tag: str) -> str:
        """normalize 后再经 synonyms 归并到 canonical tag；未知则返回 normalize 结果。"""
        key = normalize_tag(tag)
        if not key:
            return ""
        return self._synonym_map.get(key, key)

    def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """按 id 取条目。"""
        if entry_id in self._entry_cache:
            return self._entry_cache[entry_id]
        payload = self.catalog.get(entry_id)
        if payload is None:
            return None
        entry = decode_catalog_payload(entry_id, payload)
        source = (self.repo_root / entry.path).resolve()
        try:
            source.relative_to(self.repo_root.resolve())
            raw = source.read_bytes()
        except (ValueError, OSError):
            self._entry_cache[entry_id] = None
            self._missing_entries.add(entry_id)
            return None
        metadata, _body = parse_front_matter(raw.decode("utf-8-sig"))
        entry.index_stale = entry.source_fingerprint != hashlib.sha256(raw).hexdigest()
        entry.kind = resolve_entry_type(metadata, entry.path)
        entry.title = str(metadata.get("title") or entry.title)
        entry.priority = str(metadata.get("priority") or "unset").strip().lower()
        entry.status = str(metadata.get("status", "")).strip().lower()
        entry.confidence = str(metadata.get("confidence", "")).strip().lower()
        entry.last_reviewed = str(metadata.get("last_reviewed", "")).strip()
        entry.tags = [normalize_tag(tag) for tag in as_str_list(metadata.get("tags"))]
        entry.related = as_str_list(metadata.get("related"))
        self._entry_cache[entry_id] = entry
        return entry

    def ids_for_tag(self, tag: str) -> List[str]:
        """单个 tag 下的全部条目 id。"""
        payload = self.tag_inverted.get(self._canonical_tag(tag))
        if not payload:
            return []
        return [part for part in payload.split("|") if part]

    def expand_tags(
        self,
        seeds: Sequence[str],
        hop: Optional[int] = None,
        max_nodes: Optional[int] = None,
    ) -> Dict[str, TagExpandInfo]:
        """扩展多级相关 tag（加权）。"""
        return self.tag_graph.expand(seeds, hop=hop, max_nodes=max_nodes)

    def associate(
        self,
        seed_tags: Sequence[str],
        hop: Optional[int] = None,
        include_entry_related: bool = True,
        entry_related_hops: Optional[int] = None,
        limit: Optional[int] = 10,
        types: Optional[Sequence[str]] = None,
        include_inactive: bool = False,
    ) -> Tuple[List[AssociateHit], Dict[str, Any]]:
        """联想查询主函数。

        流程：seed tags → hop 加权扩 tag → tag 反查并集 ids →（可选）条目 related 一跳 → 解析路径。
        ``types`` 非空时，只保留 ``entry.kind`` 命中该集合的条目。
        """
        self._entry_cache.clear()
        self._missing_entries.clear()
        unknown_seeds = []
        normalized_seeds = []
        for seed in seed_tags:
            tag = self._canonical_tag(seed)
            if not tag:
                continue
            normalized_seeds.append(tag)

        tag_expanded = self.expand_tags(normalized_seeds, hop=hop)
        # 确保种子至少在结果里
        for tag in normalized_seeds:
            if tag not in tag_expanded:
                tag_expanded[tag] = TagExpandInfo(hop=0, cost=0.0, strength=1.0, path=[tag])

        hop_decay = float(self.tag_graph.hop_decay)

        # tag → ids；条目取最佳 via tag（按 strength * hop_decay^hop）
        id_to_via: Dict[str, Set[str]] = {}
        id_to_min_hop: Dict[str, int] = {}
        id_to_best_score: Dict[str, float] = {}
        id_to_best_strength: Dict[str, float] = {}
        id_to_best_cost: Dict[str, float] = {}
        id_to_best_path: Dict[str, List[str]] = {}

        for tag, info in tag_expanded.items():
            score = float(info.strength) * (hop_decay ** int(info.hop))
            for entry_id in self.ids_for_tag(tag):
                id_to_via.setdefault(entry_id, set()).add(tag)
                prev_hop = id_to_min_hop.get(entry_id)
                if prev_hop is None or info.hop < prev_hop:
                    id_to_min_hop[entry_id] = info.hop
                prev_score = id_to_best_score.get(entry_id)
                if prev_score is None or score > prev_score:
                    id_to_best_score[entry_id] = score
                    id_to_best_strength[entry_id] = float(info.strength)
                    id_to_best_cost[entry_id] = float(info.cost)
                    id_to_best_path[entry_id] = list(info.path)

        related_extra: Set[str] = set()
        rel_hops = (
            int(self.config.get("entry_related_hops", 1))
            if entry_related_hops is None
            else int(entry_related_hops)
        )
        if include_entry_related and rel_hops > 0:
            frontier = set(id_to_min_hop.keys())
            for _ in range(rel_hops):
                nxt: Set[str] = set()
                for entry_id in frontier:
                    entry = self.get_entry(entry_id)
                    if not entry or (entry.kind == "rule" and entry.status != "active" and not include_inactive):
                        continue
                    for rel_id in entry.related:
                        if rel_id in id_to_min_hop or rel_id in related_extra:
                            continue
                        related_extra.add(rel_id)
                        nxt.add(rel_id)
                frontier = nxt

        hits: List[AssociateHit] = []
        for entry_id, via in id_to_via.items():
            entry = self.get_entry(entry_id)
            if not entry or (entry.kind == "rule" and entry.status != "active" and not include_inactive):
                continue
            if not (set(entry.tags) & via):
                continue
            hits.append(
                AssociateHit(
                    entry=entry,
                    via_tags=sorted(via),
                    min_tag_hop=id_to_min_hop.get(entry_id, 0),
                    from_entry_related=False,
                    path_strength=id_to_best_strength.get(entry_id, 1.0),
                    path_cost=id_to_best_cost.get(entry_id, 0.0),
                    via_path=id_to_best_path.get(entry_id, []),
                )
            )
        for entry_id in related_extra:
            entry = self.get_entry(entry_id)
            if not entry or (entry.kind == "rule" and entry.status != "active" and not include_inactive):
                continue
            hits.append(
                AssociateHit(
                    entry=entry,
                    via_tags=[],
                    min_tag_hop=999,
                    from_entry_related=True,
                    path_strength=0.0,
                    path_cost=float("inf"),
                    via_path=[],
                )
            )

        priority_rank = {"high": 0, "medium": 1, "low": 2}
        kind_rank = {
            "rule": 0,
            "template": 1,
            "decision": 2,
            "lesson": 3,
            "reference": 4,
            "distilled-source": 5,
            "source": 6,
            "skill": 7,
            "mcp-server": 8,
            "hook": 9,
        }
        types_set = {str(t).strip().lower() for t in types if str(t).strip()} if types else set()
        if types_set:
            hits = [h for h in hits if str(h.entry.kind or "").lower() in types_set]
        hits.sort(
            key=lambda h: (
                0 if not h.from_entry_related else 1,
                h.min_tag_hop,
                -float(h.path_strength if not h.from_entry_related else 0.0),
                priority_rank.get(h.entry.priority, 3),
                kind_rank.get(h.entry.kind, 9),
                h.entry.id,
            )
        )
        total_hits = len(hits)
        if limit is not None:
            if int(limit) < 0:
                raise ValueError("associate limit 不能为负数")
            hits = hits[: int(limit)]

        expanded_payload = {
            tag: info.as_dict() for tag, info in sorted(tag_expanded.items(), key=lambda x: (x[1].hop, x[1].cost, x[0]))
        }
        meta = {
            "seed_tags": normalized_seeds,
            "expanded_tags": expanded_payload,
            "unknown_seeds": unknown_seeds,
            "hit_count": len(hits),
            "total_hit_count": total_hits,
            "truncated": total_hits > len(hits),
            "index_stale": any(entry.index_stale for entry in self._entry_cache.values() if entry) or bool(self._missing_entries),
            "freshness_scope": "queried_entries",
            "missing_entries": sorted(self._missing_entries),
            "hop": self.tag_graph.default_hop if hop is None else hop,
            "entry_related_hops": rel_hops if include_entry_related else 0,
            "types": sorted(types_set),
            "weight": {
                "min_expand": self.tag_graph.min_expand,
                "default_edge": self.tag_graph.default_edge,
                "hop_decay": self.tag_graph.hop_decay,
            },
        }
        return hits, meta
