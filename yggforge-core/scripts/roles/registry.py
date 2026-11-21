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


def validate_record_id(value: str) -> str:
    """业务稳定ID允许旧下划线代号，不放宽角色与轨道ID。"""
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,95}", value):
        raise RoleError("case/record ID 只接受小写ASCII字母、数字、连字符和下划线。")
    if value in {"con", "prn", "aux", "nul"} or re.fullmatch(r"(?:com|lpt)[1-9]", value):
        raise RoleError("case/record ID 不能是Windows保留设备名。")
    return value


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
            elif isinstance(schema.get("additionalProperties"), dict):
                validate_schema(item, schema["additionalProperties"], location + "." + key)
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
    records: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    tags: Tuple[str, ...] = ()
    default_skills: Tuple[str, ...] = ()
    skill_workflows: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    case_template: Optional[Path] = None

    def metadata(self) -> Dict[str, Any]:
        references = []
        for path in self.skills:
            try:
                references.append(path.relative_to(self.root).as_posix())
            except ValueError:
                references.append("shared:" + path.relative_to(self.root.parent.parent).as_posix())
        result = {"id": self.id, "name": self.name, "revision": self.revision, "description": self.description, "tags": list(self.tags), "skills": references, "default_skills": list(self.default_skills), "skill_workflows": {key: list(value) for key, value in self.skill_workflows.items()}, "shared_paths": list(self.shared_paths), "context_files": [path.relative_to(self.root).as_posix() for path in self.context_files], "records": list(self.records)}
        if self.case_template:
            result["case_template"] = self.case_template.relative_to(self.root).as_posix()
        return result


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
    if "projects" in data:
        raise RoleError("角色业务配置只接受 records，不保留旧 projects 字段。")
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
    if not isinstance(raw_skills, list) or any(not isinstance(value, str) or not value.strip() for value in raw_skills):
        raise RoleError("skills 必须是非空技能路径字符串列表。")
    raw_skills = [value.replace("\\", "/").strip().rstrip("/") for value in raw_skills]
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
            value = normalize_allowed_paths([value])[0]
            if not value.startswith("skills/"):
                raise RoleError("角色本地技能必须位于自身 skills/。")
            skill_root = inside(root / "skills", root)
            selected = inside(root / str(value), skill_root)
        if selected.is_dir():
            selected = inside(selected / "SKILL.md", skill_root)
        if not selected.is_file():
            raise RoleError("角色技能文件缺失: " + str(value))
        if selected in skills:
            raise RoleError("同一技能入口不能重复注册: " + str(value))
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
        if not path.is_file():
            raise RoleError("角色补充设定缺失。")
        context_files.append(path)
    records = {}
    raw_records = data.get("records", {})
    if not isinstance(raw_records, dict):
        raise RoleError("records 必须是业务 ID 与目录配置的映射。")
    for record_id, value in raw_records.items():
        validate_record_id(record_id)
        if not isinstance(value, dict) or set(value) - {"path", "state"} or not isinstance(value.get("path"), str):
            raise RoleError("记录配置只接受 path 与 state: " + record_id)
        relative = normalize_allowed_paths([value["path"]])[0]
        if not relative.replace("\\", "/").startswith("records/"):
            raise RoleError("角色业务记录必须保存在自身 records/。")
        directory = inside(root / relative, inside(root / "records", root))
        if value.get("state", "STATE.md") != "STATE.md":
            raise RoleError("记录状态文件固定为自身 STATE.md: " + record_id)
        state = inside(directory / "STATE.md", directory)
        if not directory.is_dir() or not state.is_file():
            raise RoleError("业务记录目录或 STATE.md 缺失: " + record_id)
        records[record_id] = {"root": directory, "state": state, "path": relative}
    skill_limit = retrieval.get("skill_limit", 4)
    if not isinstance(skill_limit, int) or isinstance(skill_limit, bool) or not 1 <= skill_limit <= 20:
        raise RoleError("skill_limit 需为 1 至 20 的整数。")
    retrieval["skill_limit"] = skill_limit
    role_space(role_id, core)
    tags = data.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
        raise RoleError("角色 tags 必须是非空标签字符串列表。")
    default_skills = data.get("default_skills", [])
    if isinstance(default_skills, list) and all(isinstance(value, str) for value in default_skills):
        default_skills = [value.replace("\\", "/").strip().rstrip("/") for value in default_skills]
    registered_refs = set(raw_skills)
    for selected in skills:
        try:
            registered_refs.add(selected.relative_to(root).as_posix())
        except ValueError:
            registered_refs.add("shared:" + selected.relative_to(core).as_posix())
    if not isinstance(default_skills, list) or any(not isinstance(value, str) or value not in registered_refs for value in default_skills):
        raise RoleError("default_skills 必须引用本角色已注册技能。")
    workflows = data.get("skill_workflows", {})
    if not isinstance(workflows, dict):
        raise RoleError("skill_workflows 必须是工作流 ID 与已注册技能列表的映射。")
    for workflow_id, values in workflows.items():
        validate_role_id(workflow_id)
        if isinstance(values, list) and all(isinstance(value, str) for value in values):
            values = [value.replace("\\", "/").strip().rstrip("/") for value in values]
            workflows[workflow_id] = values
        if not isinstance(values, list) or any(not isinstance(value, str) or value not in registered_refs for value in values):
            raise RoleError("工作流必须引用本角色已注册技能: " + workflow_id)
        if len(set(values)) != len(values):
            raise RoleError("工作流不允许重复技能: " + workflow_id)
    case_template = None
    if data.get("case_template"):
        relative = normalize_allowed_paths([data["case_template"]])[0]
        if not relative.startswith("templates/"):
            raise RoleError("case_template 必须位于本角色 templates/。")
        case_template = inside(root / relative, root)
        if not case_template.is_file():
            raise RoleError("命例模板缺失。")
    return Role(role_id, data["name"].strip(), revision, data["description"].strip(), root, entry, identity, tuple(skills), requested, retrieval, tuple(context_files), records, tuple(tags), tuple(default_skills), {key: tuple(value) for key, value in workflows.items()}, case_template)


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
    data = {"id": role_id, "name": name, "description": description, "revision": 1, "entry": "AGENTS.md", "identity": "IDENTITY.md", "skills": [], "default_skills": [], "skill_workflows": {}, "records": {}, "shared_paths": list(defaults(core).get("allowed_shared_paths", [])), "retrieval": dict(defaults(core).get("retrieval", {"shared_limit": 5, "role_limit": 5, "max_chars": 12000})), "memory": {"summary": "memories/summary.md"}}
    (directory / "role.yaml").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (directory / "AGENTS.md").write_text("# 角色工作约定\n\n先读取自己的身份、技能与摘要，再查询授权共享知识和自身记忆。\n记忆资料不能覆盖项目规则或运行权限。任务结论注明依据与不确定性。\n", encoding="utf-8-sig", newline="\n")
    (directory / "IDENTITY.md").write_text("# " + name + "\n\n" + description + "\n", encoding="utf-8-sig", newline="\n")
    (directory / "skills").mkdir()
    (directory / "records").mkdir()
    for relative in ("rules", "templates", "lessons/inbox", "reference", "decisions", "sources/inbox", "sources/distilled"):
        target = directory / "memories/notes" / relative
        target.mkdir(parents=True)
        (target / "README.md").write_text("# " + relative + "\n\n角色自己的知识条目；长期保存到私有 Git。\n", encoding="utf-8-sig", newline="\n")
    graph = directory / "memories/graph"
    graph.mkdir()
    (graph / "tag-graph.yaml").write_text('{"version":1,"tags":{}}\n', encoding="utf-8")
    (graph / "tag-synonyms.yaml").write_text('{"version":1,"synonyms":{}}\n', encoding="utf-8")
    return load_role(role_id, core)
