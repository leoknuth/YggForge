#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ygg tag CLI：list / add / relate / weight / propagate。"""

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

from knowledge.tag_manager import TagManager, build_propagate_report  # noqa: E402

def _force_from_args(args: argparse.Namespace):
    flags = [
        ("yes", getattr(args, "yes", False)),
        ("no", getattr(args, "no", False)),
        ("dry_run", getattr(args, "dry_run", False)),
    ]
    active = [name for name, on in flags if on]
    if len(active) > 1:
        raise ValueError("--yes / --no / --dry-run 不能同时使用")
    if getattr(args, "yes", False):
        return "allow"
    if getattr(args, "no", False):
        return "deny"
    if getattr(args, "dry_run", False):
        return "dry_run"
    return None

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage YggForge tag graph and review propagate candidates.")
    parser.add_argument("--list", action="store_true", help="列出 tag-graph 中的全部标签")
    parser.add_argument("--add", nargs="+", default=[], help="添加一个或多个标签")
    parser.add_argument(
        "--relate",
        nargs=2,
        metavar=("TAG_A", "TAG_B"),
        default=None,
        help="在两个标签之间建立双向关联（可用 --weight）",
    )
    parser.add_argument(
        "--weight",
        type=float,
        default=None,
        help="配合 --relate：设置边权 [0,1]；单独使用需 --set-weight TAG_A TAG_B",
    )
    parser.add_argument(
        "--set-weight",
        nargs=2,
        metavar=("TAG_A", "TAG_B"),
        default=None,
        help="仅更新已有边的 weight（需同时给 --weight）；人工路径走 tag_weight_update",
    )
    parser.add_argument(
        "--authority-writeback",
        nargs=2,
        metavar=("TAG_A", "TAG_B"),
        default=None,
        help="统计/校准回写权威 weight（需 --weight；走 tag_weight_authority_writeback，默认 deny）",
    )
    parser.add_argument("--propagate", metavar="TAG", default=None, help="生成标签传播审查报告（不改文件）")
    parser.add_argument(
        "--suggest",
        action="store_true",
        help="基于条目 tag 共现计算 PPMI 建议边，写入 yggforge-generated/indexes/tag-suggestions.json",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="配合 --suggest：经 tag_suggest_apply 闸门把建议边合并进 tag-graph.yaml",
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--yes", action="store_true", help="本次强制 allow（直接写入）")
    parser.add_argument("--no", action="store_true", help="本次强制 deny（拒绝写入）")
    parser.add_argument("--dry-run", action="store_true", help="本次强制 dry_run（只预览不写）")
    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        force = _force_from_args(args)
    except ValueError as exc:
        parser.error(str(exc))
        return 2
    tm = TagManager()

    if args.apply and not args.suggest:
        parser.error("--apply 必须与 --suggest 一起使用")

    actions = sum(
        [
            1 if args.list else 0,
            1 if args.add else 0,
            1 if args.relate else 0,
            1 if args.set_weight else 0,
            1 if args.authority_writeback else 0,
            1 if args.propagate else 0,
            1 if args.suggest else 0,
        ]
    )
    if actions != 1:
        parser.error(
            "请恰好指定一个动作：--list / --add / --relate / --set-weight / "
            "--authority-writeback / --propagate / --suggest"
        )

    if args.suggest:
        from knowledge.tag_suggest import apply_suggestions, compute_suggestions, write_suggestions

        payload = compute_suggestions()
        out_path = write_suggestions(payload)
        if args.apply:
            result = apply_suggestions(payload.get("suggestions") or [], force=force)
            if args.json:
                json.dump(
                    {"suggestions_file": str(out_path), "suggest": payload, "apply": result},
                    sys.stdout,
                    ensure_ascii=False,
                    indent=2,
                )
                sys.stdout.write("\n")
            else:
                print("suggest_file   : {0}".format(out_path))
                print("suggest_count  : {0}".format(len(payload.get("suggestions") or [])))
                print("apply_status   : {0}".format(result.get("status")))
                print("apply_written  : {0}".format(len(result.get("applied") or [])))
                print("apply_skipped  : {0}".format(len(result.get("skipped") or [])))
                cw = result.get("core_write") or {}
                if result.get("status") in ("denied", "dry_run"):
                    print("core_write     : {0} ({1})".format(result["status"], cw.get("reason")))
                    if cw.get("hint"):
                        print("hint           : {0}".format(cw["hint"]))
            return 0 if result.get("status") not in ("denied",) else 2
        if args.json:
            json.dump({"suggestions_file": str(out_path), "suggest": payload}, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            print("suggest_file  : {0}".format(out_path))
            print("suggest_docs  : {0}".format(payload.get("n_docs_with_tags")))
            print("suggest_count : {0}".format(len(payload.get("suggestions") or [])))
            for idx, item in enumerate((payload.get("suggestions") or [])[:20], start=1):
                print(
                    "[{0}] {1} <-> {2}  w={3}  ppmi={4}  n={5}".format(
                        idx,
                        item.get("a"),
                        item.get("b"),
                        item.get("w_suggest"),
                        item.get("ppmi"),
                        item.get("count"),
                    )
                )
            if len(payload.get("suggestions") or []) > 20:
                print("... ({0} more)".format(len(payload["suggestions"]) - 20))
        return 0

    if args.list:
        tags = tm.list_tags()
        payload = {"status": "ok", "count": len(tags), "tags": tags, "relations": tm.tag_relations()}
        if args.json:
            json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            print("tag_count : {0}".format(len(tags)))
            for tag in tags:
                related = tm.related_of(tag)
                print("tag : {0}".format(tag))
                print("  related : {0}".format(", ".join(related) if related else "<none>"))
        return 0

    if args.add:
        result = tm.add_tags(args.add, force=force)
        if args.json:
            json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            print("tag_status : {0}".format(result["status"]))
            print("tag_added  : {0}".format(",".join(result["added"]) or "<none>"))
            print("tag_merged : {0}".format(result["merged"] or "<none>"))
            print("tag_skipped: {0}".format(",".join(result["skipped"]) or "<none>"))
            if result.get("status") in ("denied", "dry_run"):
                cw = result.get("core_write") or {}
                print("core_write : {0} ({1})".format(result["status"], cw.get("reason")))
                if cw.get("hint"):
                    print("hint       : {0}".format(cw["hint"]))
        return 0 if result.get("status") not in ("denied",) else 2

    if args.relate:
        a, b = args.relate
        weight = 1.0 if args.weight is None else float(args.weight)
        try:
            payload = tm.add_relation(a, b, weight=weight, force=force)
        except ValueError as exc:
            print("error: {0}".format(exc), file=sys.stderr)
            return 1
        if args.json:
            json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            print("tag_relate : {0}".format(payload["status"]))
            print("tag_a      : {0}".format(payload.get("a")))
            print("tag_b      : {0}".format(payload.get("b")))
            print("tag_weight : {0}".format(payload.get("weight")))
            if payload.get("status") in ("denied", "dry_run"):
                cw = payload.get("core_write") or {}
                print("core_write : {0} ({1})".format(payload["status"], cw.get("reason")))
                if cw.get("hint"):
                    print("hint       : {0}".format(cw["hint"]))
        return 0 if payload.get("status") not in ("denied",) else 2

    if args.set_weight:
        if args.weight is None:
            parser.error("--set-weight 需要同时指定 --weight")
        a, b = args.set_weight
        try:
            payload = tm.set_relation_weight(a, b, weight=float(args.weight), force=force)
        except ValueError as exc:
            print("error: {0}".format(exc), file=sys.stderr)
            return 1
        if args.json:
            json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            print("tag_weight_status : {0}".format(payload["status"]))
            print("tag_a             : {0}".format(payload.get("a")))
            print("tag_b             : {0}".format(payload.get("b")))
            print("tag_weight        : {0}".format(payload.get("weight")))
            if payload.get("message"):
                print("message           : {0}".format(payload["message"]))
            if payload.get("status") in ("denied", "dry_run"):
                cw = payload.get("core_write") or {}
                print("core_write        : {0} ({1})".format(payload["status"], cw.get("reason")))
                if cw.get("hint"):
                    print("hint              : {0}".format(cw["hint"]))
        if payload.get("status") == "denied":
            return 2
        if payload.get("status") == "missing":
            return 1
        return 0

    if args.authority_writeback:
        if args.weight is None:
            parser.error("--authority-writeback 需要同时指定 --weight")
        a, b = args.authority_writeback
        try:
            payload = tm.writeback_authority_weight(a, b, weight=float(args.weight), force=force)
        except ValueError as exc:
            print("error: {0}".format(exc), file=sys.stderr)
            return 1
        if args.json:
            json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            print("tag_writeback_status : {0}".format(payload["status"]))
            print("tag_a                : {0}".format(payload.get("a")))
            print("tag_b                : {0}".format(payload.get("b")))
            print("tag_weight           : {0}".format(payload.get("weight")))
            if payload.get("status") in ("denied", "dry_run"):
                cw = payload.get("core_write") or {}
                print("core_write           : {0} ({1})".format(payload["status"], cw.get("reason")))
                if cw.get("hint"):
                    print("hint                 : {0}".format(cw["hint"]))
        return 0 if payload.get("status") not in ("denied",) else 2

    if args.propagate:
        report = build_propagate_report(args.propagate)
        if args.json:
            json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            print("propagate_status : {0}".format(report.get("status")))
            print("propagate_tag    : {0}".format(report.get("tag")))
            print("propagate_related: {0}".format(",".join(report.get("related_tags") or []) or "<none>"))
            print("propagate_count  : {0}".format(report.get("candidate_count", 0)))
            for idx, item in enumerate(report.get("candidates") or [], start=1):
                print("[{0}]".format(idx))
                print("  id    : {0}".format(item.get("id")))
                print("  title : {0}".format(item.get("title")))
                print("  path  : {0}".format(item.get("path")))
                print("  tags  : {0}".format(",".join(item.get("current_tags") or [])))
            if report.get("instruction"):
                print("propagate_hint   : {0}".format(report["instruction"]))
        return 0 if report.get("status") != "error" else 1

    return 1

if __name__ == "__main__":
    raise SystemExit(main())
