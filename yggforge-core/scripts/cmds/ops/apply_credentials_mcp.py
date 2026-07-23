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
from typing import Dict

def load_env_file(path: Path) -> Dict[str, str]:
    # 解析 KEY=VALUE，忽略空行与 # 注释
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SystemExit("Invalid env line in {0}: {1}".format(path, raw_line))
        key, value = line.split("=", 1)
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
    target_path = Path(os.path.expanduser(args.target)).resolve()
    env_path = (credentials_root / args.env_file).resolve()

    if not example_path.is_file():
        raise SystemExit("Example not found: {0}".format(example_path))
    if not env_path.is_file():
        raise SystemExit("Env file not found: {0}".format(env_path))

    with example_path.open("r", encoding="utf-8") as handle:
        mcp = json.load(handle)

    env_values = load_env_file(env_path)
    apply_env_to_mcp(mcp, env_values)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8") as handle:
        json.dump(mcp, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.chmod(str(target_path), 0o600)

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
