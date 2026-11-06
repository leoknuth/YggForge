#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台部署工具：link / copy / render + 反向 import + 部署清单。

把 ``yggforge-core`` 整包投影到 Agent 家目录（如 ``~/.cursor/yggforge-core``），
并叠加薄入口（AGENTS.md / rules / hooks）。由 ``ygg deploy|import|status`` 或
兼容包装 ``deploy.ps1|sh`` 调用。

- link：symlink/junction（Windows 跨盘单文件可退化为 copy）
- copy：整份复制
- render：先渲染到 generated，再 copy 到目标
- import：仅 copy/render 有意义；link 模式改动已在仓库，import 为 no-op
"""

from pathlib import Path
import sys

# cmds/<domain>/<script>.py → scripts/
SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
SCRIPT_DIR = SCRIPTS_ROOT

import argparse
import difflib
import filecmp
import hashlib
import json
import os
import shutil
import stat
import time
import subprocess
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".ps1",
    ".sh",
    ".py",
}

ALLOWED_IMPORT_PREFIXES = (
    "yggforge-core/profiles/",
    "yggforge-core/knowledge/",
    "profiles/",
    "knowledge/",
    "docs/",
)

class MappingSpec(object):
    def __init__(self, name: str, source: str, target: str) -> None:
        self.name = name
        self.source = source
        self.target = target

class DeploySpec(object):
    def __init__(self, enabled: bool, profile: str, mappings: List[MappingSpec]) -> None:
        self.enabled = enabled
        self.profile = profile
        self.mappings = mappings

class DeployError(RuntimeError):
    pass

from lib.repo_paths import CORE_ROOT, GENERATED_ROOT, REPO_ROOT, RUNTIME_ROOT, resolve_core_source  # noqa: E402

CONFIG_PATH = CORE_ROOT / "config" / "deploy.defaults.json"
LOCAL_CONFIG_PATH = RUNTIME_ROOT / "config" / "deploy.local.json"
MANIFEST_ROOT = GENERATED_ROOT / "deploy-manifests"
RENDER_ROOT = GENERATED_ROOT / "rendered"
IMPORT_ROOT = GENERATED_ROOT / "imports"

from lib.common import deep_merge_dict, load_json

def current_platform_key() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "darwin"
    return sys.platform

def mapping_from_raw(
    raw_mapping: Dict[str, Any],
    platform: str,
    index: int = 0,
    scope: str = "user",
) -> Optional[MappingSpec]:
    # 平台特定 source（可选）：sources: {windows: "...", linux: "..."}
    # 用于需要按平台选用不同真源文件的 mapping（如 cursor 的 hooks_config：
    # Windows 用 py launcher、Linux 用 python3 的 hooks.json）。
    raw_sources = raw_mapping.get("sources", {})
    source = raw_mapping.get("source")
    if raw_sources:
        if platform not in raw_sources:
            raise DeployError(
                "Mapping '{0}' does not define a source for platform '{1}'.".format(
                    raw_mapping.get("name", index), platform
                )
            )
        source = raw_sources[platform]
    if not source:
        raise DeployError(
            "Mapping '{0}' is missing source information.".format(raw_mapping.get("name", index))
        )

    # scope=user 用 targets/target；scope=project 用 project_targets/project_target。
    # 某 scope 下无 target → 返回 None（该 mapping 不适用于此 scope，跳过）。
    if scope == "project":
        raw_targets = raw_mapping.get("project_targets", {})
        target = raw_mapping.get("project_target")
    else:
        raw_targets = raw_mapping.get("targets", {})
        target = raw_mapping.get("target")
    if raw_targets:
        if platform not in raw_targets:
            return None
        target = raw_targets[platform]
    if not target:
        return None
    return MappingSpec(
        name=str(raw_mapping.get("name", "mapping_{0}".format(index))),
        source=str(source),
        target=str(target),
    )

def normalize_mappings(value: Dict[str, Any], platform: str, scope: str = "user") -> List[MappingSpec]:
    mappings: List[MappingSpec] = []

    # 整包核心：优先部署，避免散落在 Agent 家目录根下。
    # 项目级 scope 通常不部署整包（整包留在用户级），故 core_bundle 无 project_targets 时自然跳过。
    raw_core = value.get("core_bundle")
    if isinstance(raw_core, dict):
        core = dict(raw_core)
        core.setdefault("name", "yggforge_core")
        core.setdefault("source", ".")
        spec = mapping_from_raw(core, platform, index=-1, scope=scope)
        if spec is not None:
            mappings.append(spec)

    if "mappings" in value:
        for index, raw_mapping in enumerate(value["mappings"]):
            spec = mapping_from_raw(raw_mapping, platform, index=index, scope=scope)
            if spec is not None:
                mappings.append(spec)
        if mappings:
            return mappings

    if scope == "user" and "source" in value and "target" in value:
        mappings.append(
            MappingSpec(
                name="default",
                source=str(value["source"]),
                target=str(value["target"]),
            )
        )
        return mappings

    if mappings:
        return mappings

    raise DeployError(
        "Invalid deploy config entry: expected 'core_bundle', 'mappings', or 'source' + 'target'."
    )

def load_config(scope: str = "user") -> Dict[str, DeploySpec]:
    raw = {}
    if CONFIG_PATH.exists():
        raw = load_json(CONFIG_PATH)
    if LOCAL_CONFIG_PATH.exists():
        raw = deep_merge_dict(raw, load_json(LOCAL_CONFIG_PATH))

    platform = current_platform_key()
    config = {}
    for key, value in raw.items():
        config[key] = DeploySpec(
            enabled=bool(value.get("enabled", False)),
            profile=str(value["profile"]),
            mappings=normalize_mappings(value, platform, scope=scope),
        )
    return config

def ensure_generated_layout() -> None:
    from lib.repo_paths import ensure_layout

    ensure_layout()
    MANIFEST_ROOT.mkdir(parents=True, exist_ok=True)
    RENDER_ROOT.mkdir(parents=True, exist_ok=True)
    IMPORT_ROOT.mkdir(parents=True, exist_ok=True)

def manifest_path(target: str) -> Path:
    return MANIFEST_ROOT / "{0}.json".format(target)

def read_manifest(target: str) -> Optional[Dict[str, Any]]:
    path = manifest_path(target)
    if not path.exists():
        return None
    return load_json(path)

def write_manifest(
    target: str,
    spec: DeploySpec,
    action: str,
    mode: str,
    operations: List[Dict[str, Any]],
    scope: str = "user",
    project_root: Optional[Path] = None,
) -> None:
    ensure_generated_layout()
    payload = {
        "target": target,
        "profile": spec.profile,
        "action": action,
        "mode": mode,
        "scope": scope,
        "project_root": normalized_path(project_root) if project_root else None,
        "requires_import": any(item.get("actual_mode", mode) != "link" for item in operations),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "mappings": operations,
    }
    path = manifest_path(target)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def expand_target_path(raw: str, project_root: Optional[Path] = None) -> Path:
    text = raw
    if project_root is not None and text.startswith("<project>"):
        text = str(project_root) + text[len("<project>"):]
    return Path(os.path.abspath(os.path.expandvars(os.path.expanduser(text))))

def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

def repo_relative(path: Path) -> Optional[Path]:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return None

def normalized_path(path: Path) -> str:
    """规范化清单身份；Windows 路径比较忽略大小写。"""
    return os.path.normcase(str(path.resolve()))

def assert_import_allowed(destination: Path) -> None:
    rel = repo_relative(destination)
    if rel is None:
        raise DeployError("Import destination is outside the repository: {0}".format(destination))
    rel_text = rel.as_posix()
    if rel_text == "yggforge-generated/imports" or rel_text.startswith("yggforge-generated/imports/"):
        return
    for prefix in ALLOWED_IMPORT_PREFIXES:
        if rel_text == prefix.rstrip("/") or rel_text.startswith(prefix):
            return
    raise DeployError(
        "Import destination '{0}' is not in the allowed prefixes: {1}".format(
            rel_text, ", ".join(ALLOWED_IMPORT_PREFIXES)
        )
    )

def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    try:
        path.read_text(encoding="utf-8-sig")
        return True
    except Exception:
        return False

def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def render_output_path(target_name: str, mapping_name: str, source: Path) -> Path:
    return RENDER_ROOT / target_name / mapping_name / source.name

def import_review_path(target_name: str, mapping_name: str, source: Path) -> Path:
    return IMPORT_ROOT / target_name / mapping_name / source.name

def build_rendered_text(source: Path, target_name: str, mapping_name: str, original_text: str) -> str:
    rel = repo_relative(source)
    rel_text = rel.as_posix() if rel else str(source)
    lines = [
        "# Rendered Entrypoint",
        "",
        "This file is generated by `YggForge` render mode.",
        "",
        "- target: `{0}`".format(target_name),
        "- mapping: `{0}`".format(mapping_name),
        "- canonical source: `{0}`".format(rel_text),
        "- generated at: `{0}`".format(datetime.now().isoformat(timespec="seconds")),
        "",
        "Edit the canonical source file instead of editing this rendered file directly.",
        "",
        "---",
        "",
    ]
    return "\n".join(lines) + original_text

def render_source(source: Path, target_name: str, mapping_name: str) -> Path:
    rendered_path = render_output_path(target_name, mapping_name, source)
    ensure_parent(rendered_path)

    if source.is_dir():
        if rendered_path.exists():
            shutil.rmtree(str(rendered_path))
        shutil.copytree(str(source), str(rendered_path))
        return rendered_path

    # 只有 Markdown 入口允许增加说明，配置和脚本保持原格式与字节内容。
    if source.suffix.lower() == ".md":
        original_text = read_text_file(source)
        rendered_text = build_rendered_text(source, target_name, mapping_name, original_text)
        rendered_path.write_text(rendered_text, encoding="utf-8-sig")
        return rendered_path

    shutil.copy2(str(source), str(rendered_path))
    return rendered_path

def backup_target(target: Path) -> None:
    """把将被覆盖的目标移到 yggforge-runtime/deploy-backups/<ts>/。"""
    if not target.exists() and not target.is_symlink():
        return
    from lib.repo_paths import RUNTIME_ROOT
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = RUNTIME_ROOT / "deploy-backups" / ts
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / target.name
    if dest.exists():
        dest = backup_dir / "{0}-{1}".format(target.name, int(time.time() * 1000) % 10000)
    shutil.move(str(target), str(dest))
    print("  backup  : {0} -> {1}".format(target, dest))

def copy_deployment(source: Path, target: Path, backup: bool = False) -> None:
    # 同一棵树不能同时作为复制源和覆盖目标，避免自删或递归复制。
    source_path, target_path = source.resolve(), target.resolve()
    if source_path == target_path or source_path in target_path.parents or target_path in source_path.parents:
        raise DeployError("Deployment source and target overlap: {0}".format(target))
    ensure_parent(target)
    if _is_link_like(target):
        raise DeployError(
            "Refusing to copy onto an existing symlink target: {0}. Remove it first or use link mode.".format(target)
        )
    if source.is_dir():
        if target.exists():
            if backup:
                backup_target(target)
            else:
                shutil.rmtree(str(target))
        shutil.copytree(str(source), str(target))
    else:
        if target.exists() and backup:
            backup_target(target)
        shutil.copy2(str(source), str(target))
    print("  copied  : {0}".format(target))

def _is_link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    if not sys.platform.startswith("win"):
        return False
    try:
        attrs = path.lstat().st_file_attributes  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False
    return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)

def link_deployment(source: Path, target: Path, backup: bool = False) -> str:
    source = source.resolve()

    # 正确的现有链接先辨认，随后对真实路径检查重叠；备份前不能移动源树。
    target_path = target.resolve()
    if _is_link_like(target) and target_path == source:
        print("  skip    : target already linked -> {0}".format(target))
        return "link"
    if source.is_file() and target.is_file() and os.path.samefile(str(source), str(target)):
        print("  skip    : target already shares source -> {0}".format(target))
        return "link"
    if source == target_path or source in target_path.parents or target_path in source.parents:
        raise DeployError("Deployment source and target overlap: {0}".format(target))
    ensure_parent(target)

    if _is_link_like(target):
        try:
            current = target.resolve()
        except OSError:
            current = None
        if current == source:
            print("  skip    : target already linked -> {0}".format(target))
            return "link"
        # stale link: remove or backup
        if backup:
            backup_target(target)
        elif target.is_symlink():
            target.unlink()
        elif target.is_dir():
            target.rmdir()
        else:
            target.unlink()
        print("  relink  : removing stale link -> {0}".format(target))
    elif target.exists():
        # 目标已存在且不是 link
        if source.is_file() and target.is_file() and file_is_identical(source, target):
            print("  skip    : target already matches source (copy fallback) -> {0}".format(target))
            return "link" if os.path.samefile(str(source), str(target)) else "copy"
        if backup:
            backup_target(target)
        else:
            raise DeployError(
                "Target already exists and is not a symlink/junction: {0}. "
                "Content differs from source; remove it manually, use copy mode, or use --backup.".format(target)
            )

    try:
        target.symlink_to(source, target_is_directory=source.is_dir())
        print("  linked  : {0}".format(target))
        return "link"
    except OSError as symlink_exc:
        if sys.platform.startswith("win") and source.is_dir():
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print("  junction: {0}".format(target))
                return "link"
            detail = (result.stderr or result.stdout or "").strip()
            raise DeployError(
                "Failed to create junction {0} -> {1}: {2}".format(
                    target, source, detail or "mklink failed"
                )
            ) from symlink_exc

        # 文件：尝试硬链接（同卷）；跨盘或不支持时退化复制并提示
        if source.is_file():
            try:
                os.link(str(source), str(target))
                print("  hardlink: {0}".format(target))
                return "link"
            except OSError:
                shutil.copy2(str(source), str(target))
                print(
                    "  copied  : {0} (symlink privilege unavailable; edits will not auto-flow back)".format(
                        target
                    )
                )
                return "copy"

        raise DeployError(
            "Failed to create link {0} -> {1}: {2}".format(target, source, symlink_exc)
        ) from symlink_exc

def file_is_identical(left: Path, right: Path) -> bool:
    if not left.exists() or not right.exists():
        return False
    if left.is_dir() or right.is_dir():
        return False
    return filecmp.cmp(str(left), str(right), shallow=False)

def preview_text_diff(destination: Path, target: Path, preview_lines: int) -> None:
    old_text = read_text_file(destination).splitlines()
    new_text = read_text_file(target).splitlines()
    diff = list(
        difflib.unified_diff(
            old_text,
            new_text,
            fromfile=str(destination),
            tofile=str(target),
            lineterm="",
        )
    )
    if not diff:
        print("  preview : no textual diff detected")
        return

    print("  preview : showing first {0} diff lines".format(preview_lines))
    for line in diff[:preview_lines]:
        print("    {0}".format(line))
    if len(diff) > preview_lines:
        print("    ... ({0} more diff lines omitted)".format(len(diff) - preview_lines))

def preview_import(destination: Path, target: Path, preview_lines: int) -> bool:
    if not target.exists():
        raise DeployError("Target path does not exist: {0}".format(target))

    if target.is_dir():
        if destination.exists():
            print("  preview : directory import into existing path -> {0}".format(destination))
        else:
            print("  preview : directory import into new path -> {0}".format(destination))
        return False

    if destination.exists():
        if file_is_identical(destination, target):
            print("  no-op   : destination already matches target -> {0}".format(destination))
            return True
        if is_text_file(destination) and is_text_file(target):
            preview_text_diff(destination, target, preview_lines)
        else:
            print("  preview : binary or non-text file will be replaced -> {0}".format(destination))
    else:
        print("  preview : destination does not exist yet -> {0}".format(destination))
        if is_text_file(target):
            preview_text_diff_text_only(target, preview_lines)

    return False

def preview_text_diff_text_only(target: Path, preview_lines: int) -> None:
    lines = read_text_file(target).splitlines()
    print("  preview : showing first {0} content lines from new file".format(preview_lines))
    for line in lines[:preview_lines]:
        print("    + {0}".format(line))
    if len(lines) > preview_lines:
        print("    ... ({0} more content lines omitted)".format(len(lines) - preview_lines))

def snapshot_path(path: Path) -> Dict[str, str]:
    """记录文件摘要和目录类型；导入树内的链接不作为可写内容接受。"""
    result: Dict[str, str] = {}

    def visit(current: Path, relative: str) -> None:
        if _is_link_like(current):
            raise DeployError("Import tree contains a link: {0}".format(current))
        if current.is_dir():
            result[relative] = "directory"
            for child in sorted(current.iterdir()):
                visit(child, relative + "/" + child.name if relative else child.name)
        elif current.is_file():
            digest = hashlib.sha256()
            with current.open("rb") as handle:
                for block in iter(lambda: handle.read(65536), b""):
                    digest.update(block)
            result[relative] = "file:" + digest.hexdigest()
        elif current.exists():
            raise DeployError("Unsupported import entry: {0}".format(current))

    visit(path, "")
    return result

def validate_snapshot(snapshot: Dict[str, str]) -> None:
    """拒绝清单中的绝对路径和向上跳转，避免暂存计划越界。"""
    if not isinstance(snapshot, dict):
        raise DeployError("Invalid deployment baseline; redeploy after saving target edits.")
    for name, signature in snapshot.items():
        if not isinstance(name, str) or not isinstance(signature, str):
            raise DeployError("Invalid deployment baseline.")
        if name and (Path(name).is_absolute() or "\\" in name or any(part in ("", ".", "..") for part in name.split("/"))):
            raise DeployError("Unsafe path in deployment baseline.")

def prepare_import_plan(target: Path, destination: Path, baseline: Optional[Dict[str, str]]) -> Dict[str, Any]:
    """三方比较部署基线、副本和真源，只接纳副本发生的变化。"""
    assert_import_allowed(destination)
    incoming = snapshot_path(target)
    current = snapshot_path(destination)
    if baseline is None:
        # 旧清单没有基线时只能安全接纳完全一致的内容；render 仅写复核区。
        rel = repo_relative(destination)
        review = rel is not None and rel.as_posix().startswith("yggforge-generated/imports/")
        if not review and incoming != current:
            raise DeployError("No deployment baseline for {0}; save target edits and redeploy before import.".format(destination))
        desired = dict(incoming)
        changes = {name: incoming.get(name) for name in set(incoming) | set(current) if incoming.get(name) != current.get(name)}
    else:
        validate_snapshot(baseline)
        changes = {}
        conflicts = []
        for name in sorted(set(baseline) | set(incoming)):
            before, after, actual = baseline.get(name), incoming.get(name), current.get(name)
            if before == after:
                continue
            if actual not in (before, after):
                conflicts.append(name or "<root>")
                continue
            if before == "directory" and after != "directory":
                def subtree(tree: Dict[str, str]) -> Dict[str, str]:
                    return {key: value for key, value in tree.items() if key == name or not name or key.startswith(name + "/")}
                if subtree(current) not in (subtree(baseline), subtree(incoming)):
                    conflicts.append(name or "<root>")
                    continue
            changes[name] = after
        if conflicts:
            raise DeployError("Import conflict at {0}: {1}".format(destination, ", ".join(conflicts)))
        desired = dict(current)
        for name, signature in changes.items():
            if signature is None:
                desired.pop(name, None)
            else:
                desired[name] = signature
    # 文件/目录类型转换不能悄悄删除真源独有的后代。
    for name, signature in desired.items():
        if name and desired.get("") != "directory":
            raise DeployError("Import conflict: root type changed at {0}".format(destination))
        for parent in Path(name).parents:
            parent_name = parent.as_posix()
            if parent_name == ".":
                continue
            if desired.get(parent_name) != "directory":
                raise DeployError("Import conflict: parent type changed at {0}".format(destination / parent_name))
        if signature != "directory" and any(key.startswith(name + "/") for key in desired if name):
            raise DeployError("Import conflict: directory contents changed at {0}".format(destination / name))
    return {"target": target, "destination": destination, "incoming": incoming, "current": current, "desired": desired, "changes": changes}

def apply_import_plan(plan: Dict[str, Any]) -> None:
    """先在同卷暂存完整结果，再替换；替换失败恢复旧目录。"""
    if plan["desired"] == plan["current"]:
        return
    target, destination = plan["target"], plan["destination"]
    ensure_parent(destination)
    temporary = Path(tempfile.mkdtemp(prefix=".ygg-import-", dir=str(destination.parent)))
    staged, previous = temporary / "incoming", temporary / "previous"
    cleanup = True
    try:
        for name, signature in sorted(plan["desired"].items(), key=lambda item: (item[0].count("/"), item[0])):
            output = staged / name if name else staged
            if signature == "directory":
                output.mkdir(parents=True, exist_ok=True)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                source_root = target if name in plan["changes"] else destination
                shutil.copy2(str(source_root / name if name else source_root), str(output))
        if snapshot_path(staged) != plan["desired"] or snapshot_path(destination) != plan["current"]:
            raise DeployError("Import inputs changed while staging; retry after reviewing {0}.".format(destination))
        if destination.exists():
            os.replace(str(destination), str(previous))
        try:
            if staged.exists():
                os.replace(str(staged), str(destination))
        except OSError as exc:
            if previous.exists():
                try:
                    os.replace(str(previous), str(destination))
                except OSError:
                    cleanup = False
                    raise DeployError("Import failed; recovery copy retained at {0}.".format(previous)) from exc
            raise DeployError("Import replacement failed; original restored: {0}".format(destination)) from exc
    finally:
        if cleanup:
            shutil.rmtree(str(temporary))

def copy_into_destination(target: Path, destination: Path, baseline: Optional[Dict[str, str]] = None) -> None:
    apply_import_plan(prepare_import_plan(target, destination, baseline))

def find_manifest_mapping(last_manifest: Dict[str, Any], mapping_name: str) -> Optional[Dict[str, Any]]:
    for item in last_manifest.get("mappings", []):
        if item.get("name") == mapping_name:
            return item
    return None

def import_from_target(
    target: Path,
    mapping_name: str,
    target_name: str,
    last_manifest: Optional[Dict[str, Any]],
    preview_lines: int,
    preview_only: bool,
    collected_plans: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Path]:
    if not last_manifest:
        raise DeployError("No deployment manifest found for '{0}'. Import requires a prior deploy.".format(target_name))
    manifest_mapping = find_manifest_mapping(last_manifest, mapping_name)
    if not manifest_mapping:
        raise DeployError(
            "No manifest entry found for mapping '{0}' in target '{1}'.".format(mapping_name, target_name)
        )

    if normalized_path(target) != normalized_path(Path(manifest_mapping["target_path"])):
        raise DeployError("Deployment target identity changed; refusing import for {0}.".format(mapping_name))
    canonical = Path(manifest_mapping["canonical_source"])
    mode = manifest_mapping.get("actual_mode", last_manifest.get("mode"))
    if mode == "link":
        if target.exists() and canonical.exists() and os.path.samefile(str(target), str(canonical)):
            print("  no-op   : mapping '{0}' still links to the canonical source".format(mapping_name))
            return None
        raise DeployError("Linked mapping no longer shares its source; save target edits and redeploy: {0}".format(target))
    destination = Path(manifest_mapping["import_destination"])
    expected = import_review_path(target_name, mapping_name, canonical) if mode == "render" else canonical
    if normalized_path(destination) != normalized_path(expected):
        raise DeployError("Import destination identity does not match deployment mode.")
    if not target.exists():
        raise DeployError("Target path does not exist: {0}".format(target))
    roots = manifest_mapping.get("import_roots")
    if normalized_path(canonical) == normalized_path(CORE_ROOT) and mode == "copy":
        if roots is None:
            raise DeployError("Core copy manifest lacks subtree baselines; save target edits and redeploy.")
        plans = []
        for root in roots:
            relative = root["relative"]
            if relative not in ("knowledge", "profiles"):
                raise DeployError("Core bundle import contains a forbidden subtree.")
            plans.append(prepare_import_plan(target / relative, CORE_ROOT / relative, root.get("baseline")))
    else:
        baseline = manifest_mapping.get("review_baseline") if mode == "render" else manifest_mapping.get("baseline")
        plans = [prepare_import_plan(target, destination, baseline)]
    for plan in plans:
        print("  preview : {0} changed entries -> {1}".format(len(plan["changes"]), plan["destination"]))
    if collected_plans is not None:
        collected_plans.extend(plans)
    if preview_only:
        return destination
    for plan in plans:
        apply_import_plan(plan)
    if roots is not None and mode == "copy":
        for root, plan in zip(roots, plans):
            root["baseline"] = plan["incoming"]
    else:
        manifest_mapping["baseline"] = plans[0]["incoming"]
        if mode == "render":
            manifest_mapping["review_baseline"] = plans[0]["incoming"]
    print("  imported: {0} -> {1}".format(target, destination))
    return destination

def validate_shared_changes(plans: List[Dict[str, Any]]) -> None:
    """整包和薄入口可能指向同一真源，先拒绝互相矛盾的副本改动。"""
    changes: Dict[str, Optional[str]] = {}
    for plan in plans:
        for name, signature in plan["changes"].items():
            path = normalized_path(plan["destination"] / name if name else plan["destination"])
            if path in changes and changes[path] != signature:
                raise DeployError("Import conflict between deployed copies at {0}".format(path))
            changes[path] = signature
    for path, signature in changes.items():
        if signature != "directory" and any(path != child and value is not None and Path(path) in Path(child).parents for child, value in changes.items()):
            raise DeployError("Import conflict between parent and child mappings at {0}".format(path))

def manifest_key(target_name: str, scope: str, project_root: Optional[Path] = None) -> str:
    if scope != "project":
        return target_name
    if project_root is None:
        raise DeployError("Project deployment manifest requires a project root.")
    digest = hashlib.sha256(normalized_path(project_root).encode("utf-8")).hexdigest()[:16]
    return "{0}@project-{1}".format(target_name, digest)

def resolve_project_root(raw: Optional[str]) -> Path:
    if raw:
        return Path(os.path.expandvars(os.path.expanduser(raw))).resolve()
    return Path.cwd().resolve()

def show_status(target_name: str, spec: DeploySpec, scope: str = "user", project_root: Optional[Path] = None) -> None:
    mkey = manifest_key(target_name, scope, project_root)
    last_manifest = read_manifest(mkey)
    print()
    print("[{0}] scope={1}".format(target_name, scope))
    print("  profile         : {0}".format(spec.profile))
    print("  enabled         : {0}".format(spec.enabled))
    if last_manifest:
        print("  last_action     : {0}".format(last_manifest.get("action")))
        print("  last_mode       : {0}".format(last_manifest.get("mode")))
        print("  last_updated_at : {0}".format(last_manifest.get("updated_at")))
    else:
        print("  last_action     : <none>")
        print("  last_mode       : <none>")
        print("  last_updated_at : <none>")

    print("  core_root       : {0}".format(CORE_ROOT))
    print("  repo_root       : {0}".format(REPO_ROOT))
    if scope == "project":
        print("  project_root    : {0}".format(project_root))
    for mapping in spec.mappings:
        source = resolve_core_source(mapping.source)
        target = expand_target_path(mapping.target, project_root=project_root if scope == "project" else None)
        print("  mapping         : {0}".format(mapping.name))
        print("    source        : {0}".format(source))
        print("    target        : {0}".format(target))
        print("    source_exists : {0}".format(source.exists()))
        print("    target_exists : {0}".format(target.exists() or target.is_symlink() or _is_link_like(target)))
        print("    target_is_link: {0}".format(_is_link_like(target)))
        if _is_link_like(target):
            try:
                print("    target_link_to: {0}".format(target.resolve()))
            except OSError as exc:
                print("    target_link_to: <unresolvable: {0}>".format(exc))

def print_preview(target_name: str, action: str, mode: str, spec: DeploySpec, scope: str = "user") -> None:
    print()
    print("[{0}] action={1} mode={2} scope={3}".format(target_name, action, mode, scope))
    print("  profile : {0}".format(spec.profile))
    print("  enabled : {0}".format(spec.enabled))
    print("  core    : {0}".format(CORE_ROOT))
    print("  mappings: {0}".format(len(spec.mappings)))
    for mapping in spec.mappings:
        print("    - {0}: {1} -> {2}".format(mapping.name, mapping.source, mapping.target))


def _check_deps_for_deploy(install: bool) -> None:
    """部署前检测依赖；缺失时提示或自动补装（经 behavior 门禁 deps.install）。

    非阻塞：仅提示/补装，不中止部署（依赖缺失有回退解析器，部署本身不依赖 PyYAML）。
    """
    from lib.deps import install_missing, missing_deps

    missing = missing_deps()
    if not missing:
        return
    print("deps_check      : 缺失推荐依赖 {0}".format(", ".join(missing)), flush=True)
    if not install:
        print("deps_hint       : 运行 `ygg doctor --fix-deps` 补装，或 `ygg deploy ... --install-deps`", flush=True)
        return
    # 自动补装：经 behavior 门禁
    from policies.behavior import authorize

    decision = authorize(
        "deps.install",
        "部署前 pip install 缺失依赖：{0}".format(", ".join(missing)),
        force=None,
    )
    if not decision.get("allowed"):
        print("deps_check      : 跳过自动补装（{0}）；继续部署".format(decision.get("reason", "denied")), flush=True)
        return
    code, _installed = install_missing(only_missing=True)
    if code == 0:
        print("deps_check      : 依赖补装完成", flush=True)
    else:
        print("deps_check      : 依赖补装失败（pip 返回 {0}）；继续部署（有回退解析器）".format(code), flush=True)


def run(args: argparse.Namespace) -> int:
    dry_run = bool(getattr(args, "dry_run", False)) or (args.action == "deploy" and bool(args.preview_only))
    if not dry_run and args.action != "status" and not args.preview_only:
        ensure_generated_layout()
    # 部署前依赖检测（仅 deploy 动作；status/import 不检）
    if getattr(args, "action", "") == "deploy" and not dry_run:
        _check_deps_for_deploy(install=bool(getattr(args, "install_deps", False)))
    scope = getattr(args, "scope", "user") or "user"
    project_root = resolve_project_root(getattr(args, "project_root", None)) if scope == "project" else None
    config = load_config(scope=scope)

    for target_name in args.targets:
        if target_name not in config:
            raise DeployError("Unknown deployment target: {0}".format(target_name))

        spec = config[target_name]
        if args.action == "status":
            show_status(target_name, spec, scope=scope, project_root=project_root)
            continue

        mkey = manifest_key(target_name, scope, project_root)
        last_manifest = read_manifest(mkey)
        if args.action == "import" and last_manifest:
            expected_root = normalized_path(project_root) if project_root else None
            if (last_manifest.get("target") != mkey or last_manifest.get("scope", "user") != scope
                    or last_manifest.get("project_root") != expected_root or last_manifest.get("profile") != spec.profile):
                raise DeployError("Deployment manifest identity does not match this target/project.")
            # 先检查所有映射，避免发现后续冲突之前已经改动前面的真源。
            preflight_plans: List[Dict[str, Any]] = []
            for mapping in spec.mappings:
                item = find_manifest_mapping(last_manifest, mapping.name)
                if item is None or normalized_path(Path(item["canonical_source"])) != normalized_path(resolve_core_source(mapping.source)):
                    raise DeployError("Canonical mapping changed; save target edits and redeploy.")
                import_from_target(expand_target_path(mapping.target, project_root), mapping.name, mkey,
                                   last_manifest, args.preview_lines, True, preflight_plans)
            validate_shared_changes(preflight_plans)
        effective_mode = args.mode
        if args.action == "import" and last_manifest and last_manifest.get("mode"):
            effective_mode = str(last_manifest.get("mode"))

        print_preview(target_name, args.action, effective_mode, spec, scope=scope)
        if not spec.enabled:
            print("  skip    : disabled in config")
            continue

        if not spec.mappings:
            print("  skip    : no mappings for scope={0}".format(scope))
            continue

        operations = []
        for mapping in spec.mappings:
            canonical_source = resolve_core_source(mapping.source)
            target = expand_target_path(mapping.target, project_root=project_root)
            print("  mapping : {0}".format(mapping.name))
            print("    source: {0}".format(canonical_source))
            print("    target: {0}".format(target))

            if dry_run:
                if not canonical_source.exists():
                    raise DeployError("Deployment source does not exist: {0}".format(canonical_source))
                print("    dry_run: would deploy via {0}; no files changed".format(args.mode))
                continue

            if args.action == "deploy":
                if not canonical_source.exists():
                    raise DeployError("Deployment source does not exist: {0}".format(canonical_source))
                deployed_source = canonical_source
                import_destination = canonical_source
                actual_mode = args.mode

                if args.mode == "link":
                    actual_mode = link_deployment(canonical_source, target, backup=args.backup)
                elif args.mode == "copy":
                    copy_deployment(canonical_source, target, backup=args.backup)
                elif args.mode == "render":
                    deployed_source = render_source(canonical_source, mkey, mapping.name)
                    import_destination = import_review_path(mkey, mapping.name, canonical_source)
                    print("    rendered_source: {0}".format(deployed_source))
                    print("    import_review  : {0}".format(import_destination))
                    copy_deployment(deployed_source, target, backup=args.backup)

                operation = {
                        "name": mapping.name,
                        "canonical_source": str(canonical_source),
                        "deployed_source": str(deployed_source),
                        "target_path": str(target),
                        "import_destination": str(import_destination),
                        "actual_mode": actual_mode,
                    }
                if actual_mode != "link":
                    if actual_mode == "copy" and normalized_path(canonical_source) == normalized_path(CORE_ROOT):
                        operation["import_roots"] = [{"relative": name, "baseline": snapshot_path(target / name)} for name in ("knowledge", "profiles")]
                    else:
                        operation["baseline"] = snapshot_path(target)
                operations.append(operation)
                continue

            if args.action == "import":
                destination = import_from_target(
                    target=target,
                    mapping_name=mapping.name,
                    target_name=mkey,
                    last_manifest=last_manifest,
                    preview_lines=args.preview_lines,
                    preview_only=args.preview_only,
                )
                operations.append(dict(find_manifest_mapping(last_manifest, mapping.name)))

        if args.action == "deploy" and not dry_run:
            write_manifest(mkey, spec, args.action, args.mode, operations, scope, project_root)
        elif args.action == "import" and not args.preview_only and not dry_run:
            last_mode = last_manifest["mode"] if last_manifest else args.mode
            effective_action = "import-preview" if args.preview_only else args.action
            write_manifest(mkey, spec, effective_action, last_mode, operations, scope, project_root)

    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cross-platform deployment tool for YggForge.")
    parser.add_argument("--action", choices=["deploy", "import", "status"], default="deploy")
    parser.add_argument("--mode", choices=["link", "copy", "render"], default="link")
    parser.add_argument("--scope", choices=["user", "project"], default="user", help="user=部署到 ~/.<agent>/；project=部署到 <project-root>/.<agent>/ 或 <project-root>/AGENTS.md")
    parser.add_argument("--project-root", default=None, help="项目级部署根目录（默认当前工作目录）")
    parser.add_argument("--targets", nargs="+", default=["cursor"])
    parser.add_argument("--preview-lines", type=int, default=40)
    parser.add_argument("--preview-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不部署、备份、写清单或安装依赖")
    parser.add_argument("--backup", action="store_true", help="覆盖前把旧目标备份到 yggforge-runtime/deploy-backups/<ts>/")
    parser.add_argument("--install-deps", action="store_true", help="部署前自动检测并补装缺失依赖（经 behavior 门禁 deps.install）")
    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return run(args)
    except DeployError as exc:
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
