#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""联想检索 CLI：seed tags → 多跳相关 tag → 条目并集 → related 一跳 → 路径。

用法：
  python3 scripts/cmds/graph/associate.py --tag simu --tag git --hop 2
  # 或：ygg associate --tag simu --tag git --hop 2
"""

from __future__ import print_function

from pathlib import Path
import sys

# cmds/<domain>/<script>.py → scripts/
SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
SCRIPT_DIR = SCRIPTS_ROOT

import argparse
import json

from knowledge.graph import GraphError, KnowledgeGraphIndex  # noqa: E402

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Associate knowledge entries from seed tags via tag graph hops."
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="种子 tag（可重复）。通常由 Agent 根据对话/任务自动提炼。",
    )
    parser.add_argument("--hop", type=int, default=None, help="tag 扩展跳数，默认读配置")
    parser.add_argument(
        "--no-entry-related",
        action="store_true",
        help="不合并条目 front matter related 一跳",
    )
    parser.add_argument("--limit", type=int, default=10, help="最多返回多少条（默认 10）")
    parser.add_argument("--include-inactive", action="store_true", help="显式查看索引中的非生效规则")
    parser.add_argument(
        "--type",
        action="append",
        default=[],
        help="按 type 过滤命中（可重复，如 rule / lesson / skill / mcp-server / hook）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 输出，便于 Agent 继续处理",
    )
    return parser

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # 三庭合议 P2-2：避免非 UTF-8 终端中文 mojibake
    except Exception:
        pass
    parser = build_parser()
    args = parser.parse_args()
    if not args.tag:
        parser.error("至少提供一个 --tag 作为种子")
    if args.limit < 0:
        parser.error("--limit 不能为负数")

    try:
        index = KnowledgeGraphIndex()
        hits, meta = index.associate(
            seed_tags=args.tag,
            hop=args.hop,
            include_entry_related=not args.no_entry_related,
            limit=args.limit,
            types=args.type or None,
            include_inactive=args.include_inactive,
        )
    except GraphError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        payload = {
            "meta": {
                "seed_tags": meta["seed_tags"],
                "hop": meta["hop"],
                "entry_related_hops": meta["entry_related_hops"],
                "expanded_tags": meta["expanded_tags"],
                "hit_count": meta["hit_count"],
                "total_hit_count": meta["total_hit_count"],
                "truncated": meta["truncated"],
                "index_stale": meta["index_stale"],
                "freshness_scope": meta["freshness_scope"],
                "missing_entries": meta["missing_entries"],
                "types": meta.get("types", []),
                "weight": meta.get("weight", {}),
            },
            "hits": [
                {
                    "id": hit.entry.id,
                    "path": hit.entry.path,
                    "type": hit.entry.kind,
                    "title": hit.entry.title,
                    "tags": hit.entry.tags,
                    "related": hit.entry.related,
                    "priority": hit.entry.priority,
                    "status": hit.entry.status,
                    "confidence": hit.entry.confidence,
                    "last_reviewed": hit.entry.last_reviewed,
                    "index_stale": hit.entry.index_stale,
                    "via_tags": hit.via_tags,
                    "min_tag_hop": hit.min_tag_hop,
                    "from_entry_related": hit.from_entry_related,
                    "path_strength": hit.path_strength,
                    "path_cost": hit.path_cost if hit.path_cost != float("inf") else None,
                    "via_path": hit.via_path,
                }
                for hit in hits
            ],
        }
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    print("associate_seeds : {0}".format(",".join(meta["seed_tags"])))
    print("associate_hop   : {0}".format(meta["hop"]))
    expanded = meta["expanded_tags"]
    print(
        "associate_tags  : {0}".format(
            ", ".join(
                "{0}@h{1}/s{2:.3f}".format(tag, info.get("hop", 0), float(info.get("strength", 0.0)))
                for tag, info in sorted(
                    expanded.items(),
                    key=lambda x: (x[1].get("hop", 0), x[1].get("cost", 0.0), x[0]),
                )
            )
        )
    )
    print("associate_hits  : {0}".format(len(hits)))
    print("associate_total : {0}".format(meta["total_hit_count"]))
    print("associate_stale : {0}".format("yes" if meta["index_stale"] else "no"))
    for idx, hit in enumerate(hits, start=1):
        print("[{0}]".format(idx))
        print("  id        : {0}".format(hit.entry.id))
        print("  path      : {0}".format(hit.entry.path))
        print("  type      : {0}".format(hit.entry.kind))
        print("  status    : {0}".format(hit.entry.status or "unknown"))
        print("  confidence: {0}".format(hit.entry.confidence or "unknown"))
        print("  reviewed  : {0}".format(hit.entry.last_reviewed or "unknown"))
        print("  title     : {0}".format(hit.entry.title))
        print("  via_tags  : {0}".format(",".join(hit.via_tags) if hit.via_tags else "-"))
        print("  tag_hop   : {0}".format(hit.min_tag_hop if not hit.from_entry_related else "-"))
        if not hit.from_entry_related:
            print("  strength  : {0:.4f}".format(hit.path_strength))
            print("  via_path  : {0}".format(" -> ".join(hit.via_path) if hit.via_path else "-"))
        print("  via_related: {0}".format("yes" if hit.from_entry_related else "no"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
