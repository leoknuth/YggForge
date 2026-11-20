# 金融与法律角色任务示例

日期：20261120。仅验证上下文准备、双路联想和依赖交接，不包含真实用户或项目事实。

## 目录

- [并行任务](#并行任务)
- [依赖任务](#依赖任务)
- [资料与来源](#资料与来源)

## 并行任务

financing-task.json 使用 project_id=example-financing 和 agent/financing 标签，让两角色分别加载摘要、共同命中和自身命中。

## 依赖任务

financing-followup-task.json 的金融角色依赖法律角色，验证结果交接。没有真实合同和数值，所以输出说明方法、依据和缺失资料。

## 资料与来源

初始化记忆 source 为 example，并提供公开方法资料入口。真实任务显式填写 project_id、project_root 和根内 files，保持授权与版本范围。
