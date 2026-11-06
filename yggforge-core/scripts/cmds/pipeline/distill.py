#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inbox → distilled 启发式提炼。

由 ``ygg distill`` 调用。写出 sources/distilled；不自动晋升到 rules。
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
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from lib.repo_paths import CORE_ROOT

CONTENT_ROOT = CORE_ROOT
INBOX_ROOT = CONTENT_ROOT / "knowledge" / "sources" / "inbox"
DISTILLED_ROOT = CONTENT_ROOT / "knowledge" / "sources" / "distilled"

class DistillError(RuntimeError):
    pass

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def split_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    """委托统一解析；标量字段转为 str，保持 distill 旧调用方语义。"""
    from lib.front_matter import parse_front_matter

    meta, body = parse_front_matter(text)
    data: Dict[str, str] = {}
    for key, value in meta.items():
        if isinstance(value, list):
            continue
        data[key] = str(value)
    return data, body

def extract_section(body: str, title: str) -> str:
    pattern = r"##\s+{0}\s*\n(.*?)(?=\n##\s+|\Z)".format(re.escape(title))
    match = re.search(pattern, body, re.S)
    return match.group(1).strip() if match else ""

def load_inbox_entry(path: Path) -> Dict[str, str]:
    text = read_text(path)
    frontmatter, body = split_frontmatter(text)

    title = frontmatter.get("title") or first_heading(body) or path.stem
    source = frontmatter.get("source", "")
    raw_text = extract_section(body, "抽取正文")
    if not raw_text:
        raise DistillError("Could not find '## 抽取正文' section in inbox entry: {0}".format(path))

    author = frontmatter.get("author", "") or ""
    if not author:
        original_section = extract_section(body, "原始来源")
        for line in original_section.splitlines():
            if line.strip().startswith("- 作者："):
                author = line.split("：", 1)[1].strip()
                break

    return {
        "title": title,
        "source": frontmatter.get("source_url") or source,
        "author": author,
        "raw_text": raw_text,
        "path": str(path),
    }

def first_heading(body: str) -> str:
    match = re.search(r"^#\s+(.+)$", body, re.M)
    return match.group(1).strip() if match else ""

def choose_input_path(value: Optional[str], latest: bool) -> Path:
    inbox_files = [
        path for path in INBOX_ROOT.glob("*.md")
        if path.name.lower() != "readme.md" and not path.name.endswith(".template.md")
    ]
    inbox_files.sort(key=lambda path: (path.stat().st_mtime_ns, path.name))
    if latest:
        if not inbox_files:
            raise DistillError("No inbox Markdown entries found.")
        return inbox_files[-1]

    if not value:
        raise DistillError("distill requires --input or --latest.")

    candidate = Path(value)
    if candidate.exists():
        return candidate.resolve()

    repo_relative = CONTENT_ROOT / value
    if repo_relative.exists():
        return repo_relative.resolve()

    name_match = INBOX_ROOT / value
    if name_match.exists():
        return name_match.resolve()

    matches = [item for item in inbox_files if value in item.name]
    if len(matches) == 1:
        return matches[0].resolve()
    if len(matches) > 1:
        raise DistillError("Multiple inbox entries matched '{0}'. Be more specific.".format(value))

    raise DistillError("Could not resolve inbox input: {0}".format(value))

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "distilled-source"

def infer_tags(title: str, raw_text: str) -> List[str]:
    lower = (title + "\n" + raw_text).lower()
    tags = []
    tag_rules = [
        ("linux", ["linux"]),
        ("performance", ["性能", "qps", "延迟", "吞吐", "tlb"]),
        ("memory", ["内存", "页表", "tlb", "hugepage", "页大小"]),
        ("hugepage", ["hugepage", "大页", "2mb"]),
        ("microservice", ["微服务"]),
    ]
    for tag, keywords in tag_rules:
        if any(keyword.lower() in lower for keyword in keywords):
            tags.append(tag)
    tags.append("distilled")
    seen = []
    for tag in tags:
        if tag not in seen:
            seen.append(tag)
    return seen

def sentence_candidates(raw_text: str) -> List[str]:
    raw_text = strip_code_like_blocks(raw_text)
    chunks = re.split(r"[。！？\n]+", raw_text)
    candidates = []
    for chunk in chunks:
        line = re.sub(r"\s+", " ", chunk).strip()
        if len(line) < 18:
            continue
        if len(line) > 160:
            continue
        if any(noise in line for noise in ["点赞", "关注该公众号", "微信扫一扫", "预览时标签不可点"]):
            continue
        if line.startswith("#include") or "return " in line or "printf(" in line:
            continue
        candidates.append(line)
    return candidates

def strip_code_like_blocks(raw_text: str) -> str:
    text = raw_text
    text = re.sub(r"#include[^\n]*(?:\n.*?){0,80}?return\s+0\s*;", " ", text, flags=re.S)
    text = re.sub(r"@PostMapping.*?return result;", " ", text, flags=re.S)
    return text

