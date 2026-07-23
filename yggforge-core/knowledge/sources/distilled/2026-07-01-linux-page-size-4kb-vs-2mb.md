---
id: 20260701215443-ksd$$$-l42$$$$$-69pu
title: 我将 Linux 页大小从 4KB 改为 2MB，结果性能彻底翻车了！
type: distilled-source
status: draft
confidence: medium
source: "https://mp.weixin.qq.com/s/hY5upuLC2rpPYQw09AeTvA?mpshare=1&scene=1&srcid=07018Mj49Yci3XhjB2nEDRFt&sharer_shareinfo=41e30680e43820a2ea228013684f796e&sharer_shareinfo_first=41e30680e43820a2ea228013684f796e#rd"
source_url: "https://mp.weixin.qq.com/s/hY5upuLC2rpPYQw09AeTvA?mpshare=1&scene=1&srcid=07018Mj49Yci3XhjB2nEDRFt&sharer_shareinfo=41e30680e43820a2ea228013684f796e&sharer_shareinfo_first=41e30680e43820a2ea228013684f796e#rd"
author: 深度Linux
inbox_path: knowledge/sources/inbox/2026-07-01-linux-page-size-4kb-vs-2mb.md
scope: Distilled from inbox source
last_reviewed: 2026-07-01
owners:
  - team
tags:
  - linux
  - performance
  - memory
  - hugepage
facts:
  - 给大家看真实的线上异常指标，全部是改 2MB 大页后直接出现的问题，这些问题并不是偶然现象，而是大页机制在微服务这种碎片化访问场景下必然会触发的系统性副作用。
  - 通过这次踩坑我总结出明确的使用边界，2MB 大页并非通用的性能优化方案，它更适合数据库、缓存组件、高性能网络转发、大型计算任务这类场景，这类业务的特点是单次占用内存空间大、内存使用连续、内存生命周期长，大页带来的 TLB 优化收益可以充分发挥出来。
  - 我连夜紧急回滚配置、抓取系统栈信息、逐项排查内核内存参数，足足折腾了一整天，才彻底摸清背后底层逻辑：大页的性能优势极度依赖业务场景，市面上绝大多数常规线上业务，保持系统默认 4KB 小页，才是最稳妥、性能最优的选择。
  - 在我的微服务场景中，业务瓶颈从来不是 CPU 地址翻译带来的开销，而是高频次的小额内存分配、释放，以及碎片化的内存读写。
  - 页面合并的过程需要频繁对页表加锁并进行遍历扫描，在高并发微服务场景下，这种操作会带来严重的内核锁竞争，不断抢占业务线程的 CPU 资源，最终让系统出现周期性的性能抖动，这也是优化之后服务稳定性反而不如优化前的重要原因。
inferences:
  - 这是自动生成的第一版 distilled 草稿，推论部分应由人工进一步确认。
practices:
  - 不要把 HugePage 当成默认全局优化项直接启用。
  - 做大页优化前，应先确认 workload 是否属于大内存、连续访问、长期驻留场景。
  - 任何页大小优化都应通过可回滚、可观测的实验验证。
risks:
  - 本条目由自动 distill 生成，仍需人工校对。
  - 若原始来源带有强叙事性、营销性或未验证数据，不应直接升级为规则。
promote_to: knowledge/lessons/
---
# 我将 Linux 页大小从 4KB 改为 2MB，结果性能彻底翻车了！
