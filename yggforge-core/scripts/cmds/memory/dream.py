#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""记忆整理报告：重复扫描、晋升候选、consolidation 提示。

由 ``ygg dream`` 调用。默认只报告不自动改写；写操作仍走 behavior 门禁。
"""

from pathlib import Path
import sys

# cmds/<domain>/<script>.py → scripts/
SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
SCRIPT_DIR = SCRIPTS_ROOT

import argparse
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from backends import get_memory_backend

def normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())

def duplicate_key(title: str, text: str) -> Tuple[str, str]:
    normalized_title = title.strip().lower()
    normalized_body = normalize_text(text)
    return normalized_title, normalized_body[:200]

def is_lessons_inbox_path(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    try:
        knowledge_idx = parts.index("knowledge")
    except ValueError:
        return False
    return parts[knowledge_idx : knowledge_idx + 3] == ["knowledge", "lessons", "inbox"]

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consolidate runtime memory into a reviewable dream report.")
    parser.add_argument("--scan", action="store_true", help="Read-only scan; do not write a report file.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum duplicate/candidate items to print per section.")
    parser.add_argument("--yes", action="store_true", help="本次强制 allow（覆盖 behavior ask）")
    parser.add_argument("--no", action="store_true", help="本次强制 deny")
    parser.add_argument("--json", action="store_true", help="Emit JSON for Agent consumption.")
    return parser

def build_report(
    duplicates: List[Dict[str, str]],
    candidates: List[Dict[str, str]],
    settings: Dict[str, object],
) -> str:
    lines = [
        "# Dream Report",
        "",
        "- intensity: `{0}`".format(settings.get("intensity")),
        "- depth: `{0}`".format(settings.get("depth")),
        "- period: `{0}`".format(settings.get("period")),
        "- frequency: `{0}`".format(settings.get("frequency")),
        "",
        "## Duplicate Candidates",
        "",
    ]
    if not duplicates:
        lines.append("- none")
    else:
        for item in duplicates:
            lines.append("- title: `{0}`".format(item["title"]))
            lines.append("  paths: `{0}` | `{1}`".format(item["path_a"], item["path_b"]))
    lines.extend(["", "## Promotion Candidates", ""])
    if not candidates:
        lines.append("- none")
    else:
        for item in candidates:
            lines.append("- title: `{0}`".format(item["title"]))
            lines.append("  path: `{0}`".format(item["path"]))
            lines.append("  rationale: {0}".format(item["rationale"]))
    lines.append("")
    return "\n".join(lines)

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.yes and args.no:
        raise SystemExit("--yes 与 --no 不能同时使用")

    force: Optional[str] = None
    if args.yes:
        force = "allow"
    elif args.no:
        force = "deny"

    from policies.behavior import authorize, dream_settings, load_behavior_config

    cfg = load_behavior_config()
    settings = dream_settings(cfg)
    if not settings.get("enabled", True):
        print("dream_status : disabled (behavior.dream.enabled=false)", file=sys.stderr)
        return 2

    d_run = authorize(
        "dream.mode",
        "执行 dream 扫描（intensity={0}, depth={1}）".format(
            settings.get("intensity"), settings.get("depth")
        ),
        force=force,
        cfg=cfg,
    )
    if not d_run.get("allowed"):
        if args.json:
            json.dump({"status": "denied", "behavior": d_run, "dream": settings}, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            print("dream_status  : denied")
            print("behavior_reason: {0}".format(d_run.get("reason")))
            if d_run.get("hint"):
                print("behavior_hint  : {0}".format(d_run["hint"]))
        return 2

    limit = args.limit if args.limit is not None else int(settings.get("max_items_per_section") or 10)

    backend = get_memory_backend()
    entries = backend.collect_existing_entries()

    duplicates: List[Dict[str, str]] = []
    candidates: List[Dict[str, str]] = []
    seen_duplicate_keys = set()
    key_to_entry: Dict[Tuple[str, str], Tuple[Path, str, str]] = {}

    for path, title, raw_text in entries:
        key = duplicate_key(title, raw_text)
        existing = key_to_entry.get(key)
        if existing and key not in seen_duplicate_keys:
            duplicates.append(
                {
                    "title": title or path.stem,
                    "path_a": str(existing[0]),
                    "path_b": str(path),
                }
            )
            seen_duplicate_keys.add(key)
        else:
            key_to_entry[key] = (path, title, raw_text)

        metadata, _body = backend.parse_front_matter(raw_text)
        entry_type = str(metadata.get("type") or "").lower()
        status = metadata.get("status", "")
        promoted_to = metadata.get("promoted_to", "")
        if entry_type == "observation" and status == "recorded":
            candidates.append(
                {
                    "title": title or path.stem,
                    "path": str(path),
                    "rationale": "raw observation has not yet been consolidated into a promoted artifact",
                }
            )
        elif status == "draft" and not promoted_to and is_lessons_inbox_path(path):
            candidates.append(
                {
                    "title": title or path.stem,
                    "path": str(path),
                    "rationale": "draft lesson still waiting for review or promotion",
                }
            )

    duplicates = duplicates[:limit]
    candidates = candidates[:limit]

    report_path = ""
    write_report = False
    d_write = {"allowed": False, "reason": "scan_only"}
    if not args.scan:
        d_write = authorize(
            "dream.write_report",
            "写入 dream 报告到 runtime/memory/index",
            force=force,
            cfg=cfg,
        )
        write_report = bool(d_write.get("allowed"))
        if write_report:
            report_root = backend.index_root
            report_root.mkdir(parents=True, exist_ok=True)
            report_path = str(
                report_root / "{0}-dream-report.md".format(datetime.now().strftime("%Y%m%d-%H%M%S"))
            )
            Path(report_path).write_text(
                build_report(duplicates, candidates, settings),
                encoding="utf-8-sig",
            )

    if args.json:
        payload = {
            "scan": True,
            "entries": len(entries),
            "duplicates": duplicates,
            "candidates": candidates,
            "report_path": report_path or None,
            "dream": settings,
            "behavior": {"mode": d_run, "write_report": d_write},
        }
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    print("dream_scan     : {0}".format(True))
    print("dream_intensity: {0}".format(settings.get("intensity")))
    print("dream_depth    : {0}".format(settings.get("depth")))
    print("dream_period   : {0}".format(settings.get("period")))
    print("dream_freq     : {0}".format(settings.get("frequency")))
    print("dream_entries  : {0}".format(len(entries)))
    print("dream_dupes    : {0}".format(len(duplicates)))
    print("dream_promote  : {0}".format(len(candidates)))

    for idx, item in enumerate(duplicates, start=1):
        print("[duplicate {0}]".format(idx))
        print("  title : {0}".format(item["title"]))
        print("  path_a: {0}".format(item["path_a"]))
        print("  path_b: {0}".format(item["path_b"]))

    for idx, item in enumerate(candidates, start=1):
        print("[candidate {0}]".format(idx))
        print("  title    : {0}".format(item["title"]))
        print("  path     : {0}".format(item["path"]))
        print("  rationale: {0}".format(item["rationale"]))

    if report_path:
        print("dream_report   : {0}".format(report_path))
    elif not args.scan and not write_report:
        print("dream_report   : <skipped by behavior>")
    if d_run.get("persist_path"):
        print("behavior_local : {0}".format(d_run["persist_path"]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
