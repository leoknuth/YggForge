#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性迁移：上收 metadata 到 YAML，补 type，精简正文。

用法（仓库根）：
  py -X utf8 yggforge-core/scripts/cmds/tools/migrate_knowledge_front_matter.py
"""

from __future__ import print_function

from pathlib import Path
import sys

# cmds/<domain>/<script>.py → scripts/
SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
SCRIPT_DIR = SCRIPTS_ROOT

import re
from typing import Any, Dict, List, Optional, Tuple

from lib.front_matter import (  # noqa: E402
    as_str_list,
    dump_front_matter_lines,
    parse_front_matter,
    render_with_front_matter,
)
from lib.repo_paths import CORE_ROOT  # noqa: E402
from knowledge.schema import infer_type_from_path, reset_schema_cache  # noqa: E402

SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

def split_sections(body: str) -> Tuple[str, List[Tuple[str, str]]]:
    """返回 (前言, [(标题, 内容)])。前言是第一个 ## 之前。"""
    matches = list(SECTION_RE.finditer(body))
    if not matches:
        return body.strip(), []
    preface = body[: matches[0].start()].strip()
    sections: List[Tuple[str, str]] = []
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections.append((title, body[start:end].strip()))
    return preface, sections

def bullets(text: str) -> List[str]:
    items: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
        elif stripped.startswith("* "):
            items.append(stripped[2:].strip())
    return [x for x in items if x and not x.startswith("<") and x != "TODO"]

def leading_bullets(text: str) -> List[str]:
    """只取节首连续 bullet，遇到散文/空行后非列表内容即停。

    避免把 When To Read 节里后半段规则正文误吸入 when_to_read。
    """
    items: List[str] = []
    seen_blank = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if items:
                seen_blank = True
            continue
        is_bullet = stripped.startswith("- ") or stripped.startswith("* ")
        if is_bullet:
            if seen_blank and items:
                # 散文段落后又出现列表 → 视为正文，停止
                break
            seen_blank = False
            item = stripped[2:].strip()
            if item and not item.startswith("<") and item != "TODO":
                items.append(item)
            continue
        # 非列表行
        if items:
            break
    return items

def looks_like_knowledge_id(value: str) -> bool:
    text = value.strip().strip("`")
    if "/" in text or text.endswith(".md"):
        return False
    return bool(re.match(r"^[0-9]{8,}", text))

def kv_bullets(text: str) -> Dict[str, str]:
    """解析 '- key: value' 列表。"""
    out: Dict[str, str] = {}
    for item in bullets(text):
        if ":" not in item:
            continue
        k, v = item.split(":", 1)
        k, v = k.strip().lower().replace(" ", "_"), v.strip().strip("`")
        if v and v.lower() != "todo":
            out[k] = v
    return out

def ensure_list_field(meta: Dict[str, Any], key: str, values: List[str]) -> None:
    existing = as_str_list(meta.get(key))
    merged = existing[:]
    for v in values:
        if v and v not in merged:
            merged.append(v)
    if merged:
        meta[key] = merged

def heading_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback

def rebuild_body(title: str, sections: List[Tuple[str, str]]) -> str:
    parts = ["# {0}".format(title), ""]
    for h, content in sections:
        if not content.strip():
            continue
        parts.append("## {0}".format(h))
        parts.append("")
        parts.append(content.strip())
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"

def migrate_rule(meta: Dict[str, Any], body: str) -> Tuple[Dict[str, Any], str]:
    preface, sections = split_sections(body)
    keep: List[Tuple[str, str]] = []
    for title, content in sections:
        key = title.lower()
        if key in ("when to read", "何时阅读"):
            ensure_list_field(meta, "when_to_read", leading_bullets(content))
            # 节内其余内容（散文 + 后续列表）保留为正文前言
            rest = _when_to_read_remainder(content)
            if rest:
                keep.insert(0, ("__preface__", rest))
            continue
        if key in ("related", "相关"):
            ensure_list_field(
                meta,
                "related",
                [b for b in bullets(content) if looks_like_knowledge_id(b)],
            )
            continue
        keep.append((title, content))
    title = str(meta.get("title") or heading_title(body, "untitled"))
    # flatten synthetic preface
    preface_bits = [c for t, c in keep if t == "__preface__"]
    keep = [(t, c) for t, c in keep if t != "__preface__"]
    body_out = rebuild_body(title, keep)
    if preface_bits:
        # insert after H1
        lines = body_out.splitlines()
        h1 = lines[0] if lines else "# {0}".format(title)
        rest = "\n".join(lines[1:]).lstrip("\n")
        body_out = h1 + "\n\n" + "\n\n".join(preface_bits) + ("\n\n" + rest if rest else "\n")
        if not body_out.endswith("\n"):
            body_out += "\n"
    return meta, body_out

