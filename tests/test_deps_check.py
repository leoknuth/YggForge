#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最小测试：依赖检测模块 lib/deps（自动检测与自动安装基础）。

三庭合议后续：覆盖 requirements.txt 解析、import 探测、缺失判定、
import 名归并（pyyaml → yaml）。纯标准库，pytest 与 `py -X utf8` 均可跑。

跑法：
    py -X utf8 tests\test_deps_check.py
"""
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

_SCRIPTS = Path(__file__).resolve().parent.parent / "yggforge-core" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lib.deps import check_deps, missing_deps, parse_requirements, _import_name  # noqa: E402


def test_import_name_mapping():
    assert _import_name("pyyaml") == "yaml"
    assert _import_name("Pillow") == "PIL"
    assert _import_name("some-pkg") == "some_pkg"
    assert _import_name("python-dateutil") == "dateutil"


def test_parse_requirements_handles_comments_and_specs():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, prefix="ygg_req_"
    ) as f:
        f.write("# header comment\n\npyyaml>=5.0\nsome-pkg==1.0  # inline\n\n")
        path = Path(f.name)
    try:
        deps = parse_requirements(path)
        assert deps == [("pyyaml", "yaml", ">=5.0"), ("some-pkg", "some_pkg", "==1.0")]
    finally:
        path.unlink(missing_ok=True)


def test_check_deps_detects_installed_and_missing():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, prefix="ygg_req_"
    ) as f:
        # 安装探测用合成模块验证，不要求测试环境安装 PyYAML。
        f.write("pyyaml>=5.0\nnonexistent-ygg-test-xyz>=0.0.1\n")
        path = Path(f.name)
    try:
        with patch.dict(sys.modules, {"yaml": types.ModuleType("yaml")}):
            results = check_deps(path)
            by_pkg = {d["package"]: d for d in results}
            assert by_pkg["pyyaml"]["installed"] is True
            assert by_pkg["nonexistent-ygg-test-xyz"]["installed"] is False
            missing = missing_deps(path)
            assert missing == ["nonexistent-ygg-test-xyz"]
    finally:
        path.unlink(missing_ok=True)


def test_parse_requirements_missing_file_returns_empty():
    assert parse_requirements(Path("Z:/no/such/requirements.txt")) == []


def _run_all():
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS  {0}".format(name))
            except AssertionError as exc:
                failures += 1
                print("FAIL  {0}: {1}".format(name, exc))
    return failures


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)
