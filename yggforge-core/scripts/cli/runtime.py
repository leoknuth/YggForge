# -*- coding: utf-8 -*-
"""Ygg CLI 运行时辅助：路径、subprocess、behavior 门禁、sync 编排。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib.common import deep_merge_dict, load_json
from lib.leaf_scripts import resolve_leaf
from lib.repo_paths import CORE_ROOT, GENERATED_ROOT, REPO_ROOT, RUNTIME_ROOT
from cli.errors import YggError

# runtime.py 在 scripts/cli/，上两层是 scripts/
SCRIPT_DIR = Path(__file__).resolve().parent.parent
SYNC_POLICY_PATH = CORE_ROOT / "config" / "sync.defaults.json"
LOCAL_SYNC_POLICY_PATH = RUNTIME_ROOT / "config" / "sync.local.json"
MANIFEST_ROOT = GENERATED_ROOT / "deploy-manifests"
KNOWN_TARGETS = ("cursor", "codex", "opencode")


def load_sync_policy() -> Dict[str, Any]:
    policy: Dict[str, Any] = {}
    if SYNC_POLICY_PATH.exists():
        policy = load_json(SYNC_POLICY_PATH)
    if LOCAL_SYNC_POLICY_PATH.exists():
        policy = deep_merge_dict(policy, load_json(LOCAL_SYNC_POLICY_PATH))
    return policy


def read_deploy_manifest(target: str) -> Optional[Dict[str, Any]]:
    path = MANIFEST_ROOT / "{0}.json".format(target)
    if not path.exists():
        return None
    return load_json(path)


def run_python(script_name: str, args: List[str]) -> int:
    """按短名或相对路径启动叶子 CLI；保证 ``scripts/`` 在 PYTHONPATH。"""
    script_path = resolve_leaf(SCRIPT_DIR, script_name)
    if not script_path.is_file():
        raise YggError("Leaf script not found: {0} -> {1}".format(script_name, script_path))
    env = os.environ.copy()
    # 三庭合议 P2-2：强制子进程 UTF-8 模式，避免 Windows 非 UTF-8 终端下
    # 各叶子 CLI 的中文输出 mojibake（等价于 py -X utf8，对所有 ygg 子命令统一生效）。
    env["PYTHONUTF8"] = "1"
    scripts = str(SCRIPT_DIR)
    existing = env.get("PYTHONPATH", "")
    if existing:
        parts = existing.split(os.pathsep)
        if scripts not in parts:
            env["PYTHONPATH"] = scripts + os.pathsep + existing
    else:
        env["PYTHONPATH"] = scripts
    result = subprocess.run([sys.executable, str(script_path)] + args, env=env)
    return int(result.returncode)


def parse_target_list(action: str, rest: List[str]) -> List[str]:
    if not rest:
        return []

    targets: List[str] = []
    for token in rest:
        lowered = token.lower()
        if lowered not in KNOWN_TARGETS:
            raise YggError(
                "`ygg {0}` currently only accepts optional target names: {1}".format(
                    action, ", ".join(KNOWN_TARGETS)
                )
            )
        if lowered not in targets:
            targets.append(lowered)
    return targets


def git_sync_args(action: str, policy: Dict[str, Any]) -> List[str]:
    git_policy = policy.get("git", {})
    args = [
        "--action",
        "update-push" if action == "push" else "update",
        "--repo",
        str(REPO_ROOT),
        "--remote",
        str(git_policy.get("remote", "origin")),
    ]
    branch = git_policy.get("branch")
    if branch:
        args.extend(["--branch", str(branch)])
    return args


def _ensure_script_path() -> None:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))


def _pop_force_flags(tokens: List[str]) -> Tuple[List[str], Optional[str]]:
    """从 argv 抽出 --yes/--no/--dry-run，返回 (剩余 tokens, force)。"""
    rest: List[str] = []
    yes = no = dry = False
    for token in tokens:
        if token == "--yes":
            yes = True
        elif token == "--no":
            no = True
        elif token == "--dry-run":
            dry = True
        else:
            rest.append(token)
    _ensure_script_path()
    from policies.behavior import force_from_flags

    try:
        force = force_from_flags(yes=yes, no=no, dry_run=dry)
    except ValueError as exc:
        raise YggError(str(exc))
    return rest, force


def behavior_gate(
    operation: str,
    summary: str,
    force: Optional[str] = None,
    *,
    deny_means: str = "abort",
) -> Tuple[str, Dict[str, Any]]:
    """统一 behavior 闸门。

    返回 (outcome, decision)：
      - proceed：允许执行
      - skip：策略 deny（或 forced deny），调用方应跳过并视为成功
      - abort：ask 拒绝 / 非交互 ask / dry_run 等，调用方应中止（非 0）
    deny_means: "skip" | "abort" — policy_deny 时的语义（git 用 skip）
    """
    _ensure_script_path()
    from policies.behavior import authorize

    decision = authorize(operation, summary, force=force)
    if decision.get("allowed"):
        return "proceed", decision
    reason = str(decision.get("reason") or "")
    if reason in ("policy_deny", "forced_deny"):
        if deny_means == "skip":
            print(
                "behavior_skip  : {0} ({1})".format(operation, reason),
                flush=True,
            )
            if decision.get("hint"):
                print("behavior_hint  : {0}".format(decision["hint"]), flush=True)
            return "skip", decision
        return "abort", decision
    print("behavior_denied: {0} ({1})".format(operation, reason), flush=True)
    if decision.get("hint"):
        print("behavior_hint  : {0}".format(decision["hint"]), flush=True)
    if decision.get("persist_path"):
        print("behavior_local : {0}".format(decision["persist_path"]), flush=True)
    return "abort", decision


def maybe_import_targets(action: str, targets: List[str], policy: Dict[str, Any]) -> None:
    if not targets:
        return

    mode_actions = policy.get("mode_actions", {})
    policy_key = "import_before_push" if action == "push" else "import_before_sync"

    for target in targets:
        manifest = read_deploy_manifest(target)
        if not manifest:
            print("ygg import     : skip -> {0} has no deploy manifest".format(target), flush=True)
            continue

        mode = str(manifest.get("mode", "")).strip().lower()
        mode_policy = mode_actions.get(mode, {})
        should_import = bool(mode_policy.get(policy_key, False))
        preview_only = bool(mode_policy.get("preview_only", False))

        if not should_import:
            print(
                "ygg import     : skip -> {0} mode={1} does not require reverse sync".format(target, mode),
                flush=True,
            )
            continue

        import_args = ["--action", "import", "--targets", target]
        if preview_only:
            import_args.append("--preview-only")

        print("ygg import     : start -> {0} mode={1}".format(target, mode), flush=True)
        if run_python("deploy.py", import_args) != 0:
            raise YggError("`ygg {0}` failed while importing target '{1}'.".format(action, target))


