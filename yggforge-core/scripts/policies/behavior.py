#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一行为策略：ask/allow/deny/… + 可选特性开关。

配置（YAML，可注释）：
- yggforge-core/config/behavior.defaults.yaml
- yggforge-runtime/config/behavior.local.yaml

模式约定（配置值）：
- ask   — 每次询问；交互 [y]=仅本次，[a]lways allow → 持久化为 allow
- allow — 不再询问直接执行（即「always allow」落盘后的值；勿在配置里写 always_allow，
          但 always_allow 别名会被规范成 allow）
- deny  — 拒绝；对 git 类操作为跳过

进阶：warn / audit / dry_run。与 core_write_policy 共用语义。
"""

from __future__ import print_function

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib.repo_paths import CORE_ROOT, RUNTIME_ROOT, ensure_layout

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

DEFAULTS_PATH = CORE_ROOT / "config" / "behavior.defaults.yaml"
LOCAL_PATH = RUNTIME_ROOT / "config" / "behavior.local.yaml"

VALID_MODES = ("ask", "allow", "deny", "warn", "audit", "dry_run")

MODE_ALIASES = {
    "ask": "ask",
    "ask_user": "ask",
    "prompt": "ask",
    "confirm": "ask",
    "allow": "allow",
    "always_allow": "allow",
    "always-allow": "allow",
    "auto": "allow",
    "yes": "allow",
    "deny": "deny",
    "always_deny": "deny",
    "always-deny": "deny",
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


class BehaviorDenied(RuntimeError):
    """行为策略拒绝执行。"""


from lib.common import deep_merge_dict


def _parse_scalar(raw: str) -> Any:
    text = raw.strip()
    if not text:
        return ""
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    low = text.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "none", "~"):
        return None
    try:
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return int(text)
        return float(text)
    except ValueError:
        return text


def _parse_simple_nested_yaml(text: str) -> Dict[str, Any]:
    """无 PyYAML 时解析 behavior YAML 的最小子集（嵌套 map + 标量，忽略注释）。"""
    root: Dict[str, Any] = {}
    stack: List[Tuple[int, Dict[str, Any]]] = [(-1, root)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if ":" not in stripped or stripped.startswith("-"):
            continue
        key, _, rest = stripped.partition(":")
        key = key.strip()
        rest = rest.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if rest == "":
            child: Dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(rest)
    return root


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    if yaml is not None:
        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else {}
    # 零依赖回退：足够读 behavior.defaults.yaml / 本机覆盖
    return _parse_simple_nested_yaml(text)


def _dump_yaml(path: Path, data: Dict[str, Any]) -> None:
    ensure_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml is None:
        # 无 PyYAML 时退回 JSON（仍可用）
        json_path = path.with_suffix(".json")
        with json_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return
    header = (
        "# YggForge behavior.local.yaml — 本机覆盖（通常不入库）\n"
        "# 由交互 always allow/deny 或人工编辑生成。\n"
    )
    body = yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    path.write_text(header + body, encoding="utf-8")


def load_behavior_config() -> Dict[str, Any]:
    cfg = _load_yaml(DEFAULTS_PATH)
    local = _load_yaml(LOCAL_PATH)
    # 兼容：若只有 JSON 本地覆盖
    local_json = RUNTIME_ROOT / "config" / "behavior.local.json"
    if local_json.exists():
        with local_json.open("r", encoding="utf-8-sig") as handle:
            j = json.load(handle)
        if isinstance(j, dict):
            local = deep_merge_dict(local, j)
    if local:
        cfg = deep_merge_dict(cfg, local)
    if "default_mode" not in cfg:
        cfg["default_mode"] = "ask"
    return cfg


def normalize_mode(value: Any, *, fallback: str = "ask") -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if not text:
        return fallback if fallback in VALID_MODES else "ask"
    mode = MODE_ALIASES.get(text, "")
    if mode in VALID_MODES:
        return mode
    return fallback if fallback in VALID_MODES else "ask"


def _dig(cfg: Dict[str, Any], dotted: str) -> Any:
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def resolve_mode(operation: str, cfg: Optional[Dict[str, Any]] = None) -> str:
    """operation 使用点分路径，如 memory.record_observation / promote.to_rule。"""
    data = cfg if cfg is not None else load_behavior_config()
    raw = _dig(data, operation)
    if raw is None and operation.startswith("core_write.operations."):
        # 兼容仅写了 core_write.default
        pass
    if raw is not None and not isinstance(raw, dict):
        return normalize_mode(raw, fallback=normalize_mode(data.get("default_mode", "ask")))
    # core_write.operations.X 快捷
    if operation.startswith("core_write.") and not operation.startswith("core_write.operations."):
        key = operation.split(".", 1)[1]
        ops = (data.get("core_write") or {}).get("operations") or {}
        if key in ops:
            return normalize_mode(ops[key], fallback=normalize_mode(data.get("default_mode", "ask")))
    # memory.kinds.X
    if operation.startswith("memory.kinds."):
        kind = operation.split(".", 2)[-1]
        kinds = (data.get("memory") or {}).get("kinds") or {}
        if kind in kinds:
            return normalize_mode(kinds[kind], fallback=normalize_mode(data.get("default_mode", "ask")))
    cw_default = (data.get("core_write") or {}).get("default")
    if operation.startswith("core_write") and cw_default is not None:
        return normalize_mode(cw_default, fallback="ask")
    return normalize_mode(data.get("default_mode", "ask"))


def feature_enabled(name: str, cfg: Optional[Dict[str, Any]] = None) -> bool:
    data = cfg if cfg is not None else load_behavior_config()
    features = data.get("features") or {}
    return bool(features.get(name, False))


def dream_settings(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = cfg if cfg is not None else load_behavior_config()
    dream = dict(data.get("dream") or {})
    dream.setdefault("enabled", True)
    dream.setdefault("period", "7d")
    dream.setdefault("frequency", "weekly")
    dream.setdefault("intensity", "normal")
    dream.setdefault("depth", 1)
    dream.setdefault("max_items_per_section", 10)
    return dream


def set_local_mode(operation: str, mode: str) -> Path:
    """将点分 operation 写入 behavior.local.yaml。"""
    mode = normalize_mode(mode)
    local = _load_yaml(LOCAL_PATH)
    if "version" not in local:
        local["version"] = 1
    parts = operation.split(".")
    cur: Dict[str, Any] = local
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = mode
    _dump_yaml(LOCAL_PATH, local)
    return LOCAL_PATH


def _stdin_interactive() -> bool:
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def _prompt_choice(summary: str, operation: str, mode: str, cfg: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """返回 (allowed, persist_mode_or_None)。"""
    ask_cfg = cfg.get("ask") or {}
    offer_a = bool(ask_cfg.get("offer_always_allow", True))
    offer_d = bool(ask_cfg.get("offer_always_deny", True))

    sys.stderr.write("[behavior] 操作: {0}（当前策略: {1}）\n".format(operation, mode))
    for line in str(summary).splitlines() or ["(无摘要)"]:
        sys.stderr.write("  {0}\n".format(line))
    options = ["[y]es", "[n]o"]
    if offer_a:
        options.append("[a]lways allow")
    if offer_d:
        options.append("[d]eny always")
    sys.stderr.write("选择: {0}  ".format(" / ".join(options)))
    sys.stderr.flush()
    try:
        answer = (sys.stdin.readline() or "").strip().lower()
    except Exception:
        return False, None
    if answer in ("y", "yes"):
        return True, None
    if answer in ("a", "always", "always allow", "always_allow") and offer_a:
        return True, "allow"
    if answer in ("d", "deny", "always deny", "always_deny") and offer_d:
        return False, "deny"
    return False, None


def authorize(
    operation: str,
    summary: str,
    *,
    force: Optional[str] = None,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """统一授权。force 覆盖单次：allow/deny/dry_run/…"""
    data = cfg if cfg is not None else load_behavior_config()
    op = str(operation or "").strip()

    if force is not None:
        mode = normalize_mode(force, fallback="deny")
    else:
        mode = resolve_mode(op, data)

    def _result(allowed: bool, reason: str, **extra: Any) -> Dict[str, Any]:
        out = {
            "allowed": bool(allowed),
            "mode": mode,
            "operation": op,
            "reason": reason,
            "summary": summary,
            "dry_run": mode == "dry_run" and not allowed and reason == "dry_run",
        }
        out.update(extra)
        return out

    if mode == "deny":
        return _result(False, "forced_deny" if force else "policy_deny")

    if mode == "dry_run":
        sys.stderr.write("[behavior:dry_run] {0}\n".format(op))
        for line in str(summary).splitlines():
            sys.stderr.write("  {0}\n".format(line))
        return _result(False, "dry_run", dry_run=True, hint="dry_run：未执行。")

    if mode == "ask":
        if not _stdin_interactive():
            return _result(
                False,
                "ask_non_interactive",
                hint="非交互环境请将 {0} 设为 allow，或传入 --yes。".format(op),
            )
        allowed, persist = _prompt_choice(summary, op, mode, data)
        persist_path = None
        if persist and (data.get("ask") or {}).get("persist_to", "local") == "local":
            persist_path = str(set_local_mode(op, persist))
        if allowed:
            return _result(
                True,
                "user_confirmed" if not persist else "user_always_allow",
                persisted_mode=persist,
                persist_path=persist_path,
            )
        return _result(
            False,
            "user_declined" if not persist else "user_always_deny",
            persisted_mode=persist,
            persist_path=persist_path,
        )

    if mode == "warn":
        sys.stderr.write("[behavior:warn] {0}\n".format(op))
        for line in str(summary).splitlines():
            sys.stderr.write("  {0}\n".format(line))
        return _result(True, "policy_warn")

    if mode == "audit":
        decision = _result(True, "policy_audit")
        try:
            from policies.core_write import _append_audit

            path = _append_audit(decision)
            if path:
                decision["audit_path"] = path
        except Exception:
            pass
        return decision

    # allow
    return _result(True, "forced_allow" if force else "policy_allow")




def force_from_flags(*, yes: bool = False, no: bool = False, dry_run: bool = False) -> Optional[str]:
    """CLI --yes/--no/--dry-run → force 字符串；冲突时抛 ValueError。"""
    active = []
    if yes:
        active.append("yes")
    if no:
        active.append("no")
    if dry_run:
        active.append("dry_run")
    if len(active) > 1:
        raise ValueError("--yes / --no / --dry-run 不能同时使用")
    if yes:
        return "allow"
    if no:
        return "deny"
    if dry_run:
        return "dry_run"
    return None


def list_operation_modes(cfg: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """供 status / 文档导出。"""
    data = cfg if cfg is not None else load_behavior_config()
    keys = [
        "deploy.git_sync_after",
        "git.update",
        "git.push",
        "memory.record_observation",
        "memory.mirror_to_lessons_inbox",
        "promote.to_lesson",
        "promote.to_rule",
        "promote.to_template",
        "promote.to_decision",
        "promote.auto_to_rule",
        "promote.auto_to_rule_on_standing",
        "promote.auto_to_lesson",
        "dream.mode",
        "dream.write_report",
        "dream.auto_run",
        "core_write.operations.tag_add",
        "core_write.operations.tag_relate",
        "core_write.operations.tag_weight_update",
        "core_write.operations.tag_suggest_apply",
        "core_write.operations.tag_weight_authority_writeback",
    ]
    rows = []
    for key in keys:
        rows.append({"operation": key, "mode": resolve_mode(key, data)})
    kinds = ((data.get("memory") or {}).get("kinds") or {})
    for kind, mode in sorted(kinds.items()):
        rows.append({"operation": "memory.kinds.{0}".format(kind), "mode": normalize_mode(mode)})
    return rows
