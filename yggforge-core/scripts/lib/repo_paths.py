# -*- coding: utf-8 -*-
"""YggForge 路径约定：核心包 / 生成物 / 本机运行时。

仓库布局::

    <REPO_ROOT>/
    ├── docs/                      # 人类文档（不部署）
    ├── AGENTS.md / README.md
    ├── ygg.sh / ygg.ps1
    ├── yggforge-core/             # CORE_ROOT：可版本化、可部署的产品真源
    │   └── graph/                  # 图索引真源 + 机器索引（catalog/tag-inverted，随核心包部署）
    ├── yggforge-generated/        # GENERATED_ROOT：可再生产物（非真源；rendered/imports/manifests/scratch/indexes）
    └── yggforge-runtime/          # RUNTIME_ROOT：本机可变状态（不入库）

部署时通常只投影 CORE_ROOT → ``~/<agent>/yggforge-core``。
"""

from __future__ import annotations

from pathlib import Path


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
        GENERATED_ROOT / "deploy-manifests",
        GENERATED_ROOT / "rendered",
        GENERATED_ROOT / "imports",
        CORE_ROOT / "graph" / "catalog",
        CORE_ROOT / "graph" / "tag-inverted",
        GENERATED_ROOT / "indexes" / "by-tag",
        GENERATED_ROOT / "scratch",
        RUNTIME_ROOT / "memory" / "raw",
        RUNTIME_ROOT / "memory" / "index",
        RUNTIME_ROOT / "cache",
        RUNTIME_ROOT / "config",
    ):
        path.mkdir(parents=True, exist_ok=True)
