# -*- coding: utf-8 -*-
"""YggForge 知识图与标签域（knowledge 子包）。

知识结构的读写内核，被 CLI 与记忆后端复用：

- ``graph``：兼容门面；实现拆在 ``graph_models`` / ``shard_store`` /
  ``tag_graph`` / ``graph_scan`` / ``graph_build`` / ``graph_query``。
- ``tag_manager``：``TagManager`` + 门面；YAML/同义词拆在 ``tag_yaml`` /
  ``synonyms``。写入受 ``policies.core_write`` 约束。
- ``knowledge_id``：条目 ID 生成。
- ``schema``：按 ``schemas/knowledge-item.schema.yaml`` v2 校验 front matter（必填含 ``type``）。

Front matter 统一解析在 ``lib.front_matter``（勿在子模块重复实现）。

对外优先 ``from knowledge.graph import ...`` /
``from knowledge.tag_manager import ...``；子模块也可直连。
"""
