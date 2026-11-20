# -*- coding: utf-8 -*-
"""YggForge 路径约定：核心包 / 生成物 / 本机运行时。

仓库布局::

    <REPO_ROOT>/
    ├── docs/                      # 人类文档（不部署）
    ├── AGENTS.md / README.md
    ├── ygg.sh / ygg.ps1
    ├── yggforge-core/             # CORE_ROOT：可版本化、可部署的产品真源
    │   └── graph/                  # 图索引真源 + 机器索引（catalog/tag-inverted，随核心包部署）
    ├── yggforge-generated/        # GENERATED_ROOT：hosts/<id>/ 存放本宿主生成物
    └── yggforge-runtime/          # RUNTIME_ROOT：共享记忆与 hosts/<id>/ 本机状态（不入库）

部署时通常只投影 CORE_ROOT → ``~/<agent>/yggforge-core``。
"""

from __future__ import annotations

import getpass
import hashlib
import os
from pathlib import Path
import re
import socket
import sys
from typing import Optional


def find_repo_root(start: Path) -> Path:
    """自 start 向上查找含 .git 的目录；找不到则按目录名回退。"""
    cur = start.resolve()
    for _ in range(8):
        git_entry = cur / ".git"
        if git_entry.exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    if start.name == "yggforge-core":
        return start.parent
    return start


# repo_paths.py 位于 scripts/lib/，向上三层回到 yggforge-core/（CORE_ROOT）：
#   scripts/lib/repo_paths.py → scripts/lib → scripts → yggforge-core
CORE_ROOT = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = find_repo_root(CORE_ROOT)
GENERATED_ROOT = REPO_ROOT / "yggforge-generated"
RUNTIME_ROOT = REPO_ROOT / "yggforge-runtime"


def validate_host_id(value: str) -> str:
    """拒绝宿主目录身份中的路径、空值或过长值。"""
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}", value):
        raise ValueError("YGG_HOST_ID must be a safe directory name (letters, digits, '-' or '_').")
    return value.lower()


def current_host_id() -> str:
    """按平台和用户定位本机状态；显式覆盖只接受安全目录名。"""
    override = os.environ.get("YGG_HOST_ID", "").strip()
    if override:
        return validate_host_id(override)

    user = getpass.getuser()
    distro = os.environ.get("WSL_DISTRO_NAME", "").strip()
    if sys.platform.startswith("linux") and distro:
        identity = "wsl-{0}-{1}".format(distro, user)
    else:
        platform = "windows" if sys.platform.startswith("win") else "darwin" if sys.platform == "darwin" else "linux"
        identity = "{0}-{1}-{2}".format(platform, socket.gethostname(), user)
    normalized = re.sub(r"[^a-z0-9_-]+", "-", identity.lower()).strip("-")
    # 截断或有损转换时保留摘要，避免不同宿主归入同一个目录。
    if len(normalized) > 115 or normalized != identity.lower():
        normalized = normalized[:115] + "-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    return normalized


def host_runtime_root(repo_root: Optional[Path] = None, host_id: Optional[str] = None) -> Path:
    """返回宿主配置与缓存根；共享记忆仍位于 RUNTIME_ROOT/memory。"""
    root = Path(repo_root) / "yggforge-runtime" if repo_root is not None else RUNTIME_ROOT
    return root / "hosts" / validate_host_id(host_id if host_id is not None else current_host_id())


def host_generated_root(repo_root: Optional[Path] = None, host_id: Optional[str] = None) -> Path:
    """返回宿主部署收据、渲染和导入暂存根。"""
    root = Path(repo_root) / "yggforge-generated" if repo_root is not None else GENERATED_ROOT
    return root / "hosts" / validate_host_id(host_id if host_id is not None else current_host_id())


HOST_ID = current_host_id()
HOST_RUNTIME_ROOT = host_runtime_root(host_id=HOST_ID)
HOST_GENERATED_ROOT = host_generated_root(host_id=HOST_ID)


def resolve_core_source(source: str) -> Path:
    """解析相对 CORE_ROOT 的部署源路径；``.`` / 空 / ``yggforge-core`` 表示整包。"""
    text = (source or "").strip().replace("\\", "/")
    if text in ("", ".", "yggforge-core"):
        return CORE_ROOT.resolve()
    return (CORE_ROOT / text).resolve()


def ensure_layout() -> None:
    """确保 generated / runtime 的基础子目录存在。

    注意：图机器索引（catalog / tag-inverted）位于 ``CORE_ROOT/graph/`` 而非
    ``GENERATED_ROOT/``——它随核心包部署，使 ``ygg associate`` 在部署后仍可命中。
    """
    for path in (
        HOST_GENERATED_ROOT / "deploy-manifests",
        HOST_GENERATED_ROOT / "rendered",
        HOST_GENERATED_ROOT / "imports",
        CORE_ROOT / "graph" / "catalog",
        CORE_ROOT / "graph" / "tag-inverted",
        HOST_GENERATED_ROOT / "indexes" / "by-tag",
        HOST_GENERATED_ROOT / "scratch",
        RUNTIME_ROOT / "memory" / "raw",
        RUNTIME_ROOT / "memory" / "index",
        HOST_RUNTIME_ROOT / "cache",
        HOST_RUNTIME_ROOT / "config",
    ):
        path.mkdir(parents=True, exist_ok=True)
