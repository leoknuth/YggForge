#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""角色长期记忆：自身 notes、独立图、跨项目摘要和原子保存。"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path, PureWindowsPath
import tempfile
from typing import Any, Dict, Optional

from backends.file_backend import FileMemoryBackend
from knowledge.spaces import KnowledgeSpace
from lib.front_matter import as_str_list, parse_front_matter, render_with_front_matter, source_text_fingerprint


class RoleMemoryError(ValueError):
    """角色记忆路径、所有者或写入状态不正确。"""


def atomic_write_text(path: Path, text: str) -> None:
    """在相同目录写入完整 UTF-8 BOM 文件，再原子替换。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".role-memory-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="\n") as stream:
            stream.write(text.rstrip() + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _runtime_root(space: KnowledgeSpace) -> Path:
    """记忆布局固定在 core/roles/id/memories，锁使用同一仓库运行时。"""
    return space.root.parents[3] / "yggforge-runtime"


@contextmanager
def role_write_lock(space: KnowledgeSpace, timeout: float = 15.0):
    """记忆、图与摘要共用可重入锁，跨宿主不会读到同次更新的中间状态。"""
    if not space.owner_role:
        raise RoleMemoryError("角色写锁需要固定角色身份。")
    from knowledge.space_lock import graph_lock
    with graph_lock(space.root, space.config, timeout=timeout):
        yield


def _summary_records(space: KnowledgeSpace):
    """摘要只含跨项目记录；项目事实由带项目过滤的联想返回。"""
    records = []
    for path in sorted(space.note_root.rglob("*.md")):
        if path.name == "README.md" or path.name.endswith(".template.md"):
            continue
        try:
            path.resolve().relative_to(space.note_root.resolve())
        except ValueError:
            continue
        metadata, body = parse_front_matter(path.read_text(encoding="utf-8-sig"))
        if metadata.get("owner_role") not in (None, "", space.owner_role):
            continue
        if metadata.get("project_id") or str(metadata.get("scope", "")) not in ("", "role", "global", "cross-project"):
            continue
        if metadata.get("type") == "rule" and metadata.get("status") != "active":
            continue
        preview = FileMemoryBackend.extract_section(body, "Observation") or FileMemoryBackend.extract_section(body, "Rule") or body
        preview = " ".join(line.strip() for line in preview.splitlines() if line.strip())[:220]
        records.append((metadata, path.relative_to(space.root).as_posix(), preview))
    return records


def refresh_role_memory(space: KnowledgeSpace, *, acquire_lock: bool = True) -> Dict[str, Any]:
    """重建本角色图并保存有来源的摘要，不写共享知识或修改其它角色。"""
    if not space.owner_role:
        raise RoleMemoryError("角色记忆刷新需要角色知识空间。")
    if acquire_lock:
        with role_write_lock(space):
            return refresh_role_memory(space, acquire_lock=False)
    from knowledge.graph_build import build_indexes

    graph = build_indexes(repo_root=space.root, config=space.config)
    records = _summary_records(space)
    metadata = {
        "space_id": space.space_id,
        "owner_role": space.owner_role,
        "source_digest": graph["source_digest"],
        "recorded_at": datetime.now().strftime("%Y%m%d"),
        "entry_ids": [str(item[0].get("id", "")) for item in records],
    }
    lines = ["# 角色长期记忆摘要", "", "本摘要属于记忆资料，不改变项目约定、共享规则或运行权限。", "", "## 跨项目记录", ""]
    if records:
        for record, relative, preview in records[:40]:
            lines.append("- {0}〔{1}；{2}〕：{3}".format(record.get("title", relative), record.get("status", ""), record.get("confidence", ""), preview))
            lines.append("  来源：`{0}`；条目：`{1}`；来源类型：`{2}`。".format(relative, record.get("id", ""), record.get("source", "")))
    else:
        lines.append("当前没有跨项目长期记录；项目事实通过本角色图按任务项目检索。")
    summary = space.root / "summary.md"
    atomic_write_text(summary, render_with_front_matter(metadata, "\n".join(lines) + "\n"))
    return {"status": "refreshed", "space_id": space.space_id, "source_digest": graph["source_digest"], "summary_path": str(summary), "summary_sha256": source_text_fingerprint(summary.read_bytes()), "graph_entries": graph["entries"], "warnings": graph["warnings"]}


def role_summary_status(space: KnowledgeSpace) -> Dict[str, Any]:
    """在一致读锁内核对摘要与图，避免更新中途把两个版本混在一起。"""
    with role_write_lock(space):
        return _role_summary_status_unlocked(space)


def _role_summary_status_unlocked(space: KnowledgeSpace) -> Dict[str, Any]:
    from knowledge.graph_build import check_indexes

    checked = check_indexes(repo_root=space.root, config=space.config)
    path = space.root / "summary.md"
    metadata, body = parse_front_matter(path.read_text(encoding="utf-8-sig")) if path.is_file() else ({}, "")
    expected = checked.get("source_digest", "")
    matched = bool(expected and metadata.get("source_digest") == expected and metadata.get("space_id") == space.space_id and metadata.get("owner_role") == space.owner_role and checked.get("index_status") == "consistent")
    return {"matched": matched, "status": "current" if matched else "stale", "space_id": space.space_id, "path": str(path), "metadata": metadata, "body": body, "source_digest": expected, "graph_status": checked.get("index_status")}


class RoleMemoryBackend(FileMemoryBackend):
    """复用记忆检索与去重方法，所有读取和写入固定在本角色 notes。"""

    def __init__(self, space: KnowledgeSpace, config: Dict[str, Any]):
        if not space.owner_role:
            raise RoleMemoryError("角色后端必须绑定角色空间。")
        if space.space_id != "role:" + space.owner_role or space.root.name != "memories" or space.root.parent.name != space.owner_role:
            raise RoleMemoryError("角色身份与记忆根不一致。")
        super().__init__(space.root, config, runtime_root=_runtime_root(space))
        self.space = space
        self.notes_root = space.note_root
        try:
            self.notes_root.resolve().relative_to(space.root.resolve())
        except ValueError as exc:
            raise RoleMemoryError("角色 notes 根不能链接到空间之外。") from exc
        self.raw_root = self.lessons_inbox_root = self.notes_root / "lessons/inbox"
        self.index_root = _runtime_root(space) / "roles" / space.owner_role / "index"
        self.lessons_root = self.notes_root / "lessons"
        self.rules_root = self.notes_root / "rules"
        self.templates_root = self.notes_root / "templates"
        self.decisions_root = self.notes_root / "decisions"
        self.reference_root = self.notes_root / "reference"
        self.distilled_sources_root = self.notes_root / "sources/distilled"
        self.search_roots = [(self.lessons_root, "lesson"), (self.rules_root, "rule"), (self.templates_root, "template"), (self.decisions_root, "decision"), (self.reference_root, "reference"), (self.distilled_sources_root, "distilled-source"), (self.notes_root / "sources/inbox", "source")]
        self.auto_refresh = bool(config.get("memory", {}).get("auto_refresh", True))
        if config.get("memory", {}).get("mirror_to_global_inbox", False):
            raise RoleMemoryError("角色私有记忆不能自动镜像全局 inbox。")
        self.tag_add_mode = config.get("memory", {}).get("tag_add_mode", "allow")
        if self.tag_add_mode not in {"allow", "deny", "dry_run"}:
            raise RoleMemoryError("角色 tag_add_mode 必须是 allow、deny 或 dry_run。")

    def _entry_path_allowed(self, path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(self.notes_root.resolve())
            self.notes_root.resolve().relative_to(self.space.root.resolve())
            path.resolve().relative_to(root.resolve())
        except ValueError:
            return False
        return True

    def _entry_metadata_allowed(self, metadata: Dict[str, Any]) -> bool:
        return metadata.get("owner_role") in (None, "", self.space.owner_role) and metadata.get("space_id") in (None, "", self.space.space_id)

    def _finish_write(self) -> Dict[str, Any]:
        if self.auto_refresh:
            try:
                return refresh_role_memory(self.space, acquire_lock=False)
            except Exception as exc:
                # 原始用户记录已保存；派生物失败不能丢弃记录，也不能报告完整成功。
                return {"status": "pending_error", "space_id": self.space.space_id, "needs_refresh": True, "error_type": type(exc).__name__}
        return {"status": "pending", "space_id": self.space.space_id, "needs_refresh": True}

    def collect_existing_entries(self):
        with role_write_lock(self.space):
            return super().collect_existing_entries()

    def search_memories(self, *args, **kwargs):
        with role_write_lock(self.space):
            return super().search_memories(*args, **kwargs)

    def _find_role_duplicate(self, title: str, note: str, project_id: str) -> Optional[Path]:
        """项目事实只在相同项目内去重，避免另一项目同名条目阻止保存。"""
        for path, existing_title, text in self.collect_existing_entries():
            metadata, body = parse_front_matter(text)
            if str(metadata.get("project_id", "")) != project_id:
                continue
            observation = self.extract_section(body, "Observation") or body
            if existing_title.strip().lower() == title.strip().lower() or note.strip() in observation:
                return path
        return None

    def record_observation(
        self,
        note: str,
        title: Optional[str] = None,
        source: str = "user",
        scope: str = "cross-project",
        allow_duplicate: bool = False,
        tags=None,
        title_refined: str = "",
        mirror_to_inbox=None,
        channel=None,
        force=None,
        project_id: str = "",
        confidence: str = "medium",
    ) -> Dict[str, Any]:
        from knowledge.knowledge_id import generate_knowledge_id
        from knowledge.tag_manager import TagManager

        # 新增自己记忆的标签不会扩大读取范围；不借此授权全局图或强规则写入。
        if force is None:
            force = self.tag_add_mode

        note = note.strip()
        if not note:
            raise RoleMemoryError("记忆正文不能为空。")
        if confidence not in ("high", "medium", "low"):
            raise RoleMemoryError("confidence 必须为 high、medium 或 low。")
        derived = self.derive_title(note, title)
        with role_write_lock(self.space):
            for graph_path in (self.space.graph_root, self.space.graph_root / "tag-graph.yaml", self.space.graph_root / "tag-synonyms.yaml"):
                try:
                    graph_path.resolve().relative_to(self.space.root.resolve())
                except ValueError as exc:
                    raise RoleMemoryError("角色标签图路径越界。") from exc
            duplicate = self._find_role_duplicate(derived, note, project_id)
            if duplicate and not allow_duplicate:
                return {"status": "duplicate", "space_id": self.space.space_id, "owner_role": self.space.owner_role, "title": derived, "raw_path": str(duplicate), "lesson_draft_path": str(duplicate), "tags": [], "memory_refresh": self._finish_write()}
            manager = TagManager(self.space.graph_root / "tag-graph.yaml", self.space.graph_root / "tag-synonyms.yaml")
            normalized_tags = manager.deduplicate_tags(list(tags or []))
            # 只更新角色自己的图，不调用默认全局 TagManager。
            tag_meta = manager.add_tags(normalized_tags, force=force) if normalized_tags else {}
            now = datetime.now()
            path = self.lessons_inbox_root / (now.strftime("%Y%m%d-%H%M%S-%f") + "-" + self.slugify(title_refined or derived)[:80] + ".md")
            if not self._entry_path_allowed(path, self.notes_root):
                raise RoleMemoryError("角色记忆写入路径越界。")
            existing_ids = {str(parse_front_matter(raw)[0].get("id", "")) for _path, _title, raw in self.collect_existing_entries()}
            metadata = {
                "id": generate_knowledge_id(
                    path, derived, repo_root=self.space.root,
                    created=now, existing_ids=existing_ids,
                ),
                "title": derived,
                "type": "lesson",
                "status": "draft",
                "confidence": confidence,
                "source": source,
                "scope": scope,
                "project_id": project_id,
                "owner_role": self.space.owner_role,
                "space_id": self.space.space_id,
                "recorded_at": now.strftime("%Y%m%d"),
                "last_reviewed": now.strftime("%Y%m%d"),
                "channel": channel or "",
                "tags": normalized_tags,
                "related": [],
                "promoted_to": "",
                "applies_to": [],
                "when_to_read": [],
            }
            if title_refined:
                metadata["title_refined"] = title_refined
            body = "# {0}\n\n## Observation\n\n{1}\n\n## Principle\n\n- 待整理。\n".format(derived, note)
            atomic_write_text(path, render_with_front_matter(metadata, body))
            refresh = self._finish_write()
        return {
            "status": "recorded_refresh_pending" if refresh["status"] == "pending_error" else "recorded",
            "space_id": self.space.space_id,
            "owner_role": self.space.owner_role,
            "title": derived,
            "title_refined": title_refined or "",
            "raw_path": str(path),
            "lesson_draft_path": str(path),
            "tags": normalized_tags,
            "tag_meta": tag_meta,
            "project_id": project_id,
            "channel": channel or "",
            "memory_refresh": refresh,
        }

    def resolve_memory_entry(self, entry: str) -> Path:
        normalized = str(entry).replace("\\", "/")
        candidate = Path(normalized)
        if ".." in candidate.parts or (PureWindowsPath(normalized).drive and not candidate.is_absolute()):
            raise RoleMemoryError("角色记忆路径越界。")
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.notes_root / candidate).resolve()
            if not resolved.is_file():
                matches = []
                for path, _title, raw in self.collect_existing_entries():
                    metadata, _ = parse_front_matter(raw)
                    if metadata.get("id") == entry or path.name == entry:
                        matches.append(path)
                if len(matches) != 1:
                    raise RoleMemoryError("记忆条目不存在或不唯一。")
                resolved = matches[0].resolve()
        if not self._entry_path_allowed(resolved, self.notes_root) or not resolved.is_file():
            raise RoleMemoryError("角色只能操作自己的记忆条目。")
        metadata, _ = parse_front_matter(resolved.read_text(encoding="utf-8-sig"))
        if not self._entry_metadata_allowed(metadata):
            raise RoleMemoryError("记忆所有者不属于当前角色。")
        return resolved

    def _authorize_rule_change(self, metadata: Dict[str, Any], force=None) -> None:
        """活动角色规则的修改和删除沿用强规则授权，不由普通记忆写入替代。"""
        if metadata.get("type") == "rule" and metadata.get("status") == "active":
            from policies.behavior import authorize
            decision = authorize("promote.to_rule", "修改活动角色规则: " + self.space.owner_role, force=force)
            if not decision.get("allowed"):
                raise RoleMemoryError("活动角色规则变更未获授权。")

    def update_entry(self, entry: str, note: str, title: Optional[str] = None, force=None) -> Dict[str, Any]:
        if not note.strip():
            raise RoleMemoryError("更新正文不能为空。")
        with role_write_lock(self.space):
            path = self.resolve_memory_entry(entry)
            metadata, _ = parse_front_matter(path.read_text(encoding="utf-8-sig"))
            self._authorize_rule_change(metadata, force=force)
            if title:
                if not title.strip():
                    raise RoleMemoryError("标题不能为空白。")
                metadata["title"] = title.strip()
            metadata["last_reviewed"] = datetime.now().strftime("%Y%m%d")
            metadata["revision"] = int(metadata.get("revision", "0")) + 1
            body = "# {0}\n\n## Observation\n\n{1}\n".format(metadata.get("title", path.stem), note.strip())
            atomic_write_text(path, render_with_front_matter(metadata, body))
            refresh = self._finish_write()
        return {"status": "updated_refresh_pending" if refresh["status"] == "pending_error" else "updated", "space_id": self.space.space_id, "path": str(path), "memory_refresh": refresh}

    def delete_entry(self, entry: str, force=None) -> Dict[str, Any]:
        with role_write_lock(self.space):
            path = self.resolve_memory_entry(entry)
            metadata, _ = parse_front_matter(path.read_text(encoding="utf-8-sig"))
            self._authorize_rule_change(metadata, force=force)
            path.unlink()
            refresh = self._finish_write()
        return {"status": "deleted_refresh_pending" if refresh["status"] == "pending_error" else "deleted", "space_id": self.space.space_id, "path": str(path), "memory_refresh": refresh}
