#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""健康检查：Python / git / 布局 / 配置 / 索引 / 投影 / 重复 id / hooks。

由 ``ygg doctor`` 调用。输出红/黄/绿；非零退出码表示有 P0 问题。
"""

from __future__ import print_function

from pathlib import Path
import sys

# cmds/<domain>/<script>.py → scripts/
SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
SCRIPT_DIR = SCRIPTS_ROOT

import json
import subprocess
from typing import List, Tuple

from lib.repo_paths import CORE_ROOT, GENERATED_ROOT, REPO_ROOT, RUNTIME_ROOT

# ANSI 颜色（Windows 10+ 支持；alpine 支持）
_RED = "\033[31m"
_YEL = "\033[33m"
_GRN = "\033[32m"
_RST = "\033[0m"


def _color(level: str, msg: str) -> str:
    c = {"red": _RED, "yellow": _YEL, "green": _GRN}.get(level, "")
    return "{0}{1}{2}".format(c, msg, _RST)


def _stdout_utf8() -> None:
    """Windows 非 UTF-8 终端下避免中文标题 mojibake（三庭合议 P2-2）。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _check_python() -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 8):
        results.append(("red", "Python {0}.{1} < 3.8（需要 3.8+）".format(major, minor)))
    else:
        results.append(("green", "Python {0}.{1}".format(major, minor)))
    # 依 requirements.txt 逐条探测（新增依赖自动覆盖，无需改本函数）
    from lib.deps import check_deps

    deps = check_deps()
    if not deps:
        results.append(("yellow", "requirements.txt 不存在或为空（无推荐依赖声明）"))
    for d in deps:
        if d["installed"]:
            ver = " ({0})".format(d["version"]) if d["version"] else ""
            results.append(("green", "{0} 可用{1}".format(d["package"], ver)))
        else:
            results.append((
                "yellow",
                "{0} 不可用（pip install {0} 或 ygg doctor --fix-deps 自动补装）".format(d["package"]),
            ))
    return results


def _check_git() -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    try:
        out = subprocess.check_output(["git", "--version"], text=True).strip()
        results.append(("green", out))
    except (OSError, subprocess.CalledProcessError):
        results.append(("red", "git 不可用"))
    return results


def _check_layout() -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    for name in ("yggforge-core", "yggforge-generated", "yggforge-runtime"):
        p = REPO_ROOT / name
        if p.is_dir():
            results.append(("green", "目录 {0}/".format(name)))
        else:
            results.append(("red", "缺少 {0}/".format(name)))
    return results


def _check_config() -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    for rel in ("deploy.defaults.json", "sync.defaults.json", "memory.defaults.json"):
        p = CORE_ROOT / "config" / rel
        if not p.exists():
            results.append(("red", "缺少 config/{0}".format(rel)))
            continue
        try:
            json.loads(p.read_text(encoding="utf-8-sig"))
            results.append(("green", "config/{0} JSON 可解析".format(rel)))
        except Exception as exc:
            results.append(("red", "config/{0} JSON 解析失败: {1}".format(rel, exc)))
    bpath = CORE_ROOT / "config" / "behavior.defaults.yaml"
    if bpath.exists():
        results.append(("green", "config/behavior.defaults.yaml 存在"))
    else:
        results.append(("red", "缺少 config/behavior.defaults.yaml"))
    return results


def _check_catalog() -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    catalog = CORE_ROOT / "graph" / "catalog" / "_all.tsv"
    if not catalog.exists():
        results.append(("yellow", "catalog 不存在（运行 ygg graph build 重建）"))
        return results
    lines = catalog.read_text(encoding="utf-8").strip().splitlines()
    results.append(("green", "catalog {0} 条".format(len(lines))))
    return results


