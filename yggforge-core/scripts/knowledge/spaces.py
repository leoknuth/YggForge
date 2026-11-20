#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""显式知识空间：共享知识与角色长期记忆分别解析和检索。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Dict, Optional, Sequence, Tuple

from knowledge.graph_models import GraphError
from lib.common import deep_merge_dict
from lib.repo_paths import CORE_ROOT, host_generated_root


def load_mapping(path: Path) -> Dict[str, Any]:
    """读取 JSON 兼容 YAML；普通 YAML 使用已有的可选 PyYAML。"""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise GraphError("配置不可读取: {0}".format(path)) from None
    try:
        data = json.loads(text)
    except ValueError:
        try:
            import yaml
        except ImportError as exc:
            raise GraphError("普通 YAML 配置需要 PyYAML，或改用 JSON 兼容 YAML。") from exc
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError:
            raise GraphError("无效 YAML 配置: {0}".format(path)) from None
    if not isinstance(data, dict):
        raise GraphError("配置必须是映射: {0}".format(path))
    return data


def validate_role_id(role_id: str) -> str:
    """角色 ID 不允许路径或大小写别名。"""
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", role_id or "") or len(role_id) > 80:
        raise GraphError("非法角色 ID: {0}".format(role_id))
    return role_id


def normalize_allowed_paths(paths: Optional[Sequence[str]]) -> Optional[Tuple[str, ...]]:
    """允许范围是相对空间根的路径，不把标签或模型声明当权限。"""
    if paths is None:
        return None
    result = []
    for value in paths:
        text = str(value).replace("\\", "/").strip().rstrip("/")
        parts = Path(text).parts
        if not text or Path(text).is_absolute() or ":" in text or ".." in parts or any(c in text for c in "*?["):
            raise GraphError("非法知识路径范围: {0}".format(value))
        if text not in result:
            result.append(text)
    return tuple(result)


@dataclass(frozen=True)
class KnowledgeSpace:
    """固定身份和根目录；config 是本次调用使用的配置副本。"""

    space_id: str
    root: Path
    content_roots: Tuple[str, ...]
    owner_role: str = ""
    allowed_paths: Optional[Tuple[str, ...]] = None
    config: Optional[Dict[str, Any]] = None

    @property
    def note_root(self) -> Path:
        return self.root / ("notes" if self.owner_role else "knowledge")

    @property
    def graph_root(self) -> Path:
        return self.root / "graph"

    def allows(self, relative: str) -> bool:
        text = str(relative).replace("\\", "/")
        if self.allowed_paths is None:
            return True
        return any(text == prefix or text.startswith(prefix + "/") for prefix in self.allowed_paths)


def _defaults(core_root: Path) -> Dict[str, Any]:
    path = core_root / "config/graph.defaults.json"
    return load_mapping(path) if path.exists() else {}


def shared_space(core_root: Optional[Path] = None, allowed_paths: Optional[Sequence[str]] = None) -> KnowledgeSpace:
    """管理者查询默认共享根；角色调用必须传入获准路径子集。"""
    root = Path(core_root or CORE_ROOT).resolve()
    allowed = normalize_allowed_paths(allowed_paths)
    config = _defaults(root)
    config.update({"space_id": "shared", "owner_role": "", "content_roots": ["knowledge", "plugins"], "allowed_paths": list(allowed) if allowed is not None else None, "lock_root": str(root.parent / "yggforge-runtime/locks/graphs"), "staging_root": str(host_generated_root(root.parent) / "scratch/graphs")})
    return KnowledgeSpace("shared", root, ("knowledge", "plugins"), allowed_paths=allowed, config=config)


