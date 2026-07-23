#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识图数据模型。"""

from __future__ import print_function

from dataclasses import dataclass, field
from typing import List


@dataclass
class KnowledgeEntry:
    """一条真源知识的轻量视图。"""

    id: str
    path: str  # 相对仓库根的 posix 路径
    kind: str  # 属性名历史遗留：值为 front matter ``type``（非 FM 字段名 kind）
    title: str
    tags: List[str] = field(default_factory=list)
    related: List[str] = field(default_factory=list)
    priority: str = "unset"


@dataclass
class AssociateHit:
    """联想查询命中的一条结果。"""

    entry: KnowledgeEntry
    via_tags: List[str]
    min_tag_hop: int
    from_entry_related: bool
    path_strength: float = 1.0
    path_cost: float = 0.0
    via_path: List[str] = field(default_factory=list)


class GraphError(RuntimeError):
    """知识图构建或查询错误。"""
