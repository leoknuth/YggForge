#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O2：条目 tag 共现 → PPMI → 建议边权。"""

from __future__ import print_function

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from lib.common import normalize_tag
from lib.repo_paths import CORE_ROOT, GENERATED_ROOT

from knowledge.graph_build import load_graph_config
from knowledge.graph_scan import scan_knowledge_entries
from knowledge.synonyms import load_synonym_map
from knowledge.tag_yaml import DEFAULT_SYNONYMS_PATH


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(tag: str, synonym_map: Dict[str, str]) -> str:
    key = normalize_tag(tag)
    if not key:
        return ""
    return synonym_map.get(key, key)


def _suggest_cfg(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = config or load_graph_config()
    suggest = dict(cfg.get("suggest") or {})
    suggest.setdefault("min_cooccur", 3)
    suggest.setdefault("ppmi_tau", 2.0)
    suggest.setdefault("w_cooccur_min", 0.25)
    suggest.setdefault("w_cooccur_max", 0.65)
    suggest.setdefault("apply_floor", 0.55)
    suggest.setdefault("top_k_per_tag", 10)
    suggest.setdefault("max_tag_frequency", 0.50)
    suggest.setdefault("denylist", ["ygg"])
    suggest.setdefault("laplace_epsilon", 1.0)
    suggest.setdefault("output", "indexes/tag-suggestions.json")
    return suggest


def _ppmi_to_weight(ppmi: float, w_min: float, w_max: float, tau: float) -> float:
    span = max(0.0, w_max - w_min)
    mapped = w_min + span * math.tanh(ppmi / max(tau, 1e-9))
    return max(w_min, min(w_max, mapped))


def compute_suggestions(
    repo_root: Optional[Path] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """扫描 knowledge+plugins，生成 PPMI 建议边。"""
    root = repo_root or CORE_ROOT
    cfg = config or load_graph_config(root)
    scfg = _suggest_cfg(cfg)
    max_depth = int(cfg.get("max_path_depth_under_knowledge", 5))

    synonym_map = load_synonym_map(DEFAULT_SYNONYMS_PATH)
    entries, _warnings = scan_knowledge_entries(root, max_depth=max_depth)

    tag_doc_count: Counter = Counter()
    pair_count: Counter = Counter()
    n_docs = 0
    for entry in entries:
        tags: Set[str] = set()
        for raw in entry.tags:
            c = _canonical(raw, synonym_map)
            if c:
                tags.add(c)
        if len(tags) < 2:
            if tags:
                for t in tags:
                    tag_doc_count[t] += 1
                n_docs += 1
            continue
        n_docs += 1
        for t in tags:
            tag_doc_count[t] += 1
        ordered = sorted(tags)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                pair_count[(a, b)] += 1

    denylist = {normalize_tag(x) for x in (scfg.get("denylist") or []) if normalize_tag(str(x))}
    min_co = int(scfg["min_cooccur"])
    max_freq = float(scfg["max_tag_frequency"])
    tau = float(scfg["ppmi_tau"])
    w_min = float(scfg["w_cooccur_min"])
    w_max = float(scfg["w_cooccur_max"])
    top_k = int(scfg["top_k_per_tag"])
    eps = float(scfg["laplace_epsilon"])

    vocab = set(tag_doc_count.keys())
    v_size = max(1, len(vocab))
    hub_tags = set()
    if n_docs > 0:
        for tag, cnt in tag_doc_count.items():
            if (cnt / float(n_docs)) > max_freq:
                hub_tags.add(tag)

    candidates: List[Dict[str, Any]] = []
    for (a, b), co in pair_count.items():
        if co < min_co:
            continue
        if a in denylist or b in denylist:
            continue
        if a in hub_tags or b in hub_tags:
            continue
        ca = tag_doc_count[a]
        cb = tag_doc_count[b]
        # Laplace-smoothed probabilities
        p_a = (ca + eps) / (n_docs + eps * v_size)
        p_b = (cb + eps) / (n_docs + eps * v_size)
        p_ab = (co + eps) / max(n_docs, 1)
        denom = p_a * p_b
        if denom <= 0:
            continue
        pmi = math.log(p_ab / denom, 2)
        ppmi = max(0.0, pmi)
        if ppmi <= 0:
            continue
        w_suggest = _ppmi_to_weight(ppmi, w_min, w_max, tau)
        candidates.append(
            {
                "a": a,
                "b": b,
                "count": int(co),
                "count_a": int(ca),
                "count_b": int(cb),
                "ppmi": round(ppmi, 6),
                "w_suggest": round(w_suggest, 4),
            }
        )

    # per-tag top-k by ppmi
    by_tag: Dict[str, List[Dict[str, Any]]] = {}
    for item in candidates:
        by_tag.setdefault(item["a"], []).append(item)
        by_tag.setdefault(item["b"], []).append(item)
    keep: Set[Tuple[str, str]] = set()
    for tag, items in by_tag.items():
        items_sorted = sorted(items, key=lambda x: (-x["ppmi"], -x["count"], x["a"], x["b"]))
        for item in items_sorted[:top_k]:
            keep.add((item["a"], item["b"]))
    filtered = [c for c in candidates if (c["a"], c["b"]) in keep]
    filtered.sort(key=lambda x: (-x["ppmi"], -x["count"], x["a"], x["b"]))

    return {
        "version": 1,
        "generated_at": _utcnow_iso(),
        "n_entries": len(entries),
        "n_docs_with_tags": n_docs,
        "n_vocab": len(vocab),
        "params": {
            "min_cooccur": min_co,
            "ppmi_tau": tau,
            "w_cooccur_min": w_min,
            "w_cooccur_max": w_max,
            "top_k_per_tag": top_k,
            "max_tag_frequency": max_freq,
            "denylist": sorted(denylist),
            "hub_tags_excluded": sorted(hub_tags),
        },
        "suggestions": filtered,
    }


def write_suggestions(
    payload: Dict[str, Any],
    repo_root: Optional[Path] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Path:
    """写入可再生产物层（GENERATED_ROOT），不进 CORE graph。"""
    _ = repo_root  # 扫描仍用 CORE；产出落 GENERATED
    scfg = _suggest_cfg(config or load_graph_config(CORE_ROOT))
    out = GENERATED_ROOT / str(scfg["output"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def apply_suggestions(
    suggestions: Sequence[Dict[str, Any]],
    force: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """将建议边写入权威 tag-graph（经 tag_suggest_apply 闸门）。"""
    from knowledge.tag_manager import TagManager

    scfg = _suggest_cfg(config)
    floor = float(scfg["apply_floor"])
    tm = TagManager()
    applied = []
    skipped = []
    denied = None

    # 一次授权覆盖整批（摘要列出前几条）
    preview = suggestions[:8]
    summary_lines = [
        "PPMI 建议建边 {0} 条（展示前 {1}）".format(len(suggestions), len(preview))
    ]
    for item in preview:
        summary_lines.append(
            "  {0} <-> {1}  w≈{2}  ppmi={3}  n={4}".format(
                item.get("a"),
                item.get("b"),
                item.get("w_suggest"),
                item.get("ppmi"),
                item.get("count"),
            )
        )
    decision = tm._authorize(
        "tag_suggest_apply",
        "\n".join(summary_lines),
        force=force,
    )
    if not decision.get("allowed"):
        status = "dry_run" if decision.get("dry_run") else "denied"
        return {
            "status": status,
            "applied": [],
            "skipped": [],
            "core_write": decision,
            "count": len(suggestions),
        }

    for item in suggestions:
        a = str(item.get("a") or "")
        b = str(item.get("b") or "")
        w_suggest = float(item.get("w_suggest") or 0.0)
        if not a or not b:
            skipped.append({"a": a, "b": b, "reason": "empty"})
            continue
        existing_ab = tm._edge_weight(tm.canonicalize(a), tm.canonicalize(b))
        existing_ba = tm._edge_weight(tm.canonicalize(b), tm.canonicalize(a))
        existing = None
        if existing_ab is not None or existing_ba is not None:
            vals = [v for v in (existing_ab, existing_ba) if v is not None]
            existing = max(vals) if vals else None
        target = max(w_suggest, floor)
        if existing is not None and existing >= target - 1e-9:
            skipped.append(
                {
                    "a": a,
                    "b": b,
                    "reason": "authority_stronger_or_equal",
                    "existing": existing,
                    "w_suggest": w_suggest,
                }
            )
            continue
        # 已授权批次：单边写入强制 allow，避免二次 ask
        result = tm.add_relation(a, b, weight=target, force="allow")
        applied.append(
            {
                "a": a,
                "b": b,
                "weight": target,
                "w_suggest": w_suggest,
                "result": result.get("status"),
            }
        )

    return {
        "status": "ok",
        "applied": applied,
        "skipped": skipped,
        "core_write": decision,
        "count": len(suggestions),
    }
