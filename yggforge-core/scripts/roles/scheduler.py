"""按显式角色和依赖执行任务，不把准备上下文当成前序模型结果。"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional
from pathlib import Path

from knowledge.spaces import role_space
from roles.executor import execute, execution_settings
from roles.loader import prepare_context
from roles.registry import RoleError


def run_role(role_id: str, task: Dict[str, Any], backend: str = None, isolation: str = None, timeout: int = 180, core_root: Optional[Path] = None) -> Dict[str, Any]:
    backend, isolation = execution_settings(backend, isolation)
    bundle = prepare_context(role_id, task, core_root)
    result = execute(bundle, backend, isolation, timeout)
    if result["status"] == "completed":
        from backends.factory import get_memory_backend
        memory = get_memory_backend(space=role_space(role_id, core_root))
        project = task.get("project_id") or "task:" + task["task_id"]
        record = memory.record_observation(note=result["output"], title="任务结果：" + task["task_id"], source="agent", scope=project, tags=task["tags"], project_id=project, confidence="low")
        result["memory"] = record
        if record.get("status") == "recorded_refresh_pending":
            result.update({"status": "failed", "error": "模型结果已保存，但角色图或摘要刷新失败；需先修复派生物。"})
    return result


def run_task(task: Dict[str, Any], backend: str = None, isolation: str = None, timeout: int = 180, core_root: Optional[Path] = None) -> Dict[str, Any]:
    backend, isolation = execution_settings(backend, isolation)
    roles = task.get("roles", [])
    if not isinstance(roles, list) or not roles or len(set(roles)) != len(roles):
        raise RoleError("联合任务必须提供不重复的角色列表。")
    dependencies = task.get("dependencies", {})
    if not isinstance(dependencies, dict) or set(dependencies) - set(roles):
        raise RoleError("依赖配置包含未知角色。")
    for role, items in dependencies.items():
        if not isinstance(items, list) or set(items) - set(roles) or role in items:
            raise RoleError("非法角色依赖。")
    pending, results = set(roles), {}
    while pending:
        ready = [role for role in roles if role in pending and all(item in results for item in dependencies.get(role, []))]
        if not ready:
            raise RoleError("角色依赖存在循环。")
        def work(role):
            selected = dict(task)
            prior = []
            for parent in dependencies.get(role, []):
                item = results[parent]
                prior.append({"role_id": parent, "run_id": item["run_id"], "status": item["status"], **({"output": item["output"]} if item["status"] == "completed" else {})})
            if prior:
                selected["dependency_results"] = prior
            return run_role(role, selected, backend, isolation, timeout, core_root)
        with ThreadPoolExecutor(max_workers=min(4, len(ready))) as pool:
            futures = {role: pool.submit(work, role) for role in ready}
            for role in ready:
                results[role] = futures[role].result()
                pending.remove(role)
        if any(item["status"] == "failed" for item in results.values()):
            return {"task_id": task["task_id"], "status": "failed", "roles": results}
    return {"task_id": task["task_id"], "status": "completed" if backend != "prepare" else "prepared", "roles": results}
