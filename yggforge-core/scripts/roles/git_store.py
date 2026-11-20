"""协调者串行提交角色真源，不把其它工作区改动混入角色提交。"""

from pathlib import Path
from contextlib import ExitStack
import subprocess
from typing import Optional, Sequence

from knowledge.space_lock import graph_lock
from knowledge.spaces import role_space
from lib.repo_paths import CORE_ROOT, find_repo_root
from roles.registry import RoleError, load_role


def commit_roles(role_ids: Sequence[str], push: bool = False, core_root: Optional[Path] = None):
    core = Path(core_root or CORE_ROOT).resolve()
    from roles.registry import defaults
    policy = defaults(core).get("git_storage", {})
    if policy.get("enabled") is not True:
        raise RoleError("此部署未启用私有角色 Git 保存；先由管理者配置私有存储仓库。")
    repo = find_repo_root(core)
    selected = [load_role(role, core) for role in role_ids]
    if not selected:
        raise RoleError("至少选择一个角色提交。")
    paths = [role.root.relative_to(repo).as_posix() for role in selected]
    def git(*args):
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8")
        if result.returncode:
            raise RoleError("角色 Git 收尾失败，保留当前状态供处理：" + result.stderr[:1600])
        return result.stdout.strip()
    with graph_lock(core, {"space_id": "coordinator-git"}, timeout=30):
        from backends.role_memory import role_summary_status
        with ExitStack() as locks:
            # 固定顺序锁住所有所选角色，暂存和提交期间不能插入一半记忆更新。
            for role in sorted(selected, key=lambda item: item.id):
                space = role_space(role.id, core)
                locks.enter_context(graph_lock(space.root, space.config, timeout=30))
                if not role_summary_status(space).get("matched"):
                    raise RoleError("先刷新角色图和摘要再提交：" + role.id)
            staged = git("diff", "--cached", "--name-only").splitlines()
            if any(not any(name == prefix or name.startswith(prefix + "/") for prefix in paths) for name in staged):
                raise RoleError("暂存区有其它任务改动，角色提交不操作这些内容。")
            git("add", "--", *paths)
            if git("diff", "--cached", "--name-only"):
                git("commit", "-m", "chore(roles): 保存角色配置与长期记忆 " + ",".join(role.id for role in selected))
        if push:
            git("fetch", "origin")
            ahead, behind = map(int, git("rev-list", "--left-right", "--count", "HEAD...@{upstream}").split())
            if behind:
                git("pull", "--rebase", "--autostash")
            git("push")
        return {"status": "pushed" if push else "committed", "roles": list(role_ids), "commit": git("rev-parse", "HEAD")}
