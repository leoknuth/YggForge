"""命例骨架、分轨白名单和不可覆盖的冻结收据。"""

import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict

from roles.registry import RoleError, inside, validate_record_id
from knowledge.spaces import validate_role_id
from knowledge.graph_models import GraphError


SYNTHESIS_FILES = ("overview.md", "assessment.md", "classical-reflections.md", "conflicts.md", "report.md")


def _relative(value: str) -> str:
    """清单路径必须是无链接的可移植相对路径。"""
    if not isinstance(value, str) or not value:
        raise RoleError("命例路径必须是非空字符串。")
    portable = value.replace("\\", "/")
    if PurePosixPath(portable).is_absolute() or PureWindowsPath(value).drive or ":" in value or any(part in {"", ".", ".."} for part in portable.split("/")):
        raise RoleError("命例路径不能越界: " + value)
    return portable


def case_path(root: Path, value: str) -> Path:
    relative = _relative(value)
    current = root
    for part in relative.split("/"):
        current = current / part
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise RoleError("命例资料不允许链接: " + relative)
    return inside(current, root)


def _strings(value, field):
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value) or len(set(value)) != len(value):
        raise RoleError(field + " 必须是不重复的字符串列表。")
    return value


def validate_manifest(data: Dict[str, Any], role=None) -> Dict[str, Any]:
    """模板只定义输入、工序和技能，不保存命主事实或分析正文。"""
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise RoleError("命例清单 schema_version 必须为 1。")
    allowed = {"schema_version", "case_id", "input_files", "tracks", "optional_tracks", "synthesis_skills", "review_files", "review_skills", "method_memory", "blind_context_files", "reference_roots", "supplements"}
    if set(data) - allowed:
        raise RoleError("命例清单包含不支持字段。")
    inputs = _strings(data.get("input_files"), "input_files")
    if not inputs or any(not _relative(item).startswith("input/") for item in inputs):
        raise RoleError("公共输入必须明确列在 input/ 下。")
    tracks = data.get("tracks")
    if not isinstance(tracks, dict) or not tracks:
        raise RoleError("命例必须有已登记的独立轨道。")
    optional = data.get("optional_tracks", {})
    if not isinstance(optional, dict) or set(optional) & set(tracks):
        raise RoleError("可选专项须独立登记，不能重复必选轨道。")
    all_tracks = dict(tracks, **optional)
    registered = set(role.metadata()["skills"]) if role else None
    for track, config in all_tracks.items():
        validate_role_id(track)
        if not isinstance(config, dict) or not {"skills", "required_inputs", "required_calculations"} <= set(config) or set(config) - {"skills", "required_inputs", "required_calculations", "reference_files"}:
            raise RoleError("轨道配置只接受技能、输入、计算与典籍引用清单。")
        skills = _strings(config["skills"], "track.skills")
        if not skills or (registered is not None and set(skills) - registered):
            raise RoleError("轨道技能必须是本角色已注册的完整入口。")
        required = _strings(config["required_inputs"], "required_inputs")
        if not required or set(required) - set(inputs):
            raise RoleError("轨道只可声明公共输入清单中的资料。")
        calculations = _strings(config["required_calculations"], "required_calculations")
        if any(not _relative(item).startswith("calculations/" + track + "/") for item in calculations):
            raise RoleError("计算清单必须限定在自身轨道。")
        _strings(config.get("reference_files", []), "reference_files")
    synthesis = _strings(data.get("synthesis_skills", []), "synthesis_skills")
    if registered is not None and set(synthesis) - registered:
        raise RoleError("综合技能必须是本角色已注册的入口。")
    review_skills = _strings(data.get("review_skills", []), "review_skills")
    if registered is not None and set(review_skills) - registered:
        raise RoleError("回访技能必须是本角色已注册的完整入口。")
    for item in _strings(data.get("review_files", []), "review_files"):
        _relative(item)
    for item in _strings(data.get("method_memory", []), "method_memory"):
        if not _relative(item).startswith("notes/"):
            raise RoleError("method_memory 必须限定在本角色 memories/notes/。")
    for item in _strings(data.get("blind_context_files", []), "blind_context_files"):
        item = _relative(item)
        if item != "SOUL.md" and not (item.startswith("templates/") and item.endswith(".md")):
            raise RoleError("盲分析只允许 SOUL.md 与 templates/ 下已审计方法投影，拒绝原 USER/TOOLS。")
        if role and not case_path(role.root, item).is_file():
            raise RoleError("已审计方法投影缺失: " + item)
    roots = _strings(data.get("reference_roots", []), "reference_roots")
    for item in roots:
        if not _relative(item).startswith(("records/library/", "references/")):
            raise RoleError("典籍准入只能指向纯资料库，不能授权角色或records父目录。")
    for config in all_tracks.values():
        for item in config.get("reference_files", []):
            value = _relative(item)
            if not any(value == prefix or value.startswith(prefix + "/") for prefix in roots):
                raise RoleError("轨道典籍不在 reference_roots 准入范围。")
    supplements = data.get("supplements", {})
    if not isinstance(supplements, dict):
        raise RoleError("supplements 必须为后续工序映射。")
    for supplement, config in supplements.items():
        validate_role_id(supplement)
        if not isinstance(config, dict) or set(config) != {"mode", "status"} or config["mode"] not in {"optional", "independent-multisource"} or config["status"] != "pending":
            raise RoleError("补充工序只声明独立方法与 pending，不填写虚构结论。")
    return data


