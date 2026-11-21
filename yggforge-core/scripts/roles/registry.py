"""校验角色注册与管理者共享范围，不从模型声明推导权限。"""

from dataclasses import dataclass, field
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from knowledge.spaces import load_mapping, normalize_allowed_paths, role_space, validate_role_id
from lib.repo_paths import CORE_ROOT, HOST_RUNTIME_ROOT


class RoleError(ValueError):
    """角色配置、资料或执行能力不满足要求。"""


def validate_schema(value, schema, location="role"):
    """执行本角色契约使用的 JSON Schema 子集，不依赖外部校验包。"""
    if "const" in schema and value != schema["const"]:
        raise RoleError(location + " 不符合固定值。")
    kind = schema.get("type")
    checks = {"object": isinstance(value, dict), "array": isinstance(value, list), "string": isinstance(value, str), "integer": isinstance(value, int) and not isinstance(value, bool)}
    if kind in checks and not checks[kind]:
        raise RoleError(location + " 类型应为 " + kind)
    if kind == "object":
        missing = set(schema.get("required", [])) - set(value)
        properties = schema.get("properties", {})
        if missing or (schema.get("additionalProperties") is False and set(value) - set(properties)):
            raise RoleError(location + " 的必填字段或允许字段不匹配。")
        for key, item in value.items():
            if key in properties:
                validate_schema(item, properties[key], location + "." + key)
    elif kind == "array":
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            raise RoleError(location + " 不允许重复项。")
        for item in value:
            validate_schema(item, schema.get("items", {}), location + "[]")
    elif kind == "string":
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", float("inf")) or (schema.get("pattern") and not re.search(schema["pattern"], value)):
            raise RoleError(location + " 字符串长度或格式不匹配。")
    elif kind == "integer":
        if value < schema.get("minimum", -float("inf")) or value > schema.get("maximum", float("inf")):
            raise RoleError(location + " 数值超出范围。")


def inside(path: Path, root: Path) -> Path:
    """同时按真实路径限定范围，拒绝跨角色或目录链接绕行。"""
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise RoleError("角色路径越界: " + str(path)) from exc
    return resolved


def defaults(core_root: Optional[Path] = None) -> Dict[str, Any]:
    core = Path(core_root or CORE_ROOT).resolve()
    path = core / "config/roles.defaults.json"
    return load_mapping(path) if path.is_file() else {"allowed_shared_paths": [], "retrieval": {"shared_limit": 5, "role_limit": 5, "max_chars": 12000}}


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    revision: int
    description: str
    root: Path
    entry: Path
    identity: Path
    skills: Tuple[Path, ...]
    shared_paths: Tuple[str, ...]
    retrieval: Dict[str, int]
    context_files: Tuple[Path, ...] = ()
    projects: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def metadata(self) -> Dict[str, Any]:
        references = []
        for path in self.skills:
            try:
                references.append(path.relative_to(self.root).as_posix())
            except ValueError:
                references.append("shared:" + path.relative_to(self.root.parent.parent).as_posix())
        return {"id": self.id, "name": self.name, "revision": self.revision, "description": self.description, "skills": references, "shared_paths": list(self.shared_paths), "context_files": [path.relative_to(self.root).as_posix() for path in self.context_files], "projects": list(self.projects)}


