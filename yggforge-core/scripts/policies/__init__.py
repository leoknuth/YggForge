# -*- coding: utf-8 -*-
"""YggForge 行为与写入策略层（policies 子包）。

汇集 ask/allow/deny 门禁、core 真源写入策略、channel 规范化等"治理"模块。
这些模块被 CLI 与钩子在执行写操作前调用，决定是否放行 / 以何种模式执行：

- ``behavior``：统一行为配置（记忆/晋升/dream/git/deploy/core_write/特性开关），
  交互式 always-allow 会回写 runtime。
- ``core_write``：对 ``yggforge-core`` 真源写入的策略，优先委托 ``behavior``，
  含权威 weight 回写 operation。
- ``channel``：channel 规范化（``config/channels.yaml``）。

设计上 ``behavior`` 与 ``core_write`` 互相懒加载（authorize 委托 + audit 回写），
故两者均用函数内 import 避免循环依赖。
"""
