"""角色加载、调度、任务范围与受控执行边界回归。"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "yggforge-core/scripts"
sys.path.insert(0, str(SCRIPTS))
from backends.factory import get_memory_backend
from knowledge.graph_build import build_indexes
from knowledge.spaces import role_space, shared_space
from roles.context import ContextBundle, RoleContext
from roles.executor import execute
from roles.loader import load_task, prepare_context
from roles.registry import RoleError, create_role, load_role
from roles.scheduler import run_task


class RoleRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.core = self.repo / "yggforge-core"
        (self.core / "config").mkdir(parents=True)
        (self.core / "config/roles.defaults.json").write_text(json.dumps({"allowed_shared_paths": ["knowledge/rules/shared.md"], "retrieval": {"shared_limit": 5, "role_limit": 5, "max_chars": 2000}}), encoding="utf-8")
        (self.core / "knowledge/rules").mkdir(parents=True)
        (self.core / "knowledge/rules/shared.md").write_text('---\nid: shared-id\ntitle: 共同约定\ntype: rule\nstatus: active\nconfidence: high\ntags: [agent]\n---\n共同正文\n', encoding="utf-8")
        (self.core / "graph").mkdir()
        (self.core / "graph/tag-graph.yaml").write_text('{"tags":{"agent":{"related":[]}}}', encoding="utf-8")
        for role in ("finance-expert", "legal-expert"):
            create_role(role, role, "测试角色，不含真实项目事实", self.core)
            memory = get_memory_backend(space=role_space(role, self.core))
            memory.record_observation("本角色记录：" + role, title="相同标题", tags=["agent"], scope="role", source="example")
        build_indexes(space=shared_space(self.core))

    def task(self, **kwargs):
        value = {"task_id": "example-task", "prompt": "验证角色来源", "tags": ["agent"], "project_id": ""}
        value.update(kwargs)
        return value

    def test_dual_context_has_shared_role_and_own_summary(self):
        bundle = prepare_context("finance-expert", self.task(), self.core).as_dict()
        self.assertTrue(bundle["shared_hits"])
        self.assertTrue(bundle["role_hits"])
        self.assertEqual(bundle["role_summary"]["owner_role"], "finance-expert")
        self.assertNotIn("legal-expert", json.dumps(bundle))
        self.assertEqual(bundle["role_hits"][0]["space_id"], "role:finance-expert")

    def test_project_records_are_not_reused_in_other_project(self):
        memory = get_memory_backend(space=role_space("finance-expert", self.core))
        memory.record_observation("只属于项目 A 的事实", tags=["agent"], project_id="project-a", scope="project-a")
        bundle = prepare_context("finance-expert", self.task(project_id="project-b"), self.core).as_dict()
        self.assertNotIn("只属于项目 A", json.dumps(bundle, ensure_ascii=False))

    def test_role_cannot_expand_shared_permissions(self):
        path = self.core / "roles/finance-expert/role.yaml"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["shared_paths"] = ["knowledge"]
        path.write_text(json.dumps(value))
        with self.assertRaises(RoleError):
            load_role("finance-expert", self.core)

    def test_role_entry_path_cannot_escape(self):
        path = self.core / "roles/finance-expert/role.yaml"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["identity"] = "../legal-expert/IDENTITY.md"
        path.write_text(json.dumps(value))
        with self.assertRaises(RoleError):
            load_role("finance-expert", self.core)

    def test_task_invalid_tags_and_other_role_file_are_rejected(self):
        file = self.repo / "invalid-task.json"
        file.write_text(json.dumps(self.task(tags="agent")), encoding="utf-8")
        with self.assertRaises(RoleError):
            load_task(file)
        task = self.task(project_root=str(self.core), files=["roles/legal-expert/memories/summary.md"])
        with self.assertRaises(RoleError):
            prepare_context("finance-expert", task, self.core)

    def test_prepared_dependency_does_not_transfer_private_context(self):
        captured = {}
        def fake(role_id, task, *args):
            captured[role_id] = task
            return {"role_id": role_id, "run_id": "run-" + role_id, "status": "prepared", "context": {"role_summary": "不应交给另一角色的私有内容"}}
        task = self.task(roles=["finance-expert", "legal-expert"], dependencies={"finance-expert": ["legal-expert"]})
        with patch("roles.scheduler.run_role", side_effect=fake):
            result = run_task(task)
        self.assertEqual(result["status"], "prepared")
        prior = captured["finance-expert"]["dependency_results"][0]
        self.assertEqual(set(prior), {"role_id", "run_id", "status"})

    def test_completed_dependency_transfers_only_output(self):
        captured = {}
        def fake(role_id, task, *args):
            captured[role_id] = task
            return {"role_id": role_id, "run_id": "run-" + role_id, "status": "completed", "output": "获准任务结果", "context": {"secret": "私有上下文"}}
        task = self.task(roles=["finance-expert", "legal-expert"], dependencies={"finance-expert": ["legal-expert"]})
        with patch("roles.scheduler.run_role", side_effect=fake):
            run_task(task, backend="codex")
        prior = captured["finance-expert"]["dependency_results"][0]
        self.assertEqual(prior["output"], "获准任务结果")
        self.assertNotIn("context", prior)

    def test_cycle_is_rejected(self):
        task = self.task(roles=["finance-expert", "legal-expert"], dependencies={"finance-expert": ["legal-expert"], "legal-expert": ["finance-expert"]})
        with self.assertRaises(RoleError):
            run_task(task)

    def test_prepare_cannot_claim_enforced_isolation(self):
        bundle = prepare_context("finance-expert", self.task(), self.core)
        with self.assertRaises(RoleError):
            execute(bundle, backend="prepare", isolation="enforced")

    def test_outer_timeout_preserves_failed_receipt_without_memory_success(self):
        bundle = prepare_context("finance-expert", self.task(), self.core)
        failed = subprocess.CompletedProcess([], 124, "", "timeout")
        with patch("roles.executor.HOST_RUNTIME_ROOT", self.repo / "runtime"), patch("roles.executor.shutil.which", return_value="codex"), patch("roles.executor.invoke", return_value=failed):
            result = execute(bundle, backend="codex", isolation="logical")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 124)
        self.assertTrue((Path(result["workspace"]) / "receipt.json").is_file())
        self.assertNotIn("memory", result)

    def test_unconfigured_storage_cannot_commit_role_memory(self):
        from roles.git_store import commit_roles
        with self.assertRaises(RoleError):
            commit_roles(["finance-expert"], core_root=self.core)

    def test_coordinator_holds_all_role_locks_until_commit(self):
        from contextlib import contextmanager
        from types import SimpleNamespace
        from roles.git_store import commit_roles
        config = self.core / "config/roles.defaults.json"
        value = json.loads(config.read_text())
        value["git_storage"] = {"enabled": True}
        config.write_text(json.dumps(value))
        held, staged = set(), [False]
        @contextmanager
        def lock(root, cfg, **kwargs):
            name = cfg["space_id"]
            held.add(name)
            try:
                yield
            finally:
                held.remove(name)
        def fake_git(command, **kwargs):
            args = command[3:]
            if args[0] in {"add", "commit"}:
                self.assertEqual(held, {"coordinator-git", "role:finance-expert", "role:legal-expert"})
            if args[0] == "add":
                staged[0] = True
            if args[0] == "commit":
                staged[0] = False
            output = "yggforge-core/roles/finance-expert/role.yaml" if args[0] == "diff" and staged[0] else ""
            return SimpleNamespace(returncode=0, stdout=output, stderr="")
        with patch("roles.git_store.graph_lock", side_effect=lock), patch("roles.git_store.subprocess.run", side_effect=fake_git), patch("backends.role_memory.role_summary_status", return_value={"matched": True}):
            commit_roles(["legal-expert", "finance-expert"], core_root=self.core)
        self.assertFalse(held)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux 内核文件隔离测试")
class LandlockTests(unittest.TestCase):
    def test_supervisor_does_not_follow_output_link_or_block_on_fifo(self):
        from roles.isolated_supervisor import read_regular
        import os
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data.txt").write_text("正常结果")
            self.assertEqual(read_regular(root / "data.txt"), "正常结果".encode())
            (root / "alias.txt").symlink_to(root / "data.txt")
            with self.assertRaises(OSError):
                read_regular(root / "alias.txt")
            os.mkfifo(root / "fifo")
            with self.assertRaises(ValueError):
                read_regular(root / "fifo")

    def test_reader_and_shell_cannot_read_other_role_or_symlink(self):
        from roles.landlock_worker import landlock_abi
        if not landlock_abi():
            self.skipTest("内核未启用 Landlock")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            own = root / "own"
            own.mkdir()
            (own / "data.txt").write_text("当前任务资料")
            other = root / "other.txt"
            other.write_text("其它角色资料")
            alias = own / "alias.txt"
            alias.symlink_to(other)
            request = root / "request.json"
            request.write_text(json.dumps({"action": "probe-files", "read_only": ["/usr", "/bin", "/lib", "/lib64", "/dev/null", str(own)], "writable": [], "attempts": [str(own / "data.txt"), str(other), str(alias)], "child_attempts": [str(other), str(alias)]}))
            proc = subprocess.run([sys.executable, str(SCRIPTS / "roles/landlock_worker.py"), str(request)], capture_output=True, text=True, timeout=15)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result[str(own / "data.txt")], "allowed")
            for key in (str(other), str(alias), "child:" + str(other), "child:" + str(alias)):
                self.assertEqual(result[key], "denied")


if __name__ == "__main__":
    unittest.main()
