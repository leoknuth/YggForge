# 角色知识空间与执行流程

日期：20261120。本文描述通用实现接口，不包含实际角色记忆或用户数据。

## 目录

- [存储架构图](#存储架构图)
- [流程图](#流程图)
- [接口与边界](#接口与边界)

## 存储架构图

```mermaid
flowchart TB
  subgraph core["核心真源"]
    shared["knowledge / plugins"]
    globalgraph["graph：共享索引"]
    role["roles / role-id：角色配置与技能"]
    notes["memories / notes：角色知识分层"]
    own["memories / graph：角色索引"]
    summary["memories / summary.md"]
    shared --> globalgraph
    role --> notes
    notes --> own
    notes --> summary
  end
  engine["同一图引擎 / KnowledgeSpace"]
  globalgraph --> engine
  own --> engine
  controller["可信协调者"]
  engine --> controller
  summary --> controller
  runtime["本地：会话、共享锁、缓存、部署产物"]
  controller --> runtime
  privategit["启用私有存储后：角色一致快照提交"]
  role --> privategit
  notes --> privategit
  own --> privategit
  summary --> privategit
```

## 流程图

```mermaid
flowchart TB
  task["任务：角色、标签、项目、资料"] --> bind["绑定 role-id / run-id / 配置版本"]
  bind --> load["加载入口、身份、技能"]
  load --> a["授权共享图联想"]
  load --> b["自身图联想"]
  load --> c["核对自身摘要"]
  a --> bundle["有来源的上下文包"]
  b --> bundle
  c --> bundle
  bundle --> mode{"执行方式"}
  mode -->|"prepare"| prepared["返回准备包，不声称模型已执行"]
  mode -->|"codex"| model["独立模型执行"]
  model --> output["获准任务结果"]
  output --> save["自身 inbox：agent 来源的草稿"]
  save --> refresh["重建自身图 / 更新摘要"]
  refresh --> commit["协调者串行提交角色快照"]
  output --> dependency["前序完成后交接输出"]
  dependency --> task
```

## 接口与边界

共享空间与角色空间分别携带 space_id。查询、保存、晋升和摘要使用同一空间身份，不能靠目录参数扩大范围。索引构建与记忆保存共享锁，异常保留原始记录并报告待刷新。

prepare 只准备上下文。enforced 文件模式在 Linux／WSL 用 Landlock 限定进程文件访问，模型使用原生临时工作区的获准快照；结果回收不跟随链接。普通模型服务网络连接并不因此成为网络隔离。

角色长期记忆固定排除公共框架发布。公共分发不附带实际 roles 数据，私有 Git 保存由管理者显式启用；用户可依据运行收据区分准备、完成与失败。