def load_manifest(root: Path, role=None):
    manifest = validate_manifest(json.loads(case_path(root, "CASE.json").read_text(encoding="utf-8-sig")), role)
    if not isinstance(manifest.get("case_id"), str):
        raise RoleError("正式命例清单须有稳定 case_id。")
    validate_record_id(manifest["case_id"])
    return manifest


def resolve_record(role, reference):
    """优先登记键；旧案别名只按CASE.case_id唯一解析，不猜目录名。"""
    validate_record_id(reference)
    if reference in role.records:
        return reference, role.records[reference]
    matches = []
    for key, record in role.records.items():
        if (record["root"] / "CASE.json").is_file():
            try:
                manifest = load_manifest(record["root"])
            except (RoleError, GraphError, OSError, ValueError):
                continue
            if manifest["case_id"] == reference:
                matches.append((key, record))
    if len(matches) != 1:
        raise RoleError("命例ID未唯一注册到本角色。")
    return matches[0]


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig" if path.suffix == ".md" else "utf-8", newline="\n")


def _initialize_track(root, track):
    for folder in ("calculations", "analyses", "validation"):
        (root / folder / track).mkdir(parents=True, exist_ok=True)
    _write(root / "analyses" / track / "report.md", "# 独立报告\n\n状态：pending\n\n待本术独立计算与完整分析。\n")
    _write(root / "analyses" / track / "evidence.json", json.dumps({"schema_version": 1, "track": track, "status": "pending", "source_status": "unverified", "claims": []}, ensure_ascii=False, indent=2) + "\n")


