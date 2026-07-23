#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外部 URL 摄取：拉取页面 → 写入 ``knowledge/sources/inbox`` Markdown + 资产。

由 ``ygg ingest <url>`` 调用。产出是原始材料，需再经 distill / promote。
"""

from pathlib import Path
import sys

# cmds/<domain>/<script>.py → scripts/
SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
SCRIPT_DIR = SCRIPTS_ROOT

import argparse
import html
import json
import re
from datetime import datetime
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from lib.repo_paths import CORE_ROOT

CONTENT_ROOT = CORE_ROOT
INBOX_ROOT = CONTENT_ROOT / "knowledge" / "sources" / "inbox"
ASSET_ROOT = INBOX_ROOT / "assets"

class IngestError(RuntimeError):
    pass

def fetch_url(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://mp.weixin.qq.com/",
    }
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise IngestError("HTTP {0} fetching {1}".format(exc.code, url)) from exc
    except URLError as exc:
        raise IngestError("Fetch failed: {0}".format(exc.reason)) from exc

def first_group(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.S)
    return html.unescape(match.group(1).strip()) if match else ""

def extract_wechat(url: str, raw_html: str) -> dict:
    title = first_group(r'id="activity-name"[^>]*>(.*?)</', raw_html)
    title = re.sub(r"<[^>]+>", "", title).strip() if title else title
    if not title:
        title = first_group(r"var\s+msg_title\s*=\s*'(.*?)'", raw_html)

    author = first_group(r'id="js_name"[^>]*>(.*?)</', raw_html)
    author = re.sub(r"<[^>]+>", "", author).strip() if author else author
    publish_time = first_group(r'id="publish_time"[^>]*>(.*?)</', raw_html)

    content_match = re.search(
        r'id="js_content"[^>]*>(.*?)<section[^>]*class="wx_profile_card_inner"',
        raw_html,
        re.S,
    )
    if not content_match:
        content_match = re.search(
            r'id="js_content"[^>]*>(.*?)</div>\s*</div>\s*<script',
            raw_html,
            re.S,
        )
    content_html = content_match.group(1) if content_match else ""
    if not content_html:
        raise IngestError("Failed to extract article body from WeChat page.")

    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", content_html, flags=re.S)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>|</section>|</li>|</h\d>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = text.strip()

    images = []
    for match in re.finditer(r'<img[^>]+(?:data-src|src)="([^"]+)"[^>]*>', content_html, re.S):
        src = match.group(1)
        if src.startswith("//"):
            src = "https:" + src
        src = src.replace("&amp;", "&")
        if src not in images:
            images.append(src)

    return {
        "url": url,
        "title": title,
        "author": author,
        "publish_time": publish_time,
        "text": text,
        "images": images,
        "content_html": content_html,
    }

def detect_source_type(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "mp.weixin.qq.com" in host:
        return "wechat"
    return "generic"

def extract_content(url: str, raw_html: str) -> dict:
    source_type = detect_source_type(url)
    if source_type == "wechat":
        data = extract_wechat(url, raw_html)
        data["source_type"] = source_type
        return data
    raise IngestError("Unsupported source type for URL: {0}".format(url))

def write_file(path: Path, content: str, encoding: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)

def render_inbox_markdown(entry_id: str, extracted: dict, text_asset_path: Path, raw_html_path: Optional[Path]) -> str:
    image_urls = extracted["images"] or []
    if image_urls:
        image_yaml = "\n".join("  - {0}".format(url) for url in image_urls)
    else:
        image_yaml = "  []"

    asset_path = text_asset_path.relative_to(CONTENT_ROOT).as_posix()
    raw_html_rel = ""
    if raw_html_path is not None:
        raw_html_rel = raw_html_path.relative_to(CONTENT_ROOT).as_posix()

    title = (extracted["title"] or "Untitled Source").replace('"', '\\"')
    url = extracted["url"].replace('"', '\\"')
    author = (extracted["author"] or "unknown").replace('"', '\\"')
    publish_time = extracted["publish_time"] or "unknown"

    raw_html_line = ""
    if raw_html_rel:
        raw_html_line = 'raw_html_path: {0}\n'.format(raw_html_rel)

    return """---
id: {entry_id}
title: "{title}"
type: source
status: draft
confidence: medium
source: "{url}"
source_url: "{url}"
author: "{author}"
published_at: "{publish_time}"
asset_path: {asset_path}
{raw_html_line}last_reviewed: {today}
owners:
  - team
tags:
  - inbox
  - ingest
  - {source_type}
scope: "Archived source for later distillation or review"
image_urls:
{image_yaml}
---

# {title}

## 抽取正文

{body_text}
""".format(
        entry_id=entry_id,
        title=title,
        url=url,
        author=author,
        publish_time=publish_time,
        asset_path=asset_path,
        raw_html_line=raw_html_line,
        today=datetime.now().strftime("%Y-%m-%d"),
        image_yaml=image_yaml,
        source_type=extracted["source_type"],
        body_text=extracted["text"],
    )

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "source"

def ingest_url(url: str, slug: str, save_raw_html: bool) -> dict:
    raw_html = fetch_url(url)
    extracted = extract_content(url, raw_html)

    base_name = "{0}-{1}".format(datetime.now().strftime("%Y-%m-%d"), slug)
    text_asset_path = ASSET_ROOT / (base_name + ".txt")
    raw_html_path = ASSET_ROOT / (base_name + ".html") if save_raw_html else None
    md_path = INBOX_ROOT / (base_name + ".md")
    from knowledge.knowledge_id import generate_knowledge_id

    entry_id = generate_knowledge_id(md_path, extracted.get("title") or slug)

    write_file(text_asset_path, extracted["text"] + "\n", "utf-8-sig")
    if raw_html_path is not None:
        write_file(raw_html_path, raw_html, "utf-8")

    markdown = render_inbox_markdown(entry_id, extracted, text_asset_path, raw_html_path)
    write_file(md_path, markdown, "utf-8-sig")

    return {
        "markdown_path": str(md_path),
        "text_asset_path": str(text_asset_path),
        "raw_html_path": str(raw_html_path) if raw_html_path is not None else "",
        "title": extracted["title"],
        "image_count": len(extracted["images"]),
    }

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal source ingest helper for YggForge.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--slug", default=None)
    parser.add_argument("--save-raw-html", action="store_true")
    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        slug = args.slug or slugify(args.url)
        result = ingest_url(args.url, slug, args.save_raw_html)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except IngestError as exc:
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