def _check_mdc() -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    try:
        code = subprocess.run(
            [sys.executable, str(SCRIPTS_ROOT / "ygg.py"), "project", "mdc", "--check"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        if code.returncode == 0:
            results.append(("green", "project mdc --check 通过"))
        else:
            results.append(("yellow", "project mdc --check 有差异（运行 ygg project mdc --write 修复）"))
    except Exception as exc:
        results.append(("yellow", "project mdc --check 执行失败: {0}".format(exc)))
    return results


def _check_duplicate_ids() -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    from lib.front_matter import parse_front_matter
    ids: dict = {}
    for root in ("rules", "decisions", "lessons", "templates", "reference"):
        r = CORE_ROOT / "knowledge" / root
        if not r.exists():
            continue
        for p in sorted(r.rglob("*.md")):
            if p.name.lower() == "readme.md":
                continue
            if "inbox" in p.parts:
                continue
            # 跳过模板文件（含占位 id）
            if p.name.endswith(".template.md"):
                continue
            try:
                meta, _ = parse_front_matter(p.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            eid = str(meta.get("id") or "").strip()
            if not eid or eid.startswith("<"):
                continue
            if eid in ids:
                results.append(("red", "重复 id: {0} ({1} 与 {2})".format(eid, p.name, ids[eid])))
            else:
                ids[eid] = p.name
    plugins = CORE_ROOT / "plugins"
    if plugins.exists():
        for p in sorted(plugins.rglob("*.md")):
            if p.name.lower() == "readme.md":
                continue
            try:
                meta, _ = parse_front_matter(p.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            eid = str(meta.get("id") or "").strip()
            if not eid or eid.startswith("<"):
                continue
            if eid in ids:
                results.append(("red", "重复 id: {0} ({1} 与 {2})".format(eid, p.name, ids[eid])))
            else:
                ids[eid] = p.name
    if not any(l == "red" for l, _ in results):
        results.append(("green", "无重复 id（{0} 条）".format(len(ids))))
    return results


def _check_hooks() -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    home = Path.home()
    hooks_json = home / ".cursor" / "hooks.json"
    if hooks_json.exists():
        results.append(("green", "~/.cursor/hooks.json 存在"))
        heartbeat = home / ".cursor" / "ygg_hook_heartbeat.txt"
        if heartbeat.exists():
            results.append(("green", "heartbeat 存在（钩子曾运行）"))
        else:
            results.append(("yellow", "heartbeat 不存在（钩子可能未触发；重启 Cursor 后发一条消息试试）"))
    else:
        results.append(("yellow", "~/.cursor/hooks.json 不存在（未部署；运行 ygg deploy link cursor）"))
    return results


def _check_last_trigger() -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    lt = RUNTIME_ROOT / "cache" / "last_trigger.json"
    if not lt.exists():
        results.append(("yellow", "last_trigger.json 不存在（钩子未运行或 default_trigger_on_chat=false）"))
        return results
    results.append(("green", "last_trigger.json 存在（触发检测器曾运行）"))
    # 三庭合议 P0-A 可观测性：parse_error 即触发线死亡，必须升红而非 OK
    try:
        obj = json.loads(lt.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        results.append(("red", "last_trigger.json 解析失败: {0}".format(exc)))
        return results
    pe = obj.get("parse_error")
    action = obj.get("action")
    cdt = obj.get("chat_default_trigger")
    if pe:
        results.append((
            "red",
            "last_trigger.json 含 parse_error（钩子 stdin 解析失败→default_trigger 静默 skip）：{0}".format(pe),
        ))
    elif action == "skip" and cdt is None:
        results.append((
            "yellow",
            "last_trigger.json action=skip 且 chat_default_trigger=null（默认触发未路由；若 default_trigger_on_chat=true 则疑似失效）",
        ))
    elif action in ("default_on", "explicit_ygg") or obj.get("should_trigger"):
        results.append(("green", "最近一次触发 action={0}".format(action)))
    return results


def _check_tag_graph_consistency() -> List[Tuple[str, str]]:
    """三庭合议 P1-5/P2-1：tag-graph.yaml 与 catalog/tag-inverted 双向对齐。

    - 孤儿（catalog 用了但图无节点）：联想只能 hop 0 命中，扩跳断链。
    - 孤岛（图有节点但无条目使用）：对联想零贡献，污染图质量指标。
    两者均报 yellow 供人审（勿自动删/连，见 orphan triage 共识）。
    """
    results: List[Tuple[str, str]] = []
    tg = CORE_ROOT / "graph" / "tag-graph.yaml"
    inv = CORE_ROOT / "graph" / "tag-inverted" / "_all.tsv"
    if not tg.exists() or not inv.exists():
        results.append(("yellow", "tag-graph.yaml 或 tag-inverted 不存在（运行 ygg graph build）"))
        return results
    # 图顶层 tag 节点（2 空格缩进的 `key:` 行，在 `tags:` 段下）
    graph_tags: set = set()
    in_tags = False
    for line in tg.read_text(encoding="utf-8-sig").splitlines():
        s = line.rstrip("\n")
        if s.startswith("tags:"):
            in_tags = True
            continue
        if in_tags:
            if s and s[0] not in (" ", "-", "#") and s.endswith(":") and ":" not in s[:-1]:
                break  # 离开 tags 段
            if s.startswith("  ") and not s.startswith("   ") and s.endswith(":"):
                name = s.strip()
                if name and not name.startswith("#") and ":" not in name[:-1]:
                    graph_tags.add(name[:-1].strip() if name.endswith(":") else name.strip())
    # 反查表 tag（第一列）
    catalog_tags: set = set()
    for line in inv.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if parts and parts[0].strip():
            catalog_tags.add(parts[0].strip())
    orphans = sorted(catalog_tags - graph_tags)
    islands = sorted(graph_tags - catalog_tags)
    if orphans:
        results.append((
            "yellow",
            "孤儿 tag（条目使用但图无节点，扩跳断链，{0} 个）：{1}".format(len(orphans), ", ".join(orphans[:12]) + ("…" if len(orphans) > 12 else "")),
        ))
    if islands:
        results.append((
            "yellow",
            "孤岛 tag（图有节点但无条目使用，{0} 个）：{1}".format(len(islands), ", ".join(islands)),
        ))
    if not orphans and not islands:
        results.append(("green", "tag-graph 与 catalog 双向对齐（无孤儿/孤岛）"))
    return results


def _check_bom() -> List[Tuple[str, str]]:
    """三庭合议 P1-1：核心 Markdown 须 UTF-8 with BOM（AGENTS.md 编码原则）。"""
    results: List[Tuple[str, str]] = []
    candidates = [
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "README.md",
    ]
    for d in [
        CORE_ROOT / "knowledge" / "rules",
        CORE_ROOT / "plugins",
        CORE_ROOT / "profiles",
        REPO_ROOT / "docs",
        # P2-1.6 BOM 检查范围扩展（三庭合议）：核心知识层全部纳入。
        CORE_ROOT / "knowledge" / "reference",
        CORE_ROOT / "knowledge" / "lessons",
        CORE_ROOT / "knowledge" / "templates",
        CORE_ROOT / "knowledge" / "decisions",
        CORE_ROOT / "knowledge" / "sources",
    ]:
        if d.is_dir():
            for p in d.rglob("*.md"):
                if p.name.lower() == "readme.md" or "inbox" in p.parts:
                    continue
                candidates.append(p)
    missing = []
    for p in candidates:
        if not p.exists():
            continue
        try:
            b = p.read_bytes()
        except Exception:
            continue
        has_bom = len(b) >= 3 and b[0] == 0xEF and b[1] == 0xBB and b[2] == 0xBF
        if not has_bom:
            missing.append(str(p.relative_to(REPO_ROOT)))
    if missing:
        shown = missing[:12]
        results.append((
            "yellow",
            "核心 .md 缺 BOM（{0} 个，违反 AGENTS.md 编码原则）：{1}{2}".format(
                len(missing), ", ".join(shown), "…" if len(missing) > 12 else ""
            ),
        ))
    else:
        results.append(("green", "核心 .md 均含 UTF-8 BOM"))
    return results


def _check_plugins() -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    plugins_root = CORE_ROOT / "plugins"
    if not plugins_root.exists():
        results.append(("yellow", "plugins/ 不存在（智能插件管理器未初始化）"))
        return results
    from lib.front_matter import parse_front_matter
    expected = ("skills", "mcp-servers", "hooks", "rules")
    for sub in expected:
        d = plugins_root / sub
        if d.is_dir():
            count = sum(1 for _ in d.rglob("*.md") if _.name.lower() != "readme.md")
            results.append(("green", "plugins/{0}/ ({1} 条)".format(sub, count)))
        else:
            results.append(("yellow", "缺少 plugins/{0}/".format(sub)))
    bad = 0
    total = 0
    for sub in expected:
        d = plugins_root / sub
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.md")):
            if p.name.lower() == "readme.md":
                continue
            total += 1
            try:
                meta, _ = parse_front_matter(p.read_text(encoding="utf-8-sig"))
            except Exception:
                bad += 1
                continue
            if not str(meta.get("type") or "").strip():
                bad += 1
    if total and bad:
        results.append(("red", "plugins/ 有 {0}/{1} 条缺 type 或 front matter 解析失败".format(bad, total)))
    elif total:
        results.append(("green", "plugins/ 全部 {0} 条均有 type".format(total)))
    return results


def _check_deploy_targets() -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    from lib.common import load_json
    from lib.repo_paths import resolve_core_source
    cfg_path = CORE_ROOT / "config" / "deploy.defaults.json"
    if not cfg_path.exists():
        results.append(("red", "缺少 config/deploy.defaults.json"))
        return results
    try:
        raw = load_json(cfg_path)
    except Exception as exc:
        results.append(("red", "deploy.defaults.json 解析失败: {0}".format(exc)))
        return results
    for name, spec in raw.items():
        profile = str(spec.get("profile") or name)
        pdir = CORE_ROOT / "profiles" / profile
        if not pdir.is_dir():
            results.append(("red", "target '{0}': 缺少 profiles/{1}/".format(name, profile)))
            continue
        missing = 0
        for m in spec.get("mappings", []):
            src = m.get("source")
            if src and not resolve_core_source(src).exists():
                missing += 1
            for ps in (m.get("sources") or {}).values():
                if ps and not resolve_core_source(ps).exists():
                    missing += 1
        if missing:
            results.append(("yellow", "target '{0}': {1} 个 mapping source 缺失".format(name, missing)))
        else:
            results.append(("green", "target '{0}': profiles/{1}/ + sources 就绪".format(name, profile)))
    return results


def _fix_deps() -> int:
    """检测并自动安装缺失依赖（经 behavior 门禁 deps.install）。"""
    from lib.deps import install_missing, missing_deps

    missing = missing_deps()
    if not missing:
        print("doctor: 无缺失依赖，无需补装")
        return 0
    # behavior 门禁：pip install 是系统变更，默认 ask
    if str(SCRIPTS_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_ROOT))
    from policies.behavior import authorize, force_from_flags

    force = None
    try:
        force = force_from_flags(yes="--yes" in sys.argv[1:], no="--no" in sys.argv[1:])
    except ValueError as exc:
        print("doctor: {0}".format(exc))
        return 1
    decision = authorize(
        "deps.install",
        "pip install 缺失依赖：{0}".format(", ".join(missing)),
        force=force,
    )
    if not decision.get("allowed"):
        print("doctor: 跳过依赖安装（{0}）".format(decision.get("reason", "denied")))
        if decision.get("hint"):
            print("  hint: {0}".format(decision["hint"]))
        return 2
    code, _installed = install_missing(only_missing=True)
    if code == 0:
        print("doctor: 依赖补装完成")
    else:
        print("doctor: 依赖补装失败（pip 返回 {0}）".format(code))
    return code


def main() -> int:
    _stdout_utf8()

    # --fix-deps：检测并自动补装缺失依赖（经 behavior 门禁）
    if "--fix-deps" in sys.argv[1:]:
        return _fix_deps()

    checks = [
        ("Python", _check_python),
        ("Git", _check_git),
        ("Layout", _check_layout),
        ("Config", _check_config),
        ("Catalog", _check_catalog),
        ("MDC", _check_mdc),
        ("Duplicate IDs", _check_duplicate_ids),
        ("Plugins", _check_plugins),
        ("Deploy targets", _check_deploy_targets),
        ("Hooks", _check_hooks),
        ("Trigger", _check_last_trigger),
        ("Tag graph consistency", _check_tag_graph_consistency),
        ("BOM", _check_bom),
    ]
    has_red = False
    for title, fn in checks:
        print("== {0} ==".format(title))
        for level, msg in fn():
            print("  {0}".format(_color(level, msg)))
            if level == "red":
                has_red = True
    print("")
    if has_red:
        print(_color("red", "doctor: FAIL（有 P0 问题需修复）"))
        return 1
    print(_color("green", "doctor: OK"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