def initialize_case(role, case_id: str, register: bool = True, tracks=None) -> Dict[str, Any]:
    """新案只创建 pending 工序与空输入，禁止覆盖现有命例。"""
    validate_record_id(case_id)
    if not getattr(role, "case_template", None):
        raise RoleError("角色未配置 case_template。")
    manifest = json.loads(role.case_template.read_text(encoding="utf-8-sig"))
    validate_manifest(manifest, role)
    manifest = dict(manifest, case_id=case_id)
    enabled = dict(manifest["tracks"])
    for track in tracks or []:
        if track not in enabled and track not in manifest.get("optional_tracks", {}):
            raise RoleError("初始化专项未在本角色模板登记: " + track)
        if track not in enabled:
            enabled[track] = manifest["optional_tracks"][track]
    manifest["tracks"] = enabled
    manifest.pop("optional_tracks", None)
    root = case_path(role.root, "records/clients/" + case_id)
    if root.exists() or case_id in role.records:
        raise RoleError("命例已存在，不能初始化覆盖。")
    root.mkdir(parents=True)
    _write(root / "CASE.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    _write(root / "STATE.md", "# 命例状态\n\n状态：pending\n\n尚未录入真实输入，尚无计算、独立结论、冻结收据或交付。\n")
    for relative in manifest["input_files"]:
        if relative.endswith(".json"):
            _write(case_path(root, relative), json.dumps({"schema_version": 1, "source_status": "pending", "facts": {}}, ensure_ascii=False, indent=2) + "\n")
        elif Path(relative).suffix in {".md", ".txt"}:
            _write(case_path(root, relative), "# 公共输入\n\n状态：pending\n\n待保存用户原始输入与来源，不填写虚构事实。\n")
    for track in manifest["tracks"]:
        _initialize_track(root, track)
    for name in SYNTHESIS_FILES:
        _write(root / "synthesis" / name, "# " + name.removesuffix(".md") + "\n\n状态：pending\n\n待全部独立轨道冻结后综合。\n")
    (root / "deliverables").mkdir()
    (root / "provenance").mkdir()
    if manifest.get("supplements"):
        _write(root / "provenance/supplements.json", json.dumps(manifest["supplements"], ensure_ascii=False, indent=2) + "\n")
    registration = {"path": root.relative_to(role.root).as_posix(), "state": "STATE.md"}
    if register:
        config_path = role.root / "role.yaml"
        from knowledge.spaces import load_mapping
        config = load_mapping(config_path)
        config.setdefault("records", {})[case_id] = registration
        _write(config_path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    return {"status": "initialized", "case_id": case_id, "path": str(root), "registration": registration, "tracks": list(manifest["tracks"])}


def add_track(role, case_id: str, track: str) -> Dict[str, Any]:
    """从模板启用独立专项，保留已冻结术的输入、计算和首判。"""
    if not role.case_template:
        raise RoleError("角色模板或正式命例未注册。")
    _record_id, record = resolve_record(role, case_id)
    template = validate_manifest(json.loads(role.case_template.read_text(encoding="utf-8-sig")), role)
    if track not in template.get("optional_tracks", {}):
        raise RoleError("专项未在本角色 optional_tracks 登记。")
    root = record["root"]
    manifest = load_manifest(root, role)
    if track in manifest["tracks"] or (root / "analyses" / track).exists():
        raise RoleError("专项已存在，不能覆盖。")
    check_case(root)
    manifest["tracks"][track] = template["optional_tracks"][track]
    manifest["input_files"] = list(dict.fromkeys(manifest["input_files"] + template["optional_tracks"][track]["required_inputs"]))
    manifest["reference_roots"] = list(dict.fromkeys(manifest.get("reference_roots", []) + template.get("reference_roots", [])))
    validate_manifest(manifest, role)
    _initialize_track(root, track)
    _write(root / "CASE.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return {"case_id": case_id, "track": track, "status": "enabled-pending"}


def _fingerprint(root: Path, relative: str) -> str:
    path = case_path(root, relative)
    if not path.is_file():
        raise RoleError("命例必需资料缺失: " + relative)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _freeze_files(manifest, track, root=None):
    config = manifest["tracks"][track]
    files = config["required_inputs"] + config["required_calculations"] + ["analyses/" + track + "/report.md", "analyses/" + track + "/evidence.json"]
    if root:
        for folder in ("calculations", "analyses"):
            directory = case_path(root, folder + "/" + track)
            files += [path.relative_to(root).as_posix() for path in sorted(directory.rglob("*")) if path.is_file()]
    return list(dict.fromkeys(files))


def _track_contract(manifest, track):
    data = {"schema_version": manifest["schema_version"], "case_id": manifest["case_id"], "track": track, "config": manifest["tracks"][track]}
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _ready_file(root, relative):
    path = case_path(root, relative)
    _fingerprint(root, relative)
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, (dict, list)) or not data or (isinstance(data, dict) and data.get("source_status") == "pending"):
            raise RoleError("JSON资料尚未完成: " + relative)
    elif path.suffix == ".md":
        body = path.read_text(encoding="utf-8-sig").strip()
        if not body or "状态：pending" in body:
            raise RoleError("文本资料尚未完成: " + relative)


def freeze_track(root: Path, track: str) -> Dict[str, Any]:
    manifest = load_manifest(root)
    if track not in manifest["tracks"]:
        raise RoleError("命例轨道未登记。")
    receipt = case_path(root, "provenance/" + track + ".frozen.json")
    if receipt.exists():
        raise RoleError("轨道已经冻结，不能覆盖原判或原计算。")
    files = _freeze_files(manifest, track, root)
    for relative in files:
        _ready_file(root, relative)
    evidence = json.loads(case_path(root, "analyses/" + track + "/evidence.json").read_text(encoding="utf-8-sig"))
    if evidence.get("schema_version") != 1 or evidence.get("track") != track or evidence.get("status") != "completed" or evidence.get("source_status") not in {"unverified", "verified-calculation", "traditional-interpretation"}:
        raise RoleError("独立证据须有版本、轨道、完成状态和真实 source_status。")
    claims = evidence.get("claims")
    if not isinstance(claims, list) or not claims or any(not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or not isinstance(item.get("text"), str) or not item["text"] or not isinstance(item.get("basis"), list) or not item["basis"] for item in claims):
        raise RoleError("独立证据须保留非空判词与依据清单。")
    for claim in claims:
        for basis in claim["basis"]:
            if not isinstance(basis, str) or not basis.strip():
                raise RoleError("判词依据须是可追溯文件或实际典籍出处。")
            if basis.startswith(("analyses/", "synthesis/", "memories/", "notes/")) or (basis.startswith("calculations/") and not basis.startswith("calculations/" + track + "/")):
                raise RoleError("独立判词不能引用其它术结果或业务笔记。")
            if basis.startswith(("input/", "calculations/")):
                if basis not in files:
                    raise RoleError("判词引用未冻结的输入或计算: " + basis)
                _fingerprint(root, basis)
    result = {"schema_version": 1, "case_id": manifest["case_id"], "track": track, "status": "frozen", "source_status": evidence["source_status"], "contract_sha256": _track_contract(manifest, track), "files": {relative: _fingerprint(root, relative) for relative in files}}
    # 独占创建保证协调者也不能误覆盖已冻结收据。
    with receipt.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def check_case(root: Path, require_frozen: bool = False) -> Dict[str, Any]:
    manifest = load_manifest(root)
    for folder in ("input", "synthesis", "deliverables", "provenance"):
        if not case_path(root, folder).is_dir():
            raise RoleError("命例标准目录缺失: " + folder)
    for name in SYNTHESIS_FILES:
        _fingerprint(root, "synthesis/" + name)
    tracks = {}
    for track in manifest["tracks"]:
        for folder in ("calculations", "analyses", "validation"):
            if not case_path(root, folder + "/" + track).is_dir():
                raise RoleError("命例轨道目录缺失: " + folder + "/" + track)
        for name in ("report.md", "evidence.json"):
            _fingerprint(root, "analyses/" + track + "/" + name)
        path = case_path(root, "provenance/" + track + ".frozen.json")
        if not path.is_file():
            tracks[track] = "pending"
            continue
        receipt = json.loads(path.read_text(encoding="utf-8-sig"))
        expected = _freeze_files(manifest, track, root)
        if receipt.get("schema_version") != 1 or receipt.get("status") != "frozen" or receipt.get("case_id") != manifest.get("case_id") or receipt.get("track") != track or receipt.get("contract_sha256") != _track_contract(manifest, track) or set(receipt.get("files", {})) != set(expected):
            raise RoleError("冻结收据与命例工序结构不匹配: " + track)
        for relative, digest in receipt["files"].items():
            if _fingerprint(root, relative) != digest:
                raise RoleError("冻结后输入、计算或独立结论被修改: " + relative)
        tracks[track] = "frozen"
    if require_frozen and "pending" in tracks.values():
        raise RoleError("尚有独立轨道未冻结，不能加载综合上下文。")
    return {"case_id": manifest.get("case_id"), "status": "frozen" if "pending" not in tracks.values() else "pending", "tracks": tracks}


def prepare_case(role, task, record):
    """只把许可输入与自身计算投影为可用资料，不发整案STATE或目录。"""
    root = record["root"]
    manifest = load_manifest(root, role)
    stage, track = task.get("stage"), task.get("track")
    if stage not in {"blind", "synthesis", "review"}:
        raise RoleError("标准命例必须显式选择 stage=blind、synthesis 或 review。")
    if task.get("workflow") or task.get("dependency_results") or task.get("dependencies"):
        raise RoleError("标准命例不用任意工作流或前序上下文，只接受冻结成果。")
    if task.get("project_root") and Path(task["project_root"]).resolve() != root.resolve():
        raise RoleError("标准命例 project_root 必须与记录正本一致。")
    if stage == "blind":
        if track not in manifest["tracks"]:
            raise RoleError("盲阶段必须显式绑定本案独立轨道。")
        if case_path(root, "provenance/" + track + ".frozen.json").exists():
            raise RoleError("轨道已冻结，禁止重新运行覆盖原判。")
        config = manifest["tracks"][track]
        allowed = list(config["required_inputs"])
        calculations = case_path(root, "calculations/" + track)
        allowed.extend(path.relative_to(root).as_posix() for path in sorted(calculations.rglob("*")) if path.is_file())
        skills = config["skills"]
        output = "outputs/" + track
    elif stage == "synthesis":
        if track:
            raise RoleError("综合阶段不绑定单一轨道。")
        check_case(root, require_frozen=True)
        allowed = list(dict.fromkeys(item for config in manifest["tracks"].values() for item in config["required_inputs"]))
        for name in manifest["tracks"]:
            allowed.extend(_freeze_files(manifest, name, root))
            allowed.append("provenance/" + name + ".frozen.json")
        skills = manifest.get("synthesis_skills", [])
        if not skills:
            raise RoleError("综合阶段未配置完整综合技能。")
        output = "outputs/synthesis"
    else:
        if track:
            raise RoleError("回访阶段以本案显式历史资料为范围，不绑定盲轨道。")
        allowed = [relative for relative in manifest["input_files"] if case_path(root, relative).is_file()]
        allowed.extend(manifest.get("review_files", []))
        skills = manifest.get("review_skills", [])
        if not skills:
            raise RoleError("回访阶段未配置完整 review_skills。")
        output = "outputs/review"
    if task.get("skills") and list(task["skills"]) != list(skills):
        raise RoleError("命例子任务技能由本术清单限定，不能混入其它术。")
    if set(task.get("files", [])) - set(allowed):
        raise RoleError("命例任务尝试读取白名单外资料。")
    chosen = task["files"] if stage == "review" and task.get("files") else allowed
    selected = dict(task, project_root=str(root), files=list(dict.fromkeys(chosen)), skills=list(skills))
    references = list(manifest["tracks"][track].get("reference_files", [])) if stage == "blind" else list(dict.fromkeys(item for config in manifest["tracks"].values() for item in config.get("reference_files", []))) if stage == "synthesis" else []
    for value in task.get("references", []):
        value = _relative(value)
        if not any(value == prefix or value.startswith(prefix + "/") for prefix in manifest.get("reference_roots", [])):
            raise RoleError("任务典籍不在纯资料库准入范围。")
        references.append(value)
    reference_files = []
    for relative in dict.fromkeys(references):
        path = case_path(role.root, relative)
        if path.is_dir():
            reference_files.extend(item for item in sorted(path.rglob("*")) if item.is_file())
        elif path.is_file():
            reference_files.append(path)
        else:
            raise RoleError("获准典籍资料不存在。")
    for path in reference_files:
        case_path(role.root, path.relative_to(role.root).as_posix())
    policy = {"case_id": manifest["case_id"], "stage": stage, "track": track, "read_paths": selected["files"], "output_path": output, "fresh_context_required": True, "method_memory": manifest.get("method_memory"), "blind_context_files": manifest.get("blind_context_files", ["SOUL.md"] if (role.root / "SOUL.md").is_file() else []), "reference_files": [path.relative_to(role.root).as_posix() for path in reference_files], "_reference_paths": [str(path) for path in reference_files], "_source_root": str(root)}
    if stage == "blind":
        policy["artifact_contract"] = {"report.md": "本术完整独立报告", "evidence.json": {"schema_version": 1, "track": track, "status": "completed", "source_status": "unverified|verified-calculation|traditional-interpretation", "claims": [{"id": "判词ID", "text": "独立判词", "basis": ["计算文件或实际典籍出处"]}]}, "calculations/": "本术计算结果和输入口径", "validation/": "本术计算核验与待验台账"}
    elif stage == "synthesis":
        policy["artifact_contract"] = {name: "综合阶段正式正文" for name in SYNTHESIS_FILES}
    else:
        policy["artifact_contract"] = {"report.md": "明确非盲的回访：复用既定原判、核对新事实与实际反馈，保留变更依据", "evidence.json": "可选回访证据与本轮来源记录"}
    for relative in selected["files"]:
        case_path(root, relative)
    policy["source_fingerprints"] = {relative: _fingerprint(root, relative) for relative in selected["files"]}
    return selected, policy


def save_outputs(policy, artifacts: Path):
    """协调者仅接收本轨普通成果；不把快照写回计算或另一轨。"""
    root, track = Path(policy["_source_root"]), policy["track"]
    if policy["stage"] == "blind" and case_path(root, "provenance/" + track + ".frozen.json").exists():
        raise RoleError("冻结轨道不接受覆盖成果。")
    for relative, digest in policy.get("source_fingerprints", {}).items():
        if _fingerprint(root, relative) != digest:
            raise RoleError("准备后原始资料已修改，不能把旧上下文成果写回: " + relative)
    source = artifacts / policy["output_path"]
    case_path(artifacts, policy["output_path"])
    saved = []
    pending = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source).as_posix()
        case_path(source, relative)
        if policy["stage"] == "synthesis":
            if relative not in SYNTHESIS_FILES:
                raise RoleError("综合阶段只回收规定的五项正文。")
            target = "synthesis/" + relative
        elif policy["stage"] == "review":
            target = "validation/case/reviews/" + policy["review_id"] + "/" + relative
            if case_path(root, target).exists():
                raise RoleError("回访轮次已保存，不能覆盖既有回访记录。")
        elif relative in {"report.md", "evidence.json"}:
            target = "analyses/" + track + "/" + relative
        elif relative.startswith(("calculations/", "validation/")):
            folder, remaining = relative.split("/", 1)
            target = folder + "/" + track + "/" + remaining
        else:
            raise RoleError("分术成果路径不属于本轨输出契约。")
        destination = case_path(root, target)
        pending.append((path, destination, target))
    for path, destination, target in pending:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(path.read_bytes())
        saved.append(target)
    return saved
