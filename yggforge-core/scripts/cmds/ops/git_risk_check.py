#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""push 前风险摘要：保护分支、远端差异、可选 GitLab API 检查。

由 ``git_sync.py`` 在 update-push 路径 subprocess 调用；不经 ``ygg`` 直接路由。
"""

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
import subprocess
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

class RiskCheckError(RuntimeError):
    pass

def run_git(repo: Path, args: List[str]) -> str:
    result = subprocess.run(
        ["git"] + args,
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()

from lib.common import deep_merge_dict, load_json

def load_policy(repo: Path) -> Dict[str, Any]:
    # 策略真源在 yggforge-core/config/，与 cli.runtime.load_sync_policy 对齐
    core_config = repo / "yggforge-core" / "config"
    defaults_path = core_config / "sync.defaults.json"
    local_path = core_config / "sync.local.json"

    policy: Dict[str, Any] = {}
    if defaults_path.exists():
        policy = load_json(defaults_path)
    if local_path.exists():
        policy = deep_merge_dict(policy, load_json(local_path))
    return policy

def parse_project_path_from_remote(remote_url: str) -> Optional[str]:
    if "://" in remote_url:
        parsed = urllib.parse.urlparse(remote_url)
        path = parsed.path.lstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return path or None
    if ":" in remote_url:
        path = remote_url.split(":", 1)[1]
        if path.endswith(".git"):
            path = path[:-4]
        return path or None
    return None

def fetch_gitlab_json(api_url: str, token: str, endpoint: str) -> Optional[Any]:
    request = urllib.request.Request(
        "{0}{1}".format(api_url.rstrip("/"), endpoint),
        headers={"PRIVATE-TOKEN": token},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

def protected_branch(branch: str, patterns: List[str]) -> bool:
    return branch in patterns

def print_summary(payload: Dict[str, Any]) -> None:
    for key, value in payload.items():
        if isinstance(value, (list, dict, bool)):
            text = json.dumps(value, ensure_ascii=False)
        else:
            text = str(value)
        print("{0}={1}".format(key, text))

def build_unavailable_summary(branch: str, policy_action: str, is_protected: bool) -> Dict[str, Any]:
    return {
        "risk_check_available": False,
        "branch": branch,
        "protected_branch": is_protected,
        "push_access_levels": [],
        "eligible_push_members": [],
        "eligible_high_members": [],
        "risk_multi_high": "unknown",
        "policy_action": policy_action,
    }

def main() -> int:
    parser = argparse.ArgumentParser(description="Repo-level Git push risk check for YggForge.")
    parser.add_argument("--repo-path", required=True, help="Absolute path to the local repository.")
    parser.add_argument("--remote", default="origin", help="Remote name. Default: origin")
    parser.add_argument("--branch", default=None, help="Target branch. Default: current branch")
    args = parser.parse_args()

    repo = Path(args.repo_path).resolve()
    policy = load_policy(repo)
    push_safety = policy.get("push_safety", {})
    gitlab = policy.get("gitlab", {})

    current_branch = args.branch or run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    protected_patterns = push_safety.get("protected_branch_patterns", ["main", "master"])
    is_protected = protected_branch(current_branch, list(protected_patterns))

    if not bool(push_safety.get("enable_warning", True)):
        print_summary(
            {
                "risk_check_available": False,
                "branch": current_branch,
                "protected_branch": is_protected,
                "push_access_levels": [],
                "eligible_push_members": [],
                "eligible_high_members": [],
                "risk_multi_high": False,
                "policy_action": "continue",
            }
        )
        return 0

    if not is_protected:
        print_summary(
            {
                "risk_check_available": False,
                "branch": current_branch,
                "protected_branch": False,
                "push_access_levels": [],
                "eligible_push_members": [],
                "eligible_high_members": [],
                "risk_multi_high": False,
                "policy_action": "continue",
            }
        )
        return 0

    unavailable_action = str(push_safety.get("on_unable_to_check_permissions", "continue"))
    risky_action = str(push_safety.get("on_risky_protected_branch", "ask_user"))
    high_access_threshold = int(push_safety.get("high_access_threshold", 40))
    api_url = str(gitlab.get("api_url", "")).strip()
    token_env = str(gitlab.get("token_env", "YGG_GITLAB_TOKEN")).strip()
    token = os.environ.get(token_env, "").strip() if token_env else ""

    if not api_url or not token:
        print_summary(build_unavailable_summary(current_branch, unavailable_action, is_protected))
        return 0

    try:
        # 兼容旧版 git（如 1.8）：无 `remote get-url`，改用 config
        try:
            remote_url = run_git(repo, ["remote", "get-url", args.remote])
        except Exception:
            remote_url = run_git(repo, ["config", "--get", "remote.{0}.url".format(args.remote)])
    except Exception:
        print_summary(build_unavailable_summary(current_branch, unavailable_action, is_protected))
        return 0

    project_path = parse_project_path_from_remote(remote_url)
    if not project_path:
        print_summary(build_unavailable_summary(current_branch, unavailable_action, is_protected))
        return 0

    encoded = urllib.parse.quote(project_path, safe="")
    protected = fetch_gitlab_json(api_url, token, "/projects/{0}/protected_branches/{1}".format(encoded, current_branch))
    members = fetch_gitlab_json(api_url, token, "/projects/{0}/members/all?per_page=100".format(encoded))

    if not isinstance(protected, dict) or not isinstance(members, list):
        print_summary(build_unavailable_summary(current_branch, unavailable_action, is_protected))
        return 0

    push_levels_raw = protected.get("push_access_levels")
    if not isinstance(push_levels_raw, list):
        print_summary(build_unavailable_summary(current_branch, unavailable_action, is_protected))
        return 0

    levels = [
        item.get("access_level")
        for item in push_levels_raw
        if isinstance(item, dict) and item.get("access_level") is not None
    ]
    min_push = min(levels) if levels else high_access_threshold
    eligible_push = [
        item.get("username")
        for item in members
        if isinstance(item, dict) and item.get("username") and int(item.get("access_level", 0)) >= min_push
    ]
    high_floor = max(min_push, high_access_threshold)
    eligible_high = [
        item.get("username")
        for item in members
        if isinstance(item, dict) and item.get("username") and int(item.get("access_level", 0)) >= high_floor
    ]
    risk_multi_high = len(eligible_high) > 1
    policy_action = risky_action if risk_multi_high else "continue"

    print_summary(
        {
            "risk_check_available": True,
            "branch": current_branch,
            "protected_branch": True,
            "push_access_levels": levels,
            "eligible_push_members": eligible_push,
            "eligible_high_members": eligible_high,
            "risk_multi_high": risk_multi_high,
            "policy_action": policy_action,
        }
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
