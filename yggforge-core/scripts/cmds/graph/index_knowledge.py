#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可选导出人类可读 tag 索引到 indexes/（需主动执行；可提交供人浏览）。"""

from __future__ import annotations

from pathlib import Path
import sys

# cmds/<domain>/<script>.py → scripts/
SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
SCRIPT_DIR = SCRIPTS_ROOT

import argparse
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from backends.file_backend import FileMemoryBackend  # noqa: E402

from lib.repo_paths import CORE_ROOT, GENERATED_ROOT, REPO_ROOT as GIT_ROOT, ensure_layout

CONTENT_ROOT = CORE_ROOT
INDEX_ROOT = GENERATED_ROOT / "indexes"
BY_TAG_ROOT = INDEX_ROOT / "by-tag"
EXPORT_META_JSON = INDEX_ROOT / "export-meta.json"
EXPORT_META_MD = INDEX_ROOT / "EXPORT_META.md"

# 与 graph_scan 对齐：正式知识层（跳过 inbox / *.template.md，见 is_skippable）
SCAN_SPECS = (
    (CONTENT_ROOT / "knowledge" / "rules", "rule"),
    (CONTENT_ROOT / "knowledge" / "decisions", "decision"),
    (CONTENT_ROOT / "knowledge" / "lessons", "lesson"),
    (CONTENT_ROOT / "knowledge" / "templates", "template"),
    (CONTENT_ROOT / "knowledge" / "sources" / "distilled", "distilled-source"),
)

GENERATED_BANNER = "> 本文件由 `ygg index` 自动导出，请勿手改。\n"

from lib.common import normalize_tag

def is_skippable(path: Path) -> bool:
    if path.name.lower() == "readme.md":
        return True
    parts = [part.lower() for part in path.parts]
    if "inbox" in parts:
        return True
    if path.name.endswith(".template.md"):
        return True
    return False

def collect_entries(backend: FileMemoryBackend) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    for root, kind in SCAN_SPECS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            if is_skippable(path):
                continue
            text = path.read_text(encoding="utf-8-sig")
            metadata, body = backend.parse_front_matter(text)
            tags = backend.metadata_list(metadata, "tags")
            if not tags:
                print("index_warn: missing tags: {0}".format(path.as_posix()), file=sys.stderr)
                continue
            title = str(metadata.get("title") or path.stem).strip()
            when_list = backend.metadata_list(metadata, "when_to_read")
            summary = ""
            if when_list:
                summary = str(when_list[0]).strip()
            if not summary:
                when_to_read = backend.extract_section(body, "When To Read")
                if when_to_read:
                    summary = next(
                        (
                            line.lstrip("- ").strip()
                            for line in when_to_read.splitlines()
                            if line.strip()
                        ),
                        "",
                    )
            if not summary:
                summary = title
            entry_type = str(metadata.get("type") or kind).strip().lower() or kind
            entries.append(
                {
                    "type": entry_type,
                    "title": title,
                    "path": path,
                    "priority": str(metadata.get("priority", "")).strip().lower() or "unset",
                    "scope": str(metadata.get("scope", "")).strip(),
                    "summary": summary,
                    "tags": tags,
                }
            )
    return entries

def build_tag_pages(entries: List[Dict[str, object]]) -> Dict[str, str]:
    grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for entry in entries:
        for tag in entry["tags"]:  # type: ignore[union-attr]
            normalized = normalize_tag(str(tag))
            if normalized:
                grouped[normalized].append(entry)

    pages: Dict[str, str] = {}
    for tag in sorted(grouped.keys()):
        items = sorted(
            grouped[tag],
            key=lambda item: (
                {"high": 0, "medium": 1, "low": 2}.get(str(item["priority"]), 3),
                str(item["type"]),
                str(item["title"]).lower(),
            ),
        )
        lines = [
            "# Tag Index: {0}".format(tag),
            "",
            GENERATED_BANNER.rstrip(),
            "",
        ]
        for item in items:
            path = item["path"]
            assert isinstance(path, Path)
            # yggforge-generated/indexes/by-tag/*.md → yggforge-core/knowledge/...
            link = Path("../../../yggforge-core/knowledge") / path.relative_to(CONTENT_ROOT / "knowledge")
            lines.append("- [{0}]({1})".format(item["title"], link.as_posix()))
            lines.append("  - {0}".format(item["summary"]))
            meta_bits = ["type: {0}".format(item["type"]), "priority: {0}".format(item["priority"])]
            if item["scope"]:
                meta_bits.append("scope: {0}".format(item["scope"]))
            lines.append("  - {0}".format(" · ".join(meta_bits)))
        lines.append("")
        pages[tag] = "\n".join(lines)
    return pages

def git_export_meta() -> Dict[str, object]:
    """采集导出时刻与仓库 commit 信息。"""
    meta: Dict[str, object] = {
        "exported_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "git_commit": "",
        "git_commit_short": "",
        "git_branch": "",
        "git_dirty": False,
    }
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(GIT_ROOT),
            text=True,
        ).strip()
        meta["git_commit"] = commit
        meta["git_commit_short"] = commit[:12]
    except (OSError, subprocess.CalledProcessError):
        pass
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(GIT_ROOT),
            text=True,
        ).strip()
        meta["git_branch"] = branch
    except (OSError, subprocess.CalledProcessError):
        pass
    try:
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=str(GIT_ROOT),
            text=True,
        ).strip()
        meta["git_dirty"] = bool(dirty)
    except (OSError, subprocess.CalledProcessError):
        pass
    return meta

