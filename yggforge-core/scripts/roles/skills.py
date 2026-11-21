"""技能目录与按任务选择：元数据先行，正文和资源仅加载激活项。"""

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
from typing import Any, Dict, List

from lib.front_matter import as_str_list, parse_front_matter
from roles.registry import RoleError

EXCLUDED = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", ".mypy_cache", ".ruff_cache", "cache", ".cache"}
ARCHIVE_SUFFIXES = {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".whl", ".zst"}
_AUTO_RESOURCES = object()
ROOT_RESOURCE_DIRS = {"references", "scripts", "assets", "templates"}
SECRET_FILES = {"credentials.json", "auth.json", "token.json", "tokens.json", "id_rsa", "id_ed25519"}


def _excluded_resource(relative: Path) -> bool:
    """资料选取排除凭据、运行缓存、归档及依赖目录。"""
    return (
        any(part.casefold() in EXCLUDED for part in relative.parts)
        or any(part.casefold().startswith(".env") for part in relative.parts)
        or any(part.casefold() in SECRET_FILES for part in relative.parts)
        or relative.suffix.casefold() in ARCHIVE_SUFFIXES | {".pyc", ".pyo"}
    )


def _ordinary_resource(path: Path) -> bool:
    """只接受普通文件或目录；声明文件名不授予执行权限。"""
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        return False
    try:
        mode = path.lstat().st_mode
    except OSError:
        return False
    return stat.S_ISREG(mode) or stat.S_ISDIR(mode)


def _declared_path(root: Path, value: str) -> Path:
    """跨平台解析技能内部相对路径，拒绝越界、链接和特殊文件。"""
    if not isinstance(value, str) or not value.strip():
        raise RoleError("技能 metadata.resources 只接受非空相对路径字符串。")
    portable = value.replace("\\", "/")
    parts = portable.split("/")
    if PurePosixPath(portable).is_absolute() or PureWindowsPath(value).drive or ":" in value or any(part in {"", ".", ".."} for part in parts):
        raise RoleError("技能资源路径必须位于自身目录: " + value)
    relative = Path(*parts)
    if _excluded_resource(relative):
        raise RoleError("技能资源声明包含凭据、缓存、依赖或归档: " + value)
    if root.name == "skills" and (root / relative.parts[0] / "SKILL.md").is_file():
        raise RoleError("根级技能资源不能包含另一项已注册技能: " + value)
    current = root
    for part in relative.parts:
        current = current / part
        if not _ordinary_resource(current):
            raise RoleError("技能资源不存在或不是无链接的普通资料: " + value)
    try:
        current.resolve().relative_to(root)
    except ValueError as exc:
        raise RoleError("技能资源路径越过自身目录: " + value) from exc
    return current


def resources(entry: Path, declared=_AUTO_RESOURCES) -> List[Path]:
    """显式清单收窄静态支持资料；未声明时扫描原技能安全资源。"""
    root = entry.parent.resolve()
    if declared is not _AUTO_RESOURCES:
        if not isinstance(declared, list):
            raise RoleError("技能 metadata.resources 必须是相对路径列表。")
        result = set()
        for value in declared:
            selected = _declared_path(root, value)
            candidates = [selected]
            if selected.is_dir():
                candidates.extend(selected.rglob("*"))
            for path in candidates:
                relative = path.relative_to(root)
                if _excluded_resource(relative) or not _ordinary_resource(path):
                    raise RoleError("技能资源声明包含不可投影的资料: " + relative.as_posix())
                try:
                    path.resolve().relative_to(root)
                except ValueError as exc:
                    raise RoleError("技能资源越过自身目录: " + relative.as_posix()) from exc
                if path.is_file() and path != entry:
                    result.add(path)
        return sorted(result)
    result = []
    if root.name == "skills":
        # 根级入口并不拥有所有并列技能和业务数据；只自动选自身常规支持区及许可。
        candidates = [path for path in root.iterdir() if path.is_file() and path.name.casefold().startswith(("license", "readme", "attribution"))]
        for name in sorted(ROOT_RESOURCE_DIRS):
            directory = root / name
            if _ordinary_resource(directory) and directory.is_dir() and not (directory / "SKILL.md").exists():
                candidates.extend(directory.rglob("*"))
    else:
        candidates = root.rglob("*")
    for path in sorted(candidates):
        relative = path.relative_to(root)
        if not _ordinary_resource(path) or not path.is_file() or _excluded_resource(relative):
            continue
        try:
            path.resolve().relative_to(root)
        except ValueError:
            continue
        if path != entry:
            result.append(path)
    return result