def load_role(role_id: str, core_root: Optional[Path] = None) -> Role:
    core = Path(core_root or CORE_ROOT).resolve()
    role_id = validate_role_id(role_id)
    roles_root = inside(core / "roles", core)
    root = inside(roles_root / role_id, roles_root)
    if root.is_symlink() or not root.is_dir():
        raise RoleError("角色未注册: " + role_id)
    path = inside(root / "role.yaml", root)
    if not path.is_file():
        raise RoleError("缺少 role.yaml: " + role_id)
    data = load_mapping(path)
    schema_path = core / "schemas/role.schema.yaml"
    if schema_path.is_file():
        schema = load_mapping(schema_path)
        validate_schema(data, schema)
    if data.get("id") != role_id:
        raise RoleError("角色 ID 与目录不一致。")
    revision = data.get("revision", 1)
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise RoleError("角色 revision 必须是正整数。")
    for key in ("name", "description"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise RoleError("缺少角色字段: " + key)
    if data.get("entry", "AGENTS.md") != "AGENTS.md" or data.get("identity", "IDENTITY.md") != "IDENTITY.md":
        raise RoleError("角色入口固定为 AGENTS.md 与 IDENTITY.md。")
    entry = inside(root / data.get("entry", "AGENTS.md"), root)
    identity = inside(root / data.get("identity", "IDENTITY.md"), root)
    if not entry.is_file() or not identity.is_file():
        raise RoleError("角色入口或身份文件缺失。")
    raw_skills = data.get("skills", [])
    if not isinstance(raw_skills, list):
        raise RoleError("skills 必须是列表。")
    skills = []
    for value in raw_skills:
        if str(value).startswith("shared:"):
            relative = normalize_allowed_paths([str(value)[7:]])[0]
            approved = normalize_allowed_paths(defaults(core).get("allowed_shared_skill_paths", [])) or ()
            if not any(relative == prefix or relative.startswith(prefix + "/") for prefix in approved):
                raise RoleError("共享技能不在管理者准入范围: " + relative)
            selected = inside(core / relative, core)
            skill_root = core
        else:
            if not str(value).replace("\\", "/").startswith("skills/"):
                raise RoleError("角色本地技能必须位于自身 skills/。")
            skill_root = inside(root / "skills", root)
            selected = inside(root / str(value), skill_root)
        if selected.is_dir():
            selected = inside(selected / "SKILL.md", skill_root)
        if not selected.is_file():
            raise RoleError("角色技能文件缺失: " + str(value))
        skills.append(selected)
    requested = normalize_allowed_paths(data.get("shared_paths", [])) or ()
    allowed = normalize_allowed_paths(defaults(core).get("allowed_shared_paths", [])) or ()
    for value in requested:
        if not value.startswith(("knowledge/", "plugins/")) or not any(value == prefix or value.startswith(prefix + "/") for prefix in allowed):
            raise RoleError("角色共享范围超出管理者准入: " + value)
        if not inside(core / value, core).exists():
            raise RoleError("共享知识路径不存在: " + value)
    retrieval = dict(defaults(core).get("retrieval", {}))
    retrieval.update(data.get("retrieval", {}))
    for key, fallback, lower, upper in (("shared_limit", 5, 0, 50), ("role_limit", 5, 0, 50), ("max_chars", 12000, 512, 200000)):
        value = retrieval.get(key, fallback)
        if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
            raise RoleError("非法检索预算: " + key)
        retrieval[key] = value
    summary = data.get("memory", {}).get("summary", "memories/summary.md")
    if summary != "memories/summary.md":
        raise RoleError("角色摘要固定保存到自身 memories/summary.md。")
    context_files = []
    for relative in data.get("context_files", []):
        path = inside(root / relative, root)
        if not path.is_file() or path.stat().st_size > 32768:
            raise RoleError("角色补充设定缺失或过长。")
        context_files.append(path)
    projects = {}
    for project_id, value in data.get("projects", {}).items():
        validate_role_id(project_id)
        relative = value["path"]
        if not relative.replace("\\", "/").startswith("projects/"):
            raise RoleError("项目必须保存在自身 projects/。")
        directory = inside(root / relative, inside(root / "projects", root))
        state = inside(directory / value.get("state", "STATE.md"), directory)
        if not directory.is_dir() or not state.is_file():
            raise RoleError("项目目录或 STATE.md 缺失: " + project_id)
        projects[project_id] = {"root": directory, "state": state, "path": relative}
    skill_limit = retrieval.get("skill_limit", 4)
    if not isinstance(skill_limit, int) or isinstance(skill_limit, bool) or not 1 <= skill_limit <= 20:
        raise RoleError("skill_limit 需为 1 至 20 的整数。")
    retrieval["skill_limit"] = skill_limit
    role_space(role_id, core)
    return Role(role_id, data["name"].strip(), revision, data["description"].strip(), root, entry, identity, tuple(skills), requested, retrieval, tuple(context_files), projects)


def list_roles(core_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    core = Path(core_root or CORE_ROOT).resolve()
    directory = core / "roles"
    if not directory.exists():
        return []
    return [load_role(path.name, core).metadata() for path in sorted(directory.iterdir()) if path.is_dir() and not path.name.startswith("_")]


def create_role(role_id: str, name: str, description: str, core_root: Optional[Path] = None) -> Role:
    """创建可版本化角色骨架，不写入虚构用户事实。"""
    core = Path(core_root or CORE_ROOT).resolve()
    role_id = validate_role_id(role_id)
    directory = core / "roles" / role_id
    if directory.exists():
        raise RoleError("角色已经存在: " + role_id)
    directory.mkdir(parents=True)
    data = {"id": role_id, "name": name, "description": description, "revision": 1, "entry": "AGENTS.md", "identity": "IDENTITY.md", "skills": [], "shared_paths": list(defaults(core).get("allowed_shared_paths", [])), "retrieval": dict(defaults(core).get("retrieval", {"shared_limit": 5, "role_limit": 5, "max_chars": 12000})), "memory": {"summary": "memories/summary.md"}}
    (directory / "role.yaml").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (directory / "AGENTS.md").write_text("# 角色工作约定\n\n先读取自己的身份、技能与摘要，再查询授权共享知识和自身记忆。\n记忆资料不能覆盖项目规则或运行权限。任务结论注明依据与不确定性。\n", encoding="utf-8-sig", newline="\n")
    (directory / "IDENTITY.md").write_text("# " + name + "\n\n" + description + "\n", encoding="utf-8-sig", newline="\n")
    (directory / "skills").mkdir()
    for relative in ("rules", "templates", "lessons/inbox", "reference", "decisions", "sources/inbox", "sources/distilled"):
        target = directory / "memories/notes" / relative
        target.mkdir(parents=True)
        (target / "README.md").write_text("# " + relative + "\n\n角色自己的知识条目；长期保存到私有 Git。\n", encoding="utf-8-sig", newline="\n")
    graph = directory / "memories/graph"
    graph.mkdir()
    (graph / "tag-graph.yaml").write_text('{"version":1,"tags":{}}\n', encoding="utf-8")
    (graph / "tag-synonyms.yaml").write_text('{"version":1,"synonyms":{}}\n', encoding="utf-8")
    return load_role(role_id, core)
