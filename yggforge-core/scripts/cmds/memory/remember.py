#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""写入运行时记忆，并可选镜像到 lessons/inbox。

由 ``ygg remember`` 调用。经 ``backends.get_memory_backend()`` 落盘到
``yggforge-runtime/memory``；站立意图可自动触发 promote。
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
import re
import subprocess
from typing import List, Optional

from backends import get_memory_backend

# 用户显式站立偏好：视为对「晋升到 rules」的人类确认
STANDING_PATTERNS = [
    r"以后一直这样",
    r"(?:以后|今后|往后|从现在开始|从今以后)[^。！？\n]{0,36}(?:始终|一直|永久|一律|必须)",
    r"写成规则",
    r"写进规则",
    r"升级成规则",
    r"升级成\s*rules?",
    r"晋升为?规则",
    r"晋升为?\s*rules?",
    r"作为规则",
    r"变成规范",
    r"自动[^。！？\n]{0,20}(升级|晋升)[^。！？\n]{0,20}(规则|rules?)",
    r"应该自动[^。！？\n]{0,20}(规则|rules?)",
    r"from now on\s+always",
    r"(?:^|[.!?\n])\s*(?:please\s+)?always do (this|it)\b",
    r"make (this|it) a rule",
    r"promote to rule",
]

NEGATIVE_STANDING_PATTERNS = [
    r"(?:不要|不需要|无需|不用|不能|不应(?:该)?|不得|不可|不准|不是|并非|不再|暂(?:时)?不|尚不|别|禁止|停止|取消|拒绝)[^。！？\n]{0,24}(?:规则|规范|晋升|升级|一直这样|始终|永久|一律|长期|必须遵守)",
    r"(?:\bdo\s+not\b|\bdon['’]t\b|\bnot\b|\bnever\b|\bno\s+need\b|\bwithout\b)[^.!?\n]{0,40}(?:\brules?\b|\bpromot\w*\b|\balways\b|\bfrom now on\b)",
    r"(?:写成规则|作为规则|晋升规则|升级规则)[^。！？\n]{0,12}(?:不需要|没必要|不可|不应|不允许)",
]


def _unquoted_text(text: str) -> str:
    """引用、代码和例子本身不能提供自动晋升规则的人类授权。"""
    text = re.sub(r"```[\s\S]*?```|`[^`\n]*`", " ", text)
    for opening, closing in (("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』"), ('"', '"')):
        text = re.sub(re.escape(opening) + r"[\s\S]*?" + re.escape(closing), " ", text)
    return re.sub(r"(?<!\w)'[^']*'(?!\w)", " ", text)

def _force_from_args(args: argparse.Namespace) -> Optional[str]:
    if getattr(args, "yes", False) and getattr(args, "no", False):
        raise SystemExit("--yes 与 --no 不能同时使用")
    if getattr(args, "yes", False):
        return "allow"
    if getattr(args, "no", False):
        return "deny"
    return None

def detect_standing_intent(*texts: str) -> bool:
    """只识别用户未引用、未否定的明确规则或长期指令；不确定时保留草稿。"""
    blob = "\n".join(t for t in texts if t).strip()
    if not blob:
        return False
    blob = _unquoted_text(blob)
    if any(re.search(pattern, blob, re.IGNORECASE) for pattern in NEGATIVE_STANDING_PATTERNS):
        return False
    if re.search(r"候选|草稿|摘录|引用|示例|例子|假设|仅供讨论|(?:文中|原文|文章)[^。！？\n]{0,16}(?:提到|写道|要求|规定)|\b(?:quote[ds]?|quotation|excerpt|draft|example|hypothetical)\b", blob, re.IGNORECASE):
        return False
    for pattern in STANDING_PATTERNS:
        if re.search(pattern, blob, re.IGNORECASE):
            return True
    return False

def _slug_name(title: str) -> str:
    """保留中英文标题生成独立文件名，避免中文偏好全部撞同一个规则。"""
    text = (title or "").strip().lower()
    slug = re.sub(r"[^\w]+", "-", text, flags=re.UNICODE).strip("-")
    if slug:
        return slug[:48] + ".md"
    from uuid import uuid4
    return "standing-{0}.md".format(uuid4().hex[:12])

