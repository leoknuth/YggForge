#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""yggforge-core 真源写入策略。

配置：
- yggforge-core/config/core_write.defaults.json
- yggforge-runtime/config/core_write.local.json（可选覆盖）

模式（canonical）：
- allow   直接写入
- ask     交互确认；非交互则拒绝
- deny    拒绝写入
- warn    写入，但向 stderr 打警告（不询问）
- audit   写入，并追加本机审计日志
- dry_run 不写入，只返回将要做什么

operations 未列出的操作回退到 default。
"""

from __future__ import print_function

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib.repo_paths import CORE_ROOT, RUNTIME_ROOT, ensure_layout

DEFAULTS_PATH = CORE_ROOT / "config" / "core_write.defaults.json"
LOCAL_PATH = RUNTIME_ROOT / "config" / "core_write.local.json"
AUDIT_LOG_PATH = RUNTIME_ROOT / "cache" / "core_write_audit.jsonl"

# 已知操作（文档与校验用；未知操作仍可用，回退 default）
KNOWN_OPERATIONS = (
    "tag_add",
    "tag_relate",
    "tag_weight_update",
    "tag_suggest_apply",
    # 统计/校准回写权威 tag-graph weight（默认 deny，见 behavior）
    "tag_weight_authority_writeback",
)

# canonical 模式 → (是否写入, 简述)
MODE_SPECS = {
    "allow": {"write": True, "prompt": False, "warn": False, "audit": False, "dry_run": False},
    "ask": {"write": None, "prompt": True, "warn": False, "audit": False, "dry_run": False},  # write 取决于用户
    "deny": {"write": False, "prompt": False, "warn": False, "audit": False, "dry_run": False},
    "warn": {"write": True, "prompt": False, "warn": True, "audit": False, "dry_run": False},
    "audit": {"write": True, "prompt": False, "warn": False, "audit": True, "dry_run": False},
    "dry_run": {"write": False, "prompt": False, "warn": False, "audit": False, "dry_run": True},
}

VALID_MODES = tuple(MODE_SPECS.keys())

# 别名 → canonical
MODE_ALIASES = {
    "ask": "ask",
    "ask_user": "ask",
    "prompt": "ask",
    "confirm": "ask",
    "allow": "allow",
    "auto": "allow",
    "yes": "allow",
    "deny": "deny",
    "refuse": "deny",
    "block": "deny",
    "no": "deny",
    "warn": "warn",
    "allow_warn": "warn",
    "warning": "warn",
    "audit": "audit",
    "allow_audit": "audit",
    "log": "audit",
    "dry_run": "dry_run",
    "dryrun": "dry_run",
    "preview": "dry_run",
    "simulate": "dry_run",
}


class CoreWriteDenied(RuntimeError):
    """策略拒绝写入 core。"""


from lib.common import deep_merge_dict


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def load_core_write_policy() -> Dict[str, Any]:
    policy = _load_json(DEFAULTS_PATH)
    local = _load_json(LOCAL_PATH)
    if local:
        policy = deep_merge_dict(policy, local)
    if "default" not in policy:
        policy["default"] = "ask"
    if "operations" not in policy or not isinstance(policy.get("operations"), dict):
        policy["operations"] = {}
    return policy




def normalize_mode(value: Any, *, fallback: str = "ask") -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if not text:
        return fallback if fallback in VALID_MODES else "ask"
    mode = MODE_ALIASES.get(text, "")
    if mode in VALID_MODES:
        return mode
    # 未知值：安全回退 ask，并尽量不静默成 allow
    return fallback if fallback in VALID_MODES else "ask"


def resolve_mode(operation: str, policy: Optional[Dict[str, Any]] = None) -> str:
    """优先读 behavior.defaults.yaml 的 core_write 段，再回退 JSON。"""
    try:
        from policies.behavior import load_behavior_config, resolve_mode as behavior_resolve

        bcfg = load_behavior_config()
        return behavior_resolve("core_write.operations.{0}".format(operation), bcfg)
    except Exception:
        pass
    cfg = policy if policy is not None else load_core_write_policy()
    ops = cfg.get("operations") or {}
    if operation in ops:
        return normalize_mode(ops.get(operation), fallback=normalize_mode(cfg.get("default", "ask")))
    return normalize_mode(cfg.get("default", "ask"))


def _stdin_is_interactive() -> bool:
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def _prompt_yes(summary: str, operation: str, mode: str) -> bool:
    sys.stderr.write("[core_write] 即将修改 yggforge-core（操作: {0}，策略: {1}）\n".format(operation, mode))
    for line in str(summary).splitlines() or ["(无摘要)"]:
        sys.stderr.write("  {0}\n".format(line))
    sys.stderr.write("是否继续写入？[y/N] ")
    sys.stderr.flush()
    try:
        answer = sys.stdin.readline()
    except Exception:
        return False
    if not answer:
        return False
    return answer.strip().lower() in ("y", "yes")


def _emit_warn(operation: str, summary: str, mode: str) -> None:
    sys.stderr.write("[core_write:{0}] {1}\n".format(mode, operation))
    for line in str(summary).splitlines() or ["(无摘要)"]:
        sys.stderr.write("  {0}\n".format(line))
    sys.stderr.flush()


def _append_audit(decision: Dict[str, Any]) -> Optional[str]:
    try:
        ensure_layout()
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "operation": decision.get("operation"),
            "mode": decision.get("mode"),
            "allowed": decision.get("allowed"),
            "reason": decision.get("reason"),
            "summary": decision.get("summary"),
        }
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return str(AUDIT_LOG_PATH)
    except Exception as exc:  # pragma: no cover
        sys.stderr.write("[core_write] audit log failed: {0}\n".format(exc))
        return None


def _decision(
    *,
    allowed: bool,
    mode: str,
    operation: str,
    reason: str,
    summary: str,
    hint: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    out = {
        "allowed": bool(allowed),
        "mode": mode,
        "operation": operation,
        "reason": reason,
        "summary": summary,
        "dry_run": bool(dry_run),
    }
    if hint:
        out["hint"] = hint
    return out


def authorize_core_write(
    operation: str,
    summary: str,
    *,
    force: Optional[str] = None,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """决定是否允许写入 core。

    force（单次覆盖配置）：
      - allow / ask / deny / warn / audit / dry_run（及其别名）
      - CLI 常用：--yes → allow，--no → deny，--dry-run → dry_run

    返回 dict: allowed, mode, operation, reason, summary, dry_run[, hint][, audit_path]

    优先委托 behavior_policy（YAML 统一策略，支持 always allow 持久化）。
    """
    op = str(operation or "").strip()
    try:
        from policies.behavior import authorize as behavior_authorize

        decision = behavior_authorize(
            "core_write.operations.{0}".format(op),
            summary,
            force=force,
        )
        # 保持调用方看到短操作名
        decision = dict(decision)
        decision["operation"] = op
        return decision
    except ImportError:
        pass

    cfg = policy if policy is not None else load_core_write_policy()

    if force is not None:
        mode = normalize_mode(force, fallback="deny")
    else:
        mode = resolve_mode(op, cfg)

    spec = MODE_SPECS[mode]

    if mode == "deny":
        return _decision(
            allowed=False,
            mode=mode,
            operation=op,
            reason="forced_deny" if force is not None else "policy_deny",
            summary=summary,
        )

    if mode == "dry_run":
        _emit_warn(op, summary, "dry_run")
        return _decision(
            allowed=False,
            mode=mode,
            operation=op,
            reason="dry_run",
            summary=summary,
            dry_run=True,
            hint="dry_run：未写入。去掉 --dry-run 或将策略改为 allow/ask/warn/audit 以真正写入。",
        )

    if mode == "ask":
        if not _stdin_is_interactive():
            return _decision(
                allowed=False,
                mode=mode,
                operation=op,
                reason="ask_non_interactive",
                summary=summary,
                hint="非交互环境请将操作设为 allow/warn/audit，或传入 --yes。",
            )
        if _prompt_yes(summary, op, mode):
            decision = _decision(
                allowed=True,
                mode=mode,
                operation=op,
                reason="user_confirmed",
                summary=summary,
            )
        else:
            return _decision(
                allowed=False,
                mode=mode,
                operation=op,
                reason="user_declined",
                summary=summary,
            )
    elif mode == "allow":
        decision = _decision(
            allowed=True,
            mode=mode,
            operation=op,
            reason="forced_allow" if force is not None else "policy_allow",
            summary=summary,
        )
    elif mode == "warn":
        _emit_warn(op, summary, "warn")
        decision = _decision(
            allowed=True,
            mode=mode,
            operation=op,
            reason="policy_warn",
            summary=summary,
        )
    elif mode == "audit":
        decision = _decision(
            allowed=True,
            mode=mode,
            operation=op,
            reason="policy_audit",
            summary=summary,
        )
    else:  # pragma: no cover
        decision = _decision(
            allowed=False,
            mode="deny",
            operation=op,
            reason="unknown_mode",
            summary=summary,
        )

    if decision.get("allowed") and (spec.get("audit") or mode == "audit"):
        path = _append_audit(decision)
        if path:
            decision["audit_path"] = path

    # warn 模式已 emit；若将来 ask+audit 组合可在此扩展
    return decision