def build_export_meta_md(meta: Dict[str, object], entry_count: int, tag_count: int) -> str:
    dirty = "是（工作区有未提交改动）" if meta.get("git_dirty") else "否"
    lines = [
        "# 索引导出元数据",
        "",
        "> 由 `ygg index` 自动写入。若时间或 commit 明显落后于当前仓库，请重新执行 `ygg index`。",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        "| 导出时间 | `{0}` |".format(meta.get("exported_at", "")),
        "| Git commit | `{0}` |".format(meta.get("git_commit", "") or "（未知）"),
        "| Git commit（短） | `{0}` |".format(meta.get("git_commit_short", "") or "（未知）"),
        "| Git 分支 | `{0}` |".format(meta.get("git_branch", "") or "（未知）"),
        "| 导出时工作区脏 | {0} |".format(dirty),
        "| 条目数 | {0} |".format(entry_count),
        "| tag 数 | {0} |".format(tag_count),
        "",
        "本目录下的 `by-tag/` 为可选人类浏览视图，**不是**联想检索真源；机器联想请用 `ygg associate`（读 `graph/`）。",
        "",
    ]
    return "\n".join(lines)

def planned_files(pages: Dict[str, str], meta: Dict[str, object], entry_count: int) -> Dict[Path, str]:
    planned: Dict[Path, str] = {
        EXPORT_META_JSON: json.dumps(
            {
                **meta,
                "entry_count": entry_count,
                "tag_count": len(pages),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        EXPORT_META_MD: build_export_meta_md(meta, entry_count, len(pages)),
    }
    for tag, content in pages.items():
        planned[BY_TAG_ROOT / "{0}.md".format(tag)] = content
    return planned

def read_existing(path: Path) -> str:
    if not path.exists():
        return ""
    if path.suffix == ".json":
        return path.read_text(encoding="utf-8")
    return path.read_text(encoding="utf-8-sig")

def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".json":
        path.write_text(content, encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8-sig")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="可选导出 indexes/by-tag（人类浏览）；需主动执行，结果可提交。"
    )
    parser.add_argument("--check", action="store_true", help="Exit non-zero if generated index differs from disk.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned writes without modifying files.")
    parser.add_argument("--json", action="store_true", help="Emit JSON for Agent consumption.")
    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    ensure_layout()
    from backends import get_memory_backend

    backend = get_memory_backend()
    entries = collect_entries(backend)
    pages = build_tag_pages(entries)
    meta = git_export_meta()
    planned = planned_files(pages, meta, len(entries))

    stale: List[Path] = []
    if BY_TAG_ROOT.exists():
        expected = {BY_TAG_ROOT / "{0}.md".format(tag) for tag in pages}
        for path in BY_TAG_ROOT.glob("*.md"):
            if path not in expected:
                stale.append(path)

    mismatches: List[Tuple[Path, str]] = []
    for path, content in planned.items():
        # export-meta 含时间戳，check 时忽略时间字段差异意义不大；仍按全文比较
        if path in (EXPORT_META_JSON, EXPORT_META_MD):
            if args.check:
                continue
        if read_existing(path) != content:
            mismatches.append((path, "update"))
    for path in stale:
        mismatches.append((path, "delete"))

    print("index_entries : {0}".format(len(entries)))
    print("index_tags    : {0}".format(len(pages)))
    print("index_files   : {0}".format(len(planned)))
    print("index_stale   : {0}".format(len(stale)))
    print("index_changed : {0}".format(len(mismatches)))
    print("index_commit  : {0}".format(meta.get("git_commit_short") or "unknown"))
    print("index_exported: {0}".format(meta.get("exported_at") or ""))

    if args.json and (args.check or args.dry_run):
        json.dump(
            {
                "entries": len(entries),
                "tags": len(pages),
                "files": len(planned),
                "stale": len(stale),
                "changed": len(mismatches),
                "mismatches": [{"action": a, "path": str(p)} for p, a in mismatches],
                "commit": meta.get("git_commit_short") or "unknown",
                "mode": "check" if args.check else "dry-run",
            },
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        sys.stdout.write("\n")
        return 1 if (args.check and mismatches) else 0

    if args.check:
        for path, action in mismatches:
            print("index_diff    : {0} {1}".format(action, path.as_posix()))
        return 1 if mismatches else 0

    if args.dry_run:
        for path, action in mismatches:
            print("index_plan    : {0} {1}".format(action, path.as_posix()))
        return 0

    for path, content in planned.items():
        write_file(path, content)
        print("index_write   : {0}".format(path.as_posix()))
    for path in stale:
        path.unlink()
        print("index_delete  : {0}".format(path.as_posix()))

    if args.json:
        json.dump(
            {
                "entries": len(entries),
                "tags": len(pages),
                "files": len(planned),
                "stale": len(stale),
                "status": "exported",
                "commit": meta.get("git_commit_short") or "unknown",
            },
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        print("index_status  : exported")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