def _when_to_read_remainder(content: str) -> str:
    """When To Read 节中，去掉首段连续 bullet 后的剩余正文。"""
    lines = content.splitlines()
    idx = 0
    # skip leading blanks
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    # consume leading bullets (+ blanks between them only until first prose)
    while idx < len(lines):
        stripped = lines[idx].strip()
        if not stripped:
            # peek: if next non-empty is bullet, continue; else stop for remainder
            j = idx + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and (lines[j].strip().startswith("- ") or lines[j].strip().startswith("* ")):
                idx = j
                continue
            break
        if stripped.startswith("- ") or stripped.startswith("* "):
            idx += 1
            continue
        break
    rest = "\n".join(lines[idx:]).strip()
    return rest

def migrate_lesson(meta: Dict[str, Any], body: str) -> Tuple[Dict[str, Any], str]:
    preface, sections = split_sections(body)
    keep: List[Tuple[str, str]] = []
    for title, content in sections:
        key = title.lower()
        if key in ("when to read", "何时阅读"):
            ensure_list_field(meta, "when_to_read", leading_bullets(content))
            continue
        if key == "context":
            for k, v in kv_bullets(content).items():
                if k in ("source", "scope", "channel", "recorded_at") and not meta.get(k):
                    meta[k] = v
            continue
        if key == "applicability":
            kv = kv_bullets(content)
            if kv.get("applies_to"):
                ensure_list_field(meta, "applies_to", [kv["applies_to"]])
            if kv.get("does_not_apply_to"):
                ensure_list_field(meta, "does_not_apply_to", [kv["does_not_apply_to"]])
            # also plain bullets
            for item in bullets(content):
                if item.startswith("applies_to"):
                    continue
                if item.startswith("does_not"):
                    continue
            continue
        if key in ("promotion notes", "晋升说明"):
            kv = kv_bullets(content)
            if kv.get("promoted_to") and not meta.get("promoted_to"):
                meta["promoted_to"] = kv["promoted_to"]
            if kv.get("reason_to_promote"):
                meta["reason_to_promote"] = kv["reason_to_promote"]
            continue
        if key in ("related", "相关"):
            ensure_list_field(
                meta,
                "related",
                [b for b in bullets(content) if looks_like_knowledge_id(b)],
            )
            continue
        # normalize section titles
        if key in ("correction or observation", "observation", "纠错或观察"):
            keep.append(("Observation", content))
            continue
        if key in ("reusable principle", "principle", "可复用原则"):
            if content.strip() in ("- TODO", "TODO", "-"):
                continue
            keep.append(("Principle", content))
            continue
        keep.append((title, content))
    title = str(meta.get("title") or heading_title(body, "untitled"))
    return meta, rebuild_body(title, keep)

def migrate_decision(meta: Dict[str, Any], body: str) -> Tuple[Dict[str, Any], str]:
    preface, sections = split_sections(body)
    keep: List[Tuple[str, str]] = []
    for title, content in sections:
        key = title.lower()
        if key in ("when to read", "何时阅读"):
            ensure_list_field(meta, "when_to_read", leading_bullets(content))
            continue
        if key == "status":
            # status 已在 YAML
            continue
        if key == "consequences":
            kv = kv_bullets(content)
            # also nested style "- positive:" then sub-bullets — keep simple
            pos, neg = [], []
            mode = None
            for line in content.splitlines():
                s = line.strip()
                if s.startswith("- positive:") or s.lower() == "positive:":
                    mode = "pos"
                    val = s.split(":", 1)[1].strip() if ":" in s else ""
                    if val:
                        pos.append(val)
                    continue
                if s.startswith("- negative:") or s.lower() == "negative:":
                    mode = "neg"
                    val = s.split(":", 1)[1].strip() if ":" in s else ""
                    if val:
                        neg.append(val)
                    continue
                if s.startswith("- ") and mode:
                    (pos if mode == "pos" else neg).append(s[2:].strip())
            ensure_list_field(meta, "consequences_positive", pos)
            ensure_list_field(meta, "consequences_negative", neg)
            continue
        if key in ("related", "相关"):
            ensure_list_field(
                meta,
                "related",
                [b for b in bullets(content) if looks_like_knowledge_id(b)],
            )
            continue
        keep.append((title, content))
    title = str(meta.get("title") or heading_title(body, "untitled"))
    return meta, rebuild_body(title, keep)

