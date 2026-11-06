#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tag↔tag 邻接图加载与加权扩展（O1）。

扩跳语义：边权 w∈[0,1] 为关联强度；路径强度 ∏w；
内部代价 cost=-ln(w)。在 hop≤H 约束下求最小代价路径
（hop-constrained most-reliable path）。
"""

from __future__ import print_function

import heapq
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

from lib.common import normalize_tag

from knowledge.graph_models import GraphError


@dataclass
class TagExpandInfo:
    """单个 tag 的扩跳结果。"""

    hop: int
    cost: float
    strength: float
    path: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "hop": self.hop,
            "cost": self.cost,
            "strength": self.strength,
            "path": list(self.path),
        }


class TagGraph(object):
    """tag↔tag 邻接表（内存无向，YAML 可单向存储）。"""

    def __init__(
        self,
        adjacency: Dict[str, List[Tuple[str, float]]],
        default_hop: int = 2,
        max_nodes: int = 64,
        min_expand: float = 0.15,
        epsilon: float = 1e-6,
        default_edge: float = 0.70,
        hop_decay: float = 0.75,
    ) -> None:
        self.adjacency = adjacency
        self.default_hop = default_hop
        self.max_nodes = max_nodes
        self.min_expand = float(min_expand)
        self.epsilon = float(epsilon)
        self.default_edge = float(default_edge)
        self.hop_decay = float(hop_decay)

    @classmethod
    def load(cls, path: Path, config: Dict[str, Any]) -> "TagGraph":
        """从 YAML 加载 tag 邻接图；可选对称化。"""
        if not path.exists():
            raise GraphError("缺少 tag 邻接图: {0}".format(path))
        text = path.read_text(encoding="utf-8-sig")
        if yaml is not None:
            raw = yaml.safe_load(text) or {}
        else:
            try:
                from knowledge.tag_yaml import _parse_simple_tag_graph_yaml
            except Exception as exc:  # pragma: no cover
                raise GraphError("需要 PyYAML 才能加载 tag-graph.yaml: {0}".format(exc))
            raw = _parse_simple_tag_graph_yaml(text)

        defaults = raw.get("defaults") or {}
        default_hop = int(defaults.get("hop", config.get("default_hop", 2)))
        max_nodes = int(defaults.get("max_nodes", config.get("max_tag_nodes", 64)))

        weight_cfg = config.get("weight") or {}
        default_edge = float(weight_cfg.get("default_edge", 0.70))
        min_expand = float(weight_cfg.get("min_expand", 0.15))
        epsilon = float(weight_cfg.get("epsilon", 1e-6))
        hop_decay = float(weight_cfg.get("hop_decay", 0.75))
        undirected = bool(weight_cfg.get("undirected_load", True))

        # directed edges first: (src,dst) -> weight
        directed: Dict[Tuple[str, str], float] = {}
        for tag, body in (raw.get("tags") or {}).items():
            src = normalize_tag(str(tag))
            related_list = []
            if isinstance(body, dict):
                related_list = body.get("related") or []
            for item in related_list:
                if isinstance(item, dict):
                    dst = normalize_tag(str(item.get("tag", "")))
                    if "weight" in item and item.get("weight") is not None:
                        weight = float(item.get("weight"))
                    else:
                        weight = default_edge
                else:
                    dst = normalize_tag(str(item))
                    weight = default_edge
                if not dst or dst == src:
                    continue
                weight = max(0.0, min(1.0, weight))
                key = (src, dst)
                prev = directed.get(key)
                if prev is None or weight > prev:
                    directed[key] = weight

        adjacency: Dict[str, List[Tuple[str, float]]] = {}
        if undirected:
            undirected_w: Dict[Tuple[str, str], float] = {}
            for (a, b), w in directed.items():
                lo, hi = (a, b) if a < b else (b, a)
                prev = undirected_w.get((lo, hi))
                if prev is None or w > prev:
                    undirected_w[(lo, hi)] = w
            for (a, b), w in undirected_w.items():
                adjacency.setdefault(a, []).append((b, w))
                adjacency.setdefault(b, []).append((a, w))
        else:
            for (a, b), w in directed.items():
                adjacency.setdefault(a, []).append((b, w))

        # stable neighbor order
        for src in adjacency:
            adjacency[src].sort(key=lambda x: x[0])

        return cls(
            adjacency=adjacency,
            default_hop=default_hop,
            max_nodes=max_nodes,
            min_expand=min_expand,
            epsilon=epsilon,
            default_edge=default_edge,
            hop_decay=hop_decay,
        )

    def edge_cost(self, weight: float) -> float:
        w = max(float(weight), self.epsilon)
        return -math.log(w)

    def expand(
        self,
        seeds: Sequence[str],
        hop: Optional[int] = None,
        max_nodes: Optional[int] = None,
    ) -> Dict[str, TagExpandInfo]:
        """hop 约束最可靠路径扩展。

        返回 tag → TagExpandInfo（种子 hop=0, strength=1, cost=0）。
        边权 w < min_expand 不扩展。排序偏好：同 hop 下 cost 更小（强度更大）。
        """
        limit_hop = self.default_hop if hop is None else int(hop)
        limit_nodes = self.max_nodes if max_nodes is None else int(max_nodes)

        best: Dict[str, TagExpandInfo] = {}
        # 输出只保留每个标签的最佳路径，扩展状态必须同时保留跳数预算。
        states: Dict[Tuple[str, int], TagExpandInfo] = {}
        # heap entries: (cost, hop, tag, path_tuple)
        heap: List[Tuple[float, int, str, Tuple[str, ...]]] = []

        for seed in seeds:
            tag = normalize_tag(seed)
            if not tag:
                continue
            info = TagExpandInfo(hop=0, cost=0.0, strength=1.0, path=[tag])
            prev = best.get(tag)
            if prev is None or info.cost < prev.cost - 1e-15:
                best[tag] = info
                states[(tag, 0)] = info
                heapq.heappush(heap, (0.0, 0, tag, (tag,)))

        while heap:
            cost, dist, current, path = heapq.heappop(heap)
            cur = states.get((current, dist))
            if cur is None:
                continue
            # stale entry
            if abs(cost - cur.cost) > 1e-12 or dist != cur.hop:
                continue
            if dist >= limit_hop:
                continue
            for neighbor, weight in self.adjacency.get(current, []):
                if weight < self.min_expand:
                    continue
                new_hop = dist + 1
                if new_hop > limit_hop:
                    continue
                new_cost = cost + self.edge_cost(weight)
                new_strength = math.exp(-new_cost)
                new_path = path + (neighbor,)

                prev = states.get((neighbor, new_hop))
                better = False
                if prev is None:
                    if neighbor not in best and len(best) >= limit_nodes:
                        continue
                    better = True
                elif new_cost < prev.cost - 1e-15:
                    better = True
                elif abs(new_cost - prev.cost) <= 1e-15 and new_hop < prev.hop:
                    better = True
                if not better:
                    continue
                info = TagExpandInfo(
                    hop=new_hop,
                    cost=new_cost,
                    strength=new_strength,
                    path=list(new_path),
                )
                states[(neighbor, new_hop)] = info
                best_info = best.get(neighbor)
                if best_info is None or new_cost < best_info.cost - 1e-15 or (
                    abs(new_cost - best_info.cost) <= 1e-15 and new_hop < best_info.hop
                ):
                    best[neighbor] = info
                heapq.heappush(heap, (new_cost, new_hop, neighbor, new_path))
        return best
