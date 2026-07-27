#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多机 git 同步：update（pull --rebase）与 update-push。

由 ``ygg sync`` / ``ygg push`` 调用。push 前可链式跑 ``git_risk_check.py``。
本脚本只动仓库 git，不负责 Agent 家目录投影。

对齐语义（与 knowledge/rules/git-workflow.md 一致）：
1. fetch
2. 报告 ahead/behind；behind>0 时提示远端领先
3. pull --rebase（dirty 时 --autostash）
4. rebase 冲突则结构化警告并停手
5. update-push 再经风险检查后 push
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
import subprocess
from typing import Any, Dict, List, Optional, Tuple

class GitSyncError(RuntimeError):
    pass

def run_git(repo: Path, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git"] + args,
        cwd=str(repo),
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise GitSyncError(
            "git {0} failed.\nstdout:\n{1}\nstderr:\n{2}".format(
                " ".join(args),
                result.stdout.strip(),
                result.stderr.strip(),
            )
        )
    return result

def run_python(script_name: str, args: List[str], repo: Path) -> subprocess.CompletedProcess:
    from lib.leaf_scripts import resolve_leaf

    leaf = resolve_leaf(SCRIPT_DIR, script_name)
    return subprocess.run(
        [sys.executable, str(leaf)] + args,
        cwd=str(repo),
        text=True,
        capture_output=True,
    )

def ensure_repo(path: Path) -> Path:
    repo = path.resolve()
    result = run_git(repo, ["rev-parse", "--show-toplevel"])
    return Path(result.stdout.strip())

def current_branch(repo: Path) -> str:
    return run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()

def working_tree_dirty(repo: Path) -> bool:
    return bool(run_git(repo, ["status", "--porcelain"], check=True).stdout.strip())

def branch_tracking(repo: Path) -> Optional[str]:
    result = run_git(repo, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()

def git_dir(repo: Path) -> Path:
    raw = run_git(repo, ["rev-parse", "--git-dir"]).stdout.strip()
    path = Path(raw)
    return path if path.is_absolute() else (repo / path)

def rebase_in_progress(repo: Path) -> bool:
    gd = git_dir(repo)
    return (gd / "rebase-merge").is_dir() or (gd / "rebase-apply").is_dir()

def ahead_behind(repo: Path, upstream: Optional[str] = None) -> Optional[str]:
    ref = upstream
    if ref is None:
        tracking = branch_tracking(repo)
        if not tracking:
            return None
        ref = "@{u}"
    result = run_git(repo, ["rev-list", "--left-right", "--count", "HEAD...{0}".format(ref)], check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()

def parse_ahead_behind(value: Optional[str]) -> Optional[Tuple[int, int]]:
    if not value:
        return None
    parts = value.split()
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None

def print_status(repo: Path) -> None:
    branch = current_branch(repo)
    tracking = branch_tracking(repo)
    ahead_behind_value = ahead_behind(repo)
    dirty = working_tree_dirty(repo)

    print("repo           : {0}".format(repo))
    print("branch         : {0}".format(branch))
    print("tracking       : {0}".format(tracking or "<none>"))
    print("working_dirty  : {0}".format(dirty))
    if ahead_behind_value:
        ahead, behind = ahead_behind_value.split()
        print("ahead          : {0}".format(ahead))
        print("behind         : {0}".format(behind))
    else:
        print("ahead          : <unknown>")
        print("behind         : <unknown>")

def ensure_tracking_branch(repo: Path) -> str:
    tracking = branch_tracking(repo)
    if not tracking:
        raise GitSyncError(
            "Current branch has no upstream tracking branch. Set one before using the multi-machine sync workflow."
        )
    return tracking

def resolve_upstream_ref(repo: Path, remote: str, branch: Optional[str]) -> str:
    if branch:
        return "{0}/{1}".format(remote, branch)
    return ensure_tracking_branch(repo)

def build_pull_rebase_args(repo: Path, remote: str, branch: Optional[str], autostash: bool) -> List[str]:
    args = ["pull", "--rebase"]
    if autostash:
        args.append("--autostash")
    if branch:
        args.extend([remote, branch])
    else:
        ensure_tracking_branch(repo)
    return args

def fetch_remote(repo: Path, remote: str) -> None:
    run_git(repo, ["fetch", remote])
    print("fetch          : ok -> {0}".format(remote))

def format_conflict_message(repo: Path, branch: str) -> str:
    return (
        "[YggForge git] rebase 冲突 — 已暂停，请人工决策\n"
        "- 分支: {0}\n"
        "- 仓库: {1}\n"
        "- 建议:\n"
        "  1. 解决冲突后: git add ... && git rebase --continue\n"
        "  2. 放弃本次对齐: git rebase --abort\n"
        "- 在你确认前，不会继续 push"
    ).format(branch, repo)

def update(repo: Path, remote: str, branch: Optional[str]) -> Dict[str, Any]:
    """Fetch + 按需 pull --rebase。返回对齐摘要供调用方/日志使用。"""
    resolved_branch = branch or current_branch(repo)
    dirty = working_tree_dirty(repo)
    fetch_remote(repo, remote)

    upstream = resolve_upstream_ref(repo, remote, branch)
    counts = parse_ahead_behind(ahead_behind(repo, upstream=upstream))
    if counts is None:
        ahead, behind = None, None
        print("align_check    : ahead=<unknown> behind=<unknown> upstream={0}".format(upstream))
    else:
        ahead, behind = counts
        print("align_check    : ahead={0} behind={1} upstream={2}".format(ahead, behind, upstream))

    summary: Dict[str, Any] = {
        "branch": resolved_branch,
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "rebased": False,
        "skipped_pull": False,
    }

    if behind == 0:
        print(
            "align_notice   : already aligned with remote "
            "(ahead={0}, behind=0); skip pull --rebase".format(ahead if ahead is not None else "<unknown>")
        )
        summary["skipped_pull"] = True
        return summary

    if behind is not None and behind > 0:
        print(
            "align_notice   : remote is ahead by {0} commit(s) "
            "(local ahead={1}); will pull --rebase before push".format(
                behind, ahead if ahead is not None else "<unknown>"
            )
        )
    else:
        print("align_notice   : ahead/behind unknown; will pull --rebase to be safe")

    pull_args = build_pull_rebase_args(repo, remote, branch, autostash=dirty)
    result = run_git(repo, pull_args, check=False)
    if result.returncode != 0:
        if rebase_in_progress(repo):
            raise GitSyncError(format_conflict_message(repo, resolved_branch))
        raise GitSyncError(
            "git {0} failed.\nstdout:\n{1}\nstderr:\n{2}".format(
                " ".join(pull_args),
                result.stdout.strip(),
                result.stderr.strip(),
            )
        )

    summary["rebased"] = True
    if dirty:
        print("update         : ok -> pull --rebase --autostash")
    else:
        print("update         : ok -> pull --rebase")
    return summary

def parse_kv_output(text: str) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if value in ("True", "False"):
            parsed[key] = value == "True"
            continue
        try:
            parsed[key] = json.loads(value)
        except Exception:
            parsed[key] = value
    return parsed

def run_push_risk_check(repo: Path, remote: str, branch: str) -> Dict[str, Any]:
    result = run_python(
        "git_risk_check.py",
        ["--repo-path", str(repo), "--remote", remote, "--branch", branch],
        repo,
    )
    if result.returncode != 0:
        raise GitSyncError(
            "git push risk check failed.\nstdout:\n{0}\nstderr:\n{1}".format(
                result.stdout.strip(),
                result.stderr.strip(),
            )
        )
    summary = parse_kv_output(result.stdout)
    summary.setdefault("policy_action", "continue")
    summary.setdefault("risk_check_available", False)
    summary.setdefault("protected_branch", branch in ("main", "master"))
    return summary

def print_risk_summary(summary: Dict[str, Any]) -> None:
    print("risk_available : {0}".format(summary.get("risk_check_available")))
    print("risk_branch    : {0}".format(summary.get("branch", "<unknown>")))
    print("risk_protected : {0}".format(summary.get("protected_branch")))
    print("risk_levels    : {0}".format(summary.get("push_access_levels", [])))
    print("risk_pushers   : {0}".format(summary.get("eligible_push_members", [])))
    print("risk_high      : {0}".format(summary.get("eligible_high_members", [])))
    print("risk_multi_high: {0}".format(summary.get("risk_multi_high")))
    print("risk_action    : {0}".format(summary.get("policy_action")))

def short_head_subject(repo: Path) -> str:
    result = run_git(repo, ["log", "-1", "--pretty=format:%h %s"], check=False)
    if result.returncode != 0:
        return "<unknown>"
    return result.stdout.strip() or "<unknown>"

def update_and_push(repo: Path, remote: str, branch: Optional[str]) -> None:
    resolved_branch = branch or current_branch(repo)
    align = update(repo, remote, resolved_branch)

    if working_tree_dirty(repo):
        if rebase_in_progress(repo):
            raise GitSyncError(format_conflict_message(repo, resolved_branch))
        raise GitSyncError(
            "Working tree is still dirty after update. Commit or resolve conflicts before pushing."
        )

    risk_summary = run_push_risk_check(repo, remote, resolved_branch)
    print_risk_summary(risk_summary)
    if str(risk_summary.get("policy_action", "continue")) != "continue":
        raise GitSyncError(
            "Push safety policy requires manual confirmation before pushing this branch. "
            "Review the risk summary above or override the policy in sync.local.json "
            "(this is not a Merge Request approval; only a local safety gate)."
        )

    run_git(repo, ["push", remote, resolved_branch])
    tip = short_head_subject(repo)
    print("push           : ok -> {0}/{1}".format(remote, resolved_branch))
    print("push_tip       : {0}".format(tip))
    if align.get("rebased"):
        print("push_note      : rebased onto newer remote before push")
    elif align.get("skipped_pull"):
        print("push_note      : already aligned; pushed local commits only")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cross-platform multi-machine git sync helper for YggForge.")
    parser.add_argument("--action", choices=["status", "update", "update-push"], default="status")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default=None)
    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        repo = ensure_repo(Path(args.repo))
        if args.action == "status":
            print_status(repo)
            return 0
        if args.action == "update":
            update(repo, args.remote, args.branch)
            return 0
        if args.action == "update-push":
            update_and_push(repo, args.remote, args.branch)
            return 0
        raise GitSyncError("Unknown action: {0}".format(args.action))
    except GitSyncError as exc:
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