def migrate_source(meta: Dict[str, Any], body: str) -> Tuple[Dict[str, Any], str]:
    preface, sections = split_sections(body)
    extract = ""
    for title, content in sections:
        key = title.lower()
        if key in ("原始来源", "source", "origin"):
            kv = kv_bullets(content)
            # Chinese keys
            for item in bullets(content):
                if item.startswith("链接：") or item.startswith("链接:"):
                    url = item.split("：", 1)[-1].split(":", 1)[-1].strip().strip("`")
                    meta.setdefault("source_url", url)
                elif item.startswith("作者：") or item.startswith("作者:"):
                    meta.setdefault("author", item.split("：", 1)[-1].split(":", 1)[-1].strip())
                elif item.startswith("发布时间"):
                    meta.setdefault("published_at", item.split("：", 1)[-1].split(":", 1)[-1].strip())
                elif "提取文本归档" in item or "asset" in item.lower():
                    path = item.split("：", 1)[-1].split(":", 1)[-1].strip().strip("`")
                    meta.setdefault("asset_path", path)
            if kv.get("链接"):
                meta.setdefault("source_url", kv["链接"])
            continue
        if key in ("图片", "images"):
            urls = []
            for item in bullets(content):
                u = item.strip().strip("`")
                if u.startswith("http"):
                    urls.append(u)
            ensure_list_field(meta, "image_urls", urls)
            continue
        if key in ("抽取正文", "extracted", "正文"):
            extract = content
            continue
    if not meta.get("source_url") and meta.get("source"):
        src = str(meta.get("source"))
        if src.startswith("http"):
            meta["source_url"] = src
    title = str(meta.get("title") or heading_title(body, "untitled"))
    body_out = "# {0}\n\n".format(title)
    if extract:
        body_out += "## 抽取正文\n\n{0}\n".format(extract.strip())
    return meta, body_out

def migrate_distilled(meta: Dict[str, Any], body: str) -> Tuple[Dict[str, Any], str]:
    preface, sections = split_sections(body)
    notes: List[str] = []
    for title, content in sections:
        key = title.lower()
        if key in ("原始来源", "source"):
            for item in bullets(content):
                if item.startswith("链接") or "`http" in item or item.startswith("http"):
                    url = item.split("：", 1)[-1].split(":", 1)[-1].strip().strip("`")
                    if url.startswith("http"):
                        meta.setdefault("source_url", url)
                elif item.startswith("作者"):
                    meta.setdefault("author", item.split("：", 1)[-1].split(":", 1)[-1].strip())
                elif "inbox" in item:
                    path = item.split("：", 1)[-1].split(":", 1)[-1].strip().strip("`")
                    meta.setdefault("inbox_path", path)
            continue
        if key in ("事实", "facts"):
            ensure_list_field(meta, "facts", bullets(content))
            continue
        if key in ("推论", "inferences"):
            ensure_list_field(meta, "inferences", bullets(content))
            continue
        if key in ("可复用结论", "reusable practices", "practices"):
            ensure_list_field(meta, "practices", bullets(content))
            continue
        if key in ("风险与保留意见", "risks"):
            ensure_list_field(meta, "risks", bullets(content))
            continue
        if key in ("建议晋升去向", "promotion recommendation"):
            items = bullets(content)
            if items and not meta.get("promote_to"):
                meta["promote_to"] = items[0].strip("`")
            kv = kv_bullets(content)
            if kv.get("promote_to"):
                meta["promote_to"] = kv["promote_to"]
            if kv.get("rationale"):
                meta["promote_rationale"] = kv["rationale"]
            continue
        if key in ("when to read", "相关", "related"):
            if key.startswith("when"):
                ensure_list_field(meta, "when_to_read", leading_bullets(content))
            else:
                ensure_list_field(
                    meta,
                    "related",
                    [b for b in bullets(content) if looks_like_knowledge_id(b)],
                )
            continue
        notes.append("## {0}\n\n{1}".format(title, content))
    if not meta.get("source_url") and meta.get("source"):
        src = str(meta.get("source"))
        if src.startswith("http"):
            meta["source_url"] = src
    title = str(meta.get("title") or heading_title(body, "untitled"))
    body_out = "# {0}\n".format(title)
    if notes:
        body_out += "\n" + "\n\n".join(notes) + "\n"
    return meta, body_out