def _auto_promote_standing(draft_path: str, title: str, force: Optional[str], as_json: bool) -> dict:
    """remember 成功后，对站立偏好自动 promote --auto --to rule --standing。"""
    args = [
        sys.executable,
        str(SCRIPT_DIR / "cmds" / "pipeline" / "promote.py"),
        "--to",
        "rule",
        "--entry",
        draft_path,
        "--auto",
        "--standing",
        "--name",
        _slug_name(title),
    ]
    if force == "allow":
        args.append("--yes")
    elif force == "deny":
        args.append("--no")
    if as_json:
        args.append("--json")
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    payload = {"status": "ok" if proc.returncode == 0 else "failed", "returncode": proc.returncode}
    if as_json and out:
        try:
            payload["result"] = json.loads(out)
        except Exception:
            payload["stdout"] = out[:2000]
    else:
        if out:
            payload["stdout"] = out[:2000]
    if err:
        payload["stderr"] = err[:500]
    return payload

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a draft remember entry inside YggForge.")
    parser.add_argument("--note", required=True, help="The correction, preference, or lesson to remember.")
    parser.add_argument("--title", default=None, help="Optional explicit original title (never overwritten).")
    parser.add_argument(
        "--title-refined",
        default=None,
        help="Optional LLM-refined short title; stored as title_refined, does not replace title.",
    )
    parser.add_argument("--source", default="user", help="Where the remembered note came from.")
    parser.add_argument("--scope", default="cross-project", help="Applicability scope for this note.")
    parser.add_argument(
        "--tags",
        nargs="+",
        default=None,
        help="Tags supplied by LLM/caller; normalized via graph/tag-synonyms.yaml.",
    )
    parser.add_argument(
        "--channel",
        default=None,
        help="沟通入口 / Agent 来源（见 config/channels.yaml；如 wechat、cursor、kimi）",
    )
    parser.add_argument(
        "--as",
        dest="as_kind",
        choices=["inbox", "lesson", "rule"],
        default="inbox",
        help="目标层级：inbox=仅草稿（默认）；rule=站立偏好，写入 inbox 后自动晋升 rules；"
        "lesson=预留（当前仍只写 inbox，可用 promote --auto --objective）。",
    )
    parser.add_argument(
        "--standing",
        action="store_true",
        help="显式标记为站立偏好（等价于 --as rule）。也可由正文/标题中的「以后一直这样」等自动识别。",
    )
    parser.add_argument(
        "--allow-duplicate",
        action="store_true",
        help="Write a new entry even if a similar title or note already exists.",
    )
    parser.add_argument("--yes", action="store_true", help="本次强制 allow（覆盖 behavior ask）")
    parser.add_argument("--no", action="store_true", help="本次强制 deny")
    parser.add_argument("--json", action="store_true", help="Emit JSON for Agent consumption.")
    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    note = args.note.strip()
    if not note:
        raise SystemExit("`remember` requires a non-empty note.")

    force = _force_from_args(args)
    from policies.behavior import authorize

    standing = bool(args.standing) or args.as_kind == "rule"
    if not standing and args.source.strip().lower() == "user":
        standing = detect_standing_intent(note, args.title or "")

    decisions = {}

    # 目标层级：inbox 不入 memory.kinds 门禁；lesson/rule 要按 kinds 控制
    target_kind = args.as_kind if args.as_kind != "inbox" else ""
    if standing:
        target_kind = "rule"
    if target_kind:
        d_kind = authorize(
            "memory.kinds.{0}".format(target_kind),
            "将记忆目标层级设为 {0}".format(target_kind),
            force=force,
        )
        decisions["memory.kinds.{0}".format(target_kind)] = d_kind
        if not d_kind.get("allowed"):
            payload = {"status": "denied", "behavior": decisions, "standing": standing}
            if args.json:
                json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
                sys.stdout.write("\n")
            else:
                print("remember_state  : denied")
                print("behavior_reason : memory.kinds.{0} = {1}".format(target_kind, d_kind.get("mode")))
                if d_kind.get("hint"):
                    print("behavior_hint   : {0}".format(d_kind["hint"]))
                if d_kind.get("persist_path"):
                    print("behavior_local  : {0}".format(d_kind["persist_path"]))
            return 2

    d_rec = authorize(
        "memory.record_observation",
        "写入 runtime 观察记忆: {0}".format((args.title or note)[:80]),
        force=force,
    )
    decisions["record_observation"] = d_rec
    if not d_rec.get("allowed"):
        payload = {"status": "denied", "behavior": decisions, "standing": standing}
        if args.json:
            json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            print("remember_state  : denied")
            print("behavior_reason : {0}".format(d_rec.get("reason")))
            if d_rec.get("hint"):
                print("behavior_hint   : {0}".format(d_rec["hint"]))
            if d_rec.get("persist_path"):
                print("behavior_local  : {0}".format(d_rec["persist_path"]))
        return 2

    d_mir = authorize(
        "memory.mirror_to_lessons_inbox",
        "镜像到 knowledge/lessons/inbox",
        force=force,
    )
    decisions["mirror_to_lessons_inbox"] = d_mir
    # deny/dry_run 镜像：仍可写 raw，只是不镜像
    mirror = bool(d_mir.get("allowed"))
    # 站立偏好必须镜像到 inbox，否则无法 promote
    if standing and not mirror:
        payload = {
            "status": "denied",
            "reason": "standing preference requires mirror_to_lessons_inbox",
            "standing": True,
            "behavior": decisions,
        }
        if args.json:
            json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            print("remember_state  : denied")
            print("remember_reason : standing requires lessons inbox mirror")
        return 2

    backend = get_memory_backend()
    result = backend.record_observation(
        note=note,
        title=args.title,
        source=args.source.strip(),
        scope=args.scope.strip(),
        allow_duplicate=args.allow_duplicate,
        tags=args.tags,
        title_refined=args.title_refined,
        mirror_to_inbox=mirror,
        channel=args.channel,
        force=force,
    )
    result["behavior"] = decisions
    result["standing"] = standing

    promote_info = None
    draft = result.get("lesson_draft_path") or ""
    if standing and draft and result.get("status") == "recorded":
        promote_info = _auto_promote_standing(
            draft_path=draft,
            title=result.get("title_refined") or result.get("title") or note[:40],
            force=force,
            as_json=True,
        )
        result["promote"] = promote_info
        promoted_items = (promote_info.get("result") or {}).get("results") or []
        if promote_info.get("status") == "ok" and promoted_items and all(
            item.get("write") == "ok" for item in promoted_items
        ):
            result["status"] = "recorded_and_promoted_rule"
        else:
            result["status"] = "recorded_promote_pending"

    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0 if result.get("status") != "denied" else 2

    print("remember_raw    : {0}".format(result.get("raw_path", "")))
    if result.get("lesson_draft_path"):
        print("remember_draft  : {0}".format(result["lesson_draft_path"]))
    elif not mirror:
        print("remember_draft  : <skipped by behavior>")
    print("remember_title  : {0}".format(result.get("title", "")))
    print("remember_refined: {0}".format(result.get("title_refined", "") or "<none>"))
    tags = result.get("tags") or []
    print("remember_tags   : {0}".format(",".join(tags) if tags else "<none>"))
    print("remember_standing: {0}".format("yes" if standing else "no"))
    print("remember_state  : {0}".format(result.get("status", "unknown")))
    if promote_info:
        print("promote_standing: {0}".format(promote_info.get("status")))
        if promote_info.get("result"):
            targets = []
            for item in promote_info["result"].get("results") or []:
                if item.get("target"):
                    targets.append(item["target"])
            if targets:
                print("promote_target  : {0}".format("; ".join(targets)))
    if d_rec.get("persist_path") or d_mir.get("persist_path"):
        print(
            "behavior_local  : {0}".format(
                d_rec.get("persist_path") or d_mir.get("persist_path")
            )
        )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
