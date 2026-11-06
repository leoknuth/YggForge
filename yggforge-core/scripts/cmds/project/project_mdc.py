#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 knowledge/rules 生成 Cursor alwaysApply 薄投影（.mdc）。

约定（真源仍为 .md，不改后缀）：
- front matter ``always_apply: true``
- 可选 ``projection`` 列出 ``profiles/cursor/rules/**/*.mdc`` 目标
- ``projection_mode: sync|manual``（缺省见下）

缺省目标：与规则相对 ``knowledge/rules/`` 的同名路径，落到
``profiles/cursor/rules/<rel>.mdc``。

- sync：用真源正文再生 .mdc（加 Cursor front matter + 真源指针）
- manual：不覆盖已有手写薄投影，只检查目标存在

用法：
  python project_mdc.py --check
  python project_mdc.py --write
  ygg project mdc
  ygg project mdc --check
"""

from __future__ import print_function

from pathlib import Path, PureWindowsPath
import sys
import re

# cmds/<domain>/<script>.py → scripts/
SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
SCRIPT_DIR = SCRIPTS_ROOT

import argparse
from typing import Any, Dict, List, Optional, Tuple

from lib.front_matter import as_str_list, parse_front_matter  # noqa: E402
from lib.repo_paths import CORE_ROOT, REPO_ROOT  # noqa: E402

class ProjectError(RuntimeError):
    pass

def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("true", "1", "yes")

def _rules_root() -> Path:
    return CORE_ROOT / "knowledge" / "rules"

def _rel_to_core(path: Path) -> str:
    try:
        return path.resolve().relative_to(CORE_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()

def default_mdc_target(rule_path: Path) -> Path:
    rel = rule_path.resolve().relative_to(_rules_root().resolve())
    return CORE_ROOT / "profiles" / "cursor" / "rules" / rel.with_suffix(".mdc")

def _safe_target(target: Path) -> Path:
    """投影只能落入 Cursor 规则根；resolve 后再次阻止 symlink 越界。"""
    root = CORE_ROOT.resolve() / "profiles" / "cursor" / "rules"
    try:
        target.resolve().relative_to(root)
    except ValueError:
        raise ProjectError("MDC 投影目标越界: {0}".format(target))
    return target

def resolve_mdc_targets(rule_path: Path, metadata: Dict[str, Any]) -> List[Path]:
    targets: List[Path] = []
    for item in as_str_list(metadata.get("projection")):
        text = item.replace("\\", "/").strip()
        if not text.endswith(".mdc"):
            continue
        if text.startswith("yggforge-core/"):
            text = text[len("yggforge-core/") :]
        # 真源 projection 只接受 core 相对、且没有父目录穿越的路径。
        if Path(text).is_absolute() or PureWindowsPath(text).drive or ".." in Path(text).parts:
            raise ProjectError("MDC projection 必须为安全的 core 相对路径: {0}".format(item))
        cand = CORE_ROOT / text
        targets.append(_safe_target(cand))
    if not targets:
        targets.append(_safe_target(default_mdc_target(rule_path)))
    return targets

def resolve_mode(rule_path: Path, metadata: Dict[str, Any], targets: List[Path]) -> str:
    explicit = str(metadata.get("projection_mode") or "").strip().lower()
    if explicit in ("sync", "manual"):
        return explicit
    # 同名默认同步；指向不同文件名的视为手写薄投影
    default = default_mdc_target(rule_path)
    for t in targets:
        if t.resolve() != default.resolve():
            return "manual"
    return "sync"

def extract_description(metadata: Dict[str, Any], body: str) -> str:
    title = str(metadata.get("title") or "").strip()
    if title:
        return title[:120]
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()[:120]
    return "YggForge projected rule"

def build_mdc_text(rule_path: Path, metadata: Dict[str, Any], body: str) -> str:
    description = extract_description(metadata, body).replace('"', '\\"')
    source_rel = _rel_to_core(rule_path)
    body_text = body.lstrip("\n")
    if not body_text.endswith("\n"):
        body_text += "\n"
    header = (
        "---\n"
        'description: "{0}"\n'
        "alwaysApply: true\n"
        "---\n"
        "\n"
        "<!-- ygg-project: sync | source: {1} -->\n"
        "\n"
    ).format(description, source_rel)
    return header + body_text

def iter_always_apply_rules() -> List[Tuple[Path, Dict[str, Any], str]]:
    root = _rules_root()
    if not root.exists():
        return []
    rows: List[Tuple[Path, Dict[str, Any], str]] = []
    for path in sorted(root.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8-sig")
        meta, body = parse_front_matter(text)
        if meta.get("type") != "rule" or meta.get("status") != "active":
            continue
        if not _truthy(meta.get("always_apply")):
            continue
        rows.append((path, meta, body))
    return rows

def project_one(
    rule_path: Path,
    metadata: Dict[str, Any],
    body: str,
    *,
    write: bool,
) -> List[str]:
    messages: List[str] = []
    targets = resolve_mdc_targets(rule_path, metadata)
    mode = resolve_mode(rule_path, metadata, targets)
    for target in targets:
        _safe_target(target)
        rel_t = _rel_to_core(target)
        rel_r = _rel_to_core(rule_path)
        if mode == "manual":
            if target.exists():
                messages.append("ok_manual   : {0} <- {1}".format(rel_t, rel_r))
            else:
                messages.append("missing     : {0} <- {1} (manual)".format(rel_t, rel_r))
            continue
        content = build_mdc_text(rule_path, metadata, body)
        if target.exists():
            old = target.read_text(encoding="utf-8-sig")
            # 手写文件若带 manual 标记则跳过覆盖
            if "ygg-project: manual" in old:
                messages.append("skip_manual : {0} (file marked manual)".format(rel_t))
                continue
            if old == content or old.replace("\r\n", "\n") == content:
                messages.append("unchanged   : {0}".format(rel_t))
                continue
        if write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8-sig")
            messages.append("wrote       : {0} <- {1}".format(rel_t, rel_r))
        else:
            messages.append("would_write : {0} <- {1}".format(rel_t, rel_r))
    return messages

def run(check_only: bool, write: bool) -> int:
    rows = iter_always_apply_rules()
    # 在任何写入前验证全部目标，避免处理到后半程才发现危险路径。
    expected = set()
    for rule_path, meta, _body in rows:
        expected.update(t.resolve() for t in resolve_mdc_targets(rule_path, meta))
    problems = 0
    for rule_path, meta, body in rows:
        for line in project_one(rule_path, meta, body, write=write and not check_only):
            print(line)
            if line.startswith("missing") or line.startswith("would_write"):
                problems += 1
    # 生成标记就是来源追踪记录；不撤销手写文件，只清理由本工具生成的孤立投影。
    projection_root = CORE_ROOT / "profiles" / "cursor" / "rules"
    if projection_root.exists():
        for target in sorted(projection_root.rglob("*.mdc")):
            _safe_target(target)
            old = target.read_text(encoding="utf-8-sig")
            if "ygg-project: manual" in old:
                continue
            generated = re.search(r"<!--\s*ygg-project:\s*sync\s*\|\s*source:\s*(.*?)\s*-->", old)
            if not generated or target.resolve() in expected:
                continue
            if write and not check_only:
                target.unlink()
                print("removed     : {0} (退役或来源/目标已变更)".format(_rel_to_core(target)))
            else:
                print("orphan      : {0} (退役或来源/目标已变更)".format(_rel_to_core(target)))
                problems += 1
    print("project_mdc  : rules={0}".format(len(rows)))
    if check_only and problems:
        return 1
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project knowledge rules to Cursor .mdc")
    parser.add_argument("--check", action="store_true", help="只检查，不写文件")
    parser.add_argument("--write", action="store_true", help="写入/更新 sync 模式的 .mdc")
    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.check and not args.write:
        args.write = True
    try:
        return run(check_only=args.check, write=args.write)
    except ProjectError as exc:
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