def _body_has_liftable_sections(body: str, entry_type: str) -> bool:
    """仅当存在该 type 的 migrator 会真正上收的节时返回 True。"""
    liftable = {
        "rule": {"when to read", "何时阅读", "related", "相关"},
        "lesson": {
            "when to read",
            "何时阅读",
            "related",
            "相关",
            "context",
            "applicability",
            "promotion notes",
            "晋升说明",
        },
        "decision": {
            "when to read",
            "何时阅读",
            "related",
            "相关",
            "status",
            "consequences",
        },
        "source": {"原始来源", "source", "origin", "图片", "images"},
        "distilled-source": {
            "原始来源",
            "source",
            "事实",
            "facts",
            "推论",
            "inferences",
            "可复用结论",
            "reusable practices",
            "practices",
            "风险与保留意见",
            "risks",
            "建议晋升去向",
            "promotion recommendation",
            "when to read",
            "相关",
            "related",
        },
        "template": set(),
    }
    allowed = liftable.get(entry_type, set())
    if not allowed:
        return False
    for title, _ in split_sections(body)[1]:
        if title.lower() in allowed:
            return True
    return False

def migrate_file(path: Path, dry_run: bool = False) -> bool:
    rel = path.resolve().relative_to(CORE_ROOT.resolve()).as_posix()
    if not rel.startswith("knowledge/"):
        return False
    text = path.read_text(encoding="utf-8-sig")
    meta, body = parse_front_matter(text)
    if not meta and not body.startswith("#"):
        return False

    entry_type = str(meta.get("type") or "").strip().lower()
    had_type = entry_type in (
        "rule",
        "lesson",
        "decision",
        "template",
        "source",
        "distilled-source",
    )
    if not had_type:
        entry_type = infer_type_from_path(rel)
    # 已迁移且无可上收节：跳过，保持幂等
    if had_type and "kind" not in meta and not _body_has_liftable_sections(body, entry_type):
        return False

    meta["type"] = entry_type
    if "kind" in meta:
        del meta["kind"]

    # promoted_to: lesson 里若值为 lesson 保留；清理空字符串
    if meta.get("promoted_to") == "":
        del meta["promoted_to"]

    if entry_type == "rule":
        meta, body = migrate_rule(meta, body)
    elif entry_type == "lesson":
        meta, body = migrate_lesson(meta, body)
    elif entry_type == "decision":
        meta, body = migrate_decision(meta, body)
    elif entry_type == "source":
        meta, body = migrate_source(meta, body)
    elif entry_type == "distilled-source":
        meta, body = migrate_distilled(meta, body)
    else:
        # template: just ensure type
        pass

    # related 只保留 id
    if "related" in meta:
        cleaned = [x for x in as_str_list(meta.get("related")) if looks_like_knowledge_id(x)]
        if cleaned:
            meta["related"] = cleaned
        else:
            del meta["related"]

    # stable key order: type near top
    ordered: Dict[str, Any] = {}
    for key in (
        "id",
        "title",
        "title_refined",
        "type",
        "status",
        "confidence",
        "source",
        "source_url",
        "author",
        "published_at",
        "asset_path",
        "raw_html_path",
        "inbox_path",
        "scope",
        "channel",
        "recorded_at",
        "last_reviewed",
        "owners",
        "tags",
        "keywords",
        "related",
        "priority",
        "agent_targets",
        "when_to_read",
        "applies_to",
        "does_not_apply_to",
        "promoted_to",
        "reason_to_promote",
        "facts",
        "inferences",
        "practices",
        "risks",
        "promote_to",
        "promote_rationale",
        "image_urls",
        "consequences_positive",
        "consequences_negative",
        "supersedes",
        "template_kind",
        "always_apply",
        "projection_mode",
        "projection",
        "objective",
        "non_goals",
    ):
        if key in meta:
            ordered[key] = meta[key]
    for key, val in meta.items():
        if key not in ordered:
            ordered[key] = val

    new_text = render_with_front_matter(ordered, body if body.endswith("\n") else body + "\n")
    if dry_run:
        return True
    bom = path.read_bytes()[:3] == b"\xef\xbb\xbf"
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + new_text.encode("utf-8"))
    return True

def main() -> int:
    dry_run = "--dry-run" in sys.argv
    reset_schema_cache()
    root = CORE_ROOT / "knowledge"
    count = 0
    for path in sorted(root.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        if path.name.endswith(".template.md"):
            continue
        if migrate_file(path, dry_run=dry_run):
            count += 1
            print("migrated", path.relative_to(CORE_ROOT))
    print("done", count, "(dry-run)" if dry_run else "")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
