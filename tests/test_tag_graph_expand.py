#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最小测试：tag-graph 加权扩展（hop-constrained Dijkstra，O1）。

三庭合议 P2-3：覆盖路径强度 ∏w、代价 -ln(w)、min_expand 过滤、hop 约束、
同 hop 下更低代价（更高强度）优先。纯标准库，pytest 与 `py -X utf8` 均可跑。

跑法：
    py -X utf8 tests\test_tag_graph_expand.py
    # 或 pytest tests\test_tag_graph_expand.py
"""
import math
import os
import sys
from pathlib import Path

# 让 lib/ 与 knowledge/ 可被导入（scripts/ 在 PYTHONPATH）
_SCRIPTS = Path(__file__).resolve().parent.parent / "yggforge-core" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from knowledge.tag_graph import TagGraph, TagExpandInfo  # noqa: E402


def _make_graph(edges, **kw):
    """edges: list of (a, b, w)。构造无向邻接表。"""
    adj = {}
    for a, b, w in edges:
        adj.setdefault(a, []).append((b, w))
        adj.setdefault(b, []).append((a, w))
    for src in adj:
        adj[src].sort(key=lambda x: x[0])
    return TagGraph(adjacency=adj, **kw)


def test_seed_hop0_strength1():
    g = _make_graph([("a", "b", 0.8)])
    out = g.expand(["a"], hop=2)
    assert "a" in out
    assert out["a"].hop == 0
    assert out["a"].strength == 1.0
    assert out["a"].cost == 0.0
    assert out["a"].path == ["a"]


def test_min_expand_filters_weak_edge():
    # w < min_expand(0.15) 不扩展
    g = _make_graph([("a", "b", 0.10)], min_expand=0.15)
    out = g.expand(["a"], hop=2)
    assert "a" in out
    assert "b" not in out, "弱边 w<min_expand 不应扩展"


def test_path_strength_and_cost():
    g = _make_graph([("a", "b", 0.5)])
    out = g.expand(["a"], hop=2)
    assert "b" in out
    assert out["b"].hop == 1
    # cost = -ln(0.5)
    assert abs(out["b"].cost - (-math.log(0.5))) < 1e-9
    # strength = exp(-cost) = 0.5
    assert abs(out["b"].strength - 0.5) < 1e-9
    assert out["b"].path == ["a", "b"]


def test_two_hop_strength_is_product():
    # a -0.5-> b -0.4-> c ：路径强度 = 0.5*0.4 = 0.2；cost = -ln(0.2)
    g = _make_graph([("a", "b", 0.5), ("b", "c", 0.4)])
    out = g.expand(["a"], hop=2)
    assert "c" in out
    assert out["c"].hop == 2
    assert abs(out["c"].strength - 0.2) < 1e-9
    assert abs(out["c"].cost - (-math.log(0.2))) < 1e-9
    assert out["c"].path == ["a", "b", "c"]


def test_hop_constraint_respected():
    g = _make_graph([("a", "b", 0.5), ("b", "c", 0.4), ("c", "d", 0.3)])
    out = g.expand(["a"], hop=2)
    assert "c" in out and out["c"].hop == 2
    # hop=2 不应再扩到 d（hop 3）
    assert "d" not in out
    # hop=3 才到 d
    out3 = g.expand(["a"], hop=3)
    assert "d" in out3 and out3["d"].hop == 3


def test_lower_cost_path_wins():
    # a->b 两条路：直连 0.3 vs 经 c 的 0.9*0.9=0.81
    # 直连 cost=-ln(0.3)=1.204；经 c cost=-ln(0.81)=0.211 -> 更低代价（更高强度）应胜
    g = _make_graph([("a", "b", 0.3), ("a", "c", 0.9), ("c", "b", 0.9)])
    out = g.expand(["a"], hop=2)
    assert "b" in out
    # 经 c 的路径强度 0.81 > 直连 0.3，故应选 a->c->b
    assert abs(out["b"].strength - 0.81) < 1e-9
    assert out["b"].path == ["a", "c", "b"]


def _run_all():
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS  {0}".format(name))
            except AssertionError as exc:
                failures += 1
                print("FAIL  {0}: {1}".format(name, exc))
    return failures


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)
