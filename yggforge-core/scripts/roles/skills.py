"""技能目录与按任务选择：元数据先行，正文和资源仅加载激活项。"""

import json
from pathlib import Path
import re
from typing import Any, Dict, List

from lib.front_matter import as_str_list, parse_front_matter
from roles.registry import RoleError

EXCLUDED = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", ".mypy_cache"}


def resources(entry: Path) -> List[Path]:
    """支持文件只来自该技能自身，不携带凭据、缓存或链接目标。"""
    root = entry.parent.resolve()
    result = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_symlink() or not path.is_file() or any(part in EXCLUDED for part in relative.parts):
            continue
        if path.name == ".env" or path.name.startswith(".env.") or path.suffix.lower() in {".pyc", ".pyo", ".zip"}:
            continue
        try:
            path.resolve().relative_to(root)
        except ValueError:
            continue
        if path != entry:
            result.append(path)
    return result


def catalog(role) -> List[Dict[str, Any]]:
    result = []
    references = role.metadata()["skills"]
    for reference, path in zip(references, role.skills):
        metadata, _body = parse_front_matter(path.read_text(encoding="utf-8-sig"))
        extra = metadata.get("metadata", {})
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except ValueError:
                extra = {}
        if not isinstance(extra, dict):
            extra = {}
        result.append({"name": str(metadata.get("name") or path.parent.name), "path": reference, "description": str(metadata.get("description", ""))[:600], "tags": as_str_list(extra.get("tags", metadata.get("tags", []))), "requires": as_str_list(extra.get("requires", metadata.get("requires", []))), "availability": extra.get("availability", "workflow"), "license": str(metadata.get("license", "")), "entry_bytes": path.stat().st_size})
    return result


def select(role, task: Dict[str, Any]):
    inventory = catalog(role)
    explicit = task.get("skills", [])
    if not isinstance(explicit, list) or any(not isinstance(item, str) for item in explicit):
        raise RoleError("任务 skills 必须是注册技能名称或路径列表。")
    selected = []
    if explicit:
        for name in explicit:
            matches = [item for item in inventory if name in {item["name"], item["path"], item["path"].split("/")[-2]}]
            if len(matches) != 1:
                raise RoleError("技能不存在或名称不唯一: " + name)
            if matches[0] not in selected:
                selected.append(matches[0])
    else:
        tags = {str(item).casefold() for item in task.get("tags", [])}
        words = set(re.findall(r"[a-z][a-z0-9-]{2,}|[\u4e00-\u9fff]{2,}", task.get("prompt", "").casefold()))
        scored = []
        for order, item in enumerate(inventory):
            own_tags = {value.casefold() for value in item["tags"]}
            score = 20 * len(tags & own_tags)
            text = (item["name"] + " " + item["description"]).casefold()
            score += 3 * sum(word in text for word in words)
            score += 5 * sum(tag in item["name"].casefold() for tag in tags)
            if score:
                scored.append((score, -order, item))
        limit = role.retrieval.get("skill_limit", 4)
        selected = [item for _, _, item in sorted(scored, key=lambda value: (value[0], value[1]), reverse=True)[:limit]]
        if not selected and inventory:
            selected = inventory[:1]
    loaded = []
    path_map = dict(zip(role.metadata()["skills"], role.skills))
    for item in selected:
        path = path_map[item["path"]]
        text = path.read_text(encoding="utf-8-sig")
        if len(text.encode("utf-8")) > 32768:
            raise RoleError("技能入口过长，请拆入 references 后再激活: " + item["name"])
        loaded.append(dict(item, body=text, resource_paths=[str(value) for value in resources(path)], resource_root=str(path.parent.resolve())))
    return inventory, loaded
