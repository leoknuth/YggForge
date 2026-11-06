#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检索运行时记忆与正式知识。

由 ``ygg recall "<query>"`` 调用。支持 kind/tag/scope 过滤与 ``--json`` 输出。
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
from typing import List

from backends import get_memory_backend

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search YggForge knowledge and runtime memory with optional filters."
    )
    parser.add_argument(
        "--query",
        default="",
        help="Search query. Optional when at least one filter is provided.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of recall results to print.")
    parser.add_argument(
        "--type",
        action="append",
        default=[],
        help=(
            "Filter by entry type (matches front matter type / path). "
            "Repeatable or comma-separated. Example: --type rule --type lesson"
        ),
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Filter by tag; multiple values are AND-ed. Example: --tag git --tag agent",
    )
    parser.add_argument(
        "--scope",
        default="",
        help="Substring filter against front matter scope (case-insensitive).",
    )
    parser.add_argument(
        "--agent",
        action="append",
        default=[],
        help="Filter by agent_targets (repeatable or comma-separated). Entries without agent_targets are excluded.",
    )
    parser.add_argument(
        "--channel",
        action="append",
        default=[],
        help="Filter by channel (repeatable or comma-separated). Example: --channel wechat --channel cursor",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON for Agent consumption.")
    parser.add_argument("--include-inactive", action="store_true", help="显式检索非生效规则")
    return parser

def flatten_values(values: List[str]) -> List[str]:
    flattened: List[str] = []
    for value in values:
        for part in value.split(","):
            item = part.strip()
            if item:
                flattened.append(item)
    return flattened

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.limit is not None and args.limit < 0:
        parser.error("--limit 不能为负数")

    kinds = flatten_values(args.type)
    tags = flatten_values(args.tag)
    agents = flatten_values(args.agent)
    channels = flatten_values(args.channel)
    scope = (args.scope or "").strip()
    query = (args.query or "").strip()

    if not query and not (kinds or tags or scope or agents or channels):
        parser.error("Provide --query and/or at least one of --type/--tag/--scope/--agent/--channel.")

    backend = get_memory_backend()
    results = backend.search_memories(
        query=query,
        limit=args.limit,
        kinds=kinds or None,
        tags=tags or None,
        scope=scope or None,
        agents=agents or None,
        channels=channels or None,
        include_inactive=args.include_inactive,
    )

    if args.json:
        payload = {
            "query": query or None,
            "type": kinds or None,
            "tag": tags or None,
            "scope": scope or None,
            "agent": agents or None,
            "channel": channels or None,
            "hits": len(results),
            "results": results,
        }
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    print("recall_query : {0}".format(query or "<none>"))
    print("recall_type  : {0}".format(",".join(kinds) if kinds else "<any>"))
    print("recall_tag   : {0}".format(",".join(tags) if tags else "<any>"))
    print("recall_scope : {0}".format(scope or "<any>"))
    print("recall_agent : {0}".format(",".join(agents) if agents else "<any>"))
    print("recall_channel: {0}".format(",".join(channels) if channels else "<any>"))
    print("recall_hits  : {0}".format(len(results)))
    for idx, item in enumerate(results, start=1):
        print("[{0}]".format(idx))
        print("  type          : {0}".format(item["type"]))
        print("  status        : {0}".format(item["status"] or "<unknown>"))
        print("  confidence    : {0}".format(item["confidence"] or "<unknown>"))
        print("  last_reviewed : {0}".format(item["last_reviewed"] or "<unknown>"))
        print("  title         : {0}".format(item["title"]))
        print("  title_refined : {0}".format(item.get("title_refined", "") or "<none>"))
        print("  path          : {0}".format(item["path"]))
        print("  recorded_at   : {0}".format(item["recorded_at"] or "<unknown>"))
        print("  scope         : {0}".format(item.get("scope", "") or "<unknown>"))
        print("  channel       : {0}".format(item.get("channel", "") or "<none>"))
        print("  tags          : {0}".format(item.get("tags", "") or "<none>"))
        print("  agent         : {0}".format(item.get("agent", "") or "<none>"))
        print("  score         : {0}".format(item["score"]))
        print("  preview       : {0}".format(item["preview"]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
