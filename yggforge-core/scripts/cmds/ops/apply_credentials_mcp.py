#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性运维：私密凭据根目录中的 env 合并进本机 ``~/.cursor/mcp.json``。

不经 ``ygg`` 路由；安装文档手动调用。明文不写回本仓库。
"""

from __future__ import print_function

from pathlib import Path
import sys

# cmds/<domain>/<script>.py → scripts/
SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
SCRIPT_DIR = SCRIPTS_ROOT

import argparse
import json
import os
import re
import tempfile
from typing import Dict

from lib.repo_paths import CORE_ROOT, REPO_ROOT

def load_env_file(path: Path) -> Dict[str, str]:
    # 解析 KEY=VALUE，忽略空行与 # 注释
    values = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SystemExit("Invalid env syntax at line {0}.".format(number))
        key, value = line.split("=", 1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key.strip()):
            raise SystemExit("Invalid env key at line {0}.".format(number))
        values[key.strip()] = value.strip()
    return values

def token_kind(value: str) -> str:
    if not value or value.startswith("YOUR_"):
        return "placeholder"
    if value.startswith("glpat-"):
        return "glpat"
    return "secret"

def apply_env_to_mcp(mcp: dict, env_values: Dict[str, str]) -> None:
    servers = mcp.setdefault("mcpServers", {})
    gitlab = servers.setdefault("gitlab_internal", {})
    env = gitlab.setdefault("env", {})
    for key, value in env_values.items():
        env[key] = value

def validate_target(target: Path, example: Path) -> Path:
    """解析链接后校验写入边界，示例本体和仓库真源不能接收秘密。"""
    resolved = target.resolve()
    # copy 部署没有 Git 根，repo_paths 的回退父目录可能就是 Agent 家目录。
    # 该目录仍可存放本机 mcp.json；真正的仓库根和核心包始终不可写。
    roots = [CORE_ROOT]
    if (REPO_ROOT / ".git").exists() or (REPO_ROOT / "ygg.sh").is_file():
        roots.append(REPO_ROOT)
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        raise SystemExit("Credential target must be outside the repository/core package.")
    if resolved == example.resolve() or (resolved.exists() and example.exists() and os.path.samefile(str(resolved), str(example))):
        raise SystemExit("Credential target must not overwrite the example file.")
    return resolved

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge env files from a private secrets root into Cursor mcp.json."
    )
    parser.add_argument(
        "--credentials-root",
        required=True,
        help="Path to the private secrets root directory",
    )
    parser.add_argument(
        "--example",
        required=True,
        help="Path to mcp.json.example (usually profiles/cursor/mcp.json.example)",
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Output path, typically ~/.cursor/mcp.json",
    )
    parser.add_argument(
        "--env-file",
        default="cursor/mcp/gitlab_internal.env",
        help="Env file relative to credentials-root",
    )
    args = parser.parse_args()

    credentials_root = Path(os.path.expanduser(args.credentials_root)).resolve()
    example_path = Path(os.path.expanduser(args.example)).resolve()
    target_path = validate_target(Path(os.path.expanduser(args.target)), example_path)
    env_path = (credentials_root / args.env_file).resolve()
    try:
        env_path.relative_to(credentials_root)
    except ValueError:
        raise SystemExit("Env file must remain inside credentials-root.")

    if not example_path.is_file():
        raise SystemExit("Example not found: {0}".format(example_path))
    if not env_path.is_file():
        raise SystemExit("Env file not found: {0}".format(env_path))

    with example_path.open("r", encoding="utf-8-sig") as handle:
        mcp = json.load(handle)

    env_values = load_env_file(env_path)
    apply_env_to_mcp(mcp, env_values)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".ygg-mcp-", dir=str(target_path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(mcp, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, str(target_path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

    token = env_values.get("GITLAB_PERSONAL_ACCESS_TOKEN", "")
    print("Wrote {0}".format(target_path))
    print(
        "Injected keys: {0}".format(
            ", ".join(sorted(env_values.keys()))
        )
    )
    print(
        "GITLAB_PERSONAL_ACCESS_TOKEN kind={0} len={1}".format(
            token_kind(token), len(token)
        )
    )
    # 额外防呆：确认输出文件不含 YOUR_TOKEN
    written = target_path.read_text(encoding="utf-8")
    if re.search(r"YOUR_TOKEN|YOUR_GITLAB_HOST", written):
        print(
            "WARNING: target still contains placeholders; check env file.",
            file=sys.stderr,
        )
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
