#!/usr/bin/env python3
"""只读检查仓库，再在临时副本验证索引构建与完整指纹。"""

import ast
import copy
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "yggforge-core"
sys.path.insert(0, str(CORE / "scripts"))
from knowledge.graph_build import build_indexes, check_indexes, index_records, load_graph_config


def main() -> int:
    python_files = list(CORE.rglob("*.py")) + list((REPO / "tests").glob("*.py"))
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    config = load_graph_config(CORE)
    source = index_records(CORE, config)
    if source["warnings"]:
        print("\n".join(source["warnings"]))
        return 1
    result = check_indexes(CORE, config)
    if result["consistency_errors"]:
        print("\n".join(result["consistency_errors"]))
        return 1
    print("stored_index: {0}; source_consistency={1}".format(result["index_status"], result["source_consistency"]))
    if result["migration_required"]:
        print("旧索引仅核验已有元数据；完整正文指纹将在临时副本验证，实际索引保持不变。")
    with tempfile.TemporaryDirectory(prefix="yggforge-ci-") as temporary:
        snapshot = Path(temporary) / "yggforge-core"
        shutil.copytree(CORE, snapshot, ignore=shutil.ignore_patterns("__pycache__"))
        isolated = copy.deepcopy(config)
        # 固定写入临时副本，避免本机配置中的路径把 CI 检查引回真源。
        isolated["paths"] = dict(isolated.get("paths", {}), catalog_dir="graph/catalog", tag_inverted_dir="graph/tag-inverted")
        build_indexes(snapshot, isolated)
        fresh = check_indexes(snapshot, isolated)
        if fresh["warnings"] or fresh["source_consistency"] != "full":
            print("临时索引验证失败:", fresh["warnings"])
            return 1
    spec = importlib.util.spec_from_file_location("ci_project_mdc", CORE / "scripts/cmds/project/project_mdc.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.run(check_only=True, write=False):
        return 1
    print("repository_check: passed ({0} Python files; isolated index fingerprint verified)".format(len(python_files)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
