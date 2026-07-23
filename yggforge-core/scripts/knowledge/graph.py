#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识图与联想检索核心库（兼容门面）。

职责：
1. 扫描真源 Markdown，构建 id→路径 与 tag→ids 的有序分片索引；
2. 加载独立维护的 tag 邻接表；
3. 按 hop 扩展相关 tag，再收集条目，并合并条目 related 一跳；
4. 在索引较小时全量载入，较大时按字典序前缀分片 + 行内二分
   （小：`_all.tsv`；tag 侧：`a.tsv`/`g.tsv`…；catalog 侧：`2026.tsv`/`202607.tsv`…）。
"""

from __future__ import print_function

from knowledge.graph_build import (
    DEFAULT_CONFIG_PATH,
    LOCAL_CONFIG_PATH,
    REPO_ROOT,
    build_indexes,
    decode_catalog_payload,
    encode_catalog_payload,
    load_graph_config,
)
from knowledge.graph_models import AssociateHit, GraphError, KnowledgeEntry
from knowledge.graph_query import KnowledgeGraphIndex
from lib.front_matter import as_str_list, parse_front_matter

from knowledge.graph_scan import (
    SKIP_DIR_NAMES,
    kind_from_path,
    path_depth_under_knowledge,
    scan_knowledge_entries,
    should_skip_path,
)
from knowledge.shard_store import GENERATED_BANNER, SortedShardStore
from knowledge.tag_graph import TagExpandInfo, TagGraph

__all__ = [
    "REPO_ROOT",
    "DEFAULT_CONFIG_PATH",
    "LOCAL_CONFIG_PATH",
    "SKIP_DIR_NAMES",
    "GENERATED_BANNER",
    "GraphError",
    "KnowledgeEntry",
    "AssociateHit",
    "SortedShardStore",
    "TagGraph",
    "TagExpandInfo",
    "load_graph_config",
    "parse_front_matter",
    "kind_from_path",
    "path_depth_under_knowledge",
    "should_skip_path",
    "as_str_list",
    "scan_knowledge_entries",
    "encode_catalog_payload",
    "decode_catalog_payload",
    "build_indexes",
    "KnowledgeGraphIndex",
]