def choose_fact_lines(candidates: List[str], limit: int) -> List[str]:
    ranked = []
    for index, line in enumerate(candidates):
        score = 0
        if "不是" in line or "并非" in line:
            score += 3
        if "导致" in line or "出现" in line:
            score += 2
        if "优势" in line or "本质" in line:
            score += 2
        if "场景" in line:
            score += 2
        if "性能" in line:
            score += 1
        if "HugePage" in line or "大页" in line or "2MB" in line or "4KB" in line:
            score += 2
        if "微服务" in line or "碎片化" in line or "TLB" in line:
            score += 2
        if index < 12:
            score += 2
        ranked.append((score, -index, line))
    ranked.sort(key=lambda item: (-item[0], -item[1]))
    results = []
    for _, _, line in ranked:
        if line not in results:
            results.append(line)
        if len(results) >= limit:
            break
    return results

def infer_reusable_conclusions(raw_text: str) -> List[str]:
    conclusions = []
    if any(token in raw_text for token in ["大页", "HugePage", "2MB"]):
        conclusions.append("不要把 HugePage 当成默认全局优化项直接启用。")
        conclusions.append("做大页优化前，应先确认 workload 是否属于大内存、连续访问、长期驻留场景。")
        conclusions.append("任何页大小优化都应通过可回滚、可观测的实验验证。")
    return conclusions

def render_distilled(entry: Dict[str, str], slug: str, entry_id: str) -> str:
    title = entry["title"]
    source = entry["source"]
    author = entry["author"] or "unknown"
    raw_text = entry["raw_text"]
    tags = infer_tags(title, raw_text)
    candidates = sentence_candidates(raw_text)
    facts = choose_fact_lines(candidates, 5)
    conclusions = infer_reusable_conclusions(raw_text)

    def yaml_list(items: List[str], empty: str = "待人工补充。") -> str:
        if not items:
            return "  - {0}".format(empty)
        lines = []
        for item in items:
            text = json.dumps(item.strip(), ensure_ascii=False)
            lines.append("  - {0}".format(text))
        return "\n".join(lines)

    fact_items = [line + "。" for line in facts] if facts else []
    tag_lines = "\n".join("  - " + tag for tag in tags) if tags else "  []"
    inbox_rel = Path(entry["path"]).resolve().relative_to(CONTENT_ROOT.resolve()).as_posix()

    return """---
id: {entry_id}
title: {title_yaml}
type: distilled-source
status: draft
confidence: medium
source: {source_yaml}
source_url: {source_yaml}
author: {author_yaml}
inbox_path: {inbox_rel_yaml}
last_reviewed: {today}
owners:
  - team
tags:
{tag_lines}
scope: "Distilled from inbox source"
facts:
{fact_yaml}
inferences:
  - 这是自动生成的第一版 distilled 草稿，推论部分应由人工进一步确认。
practices:
{practice_yaml}
risks:
  - 本条目由自动 distill 生成，仍需人工校对。
  - 若原始来源带有强叙事性、营销性或未验证数据，不应直接升级为规则。
promote_to: knowledge/lessons/
promote_rationale: ""
---

# {title}

（结构化字段已在 YAML；此处仅保留标题。人工校对后可补充说明。）
""".format(
        entry_id=entry_id,
        title=title,
        title_yaml=json.dumps(title, ensure_ascii=False),
        source_yaml=json.dumps(source, ensure_ascii=False),
        author_yaml=json.dumps(author, ensure_ascii=False),
        tag_lines=tag_lines,
        inbox_rel=inbox_rel,
        inbox_rel_yaml=json.dumps(inbox_rel, ensure_ascii=False),
        today=datetime.now().strftime("%Y-%m-%d"),
        fact_yaml=yaml_list(fact_items),
        practice_yaml=yaml_list(conclusions),
    )

def distill(input_path: Path, slug: Optional[str]) -> Dict[str, str]:
    from knowledge.knowledge_id import generate_knowledge_id

    entry = load_inbox_entry(input_path)
    derived_slug = slugify(slug or re.sub(r"^\d{4}-\d{2}-\d{2}-", "", Path(entry["path"]).stem))
    DISTILLED_ROOT.mkdir(parents=True, exist_ok=True)
    output_path = DISTILLED_ROOT / ("{0}-{1}.md".format(datetime.now().strftime("%Y-%m-%d"), derived_slug))
    if output_path.exists():
        output_path = output_path.with_name(output_path.stem + "-" + datetime.now().strftime("%H%M%S%f") + ".md")
    entry_id = generate_knowledge_id(output_path, entry["title"])
    content = render_distilled(entry, derived_slug, entry_id=entry_id)
    output_path.write_text(content, encoding="utf-8-sig")
    return {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "title": entry["title"],
    }

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a first-pass distilled draft from an inbox source.")
    parser.add_argument("--input", default=None)
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--slug", default=None)
    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        input_path = choose_input_path(args.input, args.latest)
        result = distill(input_path, args.slug)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except DistillError as exc:
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
