#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文件型记忆后端：runtime raw 记忆、lesson inbox 镜像、多根搜索与去重。

由 ``backends.factory.get_memory_backend()`` 实例化。含写入、打分检索、
channel/tag 规范化集成；不直接读 CLI argv。
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class FileMemoryBackend(object):
    def __init__(
        self,
        core_root: Path,
        config: Dict[str, Any],
        runtime_root: Optional[Path] = None,
    ) -> None:
        # core_root：知识真源；runtime_root：本机记忆与缓存（未传时回退为 core_root）
        self.core_root = core_root
        self.runtime_root = runtime_root or core_root
        self.repo_root = core_root
        backend = config.get("backend", {})
        self.raw_root = self.runtime_root / str(backend.get("raw_root", "memory/raw"))
        self.index_root = self.runtime_root / str(backend.get("index_root", "memory/index"))
        self.mirror_to_lessons_inbox = bool(backend.get("mirror_to_lessons_inbox", True))
        self.lessons_inbox_root = self.core_root / str(
            backend.get("lessons_inbox_root", "knowledge/lessons/inbox")
        )
        self.lessons_root = self.core_root / "knowledge" / "lessons"
        self.rules_root = self.core_root / "knowledge" / "rules"
        self.templates_root = self.core_root / "knowledge" / "templates"
        self.decisions_root = self.core_root / "knowledge" / "decisions"
        self.distilled_sources_root = self.core_root / "knowledge" / "sources" / "distilled"
        self.default_search_limit = int(config.get("search", {}).get("default_limit", 5))
        self.type_priority = dict(config.get("search", {}).get("type_priority", {}))
        # 兼容旧键名 kind_priority（已废弃，仍可读）
        if not self.type_priority:
            self.type_priority = dict(config.get("search", {}).get("kind_priority", {}))
        self.search_roots = [
            (self.raw_root, "raw"),
            (self.lessons_inbox_root, "lesson-draft"),
            (self.lessons_root, "lesson"),
            (self.rules_root, "rule"),
            (self.templates_root, "template"),
            (self.decisions_root, "decision"),
            (self.distilled_sources_root, "distilled-source"),
        ]

    @staticmethod
    def slugify(text: str) -> str:
        cleaned = re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)
        collapsed = re.sub(r"[\s_]+", "-", cleaned).strip("-").lower()
        return collapsed or "memory-entry"

    @staticmethod
    def derive_title(note: str, explicit_title: Optional[str]) -> str:
        if explicit_title:
            return explicit_title.strip()
        first_line = next((line.strip() for line in note.splitlines() if line.strip()), "")
        if not first_line:
            return "Untitled memory entry"
        return first_line[:80]

    @staticmethod
    def parse_front_matter(text: str) -> Tuple[Dict[str, Any], str]:
        """委托 ``lib.front_matter.parse_front_matter``（保持方法 API 兼容）。"""
        from lib.front_matter import parse_front_matter as _parse

        return _parse(text)

    @staticmethod
    def extract_section(body: str, section_name: str) -> str:
        pattern = re.compile(
            r"^##\s+{0}\s*$([\s\S]*?)(?=^##\s+|\Z)".format(re.escape(section_name)),
            flags=re.MULTILINE,
        )
        match = pattern.search(body)
        if not match:
            return ""
        return match.group(1).strip()

    def build_raw_entry(
        self,
        title: str,
        note: str,
        source: str,
        scope: str,
        recorded_at: str,
        lesson_draft_path: str,
        tags: Optional[List[str]] = None,
        title_refined: str = "",
        channel: str = "",
    ) -> str:
        body = note.strip()
        tag_lines = "\n".join("  - {0}".format(tag) for tag in (tags or []))
        if not tag_lines:
            tag_lines = "  []"
        refined_line = ""
        if title_refined:
            refined_line = 'title_refined: "{0}"\n'.format(title_refined.replace('"', '\\"'))
        return """---
title: "{title}"
{refined}type: observation
status: recorded
source: "{source}"
scope: "{scope}"
channel: "{channel}"
recorded_at: "{recorded_at}"
lesson_draft: "{lesson_draft_path}"
tags:
{tag_lines}
---

# {title}

## Observation

{body}
""".format(
            title=title.replace('"', '\\"'),
            refined=refined_line,
            channel=(channel or "").replace('"', '\\"'),
            source=source.replace('"', '\\"'),
            scope=scope.replace('"', '\\"'),
            recorded_at=recorded_at,
            lesson_draft_path=lesson_draft_path.replace('"', '\\"'),
            tag_lines=tag_lines,
            body=body,
        )

    def build_lesson_draft(
        self,
        title: str,
        note: str,
        source: str,
        scope: str,
        recorded_at: str,
        tags: Optional[List[str]] = None,
        title_refined: str = "",
        channel: str = "",
    ) -> str:
        body = note.strip()
        tag_lines = "\n".join("  - {0}".format(tag) for tag in (tags or []))
        if not tag_lines:
            tag_lines = "  []"
        refined_line = ""
        if title_refined:
            refined_line = 'title_refined: "{0}"\n'.format(title_refined.replace('"', '\\"'))
        return """---
title: "{title}"
{refined}type: lesson
status: draft
source: "{source}"
scope: "{scope}"
channel: "{channel}"
recorded_at: "{recorded_at}"
promoted_to: ""
tags:
{tag_lines}
applies_to: []
when_to_read: []
---

# {title}

## Observation

{body}

## Principle

- TODO
""".format(
            title=title.replace('"', '\\"'),
            refined=refined_line,
            channel=(channel or "").replace('"', '\\"'),
            source=source.replace('"', '\\"'),
            scope=scope.replace('"', '\\"'),
            recorded_at=recorded_at,
            tag_lines=tag_lines,
            body=body,
        )

    def collect_existing_entries(self) -> List[Tuple[Path, str, str]]:
        entries: List[Tuple[Path, str, str]] = []
        for root, _kind in self.search_roots:
            if not root.exists():
                continue
            for path in root.rglob("*.md"):
                if path.name == "README.md":
                    continue
                text = path.read_text(encoding="utf-8-sig")
                metadata, _ = self.parse_front_matter(text)
                title = metadata.get("title", "")
                entries.append((path, title, text.strip()))
        return entries

    @staticmethod
    def tokenize_query(query: str) -> List[str]:
        tokens = re.split(r"[\s,.;:!?/\\|()\[\]{}<>_-]+", query.strip().lower())
        return [token for token in tokens if token]

    def metadata_text(self, metadata: Dict[str, Any], keys: List[str]) -> str:
        parts: List[str] = []
        for key in keys:
            value = metadata.get(key)
            if isinstance(value, list):
                parts.extend(str(item) for item in value)
            elif value:
                parts.append(str(value))
        return " ".join(parts).lower()

    def score_entry(self, kind: str, metadata: Dict[str, Any], body: str, query: str) -> int:
        # kind 参数 = 条目 type（目录/过滤名）；front matter 字段名是 type
        query_text = query.strip().lower()
        query_tokens = self.tokenize_query(query_text)
        title = str(metadata.get("title", "")).lower()
        tags_keywords = self.metadata_text(metadata, ["tags", "keywords"])
        routing_text = self.metadata_text(
            metadata,
            [
                "scope",
                "priority",
                "agent_targets",
                "related",
                "when_to_read",
                "applies_to",
                "does_not_apply_to",
                "facts",
                "inferences",
                "practices",
                "risks",
            ],
        )
        headings_text = " ".join(
            self.extract_section(body, name).lower()
            for name in ["Rule", "Observation", "Principle", "Use Case", "Decision", "Context"]
        )
        body_lower = body.lower()

        score = int(self.type_priority.get(kind, 0))

        if query_text and query_text in title:
            score += 40
        if query_text and query_text in tags_keywords:
            score += 30
        if query_text and query_text in routing_text:
            score += 20
        if query_text and query_text in headings_text:
            score += 16
        if query_text and query_text in body_lower:
            score += 8

        for token in query_tokens:
            if token in title:
                score += 8
            if token in tags_keywords:
                score += 6
            if token in routing_text:
                score += 4
            if token in headings_text:
                score += 3
            if token in body_lower:
                score += 1
        return score

    def find_duplicate(self, title: str, note: str) -> Optional[Path]:
        normalized_title = title.strip().lower()
        normalized_note = note.strip()
        for path, existing_title, existing_text in self.collect_existing_entries():
            if existing_title.strip().lower() == normalized_title:
                return path
            if normalized_note and normalized_note in existing_text:
                return path
        return None

    def record_observation(
        self,
        note: str,
        title: Optional[str] = None,
        source: str = "user",
        scope: str = "cross-project",
        allow_duplicate: bool = False,
        tags: Optional[List[str]] = None,
        title_refined: Optional[str] = None,
        mirror_to_inbox: Optional[bool] = None,
        channel: Optional[str] = None,
        force: Optional[str] = None,
    ) -> Dict[str, Any]:
        note_text = note.strip()
        if not note_text:
            raise RuntimeError("Cannot record an empty memory note.")

        channel_meta: Dict[str, Any] = {}
        channel_id = ""
        try:
            from policies.channel import normalize_channel
            from policies.behavior import feature_enabled

            if feature_enabled("channel_filter") or channel:
                channel_id, channel_meta = normalize_channel(channel)
                if channel_meta.get("status") == "rejected":
                    raise RuntimeError(channel_meta.get("hint") or "unknown channel rejected")
                channel_id = channel_id or ""
        except ImportError:
            channel_id = (channel or "").strip()

        derived_title = self.derive_title(note_text, title)
        refined = (title_refined or "").strip()
        slug_source = refined or derived_title
        duplicate = self.find_duplicate(derived_title, note_text)
        if duplicate and not allow_duplicate:
            return {
                "status": "duplicate",
                "title": derived_title,
                "title_refined": refined,
                "channel": channel_id,
                "tags": [],
                "tag_meta": {},
                "raw_path": str(duplicate),
                "lesson_draft_path": str(duplicate),
            }

        normalized_tags: List[str] = []
        tag_meta: Dict[str, Any] = {}
        if tags:
            try:
                from knowledge.tag_manager import TagManager

                tm = TagManager()
                normalized_tags = tm.deduplicate_tags(list(tags))
                tag_meta = tm.add_tags(normalized_tags, force=force)
            except Exception as exc:  # pragma: no cover
                tag_meta = {"status": "error", "error": str(exc)}
                normalized_tags = [str(t).strip().lower() for t in tags if str(t).strip()]

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        recorded_at = datetime.now().strftime("%Y-%m-%d")
        filename = "{0}-{1}.md".format(timestamp, self.slugify(slug_source)[:80])

        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.index_root.mkdir(parents=True, exist_ok=True)
        lesson_draft_path = ""

        do_mirror = self.mirror_to_lessons_inbox if mirror_to_inbox is None else bool(mirror_to_inbox)
        if do_mirror:
            self.lessons_inbox_root.mkdir(parents=True, exist_ok=True)
            lesson_path = self.lessons_inbox_root / filename
            lesson_path.write_text(
                self.build_lesson_draft(
                    title=derived_title,
                    note=note_text,
                    source=source.strip(),
                    scope=scope.strip(),
                    recorded_at=recorded_at,
                    tags=normalized_tags,
                    title_refined=refined,
                    channel=channel_id,
                ),
                encoding="utf-8-sig",
            )
            lesson_draft_path = str(lesson_path)

        raw_path = self.raw_root / filename
        raw_path.write_text(
            self.build_raw_entry(
                title=derived_title,
                note=note_text,
                source=source.strip(),
                scope=scope.strip(),
                recorded_at=recorded_at,
                lesson_draft_path=lesson_draft_path,
                tags=normalized_tags,
                title_refined=refined,
                channel=channel_id,
            ),
            encoding="utf-8-sig",
        )

        return {
            "status": "recorded",
            "title": derived_title,
            "title_refined": refined,
            "channel": channel_id,
            "channel_meta": channel_meta,
            "tags": normalized_tags,
            "tag_meta": tag_meta,
            "raw_path": str(raw_path),
            "lesson_draft_path": lesson_draft_path,
        }

    @staticmethod
    def normalize_filter_values(values: Optional[List[str]]) -> List[str]:
        if not values:
            return []
        normalized: List[str] = []
        for value in values:
            for part in str(value).split(","):
                item = part.strip().lower()
                if item and item not in normalized:
                    normalized.append(item)
        return normalized

    @staticmethod
    def metadata_list(metadata: Dict[str, Any], key: str) -> List[str]:
        value = metadata.get(key, [])
        if isinstance(value, list):
            return [str(item).strip().lower() for item in value if str(item).strip()]
        if value:
            return [str(value).strip().lower()]
        return []

    def matches_filters(
        self,
        kind: str,
        metadata: Dict[str, Any],
        kinds: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        scope: Optional[str] = None,
        agents: Optional[List[str]] = None,
        channels: Optional[List[str]] = None,
    ) -> bool:
        kind_filters = self.normalize_filter_values(kinds)
        tag_filters = self.normalize_filter_values(tags)
        agent_filters = self.normalize_filter_values(agents)
        channel_filters = self.normalize_filter_values(channels)
        scope_filter = (scope or "").strip().lower()

        if kind_filters and kind.lower() not in kind_filters:
            return False

        entry_tags = set(self.metadata_list(metadata, "tags"))
        if tag_filters and not all(tag in entry_tags for tag in tag_filters):
            return False

        entry_scope = str(metadata.get("scope", "")).lower()
        if scope_filter and scope_filter not in entry_scope:
            return False

        entry_agents = set(self.metadata_list(metadata, "agent_targets"))
        if agent_filters:
            if not entry_agents:
                return False
            if not all(agent in entry_agents for agent in agent_filters):
                return False

        if channel_filters:
            entry_channel = str(metadata.get("channel", "")).strip().lower()
            if entry_channel not in channel_filters:
                return False

        return True

    def search_memories(
        self,
        query: str = "",
        limit: Optional[int] = None,
        kinds: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        scope: Optional[str] = None,
        agents: Optional[List[str]] = None,
        channels: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        query_text = (query or "").strip().lower()
        has_filters = bool(
            self.normalize_filter_values(kinds)
            or self.normalize_filter_values(tags)
            or (scope or "").strip()
            or self.normalize_filter_values(agents)
            or self.normalize_filter_values(channels)
        )
        if not query_text and not has_filters:
            return []

        effective_limit = limit or self.default_search_limit
        results: List[Dict[str, str]] = []

        for root, kind in self.search_roots:
            if not root.exists():
                continue
            for path in root.rglob("*.md"):
                if path.name == "README.md":
                    continue
                # Skip template placeholders under knowledge/templates.
                if kind == "template" and path.name.endswith(".template.md"):
                    continue
                text = path.read_text(encoding="utf-8-sig")
                metadata, body = self.parse_front_matter(text)
                if not self.matches_filters(
                    kind=kind,
                    metadata=metadata,
                    kinds=kinds,
                    tags=tags,
                    scope=scope,
                    agents=agents,
                    channels=channels,
                ):
                    continue

                searchable_text = " ".join(
                    [
                        str(metadata.get("title", "")),
                        self.metadata_text(
                            metadata,
                            ["tags", "keywords", "scope", "priority", "agent_targets", "related", "channel"],
                        ),
                        body,
                    ]
                ).lower()
                if query_text:
                    tokens = self.tokenize_query(query_text)
                    if query_text not in searchable_text and not (
                        tokens and all(token in searchable_text for token in tokens)
                    ):
                        continue

                score = self.score_entry(kind, metadata, body, query_text)
                if not query_text:
                    priority = str(metadata.get("priority", "")).lower()
                    score += {"high": 12, "medium": 6, "low": 2}.get(priority, 0)

                title = metadata.get("title", path.stem)
                when_to_read = self.metadata_list(metadata, "when_to_read")
                if when_to_read:
                    preview_source = "\n".join(when_to_read)
                else:
                    preview_source = (
                        self.extract_section(body, "Rule")
                        or self.extract_section(body, "Observation")
                        or self.extract_section(body, "Principle")
                        or body
                    )
                preview_lines = [line.strip() for line in preview_source.splitlines() if line.strip()]
                preview = " ".join(preview_lines[:2])[:180]
                agent_targets = self.metadata_list(metadata, "agent_targets")
                tag_values = self.metadata_list(metadata, "tags")
                results.append(
                    {
                        "type": str(metadata.get("type") or kind),
                        "path": str(path),
                        "title": title,
                        "score": str(score),
                        "recorded_at": str(metadata.get("recorded_at", "")),
                        "scope": str(metadata.get("scope", "")),
                        "channel": str(metadata.get("channel", "")),
                        "tags": ", ".join(tag_values),
                        "agent": ", ".join(agent_targets),
                        "preview": preview,
                    }
                )

        results.sort(key=lambda item: (-int(item["score"]), item["path"]))
        return results[:effective_limit]
