#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识条目 id 生成：创建时间 + 目录首字母 + 标题词首 + 4 位随机串。"""

from __future__ import annotations

import argparse
import random
import re
import string
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple


from lib.repo_paths import CORE_ROOT, REPO_ROOT

# knowledge 相对路径以 CORE_ROOT 为根（保持 id 目录段稳定）
# git 操作使用 REPO_ROOT（仓库根）
RAND_ALPHABET = string.ascii_lowercase + string.digits
DIR_INITIALS_LEN = 6
TITLE_INITIALS_LEN = 8
PAD_CHAR = "$"
# 英文/数字词；中文段单独匹配后跳过（无 pypinyin 时不做拼音首字母）
TITLE_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# time14-dir6-title8-rand4
ID_RE = re.compile(
    r"^(\d{{14}})-([A-Za-z0-9$]{{{0}}})-([A-Za-z0-9$]{{{1}}})-([a-z0-9]{{4}})$".format(
        DIR_INITIALS_LEN, TITLE_INITIALS_LEN
    )
)


def fit_fixed_width(text: str, width: int, pad: str = PAD_CHAR) -> str:
    """超长截断，不足右侧补 pad。"""
    raw = text or ""
    if len(raw) >= width:
        return raw[:width]
    return raw + (pad * (width - len(raw)))


def dir_initials(rel_path: Path) -> str:
    """相对 CORE_ROOT 路径中，各层目录名的首字符（不含文件名）；定长 6，不足补 $。"""
    parts = list(rel_path.parts[:-1])
    chars: List[str] = []
    for part in parts:
        if not part or part in (".", ".."):
            continue
        first = part[0]
        if "A" <= first <= "Z" or "a" <= first <= "z":
            chars.append(first.lower())
        elif "0" <= first <= "9":
            chars.append(first)
    return fit_fixed_width("".join(chars), DIR_INITIALS_LEN)


def title_initials(title: str) -> str:
    """标题各词首字符：仅 ASCII；中文跳过；定长 8，不足补 $。"""
    text = (title or "").strip().strip('"').strip("'")
    chars: List[str] = []
    if text:
        for token in TITLE_TOKEN_RE.findall(text):
            if not token:
                continue
            if CJK_RE.search(token) and not re.search(r"[A-Za-z0-9]", token):
                continue
            ch = token[0]
            if "A" <= ch <= "Z" or "a" <= ch <= "z":
                chars.append(ch.lower())
            elif "0" <= ch <= "9":
                chars.append(ch)
    return fit_fixed_width("".join(chars), TITLE_INITIALS_LEN)


def format_created_stamp(when: datetime) -> str:
    return when.strftime("%Y%m%d%H%M%S")


def random_suffix(length: int = 4, rng: Optional[random.Random] = None) -> str:
    source = rng or random.SystemRandom()
    return "".join(source.choice(RAND_ALPHABET) for _ in range(length))


def compose_id(
    created_stamp: str,
    dir_part: str,
    title_part: str,
    rand_part: str,
) -> str:
    """{yyyymmddhhmmss}-{dir6}-{title8}-{rand4}"""
    return "{0}-{1}-{2}-{3}".format(created_stamp, dir_part, title_part, rand_part)


def parse_id(entry_id: str) -> Optional[Tuple[str, str, str, str]]:
    """解析 id → (stamp, dir, title, rand)。"""
    match = ID_RE.match((entry_id or "").strip())
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3), match.group(4)


def created_datetime_for_file(path: Path, git_root: Path = REPO_ROOT) -> datetime:
    """优先用 git 首次加入时间，否则用文件 mtime。"""
    try:
        rel = path.resolve().relative_to(git_root.resolve()).as_posix()
        proc = subprocess.run(
            ["git", "log", "--diff-filter=A", "--follow", "--format=%ct", "-1", "--", rel],
            cwd=str(git_root),
            capture_output=True,
            text=True,
            check=False,
        )
        line = (proc.stdout or "").strip().splitlines()
        if line and line[0].isdigit():
            return datetime.fromtimestamp(int(line[0]))
    except (OSError, ValueError):
        pass
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return datetime.now()


def generate_knowledge_id(
    path: Path,
    title: str,
    *,
    repo_root: Path = CORE_ROOT,
    created: Optional[datetime] = None,
    rng: Optional[random.Random] = None,
    existing_ids: Optional[Set[str]] = None,
) -> str:
    """
    生成条目 id：
    {yyyymmddhhmmss}-{目录首字母定长6}-{标题词首定长8}-{4位随机}
    """
    rel = path.resolve().relative_to(repo_root.resolve())
    dir_part = dir_initials(rel)
    stamp = format_created_stamp(created or created_datetime_for_file(path, REPO_ROOT))
    title_part = title_initials(title)
    used = existing_ids if existing_ids is not None else set()
    for _ in range(64):
        rand_part = random_suffix(4, rng=rng)
        entry_id = compose_id(stamp, dir_part, title_part, rand_part)
        if entry_id not in used:
            return entry_id
    raise RuntimeError("无法生成不冲突的 knowledge id: {0}".format(path))


def is_placeholder_id(entry_id: str) -> bool:
    text = (entry_id or "").strip()
    if not text:
        return True
    if "<" in text or ">" in text:
        return True
    if "slug" in text.lower() and text.startswith("rule-"):
        return True
    return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成或预览 knowledge 条目 id。")
    parser.add_argument("--path", required=True, help="相对 CORE_ROOT 或绝对路径的 Markdown 文件")
    parser.add_argument("--title", required=True, help="条目 title")
    parser.add_argument("--created", default=None, help="可选，yyyymmddhhmmss 或 ISO 时间")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    path = Path(args.path)
    if not path.is_absolute():
        path = (CORE_ROOT / path).resolve()
    created = None
    if args.created:
        raw = args.created.strip()
        if re.fullmatch(r"\d{14}", raw):
            created = datetime.strptime(raw, "%Y%m%d%H%M%S")
        else:
            created = datetime.fromisoformat(raw)
    print(generate_knowledge_id(path, args.title, created=created))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
