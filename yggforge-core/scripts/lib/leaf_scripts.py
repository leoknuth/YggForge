# -*- coding: utf-8 -*-
"""叶子 CLI 相对 ``scripts/`` 的路径注册表。

``ygg`` 经 ``cli.runtime.run_python`` 按短名查找；交叉 subprocess
也应经 ``resolve_leaf``，避免硬编码散落。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

# 短名 → 相对 scripts/ 的 posix 路径
LEAF_SCRIPTS: Dict[str, str] = {
    "deploy.py": "cmds/ops/deploy.py",
    "git_sync.py": "cmds/ops/git_sync.py",
    "git_risk_check.py": "cmds/ops/git_risk_check.py",
    "apply_credentials_mcp.py": "cmds/ops/apply_credentials_mcp.py",
    "doctor.py": "cmds/ops/doctor.py",
    "remember.py": "cmds/memory/remember.py",
    "recall.py": "cmds/memory/recall.py",
    "dream.py": "cmds/memory/dream.py",
    "ingest.py": "cmds/pipeline/ingest.py",
    "distill.py": "cmds/pipeline/distill.py",
    "promote.py": "cmds/pipeline/promote.py",
    "associate.py": "cmds/graph/associate.py",
    "graph_index.py": "cmds/graph/graph_index.py",
    "index_knowledge.py": "cmds/graph/index_knowledge.py",
    "tag_cli.py": "cmds/graph/tag_cli.py",
    "tag_language.py": "cmds/graph/tag_language.py",
    "project_mdc.py": "cmds/project/project_mdc.py",
    "migrate_knowledge_front_matter.py": "cmds/tools/migrate_knowledge_front_matter.py",
    "trigger_detector.py": "hooks/trigger_detector.py",
}


def resolve_leaf(scripts_root: Path, script_name: str) -> Path:
    """解析叶子脚本绝对路径；允许已是相对子路径。"""
    name = script_name.replace("\\", "/")
    if name in LEAF_SCRIPTS:
        return scripts_root / LEAF_SCRIPTS[name]
    candidate = scripts_root / name
    return candidate
