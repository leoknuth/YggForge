#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""记忆后端工厂与配置加载。

按 ``config/memory.defaults.json``（+ 本机 ``memory.local.json`` 覆盖）选择记忆
后端实现，当前唯一支持 ``file`` 类型（``backends.file_backend.FileMemoryBackend``）。

工厂与实现分离：本模块只负责读配置 + 实例化，存储/检索逻辑在 ``file_backend``。
调用方统一用 ``get_memory_backend()`` 拿后端，不直接 import 具体实现——这样将来
新增后端类型（如 sqlite/向量库）时调用方无需改动，只需在本工厂里分支实例化。

配置结构（``memory.defaults.json``）::

    {
      "backend": { "type": "file" },
      ...其余键交给 FileMemoryBackend 解释...
    }

本机 ``memory.local.json`` 深合并覆盖默认，用于切后端或调参而不动仓库默认。
"""

from typing import Any, Dict

from backends.file_backend import FileMemoryBackend
from lib.common import deep_merge_dict, load_json
from lib.repo_paths import CORE_ROOT, RUNTIME_ROOT, ensure_layout


MEMORY_CONFIG_PATH = CORE_ROOT / "config" / "memory.defaults.json"
LOCAL_MEMORY_CONFIG_PATH = RUNTIME_ROOT / "config" / "memory.local.json"


class MemoryBackendError(RuntimeError):
    """不支持的记忆后端类型或配置错误。"""


def load_memory_config() -> Dict[str, Any]:
    """加载记忆后端配置：仓库 defaults + 本机 local 深合并。"""
    config: Dict[str, Any] = {}
    if MEMORY_CONFIG_PATH.exists():
        config = load_json(MEMORY_CONFIG_PATH)
    if LOCAL_MEMORY_CONFIG_PATH.exists():
        config = deep_merge_dict(config, load_json(LOCAL_MEMORY_CONFIG_PATH))
    return config


def get_memory_backend() -> FileMemoryBackend:
    """按配置实例化记忆后端。当前仅支持 ``file`` 类型，否则抛 MemoryBackendError。"""
    ensure_layout()
    config = load_memory_config()
    backend_type = str(config.get("backend", {}).get("type", "file")).strip().lower()
    if backend_type != "file":
        raise MemoryBackendError("Unsupported memory backend type: {0}".format(backend_type))
    return FileMemoryBackend(CORE_ROOT, config, runtime_root=RUNTIME_ROOT)