def _metadata(text: str) -> Dict[str, Any]:
    """完整读取标准YAML元数据；轻量环境仍支持已有JSON与resources列表。"""
    metadata, _body = parse_front_matter(text)
    normalized = text.lstrip("\ufeff").replace("\r\n", "\n")
    end = normalized.find("\n---\n", 4) if normalized.startswith("---\n") else -1
    if end >= 0:
        try:
            import yaml
        except ImportError:
            pass
        else:
            try:
                decoded = yaml.safe_load(normalized[4:end])
            except yaml.YAMLError as exc:
                raise RoleError("技能元数据不是有效YAML。") from exc
            if isinstance(decoded, dict):
                return decoded
        # 无PyYAML时只补齐嵌套metadata.resources，不能把显式清单误作自动扫描。
        match = re.search(r"(?m)^metadata:\s*$([\s\S]*?)(?=^\S|\Z)", normalized[4:end])
        if match:
            resource_match = re.search(r"(?m)^  resources:[ \t]*([^\n]*)(?:\n((?:    -[^\n]*(?:\n|$))+))?", match.group(1))
            if resource_match:
                extra = metadata.get("metadata", {})
                extra = extra if isinstance(extra, dict) else {}
                inline = resource_match.group(1).strip()
                if inline:
                    decoded, _body = parse_front_matter("---\nresources: " + inline + "\n---\n")
                    extra["resources"] = decoded.get("resources")
                else:
                    extra["resources"] = [line.strip()[2:].strip().strip("\"'") for line in (resource_match.group(2) or "").splitlines() if line.strip()]
                metadata["metadata"] = extra
    return metadata


def catalog(role) -> List[Dict[str, Any]]:
    result = []
    references = role.metadata()["skills"]
    for reference, path in zip(references, role.skills):
        metadata = _metadata(path.read_text(encoding="utf-8-sig"))
        extra = metadata.get("metadata", {})
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except ValueError:
                extra = {}
        if not isinstance(extra, dict):
            extra = {}
        if path.parent == role.root / "skills" and not metadata.get("name"):
            raise RoleError("根级 skills/SKILL.md 必须声明自身技能 name。")
        item = {"name": str(metadata.get("name") or path.parent.name), "path": reference, "description": str(metadata.get("description", "")), "tags": as_str_list(extra.get("tags", metadata.get("tags", []))), "requires": as_str_list(extra.get("requires", metadata.get("requires", []))), "availability": extra.get("availability", "workflow"), "license": str(metadata.get("license", "")), "entry_bytes": path.stat().st_size}
        if "resources" in extra:
            item["resources"] = extra["resources"]
        result.append(item)
    return result


def _aliases(item: Dict[str, Any]):
    """名称、已注册入口和其目录可定位技能；根级入口不借用通用skills别名。"""
    reference = item["path"]
    portable = reference[7:] if reference.startswith("shared:") else reference
    path = PurePosixPath(portable)
    values = {item["name"], reference}
    if path.parent.as_posix() != "skills":
        prefix = "shared:" if reference.startswith("shared:") else ""
        values.update({prefix + path.parent.as_posix(), path.parent.name})
    return values


def select(role, task: Dict[str, Any]):
    inventory = catalog(role)
    explicit = task.get("skills", [])
    if not isinstance(explicit, list) or any(not isinstance(item, str) for item in explicit):
        raise RoleError("任务 skills 必须是注册技能名称或路径列表。")
    selected = []
    def add_registered(names):
        for name in names:
            matches = [item for item in inventory if name in _aliases(item)]
            if len(matches) != 1:
                raise RoleError("技能不存在或名称不唯一: " + name)
            if matches[0] not in selected:
                selected.append(matches[0])
    if explicit:
        # 本次用户显式技能选择优先，不能被默认或自动命中替换、缩减。
        add_registered(explicit)
    else:
        add_registered(getattr(role, "default_skills", ()))
        workflow = task.get("workflow", "")
        workflows = getattr(role, "skill_workflows", {})
        if workflow:
            if not isinstance(workflow, str) or workflow not in workflows:
                raise RoleError("角色工作流未注册: " + str(workflow))
            add_registered(workflows[workflow])
        else:
            _select_automatic(role, task, inventory, selected)
    loaded = []
    path_map = dict(zip(role.metadata()["skills"], role.skills))
    for item in selected:
        path = path_map[item["path"]]
        text = path.read_text(encoding="utf-8-sig")
        loaded.append(dict(item, body=text, resource_paths=[str(value) for value in resources(path, item.get("resources", _AUTO_RESOURCES))], resource_root=str(path.parent.resolve())))
    return inventory, loaded


def _select_automatic(role, task, inventory, selected):
    """四项预算只约束可选检索，默认入口和完整工作流不受此裁剪。"""
    if inventory:
        tags = {str(item).casefold() for item in task.get("tags", [])}
        words = set(re.findall(r"[a-z][a-z0-9-]{2,}|[\u4e00-\u9fff]{2,}", task.get("prompt", "").casefold()))
        scored = []
        for order, item in enumerate(inventory):
            if item in selected:
                continue
            own_tags = {value.casefold() for value in item["tags"]}
            score = 20 * len(tags & own_tags)
            text = (item["name"] + " " + item["description"]).casefold()
            score += 3 * sum(word in text for word in words)
            score += 5 * sum(tag in item["name"].casefold() for tag in tags)
            if score:
                scored.append((score, -order, item))
        limit = role.retrieval.get("skill_limit", 4)
        selected.extend(item for _, _, item in sorted(scored, key=lambda value: (value[0], value[1]), reverse=True)[:limit])
        if not selected and inventory:
            selected.extend(inventory[:1])
