# -*- coding: utf-8 -*-
"""Memory backend implementations for YggForge.

包级导出工厂与默认文件后端实现。调用方统一用::

    from backends import get_memory_backend

即可拿到后端实例，无需关心具体实现模块（``file_backend``）或工厂模块
（``factory``），便于将来新增后端类型时调用方零改动。
"""

from backends.factory import FileMemoryBackend, MemoryBackendError, get_memory_backend

__all__ = ["get_memory_backend", "FileMemoryBackend", "MemoryBackendError"]
