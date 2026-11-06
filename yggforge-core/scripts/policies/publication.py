# -*- coding: utf-8 -*-
"""发布边界：无隐私标签具备候选资格；记忆逐项批准，隐私条目与附件不可发布。

这里只返回固定理由代码，不输出正文或秘密值；不执行复制、Git 或网络操作。
仅依赖标准库，框架文件和知识条目使用相同的检查。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Iterable, List, Optional, Set, Tuple
from urllib.parse import unquote, urlsplit


EXCLUDED_DIRECTORIES = {".git", "yggforge-runtime", "yggforge-generated", "runtime", "generated"}
MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdc"}
ASSET_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".avif",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".mp3", ".wav", ".ogg", ".mp4", ".mov", ".webm",
    ".csv", ".tsv", ".json", ".jsonl", ".yaml", ".yml", ".zip", ".gz", ".tar",
}
MAX_METADATA_BYTES = 16 * 1024 * 1024
_SENSITIVE = [
    re.compile(rb"(?m)^\s*-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----\s*$"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    re.compile(rb"\bsk-(?:proj-|ant-api[0-9]+-)?[A-Za-z0-9_-]{24,}\b"),
    re.compile(rb"<!--\s*(?:yggforge|publication):private\s*-->", re.IGNORECASE),
]


@dataclass(frozen=True)
class PublicationDecision:
    allowed: bool
    reason: str

    @property
    def eligible(self) -> bool:
        """可作为共享候选与已经获得发布授权是两件事。"""
        return self.allowed or self.reason == "APPROVAL_REQUIRED"


def is_privacy_tag(tag: object) -> bool:
    """不要求“共享”标签；精确隐私标签及隐私-子标签拒绝发布。"""
    return isinstance(tag, str) and (tag.strip() == "隐私" or tag.strip().startswith("隐私-"))


def _yaml_scalar(value: str) -> str:
    # 标签尾部允许注释；引号里的 # 保留为标签内容。
    quote = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quote:
            if char == "\\" and quote == '"':
                escaped = True
            elif char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif char == "#" and (index == 0 or value[index - 1].isspace()):
            value = value[:index]
            break
    value = value.strip()
    if value.startswith('"'):
        parsed = json.loads(value)
        if not isinstance(parsed, str):
            raise ValueError("invalid tag")
        return parsed
    if value.startswith("'"):
        if not value.endswith("'") or len(value) < 2:
            raise ValueError("invalid tag")
        return value[1:-1].replace("''", "'")
    value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
    if value.startswith("!") or any(token in value for token in ("*", "&", "{", "}", "[", "]")):
        raise ValueError("unsupported tag syntax")
    return value


def _inline_tags(value: str) -> Set[str]:
    """解析 tags 的小型 YAML 子集：引号/中文/inline list；不执行 alias 或 YAML 对象。"""
    value = value.strip()
    if value in ("", "null", "Null", "NULL", "~"):
        return set()
    if not value.startswith("["):
        return {_yaml_scalar(value)}
    # 注释只能在结束括号之后；引号里的逗号不能切分为多个 tag。
    quote = None
    escaped = False
    parts = []
    current = []
    closed = False
    for index, char in enumerate(value[1:], start=1):
        if escaped:
            current.append(char)
            escaped = False
            continue
        if quote:
            current.append(char)
            if char == "\\" and quote == '"':
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
            current.append(char)
        elif char == ",":
            parts.append("".join(current).strip())
            current = []
        elif char == "]":
            parts.append("".join(current).strip())
            tail = value[index + 1:].strip()
            if tail and not tail.startswith("#"):
                raise ValueError("invalid tags suffix")
            closed = True
            break
        else:
            current.append(char)
    if not closed or quote:
        raise ValueError("unclosed tags")
    return {_yaml_scalar(part) for part in parts if part}


def markdown_tags(text: str) -> Set[str]:
    """只读取开头 front matter 的 tags，正文中讨论“隐私”不等于贴了标签。"""
    text = text.lstrip("\ufeff")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return set()
    ending = next((i for i in range(1, len(lines)) if lines[i].strip() in ("---", "...")), None)
    if ending is None:
        raise ValueError("unclosed front matter")
    tags: Set[str] = set()
    index = 1
    while index < ending:
        line = lines[index]
        match = re.match(r"^\s*tags\s*:\s*(.*?)\s*$", line)
        if not match:
            index += 1
            continue
        value = match.group(1)
        index += 1
        if value.startswith("["):
            while "]" not in value and index < ending:
                value += " " + lines[index].strip()
                index += 1
        if value.strip() and not value.lstrip().startswith("#"):
            tags.update(_inline_tags(value))
        else:
            # YAML 的 block sequence 可缩进，也可从第 0 列开始。
            while index < ending:
                item = lines[index]
                if not item.strip() or item.lstrip().startswith("#"):
                    index += 1
                    continue
                block = re.match(r"^\s*-\s+(.*?)\s*$", item)
                if not block:
                    break
                tags.add(_yaml_scalar(block.group(1)))
                index += 1
    return tags


def _strings(value: object) -> Set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return set().union(*(_strings(item) for item in value)) if value else set()
    if isinstance(value, dict):
        result = set(value.keys())
        for item in value.values():
            result.update(_strings(item))
        return result
    return set()


def json_tags(value: object) -> Set[str]:
    """检查整份 JSON 内全部 tags；混合公私对象不能作为一个公开文件发布。"""
    tags: Set[str] = set()
    if isinstance(value, list):
        for item in value:
            tags.update(json_tags(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            tags.update(_strings(item) if key == "tags" else json_tags(item))
    return tags


def _checked_path(path: Path, root: Path) -> Tuple[Optional[Path], Optional[str]]:
    """同时检查词法路径和真实路径，防止链接从其它位置绕进 runtime 或越界。"""
    root = root.resolve()
    candidate = path if path.is_absolute() else root / path
    try:
        relative = candidate.relative_to(root)
        resolved = candidate.resolve()
        real_relative = resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None, "PATH_ESCAPE"
    if any(part in EXCLUDED_DIRECTORIES for part in relative.parts + real_relative.parts):
        return None, "EXCLUDED_PATH"
    if candidate.is_dir():
        return None, "SYMLINK_DIRECTORY" if candidate.is_symlink() else "NOT_FILE"
    if not candidate.is_file():
        return None, "NOT_FILE"
    return resolved, None


def _sensitive_file(path: Path, forbidden_terms: Iterable[str] = ()) -> Optional[str]:
    """分块检查已知密钥/显式私密标记，避免把整个二进制资产载入内存。"""
    terms = [term.encode("utf-8") for term in forbidden_terms if term]
    carry_size = max([1024] + [len(term) - 1 for term in terms])
    carry = b""
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return None
            data = carry + chunk
            if any(term in data for term in terms):
                return "FORBIDDEN_TERM"
            if any(pattern.search(data) for pattern in _SENSITIVE):
                return "SENSITIVE_MARKER"
            carry = data[-carry_size:]


def _document(path: Path) -> Tuple[str, object, Set[str]]:
    suffix = path.suffix.lower()
    if suffix not in MARKDOWN_SUFFIXES | {".json"}:
        return "", None, set()
    with path.open("rb") as stream:
        raw = stream.read(MAX_METADATA_BYTES + 1)
    if len(raw) > MAX_METADATA_BYTES:
        raise ValueError("metadata too large")
    text = raw.decode("utf-8-sig")
    if suffix == ".json":
        value = json.loads(text)
        return text, value, json_tags(value)
    return text, None, markdown_tags(text)


def evaluate_file(
    path: Path, root: Path, inherited_tags: Iterable[str] = (), *, forbidden_terms: Iterable[str] = ()
) -> PublicationDecision:
    """只检查单文件是否具备共享资格；ELIGIBLE 不表示用户已批准发布。"""
    root = Path(root).resolve()
    forbidden_terms = tuple(forbidden_terms)
    checked, reason = _checked_path(Path(path), Path(root))
    if reason:
        return PublicationDecision(False, reason)
    if any(is_privacy_tag(tag) for tag in inherited_tags):
        return PublicationDecision(False, "INHERITED_PRIVACY")
    try:
        lexical = Path(path) if Path(path).is_absolute() else root / path
        relative_names = (lexical.relative_to(root).as_posix(), checked.relative_to(root).as_posix())
        if any(term in name for term in forbidden_terms if term for name in relative_names):
            return PublicationDecision(False, "FORBIDDEN_TERM")
        _text, _value, tags = _document(checked)
        if any(is_privacy_tag(tag) for tag in tags):
            return PublicationDecision(False, "PRIVACY_TAG")
        sensitive_reason = _sensitive_file(checked, forbidden_terms)
        if sensitive_reason:
            return PublicationDecision(False, sensitive_reason)
    except (OSError, UnicodeError):
        return PublicationDecision(False, "READ_ERROR")
    except (ValueError, RecursionError):
        return PublicationDecision(False, "METADATA_INVALID")
    return PublicationDecision(True, "ELIGIBLE")


def _entry_id(text: str, value: object) -> str:
    if isinstance(value, dict) and isinstance(value.get("id"), str):
        return value["id"]
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for line in lines[1:]:
        if line.strip() in ("---", "..."):
            break
        match = re.match(r"^id\s*:\s*(.*?)\s*$", line)
        if match:
            try:
                return _yaml_scalar(match.group(1))
            except ValueError:
                return ""
    return ""


def _scope_path(item: object, root: Path) -> str:
    """批准路径只认 root 内精确相对路径；不接受 .. 或通配符。"""
    text = str(item).replace("\\", "/")
    path = Path(text)
    if path.is_absolute():
        try:
            path = path.relative_to(root)
        except ValueError:
            return ""
    if PureWindowsPath(text).drive or ".." in path.parts or any(char in text for char in ("*", "?")):
        return ""
    return path.as_posix().rstrip("/")


def _asset_references(text: str, value: object) -> Set[str]:
    """提取本地附件，不把普通知识条目之间的 Markdown 链接当作标签继承。"""
    refs: Set[str] = set()
    def asset_suffix(reference: str) -> str:
        try:
            return Path(urlsplit(reference).path).suffix.lower()
        except ValueError:
            return ""
    for match in re.finditer(r'(!?)\[[^\]]*\]\(\s*(<[^>]+>|[^\s)]+)', text):
        item = match.group(2).strip("<>")
        if match.group(1) or asset_suffix(item) in ASSET_SUFFIXES:
            refs.add(item)
    for media in re.finditer(r'<(?:img|video|audio|source)\b[^>]*>', text, re.IGNORECASE):
        for attr in re.finditer(r'\b(src|poster|srcset)\s*=\s*["\']([^"\']+)["\']', media.group(), re.IGNORECASE):
            if attr.group(1).lower() == "srcset":
                refs.update(item.strip().split()[0] for item in attr.group(2).split(",") if item.strip())
            else:
                refs.add(attr.group(2))
    # reference-style 图片附件也需继承标签。
    for match in re.finditer(r'^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)', text, re.MULTILINE):
        item = match.group(1).strip("<>")
        if asset_suffix(item) in ASSET_SUFFIXES:
            refs.add(item)
    if isinstance(value, list):
        for item in value:
            refs.update(_asset_references("", item))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in {"assets", "attachments", "files", "asset", "attachment", "image", "images", "src", "asset_path", "attachment_path", "image_path", "image_url", "file_path"}:
                refs.update(_strings(item))
            else:
                refs.update(_asset_references("", item))
    return refs


def _reference_path(reference: str, parent: Path, root: Path) -> Optional[Path]:
    try:
        parsed = urlsplit(reference)
    except ValueError:
        return None
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    path = Path(unquote(parsed.path))
    if PureWindowsPath(str(path)).drive:
        return None
    if path.is_absolute():
        # 支持本仓绝对引用；其它 /images/... 视作站点根相对资源。
        try:
            path.relative_to(root)
        except ValueError:
            path = root / str(path).lstrip("/")
    else:
        path = parent / path
    checked, reason = _checked_path(path, root)
    if reason in {"NOT_FILE", "SYMLINK_DIRECTORY"} and path.is_dir():
        # 上面的词法/真实边界与排除目录检查已通过，显式附件目录继承到子文件。
        return path.resolve()
    return checked if not reason else None


def select_files(
    root: Path, paths: Optional[Iterable[Path]] = None, *, approved_items: Iterable[str] = (),
    framework_paths: Iterable[Path] = (), forbidden_terms: Iterable[str] = ()
) -> List[Tuple[str, PublicationDecision]]:
    """先检查隐私与资产继承，再应用发布授权；无隐私标签只表示 eligible。

    paths 可由调用方提供 Git 跟踪文件清单；不提供时遍历仓库并剪掉运行时/生成物。
    不跟随目录链接，也不复制任何内容。继承按资产真实路径计算，防止换链接名绕过。
    框架路径可自动发布；其它条目必须逐 ID/文件路径批准，隐私不能被批准覆盖。
    """
    root = Path(root).resolve()
    forbidden_terms = tuple(forbidden_terms)
    discovered: List[Path] = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if name not in EXCLUDED_DIRECTORIES]
        for name in list(dirs):
            item = Path(directory) / name
            if item.is_symlink():
                discovered.append(item)
                dirs.remove(name)
        discovered.extend(Path(directory) / name for name in files)
    candidates = discovered if paths is None else [Path(item) if Path(item).is_absolute() else root / item for item in paths]
    candidates = sorted(set(candidates), key=lambda item: str(item))
    # 即使待复制清单只包含附件，也必须检查根内未被选中的私密来源。
    contexts = sorted(set(discovered + candidates), key=lambda item: str(item))
    inspections = {path: evaluate_file(path, root, forbidden_terms=forbidden_terms) for path in contexts}
    private_assets: Set[Path] = set()
    references = {}
    entry_ids = {}
    for path in contexts:
        checked, reason = _checked_path(path, root)
        if reason:
            continue
        try:
            text, value, _tags = _document(checked)
            entry_ids[path] = _entry_id(text, value)
            references[checked] = {
                target for ref in _asset_references(text, value)
                for target in [_reference_path(ref, checked.parent, root)] if target is not None
            }
        except (OSError, ValueError, UnicodeError, RecursionError):
            references[checked] = set()
            if checked.suffix.lower() in MARKDOWN_SUFFIXES:
                try:
                    # tags 不可解析时文件已被拒绝，但仍提取正文附件，避免附件漏发。
                    with checked.open("rb") as stream:
                        text = stream.read(MAX_METADATA_BYTES).decode("utf-8-sig")
                    references[checked] = {
                        target for ref in _asset_references(text, None)
                        for target in [_reference_path(ref, checked.parent, root)] if target is not None
                    }
                except (OSError, UnicodeError, ValueError):
                    pass
        if inspections[path].reason in {"PRIVACY_TAG", "SENSITIVE_MARKER", "METADATA_INVALID", "FORBIDDEN_TERM"}:
            private_assets.update(references[checked])
    # 私密附件若引用其它附件，继续传播；不会向未引用的条目广播标签。
    pending = list(private_assets)
    while pending:
        current = pending.pop()
        targets = set(references.get(current, set()))
        for source, source_targets in references.items():
            if current in source.parents:
                targets.update(source_targets)
        for target in targets:
            if target not in private_assets:
                private_assets.add(target)
                pending.append(target)
    approved_ids = set(str(item) for item in approved_items)
    approved_paths = {_scope_path(item, root) for item in approved_ids} - {""}
    framework_scopes = {_scope_path(item, root) for item in framework_paths} - {""}
    id_counts = {}
    for identifier in entry_ids.values():
        if identifier:
            id_counts[identifier] = id_counts.get(identifier, 0) + 1
    authorization = {}
    for path in contexts:
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        identifier = entry_ids.get(path, "")
        if any(relative == scope or relative.startswith(scope + "/") for scope in framework_scopes):
            authorization[path] = "FRAMEWORK_ALLOWED"
        elif relative in approved_paths or (identifier in approved_ids and id_counts.get(identifier) == 1):
            authorization[path] = "APPROVED"
    authorized_assets: Set[Path] = set()
    for path in authorization:
        checked, _reason = _checked_path(path, root)
        if inspections[path].allowed and checked not in private_assets and not any(parent in private_assets for parent in checked.parents):
            authorized_assets.update(references.get(checked, set()))
    pending = list(authorized_assets)
    while pending:
        current = pending.pop()
        targets = set(references.get(current, set()))
        for source, source_targets in references.items():
            if current in source.parents and source not in private_assets and not any(parent in private_assets for parent in source.parents):
                targets.update(source_targets)
        for target in targets:
            if target not in authorized_assets and target not in private_assets:
                authorized_assets.add(target)
                pending.append(target)
    result = []
    for path in candidates:
        checked, _reason = _checked_path(path, root)
        decision = inspections[path]
        if checked is not None and (checked in private_assets or any(parent in private_assets for parent in checked.parents)):
            decision = PublicationDecision(False, "INHERITED_PRIVACY")
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            relative = str(path)
        if decision.allowed:
            if path in authorization:
                decision = PublicationDecision(True, authorization[path])
            elif checked in authorized_assets or any(parent in authorized_assets for parent in checked.parents):
                decision = PublicationDecision(True, "APPROVED_ASSET")
            else:
                decision = PublicationDecision(False, "APPROVAL_REQUIRED")
        result.append((relative, decision))
    return result
