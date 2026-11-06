#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""标签管理：同义词归并、tag-graph 增改、propagate 审查报告。

标签提取由 LLM / 调用方完成；本模块只负责归一化、去重、写入邻接图。
tag-graph.yaml 使用仓库既有格式：related: [ { tag: x, weight: 1.0 }, ... ]
"""

from __future__ import print_function

from pathlib import Path
import os
import tempfile
from typing import Any, Dict, List, Optional, Set

from lib.common import normalize_tag

from knowledge.synonyms import load_synonym_map, load_tag_language
from knowledge.tag_yaml import (
    DEFAULT_SYNONYMS_PATH,
    DEFAULT_TAG_GRAPH_PATH,
    REPO_ROOT,
    _parse_simple_tag_graph_yaml,
    dump_yaml,
    load_yaml,
)

__all__ = [
    "DEFAULT_SYNONYMS_PATH",
    "DEFAULT_TAG_GRAPH_PATH",
    "REPO_ROOT",
    "TagManager",
    "build_propagate_report",
    "_parse_simple_tag_graph_yaml",
    "dump_yaml",
    "load_tag_language",
    "load_synonym_map",
    "load_yaml",
]


class TagManager(object):
    def __init__(
        self,
        tag_graph_path: Path = DEFAULT_TAG_GRAPH_PATH,
        synonyms_path: Path = DEFAULT_SYNONYMS_PATH,
    ) -> None:
        self.tag_graph_path = tag_graph_path
        self.synonyms_path = synonyms_path
        self._synonym_map = load_synonym_map(synonyms_path)
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        self._source_bytes = self.tag_graph_path.read_bytes() if self.tag_graph_path.exists() else None
        if not self.tag_graph_path.exists():
            self._data = {
                "version": 1,
                "defaults": {"hop": 2, "max_nodes": 64},
                "tags": {},
            }
        else:
            self._data = load_yaml(self.tag_graph_path)
            if "tags" not in self._data:
                self._data["tags"] = {}
            if "defaults" not in self._data:
                self._data["defaults"] = {"hop": 2, "max_nodes": 64}

    def _save(self) -> None:
        current = self.tag_graph_path.read_bytes() if self.tag_graph_path.exists() else None
        if current != self._source_bytes:
            raise RuntimeError("标签图已被其他操作修改，请重新加载后再写入。")
        previous = load_yaml(self.tag_graph_path) if current is not None else {}
        old_tags = previous.get("tags") or {}
        new_tags = self._data.get("tags") or {}
        added = {key: value for key, value in new_tags.items() if key not in old_tags}
        only_added = (
            bool(added)
            and all(new_tags.get(key) == value for key, value in old_tags.items())
            and {key: value for key, value in previous.items() if key != "tags"}
            == {key: value for key, value in self._data.items() if key != "tags"}
        )
        # 新增标签先尝试追加，原有注释、缩进、换行和节点保持原字节。
        with tempfile.TemporaryDirectory(prefix="ygg-tag-stage-") as temporary:
            stage = Path(temporary) / "tag-graph.yaml"
            payload = None
            if current is not None and only_added:
                dump_yaml(stage, {"tags": added})
                rendered = stage.read_text(encoding="utf-8-sig")
                if "tags:\n" in rendered:
                    suffix = rendered.split("tags:\n", 1)[1]
                    newline = b"\r\n" if b"\r\n" in current else b"\n"
                    suffix_bytes = suffix.replace("\r\n", "\n").encode("utf-8").replace(b"\n", newline)
                    candidate = current + (b"" if current.endswith(b"\n") else newline) + suffix_bytes
                    stage.write_bytes(candidate)
                    if load_yaml(stage) == self._data:
                        payload = candidate
            if payload is None:
                dump_yaml(stage, self._data)
                if load_yaml(stage) != self._data:
                    raise RuntimeError("标签图序列化未保留完整数据，已拒绝写入。")
                payload = stage.read_bytes()
            self.tag_graph_path.parent.mkdir(parents=True, exist_ok=True)
            fd, staged = tempfile.mkstemp(prefix=".tag-graph-", dir=str(self.tag_graph_path.parent))
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                if self.tag_graph_path.exists():
                    os.chmod(staged, self.tag_graph_path.stat().st_mode & 0o777)
                if (self.tag_graph_path.read_bytes() if self.tag_graph_path.exists() else None) != current:
                    raise RuntimeError("标签图在写入前发生变更，已拒绝覆盖。")
                os.replace(staged, self.tag_graph_path)
            finally:
                if os.path.exists(staged):
                    os.unlink(staged)
        self._load()

    def _authorize(self, operation: str, summary: str, force: Optional[str] = None) -> Dict[str, Any]:
        from policies.core_write import authorize_core_write

        return authorize_core_write(operation, summary, force=force)

    @property
    def existing_tags(self) -> Set[str]:
        return {normalize_tag(str(t)) for t in (self._data.get("tags") or {}).keys()}

    def related_of(self, tag: str) -> List[str]:
        body = (self._data.get("tags") or {}).get(normalize_tag(tag)) or {}
        related = body.get("related") or []
        out: List[str] = []
        for item in related:
            if isinstance(item, dict):
                name = normalize_tag(str(item.get("tag", "")))
            else:
                name = normalize_tag(str(item))
            if name:
                out.append(name)
        return out

    def tag_relations(self) -> Dict[str, List[str]]:
        return {tag: self.related_of(tag) for tag in sorted(self.existing_tags)}

    def canonicalize(self, tag: str) -> str:
        key = normalize_tag(tag)
        if not key:
            return ""
        if key in self._synonym_map:
            return self._synonym_map[key]
        for existing in self.existing_tags:
            if existing == key:
                return existing
        return key

    def deduplicate_tags(self, tags: List[str]) -> List[str]:
        seen: Set[str] = set()
        result: List[str] = []
        for tag in tags:
            canonical = self.canonicalize(tag)
            if not canonical or canonical in seen:
                continue
            seen.add(canonical)
            result.append(canonical)
        return result

    @staticmethod
    def _clamp_weight(weight: float) -> float:
        value = float(weight)
        if value < 0.0 or value > 1.0:
            raise ValueError("weight must be in [0.0, 1.0], got {0}".format(weight))
        return value

    @staticmethod
    def _related_entry(tag: str, weight: float = 1.0) -> Dict[str, Any]:
        return {"tag": tag, "weight": float(weight)}

    def _ensure_tag_node(self, tag: str) -> None:
        tags = self._data.setdefault("tags", {})
        if tag not in tags:
            tags[tag] = {"related": []}

    def add_tags(
        self,
        tags: List[str],
        related_tags: Optional[List[str]] = None,
        force: Optional[str] = None,
    ) -> Dict[str, Any]:
        added: List[str] = []
        merged: List[Dict[str, str]] = []
        skipped: List[str] = []
        related_norm = self.deduplicate_tags(related_tags or [])
        to_create: List[str] = []

        for raw in tags:
            canonical = self.canonicalize(raw)
            raw_norm = normalize_tag(raw)
            if not canonical:
                continue
            if raw_norm and raw_norm != canonical:
                merged.append({"input": raw_norm, "canonical": canonical})
            if canonical in self.existing_tags:
                skipped.append(canonical)
                continue
            to_create.append(canonical)

        if not to_create and not merged:
            return {
                "status": "unchanged",
                "added": [],
                "merged": merged,
                "skipped": skipped,
            }

        if to_create:
            decision = self._authorize(
                "tag_add",
                "向 tag-graph.yaml 新增标签: {0}".format(", ".join(to_create)),
                force=force,
            )
            if not decision.get("allowed"):
                status = "dry_run" if decision.get("dry_run") else "denied"
                return {
                    "status": status,
                    "added": [],
                    "merged": merged,
                    "skipped": skipped,
                    "core_write": decision,
                }

        for canonical in to_create:
            self._ensure_tag_node(canonical)
            if related_norm:
                body = self._data["tags"][canonical]
                existing_rel = {self._related_name(x) for x in (body.get("related") or [])}
                for rel in related_norm:
                    if rel == canonical or rel in existing_rel:
                        continue
                    body.setdefault("related", []).append(self._related_entry(rel))
                    existing_rel.add(rel)
            added.append(canonical)

        # 同一批次互相关联（可选、轻量）
        batch = self.deduplicate_tags(list(tags) + related_norm)
        for a in added:
            for b in batch:
                if a == b:
                    continue
                self._link_one_way(a, b)

        if added or merged:
            self._save()
        return {
            "status": "updated" if (added or merged) else "unchanged",
            "added": added,
            "merged": merged,
            "skipped": skipped,
            "core_write": {"allowed": True, "operation": "tag_add"} if to_create else {},
        }

    @staticmethod
    def _related_name(item: Any) -> str:
        if isinstance(item, dict):
            return normalize_tag(str(item.get("tag", "")))
        return normalize_tag(str(item))

    def _edge_weight(self, src: str, dst: str) -> Optional[float]:
        body = (self._data.get("tags") or {}).get(src) or {}
        for item in body.get("related") or []:
            if self._related_name(item) == dst:
                if isinstance(item, dict):
                    return float(item.get("weight", 1.0))
                return 1.0
        return None

    def _link_one_way(self, src: str, dst: str, weight: float = 1.0) -> str:
        """返回 added / updated / unchanged。"""
        w = self._clamp_weight(weight)
        self._ensure_tag_node(src)
        body = self._data["tags"][src]
        related = body.setdefault("related", [])
        for idx, item in enumerate(related):
            if self._related_name(item) != dst:
                continue
            if isinstance(item, dict):
                old = float(item.get("weight", 1.0))
                if abs(old - w) < 1e-9:
                    return "unchanged"
                item["weight"] = w
                return "updated"
            # 旧格式字符串边 → 升级为带 weight 的映射
            related[idx] = self._related_entry(dst, w)
            return "updated"
        related.append(self._related_entry(dst, w))
        return "added"

    def add_relation(
        self,
        tag_a: str,
        tag_b: str,
        weight: float = 1.0,
        force: Optional[str] = None,
    ) -> Dict[str, Any]:
        a = self.canonicalize(tag_a)
        b = self.canonicalize(tag_b)
        if not a or not b or a == b:
            return {"status": "unchanged", "a": a, "b": b, "changed": False}

        w = self._clamp_weight(weight)
        ab = self._edge_weight(a, b)
        ba = self._edge_weight(b, a)
        both_exist = ab is not None and ba is not None
        weights_same = (
            both_exist and abs(float(ab) - w) < 1e-9 and abs(float(ba) - w) < 1e-9
        )
        if weights_same:
            return {
                "status": "unchanged",
                "a": a,
                "b": b,
                "weight": w,
                "changed": False,
            }

        operation = "tag_weight_update" if both_exist else "tag_relate"
        summary = (
            "更新边权 {0} <-> {1} -> {2}".format(a, b, w)
            if both_exist
            else "建立关联 {0} <-> {1} (weight={2})".format(a, b, w)
        )
        decision = self._authorize(operation, summary, force=force)
        if not decision.get("allowed"):
            status = "dry_run" if decision.get("dry_run") else "denied"
            return {
                "status": status,
                "a": a,
                "b": b,
                "weight": w,
                "changed": False,
                "core_write": decision,
            }

        r1 = self._link_one_way(a, b, w)
        r2 = self._link_one_way(b, a, w)
        changed = r1 != "unchanged" or r2 != "unchanged"
        if changed:
            self._save()
        return {
            "status": "updated" if changed else "unchanged",
            "a": a,
            "b": b,
            "weight": w,
            "changed": changed,
            "sides": {"a_to_b": r1, "b_to_a": r2},
            "core_write": decision,
        }

    def set_relation_weight(
        self,
        tag_a: str,
        tag_b: str,
        weight: float,
        force: Optional[str] = None,
    ) -> Dict[str, Any]:
        """仅更新已有边的 weight；边不存在时返回 missing。"""
        a = self.canonicalize(tag_a)
        b = self.canonicalize(tag_b)
        if not a or not b:
            return {"status": "unchanged", "a": a, "b": b, "changed": False}
        w = self._clamp_weight(weight)
        ab = self._edge_weight(a, b)
        ba = self._edge_weight(b, a)
        if ab is None and ba is None:
            return {
                "status": "missing",
                "a": a,
                "b": b,
                "weight": w,
                "changed": False,
                "message": "边不存在；请先 ygg tag --relate，或使用 --relate 同时建边",
            }
        return self.add_relation(a, b, weight=w, force=force)

    def writeback_authority_weight(
        self,
        tag_a: str,
        tag_b: str,
        weight: float,
        force: Optional[str] = None,
        *,
        reason: str = "authority writeback",
    ) -> Dict[str, Any]:
        """统计/校准路径回写权威 weight（走 tag_weight_authority_writeback，默认 deny）。

        人工 `ygg tag --set-weight` 仍用 set_relation_weight → tag_weight_update。
        """
        a = self.canonicalize(tag_a)
        b = self.canonicalize(tag_b)
        if not a or not b or a == b:
            return {"status": "unchanged", "a": a, "b": b, "changed": False}
        w = self._clamp_weight(weight)
        summary = "权威 weight 回写 {0} <-> {1} -> {2} ({3})".format(a, b, w, reason)
        decision = self._authorize("tag_weight_authority_writeback", summary, force=force)
        if not decision.get("allowed"):
            status = "dry_run" if decision.get("dry_run") else "denied"
            return {
                "status": status,
                "a": a,
                "b": b,
                "weight": w,
                "changed": False,
                "core_write": decision,
            }
        # 已授权：直接改图，避免再走 tag_weight_update 二次询问
        r1 = self._link_one_way(a, b, w)
        r2 = self._link_one_way(b, a, w)
        changed = r1 != "unchanged" or r2 != "unchanged"
        if changed:
            self._save()
        return {
            "status": "updated" if changed else "unchanged",
            "a": a,
            "b": b,
            "weight": w,
            "changed": changed,
            "sides": {"a_to_b": r1, "b_to_a": r2},
            "core_write": decision,
        }

    def list_tags(self) -> List[str]:
        return sorted(self.existing_tags)


def build_propagate_report(tag: str, dry_run: bool = True) -> Dict[str, Any]:
    """为新 tag 生成审查报告：关联 tag 下的条目候选（不自动改文件）。"""
    from knowledge.graph import GraphError, KnowledgeGraphIndex

    tm = TagManager()
    canonical = tm.canonicalize(tag)
    related = set(tm.related_of(canonical))
    if not related:
        return {
            "status": "no_related",
            "tag": canonical,
            "message": "该标签没有关联标签，无需传播",
            "dry_run": dry_run,
            "candidates": [],
        }

    try:
        index = KnowledgeGraphIndex()
    except GraphError as exc:
        return {"status": "error", "tag": canonical, "message": str(exc), "candidates": []}

    candidates: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    for rel_tag in sorted(related):
        for entry_id in index.ids_for_tag(rel_tag):
            if entry_id in seen_ids:
                continue
            entry = index.get_entry(entry_id)
            if entry is None:
                continue
            seen_ids.add(entry_id)
            entry_tags = set(entry.tags)
            if canonical in entry_tags:
                continue
            path = REPO_ROOT / entry.path
            content_preview = ""
            if path.exists():
                text = path.read_text(encoding="utf-8-sig")
                content_preview = " ".join(text.split())[:400]
            candidates.append(
                {
                    "id": entry.id,
                    "path": entry.path,
                    "title": entry.title,
                    "type": entry.kind,
                    "current_tags": sorted(entry_tags),
                    "matched_related": sorted(entry_tags & related),
                    "preview": content_preview,
                }
            )

    return {
        "status": "review",
        "tag": canonical,
        "related_tags": sorted(related),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "dry_run": True,  # propagate 永远只出报告
        "instruction": (
            "请审查以上每条内容，判断是否应添加标签 '{0}'。"
            "若应添加，请人工编辑 front matter 的 tags，或重新 remember/promote；"
            "本命令不会自动改文件。"
        ).format(canonical),
    }