def role_space(role_id: str, core_root: Optional[Path] = None) -> KnowledgeSpace:
    """角色根由注册目录确定，角色配置不能把图或记忆改到别处。"""
    role_id = validate_role_id(role_id)
    core = Path(core_root or CORE_ROOT).resolve()
    role_dir = core / "roles" / role_id
    root = role_dir / "memories"
    if role_dir.is_symlink() or root.is_symlink():
        raise GraphError("角色目录或记忆根不能是链接。")
    try:
        role_dir.resolve().relative_to((core / "roles").resolve())
    except ValueError as exc:
        raise GraphError("角色目录越界。") from exc
    config_path = role_dir / "role.yaml"
    if not config_path.is_file():
        raise GraphError("角色未注册: {0}".format(role_id))
    role = load_mapping(config_path)
    if role.get("id") != role_id:
        raise GraphError("角色 ID 与目录不一致。")
    config = _defaults(core)
    override = role.get("graph", {})
    if not isinstance(override, dict):
        raise GraphError("角色 graph 配置必须是映射。")
    if set(override) - {"default_hop", "entry_related_hops", "max_tag_nodes", "weight", "storage"}:
        raise GraphError("角色 graph 只允许查询权重和存储参数，不能改变目录。")
    config = deep_merge_dict(config, deepcopy(override))
    config["paths"] = {"tag_graph": "graph/tag-graph.yaml", "tag_synonyms": "graph/tag-synonyms.yaml", "catalog_dir": "graph/catalog", "tag_inverted_dir": "graph/tag-inverted"}
    config.update({"space_id": "role:" + role_id, "owner_role": role_id, "content_roots": ["notes"], "allowed_paths": None, "include_inbox": True, "lock_root": str(core.parent / "yggforge-runtime/locks/graphs"), "staging_root": str(host_generated_root(core.parent) / "scratch/graphs")})
    return KnowledgeSpace("role:" + role_id, root.resolve(), ("notes",), owner_role=role_id, config=config)


def shared_space_for_role(role_id: str, core_root: Optional[Path] = None) -> KnowledgeSpace:
    """共享读取须同时符合管理者白名单和本角色选择，配置不能借链接扩权。"""
    private = role_space(role_id, core_root)
    core = Path(core_root or CORE_ROOT).resolve()
    role = load_mapping(core / "roles" / private.owner_role / "role.yaml")
    defaults = core / "config/roles.defaults.json"
    if not defaults.is_file():
        raise GraphError("缺少角色共享范围配置: {0}".format(defaults))
    policy = load_mapping(defaults)
    allowed = normalize_allowed_paths(policy.get("allowed_shared_paths", [])) or ()
    requested = normalize_allowed_paths(role.get("shared_paths", [])) or ()
    for value in requested:
        if value.split("/", 1)[0] not in {"knowledge", "plugins"}:
            raise GraphError("角色共享范围只能位于 knowledge 或 plugins。")
        if not any(value == prefix or value.startswith(prefix + "/") for prefix in allowed):
            raise GraphError("角色共享范围超出管理者许可: {0}".format(value))
        try:
            real = (core / value).resolve().relative_to(core).as_posix()
        except ValueError as exc:
            raise GraphError("共享范围链接越界。") from exc
        if real.split("/", 1)[0] not in {"knowledge", "plugins"}:
            raise GraphError("共享范围不能链接到角色私有目录。")
    return shared_space(core, requested)


def associate_payload(space: KnowledgeSpace, tags: Sequence[str], **kwargs) -> Dict[str, Any]:
    """将已绑定空间的命中转为上下文包，不合并不同来源的身份。"""
    from knowledge.graph_query import KnowledgeGraphIndex
    hits, meta = KnowledgeGraphIndex(space=space).associate(tags, **kwargs)
    return {"meta": meta, "hits": [
        {"space_id": space.space_id, "id": hit.entry.id, "path": hit.entry.path,
         "type": hit.entry.kind, "title": hit.entry.title, "tags": hit.entry.tags,
         "related": hit.entry.related, "priority": hit.entry.priority,
         "status": hit.entry.status, "confidence": hit.entry.confidence,
         "last_reviewed": hit.entry.last_reviewed, "index_stale": hit.entry.index_stale,
         "via_tags": hit.via_tags, "min_tag_hop": hit.min_tag_hop,
         "from_entry_related": hit.from_entry_related, "path_strength": hit.path_strength,
         "path_cost": hit.path_cost if hit.path_cost != float("inf") else None,
         "via_path": hit.via_path}
        for hit in hits]}
