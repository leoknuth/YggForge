#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""依赖检测与自动安装（三庭合议后续：可部署性）。

- ``parse_requirements``：解析 ``requirements.txt`` 为 (package, import_name, spec) 列表。
- ``check_deps``：逐条 import 探测，返回每条依赖的安装状态。
- ``missing_deps``：返回缺失依赖（用于 doctor / deploy 提示）。
- ``install_missing``：对缺失项执行 ``pip install``，受 behavior 门禁 ``deps.install`` 约束。

设计原则：
- 仅依赖标准库（pip 本身是 Python 自带模块）。
- import 名与发行包名不一致时用 ``_IMPORT_MAP`` 归并（如 pyyaml → yaml）。
- 不自动升级已装版本（避免无谓的全局变更）；仅补缺失。
"""
from __future__ import print_function

import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.repo_paths import CORE_ROOT

REQUIREMENTS_PATH = CORE_ROOT / "scripts" / "requirements.txt"

# 发行包名 → import 顶层模块名（不一致时的归并表）
_IMPORT_MAP: Dict[str, str] = {
    "pyyaml": "yaml",
    "pyyaml5": "yaml",
    "pillow": "PIL",
    "python-dateutil": "dateutil",
    "beautifulsoup4": "bs4",
}


def _import_name(package: str) -> str:
    key = package.strip().lower().replace("_", "-")
    if key in _IMPORT_MAP:
        return _IMPORT_MAP[key]
    # 默认：包名转 import 名（- → _，取首段）
    first = key.split("[")[0].split(";")[0]
    return first.replace("-", "_")


def parse_requirements(path: Path = REQUIREMENTS_PATH) -> List[Tuple[str, str, str]]:
    """解析 requirements.txt → [(package, import_name, spec), ...]。

    支持 ``#`` 注释、空行、``pkg>=1.0`` / ``pkg==1.0`` / ``pkg`` 形态。
    """
    if not path.is_file():
        return []
    out: List[Tuple[str, str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        # 形如 pkg[extra]>=1.0,<2 ; python_version<="3.9"
        m = re.match(r"^([A-Za-z0-9_.\-]+)", line)
        if not m:
            continue
        package = m.group(1)
        spec = line[len(package):].strip()
        out.append((package, _import_name(package), spec))
    return out


def check_deps(path: Path = REQUIREMENTS_PATH) -> List[Dict[str, Any]]:
    """逐条 import 探测，返回 [{package, import_name, installed, version}, ...]。"""
    results: List[Dict[str, Any]] = []
    for package, imp, _spec in parse_requirements(path):
        installed = False
        version = ""
        try:
            mod = __import__(imp)
            installed = True
            v = getattr(mod, "__version__", "")
            if v:
                version = str(v)
        except ImportError:
            installed = False
        results.append(
            {
                "package": package,
                "import_name": imp,
                "installed": installed,
                "version": version,
            }
        )
    return results


def missing_deps(path: Path = REQUIREMENTS_PATH) -> List[str]:
    """返回缺失依赖的发行包名列表。"""
    return [d["package"] for d in check_deps(path) if not d["installed"]]


def install_missing(
    path: Path = REQUIREMENTS_PATH,
    *,
    python_exe: str = sys.executable,
    only_missing: bool = True,
) -> Tuple[int, List[str]]:
    """对缺失项执行 pip install。

    ``only_missing=True`` 时只装缺失包（不升级已装）；False 时整包 ``pip install -r``。
    返回 (returncode, installed_packages)。
    """
    missing = missing_deps(path) if only_missing else []
    if only_missing:
        if not missing:
            print("deps_install    : 无缺失依赖，跳过", flush=True)
            return (0, [])
        targets = missing
        cmd = [python_exe, "-m", "pip", "install"] + targets
    else:
        cmd = [python_exe, "-m", "pip", "install", "-r", str(path)]
        targets = [d[0] for d in parse_requirements(path)]
    print("deps_install    : pip install {0}".format(" ".join(targets)), flush=True)
    try:
        proc = subprocess.run(cmd)
        return (int(proc.returncode), targets)
    except OSError as exc:
        print("deps_install    : pip 调用失败: {0}".format(exc), file=sys.stderr)
        return (1, targets)
