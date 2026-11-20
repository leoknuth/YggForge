#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在同一知识空间内把 inbox 草稿晋升为各类长期条目。

由 ``ygg promote`` 调用。含 front matter 改写、README 索引、联想查重；
写操作受既有门禁约束，角色晋升与查重始终留在自身 notes/graph。
"""

from pathlib import Path, PureWindowsPath
import sys

# cmds/<domain>/<script>.py → scripts/
SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
SCRIPT_DIR = SCRIPTS_ROOT

import argparse
import json
import re
from contextvars import ContextVar
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from lib.repo_paths import CORE_ROOT

CONTENT_ROOT = CORE_ROOT
LESSONS_INBOX = CONTENT_ROOT / "knowledge" / "lessons" / "inbox"
DESTINATION_ROOTS = {
    "lesson": CONTENT_ROOT / "knowledge" / "lessons",
    "reference": CONTENT_ROOT / "knowledge" / "reference",
    "rule": CONTENT_ROOT / "knowledge" / "rules",
    "template": CONTENT_ROOT / "knowledge" / "templates",
    "decision": CONTENT_ROOT / "knowledge" / "decisions",
}
README_PATHS = {
    "lesson": CONTENT_ROOT / "knowledge" / "lessons" / "README.md",
    "reference": CONTENT_ROOT / "knowledge" / "reference" / "README.md",
    "rule": CONTENT_ROOT / "knowledge" / "rules" / "README.md",
    "template": CONTENT_ROOT / "knowledge" / "templates" / "README.md",
    "decision": CONTENT_ROOT / "knowledge" / "decisions" / "README.md",
}
PROMOTION_SPACE = ContextVar("promotion_space", default=None)


def content_root() -> Path:
    """角色晋升使用自身空间；一般知识晋升沿用全局内容根。"""
    space = PROMOTION_SPACE.get()
    return space.root if space is not None else CONTENT_ROOT


def lessons_inbox() -> Path:
    space = PROMOTION_SPACE.get()
    return space.note_root / "lessons/inbox" if space is not None else LESSONS_INBOX


def destination_roots() -> Dict[str, Path]:
    space = PROMOTION_SPACE.get()
    if space is None:
        return DESTINATION_ROOTS
    return {kind: space.note_root / folder for kind, folder in {"lesson": "lessons", "reference": "reference", "rule": "rules", "template": "templates", "decision": "decisions"}.items()}


def readme_paths() -> Dict[str, Path]:
    space = PROMOTION_SPACE.get()
    return {kind: root / "README.md" for kind, root in destination_roots().items()} if space is not None else README_PATHS


def write_document(path: Path, text: str) -> None:
    """角色写入原子文件，一般知识保留现有保存方式。"""
    if PROMOTION_SPACE.get() is not None:
        from backends.role_memory import atomic_write_text
        atomic_write_text(path, text)
    else:
        path.write_text(text, encoding="utf-8-sig")

class PromoteError(RuntimeError):
    pass

def resolve_entry(entry: str) -> Path:
    candidate = Path(entry)
    if candidate.is_absolute():
        path = candidate
    else:
        path = (lessons_inbox() / candidate).resolve()
        if not path.exists() and not str(candidate).endswith(".md"):
            path = (lessons_inbox() / "{0}.md".format(candidate)).resolve()
    if not path.exists():
        raise PromoteError("Entry does not exist: {0}".format(entry))
    if not path.is_file():
        raise PromoteError("Entry is not a file: {0}".format(path))
    if PROMOTION_SPACE.get() is not None:
        try:
            path.resolve().relative_to(lessons_inbox().resolve())
        except ValueError as exc:
            raise PromoteError("角色只能晋升自己的 inbox 草稿。") from exc
    return path

def split_front_matter(text: str) -> Tuple[Optional[List[str]], str]:
    """委托 ``lib.front_matter.split_front_matter_lines``。"""
    from lib.front_matter import split_front_matter_lines

    return split_front_matter_lines(text)

def extract_scalar(lines: List[str], key: str) -> str:
    pattern = re.compile(r"^{0}:\s*(.+)$".format(re.escape(key)))
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1).strip().strip('"')
    return ""

def update_or_append_scalar(lines: List[str], key: str, value: str) -> None:
    pattern = re.compile(r"^{0}:\s*".format(re.escape(key)))
    if key == "id":
        replacement = "{0}: {1}".format(key, value)
    else:
        replacement = '{0}: "{1}"'.format(key, value.replace('"', '\\"'))
    for idx, line in enumerate(lines):
        if pattern.match(line):
            lines[idx] = replacement
            return
    lines.append(replacement)

def assign_knowledge_id(lines: List[str], destination: Path) -> None:
    from knowledge.knowledge_id import generate_knowledge_id

    title = extract_scalar(lines, "title") or destination.stem
    entry_id = generate_knowledge_id(destination, title, repo_root=content_root(), created=datetime.now())
    update_or_append_scalar(lines, "id", entry_id)

def update_rule_front_matter(lines: List[str], destination: Path) -> None:
    today = datetime.now().strftime("%Y%m%d")
    assign_knowledge_id(lines, destination)
    update_or_append_scalar(lines, "type", "rule")
    update_or_append_scalar(lines, "status", "active")
    update_or_append_scalar(lines, "last_reviewed", today)

def update_template_front_matter(lines: List[str], destination: Path) -> None:
    today = datetime.now().strftime("%Y%m%d")
    title = extract_scalar(lines, "title") or destination.stem
    update_or_append_scalar(lines, "title", title)
    assign_knowledge_id(lines, destination)
    update_or_append_scalar(lines, "type", "template")
    update_or_append_scalar(lines, "status", "active")
    update_or_append_scalar(lines, "template_kind", "reusable")
    update_or_append_scalar(lines, "last_reviewed", today)

def update_lesson_front_matter(lines: List[str], destination: Path) -> None:
    today = datetime.now().strftime("%Y%m%d")
    assign_knowledge_id(lines, destination)
    update_or_append_scalar(lines, "type", "lesson")
    update_or_append_scalar(lines, "status", "active")
    update_or_append_scalar(lines, "last_reviewed", today)

def update_reference_front_matter(lines: List[str], destination: Path) -> None:
    today = datetime.now().strftime("%Y%m%d")
    assign_knowledge_id(lines, destination)
    update_or_append_scalar(lines, "type", "reference")
    update_or_append_scalar(lines, "status", "active")
    update_or_append_scalar(lines, "last_reviewed", today)

def update_decision_front_matter(lines: List[str], destination: Path) -> None:
    today = datetime.now().strftime("%Y%m%d")
    assign_knowledge_id(lines, destination)
    update_or_append_scalar(lines, "type", "decision")
    update_or_append_scalar(lines, "status", "accepted")
    update_or_append_scalar(lines, "last_reviewed", today)

def render_document(front_lines: Optional[List[str]], body: str) -> str:
    from lib.front_matter import render_with_front_matter

    return render_with_front_matter(front_lines, body)

def title_from_document(front_lines: List[str], body: str, destination: Path) -> str:
    title = extract_scalar(front_lines, "title")
    if title:
        return title
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return destination.stem

def existing_markdown_entries(root: Path) -> List[Path]:
    if not root.exists():
        return []
    results = []
    for path in root.rglob("*.md"):
        if path.name == "README.md":
            continue
        # 排除 inbox 草稿：晋升判重只看正式条目，不应把待晋升的草稿自身算作重复
        if "inbox" in path.parts:
            continue
        results.append(path)
    return results

def read_title(path: Path) -> str:
    front_lines, body = split_front_matter(path.read_text(encoding="utf-8-sig"))
    if front_lines is None:
        front_lines = []
    return title_from_document(front_lines, body, path)

def find_duplicate_destination(destination_root: Path, destination_name: str, title: str, project_id: Optional[str] = None) -> Optional[Path]:
    for path in existing_markdown_entries(destination_root):
        if path.name == destination_name:
            return path
        if project_id is not None:
            from lib.front_matter import parse_front_matter
            metadata, _ = parse_front_matter(path.read_text(encoding="utf-8-sig"))
            if str(metadata.get("project_id", "")) != project_id:
                continue
        if read_title(path).strip().lower() == title.strip().lower():
            return path
    return None

def extract_tags(front_lines: List[str]) -> List[str]:
    """所有模块使用相同的 YAML 列表解析逻辑。"""
    from lib.front_matter import as_str_list, parse_front_matter

    metadata, _body = parse_front_matter("---\n{0}\n---\n".format("\n".join(front_lines)))
    return as_str_list(metadata.get("tags"))


def resolve_destination(destination_root: Path, name: str) -> Path:
    """拒绝绝对路径、父目录跳转和符号链接导致的晋升目录逃逸。"""
    normalized = name.replace("\\", "/")
    relative = Path(normalized)
    if not normalized or relative.is_absolute() or PureWindowsPath(name).is_absolute() or PureWindowsPath(name).drive or ".." in relative.parts:
        raise PromoteError("晋升名称必须是目标目录内的相对路径: {0}".format(name))
    if normalized in (".", "./"):
        raise PromoteError("晋升名称必须指向 Markdown 文件")
    if not normalized.endswith(".md"):
        relative = Path(normalized + ".md")
    root = destination_root.resolve()
    destination = (root / relative).resolve()
    try:
        root.relative_to(content_root().resolve())
        destination.relative_to(root)
    except ValueError as exc:
        raise PromoteError("晋升目标超出所选类型目录: {0}".format(name)) from exc
    return destination

def find_associate_duplicate(
    draft_tags: List[str],
    *,
    min_shared: int = 2,
    ratio_threshold: float = 0.5,
    project_id: Optional[str] = None,
) -> List[Tuple[str, List[str]]]:
    """用标签联想查重：若已有条目与草稿共享标签达到阈值，视为雷同候选。

    返回 [(entry_path, shared_tags), ...]；空列表表示无雷同。
    阈值：共享标签数 >= min_shared，或 >= 草稿标签数的 ratio_threshold。
    """
    if not draft_tags:
        return []
    try:
        from knowledge.graph import GraphError, KnowledgeGraphIndex

        space = PROMOTION_SPACE.get()
        index = KnowledgeGraphIndex(space=space) if space is not None else KnowledgeGraphIndex()
        hits, _meta = index.associate(
            seed_tags=draft_tags,
            hop=0,
            include_entry_related=False,
            limit=None,
        )
    except Exception:
        # 图未构建或依赖缺失时跳过查重（不阻断晋升）
        return []
    draft_set = set(draft_tags)
    duplicates: List[Tuple[str, List[str]]] = []
    for hit in hits:
        if "inbox" in Path(hit.entry.path).parts:
            continue
        if project_id is not None and space is not None:
            from lib.front_matter import parse_front_matter
            metadata, _ = parse_front_matter((space.root / hit.entry.path).read_text(encoding="utf-8-sig"))
            if str(metadata.get("project_id", "")) != project_id:
                continue
        shared = draft_set & set(hit.entry.tags)
        if not shared:
            continue
        if len(shared) >= min_shared or len(shared) >= len(draft_set) * ratio_threshold:
            duplicates.append((hit.entry.path, sorted(shared)))
    return duplicates

def ensure_current_entries_section(readme_text: str) -> str:
    if "## 当前条目" in readme_text:
        return readme_text
    suffix = "\n## 当前条目\n\n"
    if not readme_text.endswith("\n"):
        readme_text += "\n"
    return readme_text + suffix

def update_readme_index(kind: str, destination_name: str) -> None:
    readme_path = readme_paths()[kind]
    if not readme_path.exists():
        return
    text = ensure_current_entries_section(readme_path.read_text(encoding="utf-8-sig"))
    marker = "## 当前条目"
    head, tail = text.split(marker, 1)
    lines = tail.splitlines()
    bullet_lines = [line for line in lines[1:] if line.strip().startswith("- ")]
    # 移除原有项目符号和外围反引号，避免每次晋升重复添加。
    raw_items = set()
    for line in bullet_lines:
        item = line.strip()[2:].strip()
        if item.startswith("`") and item.endswith("`") and len(item) >= 2:
            item = item[1:-1]
        raw_items.add(item)
    raw_items.add(destination_name)
    bullet_items = sorted(raw_items)
    rebuilt = [marker, ""]
    rebuilt.extend("- `{0}`".format(item) for item in bullet_items)
    # Ensure a blank line separates the existing head from the marker.
    write_document(readme_path, "{0}\n\n{1}\n".format(head.rstrip(), "\n".join(rebuilt)))

def resolve_entries(entries: List[str], promote_all: bool) -> List[Path]:
    resolved: List[Path] = []
    if promote_all:
        if lessons_inbox().exists():
            resolved.extend(sorted(path for path in lessons_inbox().glob("*.md") if path.name != "README.md"))
        return resolved
    for entry in entries:
        resolved.append(resolve_entry(entry))
    return resolved

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Promote a lesson inbox draft into a lesson, reference, rule, template, or decision.")
    parser.add_argument("--entry", action="append", default=[], help="Inbox entry filename or path. Can be repeated.")
    parser.add_argument("--role", default=None, help="将角色草稿晋升到同一角色的 notes。")
    parser.add_argument(
        "--to",
        required=True,
        choices=["lesson", "reference", "rule", "template", "decision"],
        help="Promotion destination type.",
    )
    parser.add_argument("--name", default=None, help="Optional destination filename.")
    parser.add_argument("--dry-run", action="store_true", help="Preview the promotion without writing files.")
    parser.add_argument("--all", action="store_true", help="Promote every inbox markdown entry.")
    parser.add_argument(
        "--allow-duplicate",
        action="store_true",
        help="Allow promotion even if the destination already has the same title or filename.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="标记为自动/批处理晋升。--to rule 默认走 promote.auto_to_rule（deny）；"
        "配合 --standing 走 promote.auto_to_rule_on_standing（allow）；"
        "--to reference 走 promote.auto_to_reference（默认 allow，仅限客观知识且联想查重无雷同）；"
        "--to lesson 走 promote.auto_to_lesson。",
    )
    parser.add_argument(
        "--standing",
        action="store_true",
        help="标记为用户显式站立偏好（「以后一直这样」「写成规则」或 remember --as rule）。"
        "仅与 --auto --to rule 联用，门禁为 promote.auto_to_rule_on_standing。",
    )
    parser.add_argument(
        "--objective",
        action="store_true",
        help="标记草稿为「纯客观知识/信息」（LLM 判断）。配合 --auto --to reference 使用，"
        "会在晋升后写入 front matter objective: true 以留痕。联想查重有雷同时不晋升。",
    )
    parser.add_argument("--yes", action="store_true", help="本次强制 allow（覆盖 behavior ask）")
    parser.add_argument("--no", action="store_true", help="本次强制 deny")
    parser.add_argument("--json", action="store_true", help="Emit JSON for Agent consumption.")
    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    selected = None
    if args.role:
        from knowledge.spaces import role_space
        selected = role_space(args.role)
    token = PROMOTION_SPACE.set(selected)
    try:
        if selected is not None and not args.dry_run:
            from backends.role_memory import role_write_lock
            with role_write_lock(selected):
                return run_promotion(args)
        return run_promotion(args)
    finally:
        PROMOTION_SPACE.reset(token)


def run_promotion(args: argparse.Namespace) -> int:
    """在本次绑定的空间内执行校验、晋升和结果输出。"""

    if not args.all and not args.entry:
        raise PromoteError("`promote` requires --entry or --all.")
    if args.name and (args.all or len(args.entry) != 1):
        raise PromoteError("--name only works when promoting a single entry.")
    if args.yes and args.no:
        raise PromoteError("--yes 与 --no 不能同时使用")
    if args.objective and not (args.auto and args.to == "reference"):
        raise PromoteError("--objective 仅在 --auto --to reference 时有意义。")
    if args.standing and not (args.auto and args.to == "rule"):
        raise PromoteError("--standing 仅在 --auto --to rule 时有意义。")
    if args.auto and args.to == "reference" and not args.objective:
        raise PromoteError("自动晋升 reference 必须显式提供 --objective。")

    force = None
    if args.yes:
        force = "allow"
    elif args.no:
        force = "deny"
    # --dry-run 仍走既有「预览不写」逻辑，不占用 behavior 的 dry_run 模式

    from policies.behavior import authorize

    if args.to == "rule" and args.auto and args.standing:
        op = "promote.auto_to_rule_on_standing"
        summary = "站立偏好自动晋升 inbox → rule（用户已明示「以后一直这样/写成规则」）"
    elif args.to == "rule" and args.auto:
        op = "promote.auto_to_rule"
        summary = "自动晋升 inbox → rule（受 promote.auto_to_rule 约束）"
    elif args.to == "reference" and args.auto:
        op = "promote.auto_to_reference"
        summary = "自动晋升 inbox → reference（客观知识 + 联想查重无雷同，受 promote.auto_to_reference 约束）"
    elif args.to == "lesson" and args.auto:
        op = "promote.auto_to_lesson"
        summary = "自动晋升 inbox → lesson（受 promote.auto_to_lesson 约束）"
    else:
        op = "promote.to_{0}".format(args.to)
        summary = "晋升 inbox → {0}".format(args.to)

    decision = authorize(
        op,
        summary,
        force=force,
    )
    if not decision.get("allowed"):
        if args.json:
            json.dump({"status": "denied", "behavior": decision}, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            print("promote_status : denied")
            print("behavior_op    : {0}".format(op))
            print("behavior_reason: {0}".format(decision.get("reason")))
            if decision.get("hint"):
                print("behavior_hint  : {0}".format(decision["hint"]))
        return 2

    sources = resolve_entries(args.entry, args.all)
    if not sources:
        raise PromoteError("No inbox entries matched the promote request.")

    results: List[Dict[str, str]] = []
    for source in sources:
        source_text = source.read_text(encoding="utf-8-sig")
        front_lines, body = split_front_matter(source_text)
        selected = PROMOTION_SPACE.get()
        project_id = None
        if selected is not None:
            from lib.front_matter import parse_front_matter
            metadata, _ = parse_front_matter(source_text)
            if metadata.get("owner_role") not in (None, "", selected.owner_role) or metadata.get("space_id") not in (None, "", selected.space_id):
                raise PromoteError("草稿所有者不属于当前角色。")
            project_id = str(metadata.get("project_id", ""))

        destination_root = destination_roots()[args.to]
        destination_name = args.name or source.name
        destination = resolve_destination(destination_root, destination_name)
        destination_name = destination.relative_to(destination_root.resolve()).as_posix()

        if source.resolve() == destination.resolve():
            raise PromoteError("Source and destination are identical: {0}".format(source))

        updated_front = list(front_lines) if front_lines is not None else []
        if front_lines is None:
            updated_front = ['title: "{0}"'.format(destination.stem), 'status: "draft"']

        title = title_from_document(updated_front, body, destination)
        if selected is not None:
            update_or_append_scalar(updated_front, "owner_role", selected.owner_role)
            update_or_append_scalar(updated_front, "space_id", selected.space_id)
        duplicate = find_duplicate_destination(destination_root, destination_name, title, project_id=project_id) if selected is not None else find_duplicate_destination(destination_root, destination_name, title)
        if duplicate and not args.allow_duplicate:
            item = {
                "source": str(source),
                "target": str(duplicate),
                "type": args.to,
                "status": "duplicate",
                "write": "skipped",
            }
            results.append(item)
            if not args.json:
                print("promote_source : {0}".format(source))
                print("promote_target : {0}".format(duplicate))
                print("promote_type   : {0}".format(args.to))
                print("promote_status : duplicate")
                print("promote_write  : skipped")
            continue

        # 自动路径：标签联想查重——有雷同则跳过（客观知识才允许自动晋升）
        if args.auto:
            draft_tags = extract_tags(updated_front)
            assoc_dupes = find_associate_duplicate(draft_tags, project_id=project_id) if selected is not None else find_associate_duplicate(draft_tags)
            if assoc_dupes and not args.allow_duplicate:
                dupe_paths = "; ".join(
                    "{0} (shared: {1})".format(p, ",".join(s)) for p, s in assoc_dupes
                )
                item = {
                    "source": str(source),
                    "type": args.to,
                    "status": "duplicate_candidate",
                    "write": "skipped",
                    "reason": "associate_duplicate",
                    "similar": dupe_paths,
                }
                results.append(item)
                if not args.json:
                    print("promote_source : {0}".format(source))
                    print("promote_type   : {0}".format(args.to))
                    print("promote_status : duplicate_candidate")
                    print("promote_reason: associate_duplicate")
                    print("promote_similar: {0}".format(dupe_paths))
                    print("promote_write  : skipped")
                continue

        update_or_append_scalar(updated_front, "status", "active")
        update_or_append_scalar(updated_front, "promoted_to", args.to)
        if args.objective:
            update_or_append_scalar(updated_front, "objective", "true")
        if args.to == "rule":
            update_rule_front_matter(updated_front, destination)
        elif args.to == "template":
            update_template_front_matter(updated_front, destination)
        elif args.to == "decision":
            update_decision_front_matter(updated_front, destination)
        elif args.to == "reference":
            update_reference_front_matter(updated_front, destination)
        else:
            update_lesson_front_matter(updated_front, destination)

        rendered = render_document(updated_front, body)
        write_status = "skipped (dry-run)" if args.dry_run else "ok"
        if not args.dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            write_document(destination, rendered)
            source.unlink()
            update_readme_index(args.to, destination_name)

        item = {
            "source": str(source),
            "target": str(destination),
            "type": args.to,
            "status": "active",
            "write": write_status,
            "title": title,
        }
        results.append(item)
        if not args.json:
            print("promote_source : {0}".format(source))
            print("promote_target : {0}".format(destination))
            print("promote_type   : {0}".format(args.to))
            print("promote_status : active")
            print("promote_write  : {0}".format(write_status))

    selected = PROMOTION_SPACE.get()
    refresh = None
    if selected is not None and not args.dry_run and any(item.get("write") == "ok" for item in results):
        from backends.role_memory import refresh_role_memory
        refresh = refresh_role_memory(selected, acquire_lock=False)
    if args.json:
        json.dump({"results": results, "count": len(results), "space_id": selected.space_id if selected is not None else "shared", "memory_refresh": refresh}, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
