#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识图索引构建 CLI。

用法：
  python3 scripts/cmds/graph/graph_index.py --build
  python3 scripts/cmds/graph/graph_index.py --check
  python3 scripts/cmds/graph/graph_index.py --build --with-by-tag
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
import subprocess

from knowledge.graph import (  # noqa: E402
    GraphError,
    REPO_ROOT,
    build_indexes,
    load_graph_config,
    scan_knowledge_entries,
)
from knowledge.graph_build import check_indexes

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or check YggForge knowledge graph indexes.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", action="store_true", help="扫描真源并重建机器索引")
    group.add_argument("--check", action="store_true", help="校验警告；有警告则非 0")
    parser.add_argument(
        "--with-by-tag",
        action="store_true",
        help="额外可选导出 indexes/by-tag（默认不导出；人类浏览用）",
    )
    parser.add_argument(
        "--skip-by-tag",
        action="store_true",
        help="显式不导出 by-tag（与默认相同；保留作别名）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只扫描打印，不写分片")
    parser.add_argument("--json", action="store_true", help="Emit JSON for Agent consumption.")
    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = load_graph_config()
    max_depth = int(config.get("max_path_depth_under_knowledge", 5))

    if args.dry_run:
        entries, warnings = scan_knowledge_entries(REPO_ROOT, max_depth=max_depth)
        if args.json:
            json.dump(
                {
                    "mode": "dry-run",
                    "entries": len(entries),
                    "warnings": warnings,
                },
                sys.stdout,
                ensure_ascii=False,
                indent=2,
            )
            sys.stdout.write("\n")
        else:
            print("graph_entries : {0}".format(len(entries)))
            print("graph_warnings: {0}".format(len(warnings)))
            for warning in warnings:
                print("graph_warn    : {0}".format(warning))
        return 1 if (args.check and warnings) else 0

    try:
        result = build_indexes(config=config) if args.build else check_indexes(config=config)
    except GraphError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    by_tag_code = None
    if args.with_by_tag and not args.skip_by_tag:
        from lib.leaf_scripts import resolve_leaf

        index_args = [sys.executable, str(resolve_leaf(SCRIPT_DIR, "index_knowledge.py"))]
        if args.check and not args.build:
            index_args.append("--check")
        by_tag_code = subprocess.call(index_args)
    else:
        by_tag_code = None

    if args.json:
        payload = {
            "entries": result["entries"],
            "tags": result["tags"],
            "warnings": result["warnings"],
            "catalog_files": len(result["catalog_manifest"].get("files", [])),
            "taginv_files": len(result["tag_manifest"].get("files", [])),
            "by_tag": (
                "skipped"
                if by_tag_code is None
                else {"exit": by_tag_code}
            ),
            "status": "built" if args.build else "checked",
        }
        if args.check:
            payload.update({key: result[key] for key in ("index_status", "migration_required", "consistency_errors", "source_consistency")})
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        if args.check and result["warnings"]:
            return 1
        if by_tag_code not in (None, 0) and args.check:
            return by_tag_code
        return 0

    print("graph_entries : {0}".format(result["entries"]))
    print("graph_tags    : {0}".format(result["tags"]))
    print(
        "catalog_files : {0}".format(len(result["catalog_manifest"].get("files", [])))
    )
    print(
        "taginv_files  : {0}".format(len(result["tag_manifest"].get("files", [])))
    )
    for warning in result["warnings"]:
        print("graph_warn    : {0}".format(warning))
    if args.check:
        print("graph_status  : {0}".format(result["index_status"]))
        print("graph_sources : {0}".format(result["source_consistency"]))

    if by_tag_code is None:
        print("by_tag_status : skipped (optional export; use --with-by-tag or ygg index)")
    else:
        print("by_tag_status : exit={0}".format(by_tag_code))
        if by_tag_code != 0 and args.check:
            return by_tag_code

    if args.check and result["warnings"]:
        return 1
    if args.build:
        print("graph_status  : built")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
