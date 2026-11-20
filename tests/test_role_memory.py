#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""角色记忆回归：跨角色边界、项目过滤、摘要、晋升与真实 CLI。"""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "yggforge-core/scripts"))
from backends.role_memory import RoleMemoryBackend, RoleMemoryError, role_summary_status
from cmds.pipeline import promote
from knowledge import spaces
from lib.front_matter import parse_front_matter


class RoleMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ygg-role-memory-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.core = self.repo / "yggforge-core"
        (self.core / "config").mkdir(parents=True)
        (self.core / "config/graph.defaults.json").write_text('{"default_hop":1,"paths":{"tag_graph":"graph/tag-graph.yaml","catalog_dir":"graph/catalog","tag_inverted_dir":"graph/tag-inverted"}}', encoding="utf-8")
        self.backends = {}
        for role in ("finance-expert", "legal-expert"):
            root = self.core / "roles" / role
            (root / "memories/graph").mkdir(parents=True)
            (root / "role.yaml").write_text(json.dumps({"id": role}), encoding="utf-8")
            (root / "memories/graph/tag-graph.yaml").write_text("tags: {}\n", encoding="utf-8")
            self.backends[role] = RoleMemoryBackend(spaces.role_space(role, self.core), {"memory": {"auto_refresh": True}})

    def record(self, role="finance-expert", note="可复用的计算纠错", **kwargs):
        return self.backends[role].record_observation(note, tags=["probe"], force="allow", **kwargs)

    def test_role_records_graph_summary_and_no_global_mirror(self):
        finance = self.record(title="同名记录")
        legal = self.record("legal-expert", "法律专家专属依据", title="同名记录")
        for role, result in (("finance-expert", finance), ("legal-expert", legal)):
            path = Path(result["raw_path"])
            path.relative_to(self.core / "roles" / role / "memories/notes/lessons/inbox")
            metadata, _ = parse_front_matter(path.read_text(encoding="utf-8-sig"))
            self.assertEqual(metadata["owner_role"], role)
            self.assertEqual(metadata["space_id"], "role:" + role)
            self.assertRegex(metadata["recorded_at"], r"^\d{8}$")
            self.assertEqual(metadata["type"], "lesson")
            self.assertTrue((self.core / "roles" / role / "memories/graph/catalog/manifest.json").is_file())
            self.assertTrue(role_summary_status(self.backends[role].space)["matched"])
        self.assertFalse((self.core / "knowledge/lessons/inbox").exists())
        self.assertEqual(self.backends["finance-expert"].search_memories(query="法律专家专属"), [])

    def test_project_facts_do_not_enter_shared_role_summary(self):
        self.record(note="一般分析偏好", title="共同习惯")
        self.record(note="项目甲金额单位为万元", title="甲的单位", project_id="project-a", scope="project-a")
        self.record(note="项目乙金额单位为美元", title="乙的单位", project_id="project-b", scope="project-b")
        backend = self.backends["finance-expert"]
        summary = role_summary_status(backend.space)["body"]
        self.assertIn("一般分析偏好", summary)
        self.assertNotIn("万元", summary)
        found = backend.search_memories(query="", project_id="project-a", limit=20)
        self.assertEqual({item["title"] for item in found}, {"共同习惯", "甲的单位"})

    def test_update_delete_refresh_and_other_role_rejected(self):
        original = self.record(note="原始依据")
        other = self.record("legal-expert", "另一角色的依据")
        backend = self.backends["finance-expert"]
        before = role_summary_status(backend.space)["source_digest"]
        original_id = parse_front_matter(Path(original["raw_path"]).read_text(encoding="utf-8-sig"))[0]["id"]
        backend.update_entry(original_id, "已校对的依据")
        after = role_summary_status(backend.space)
        self.assertTrue(after["matched"])
        self.assertNotEqual(before, after["source_digest"])
        self.assertIn("已校对", after["body"])
        with self.assertRaises(RoleMemoryError):
            backend.delete_entry(other["raw_path"])
        with self.assertRaises(RoleMemoryError):
            backend.update_entry("../../legal-expert/memories/notes/a.md", "越界")
        backend.delete_entry(original_id)
        self.assertEqual(backend.search_memories(query="已校对"), [])
        self.assertTrue(role_summary_status(backend.space)["matched"])

    def test_symlink_alias_cannot_read_or_write_other_role(self):
        other = self.record("legal-expert", "法律专属秘密")
        notes = self.backends["finance-expert"].notes_root
        alias = notes / "reference/alias.md"
        alias.parent.mkdir(parents=True)
        try:
            alias.symlink_to(Path(other["raw_path"]))
        except OSError:
            self.skipTest("当前环境无创建符号链接权限")
        backend = self.backends["finance-expert"]
        self.assertEqual(backend.search_memories(query="法律专属秘密"), [])
        with self.assertRaises(RoleMemoryError):
            backend.update_entry(str(alias), "错误修改")

    def test_promotion_uses_own_inbox_and_ignores_draft_self_duplicate(self):
        result = self.record(note="以后一直这样，计算保留依据", title="计算规则")
        backend = self.backends["finance-expert"]
        output = io.StringIO()
        argv = ["promote", "--role", "finance-expert", "--entry", result["raw_path"], "--to", "rule", "--name", "calculation.md", "--auto", "--standing", "--yes", "--json"]
        with patch.object(spaces, "CORE_ROOT", self.core), patch.object(sys, "argv", argv), redirect_stdout(output):
            self.assertEqual(promote.main(), 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["results"][0]["write"], "ok")
        target = backend.notes_root / "rules/calculation.md"
        metadata, body = parse_front_matter(target.read_text(encoding="utf-8-sig"))
        self.assertEqual(metadata["type"], "rule")
        self.assertEqual(metadata["owner_role"], "finance-expert")
        self.assertIn("计算保留依据", body)
        self.assertFalse(Path(result["raw_path"]).exists())
        self.assertFalse((self.core / "knowledge/rules").exists())
        self.assertIsNone(promote.PROMOTION_SPACE.get())
        self.assertTrue(role_summary_status(backend.space)["matched"])

    def test_real_standing_cli_keeps_role_through_child_promotion(self):
        shutil.copytree(REPO / "yggforge-core/scripts", self.core / "scripts")
        shutil.copytree(REPO / "yggforge-core/schemas", self.core / "schemas")
        for name in ("memory.defaults.json", "behavior.defaults.yaml", "core-write.defaults.json"):
            source = REPO / "yggforge-core/config" / name
            if source.exists():
                shutil.copyfile(source, self.core / "config" / name)
        cli = self.core / "scripts/cmds/memory/remember.py"
        command = [sys.executable, "-X", "utf8", str(cli), "--role", "legal-expert", "--note", "以后一直这样，合同意见附条款依据", "--title", "依据要求", "--tags", "contract", "--yes", "--json"]
        process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)
        payload = json.loads(process.stdout)
        self.assertEqual(payload["status"], "recorded_and_promoted_rule", payload)
        self.assertTrue(list((self.core / "roles/legal-expert/memories/notes/rules").glob("*.md")))
        self.assertFalse((self.core / "knowledge/rules").exists())

    def test_refresh_failure_keeps_record_and_is_explicit(self):
        from backends import role_memory
        backend = self.backends["finance-expert"]
        with patch.object(role_memory, "refresh_role_memory", side_effect=OSError("派生索引中断")):
            saved = self.record(note="必须保留的原始记录")
        self.assertEqual(saved["status"], "recorded_refresh_pending")
        self.assertTrue(Path(saved["raw_path"]).is_file())
        self.assertTrue(saved["memory_refresh"]["needs_refresh"])
        self.assertNotIn("派生索引中断", str(saved["memory_refresh"]))
        role_memory.refresh_role_memory(backend.space)
        self.assertTrue(role_summary_status(backend.space)["matched"])

    def test_same_role_parallel_records_preserve_both(self):
        def save(number):
            return self.record(note="并发记录" + str(number), title="记录" + str(number))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, [1, 2]))
        self.assertEqual({item["status"] for item in results}, {"recorded"})
        backend = self.backends["finance-expert"]
        self.assertEqual(len(backend.search_memories(query="并发记录", limit=20)), 2)
        self.assertTrue(role_summary_status(backend.space)["matched"])

    def test_same_title_in_different_projects_is_not_duplicate(self):
        first = self.record(note="报表金额单位由项目确认", title="单位约定", project_id="project-a")
        second = self.record(note="报表金额单位由项目确认", title="单位约定", project_id="project-b")
        repeated = self.record(note="报表金额单位由项目确认", title="单位约定", project_id="project-a")
        self.assertEqual(first["status"], "recorded")
        self.assertEqual(second["status"], "recorded")
        self.assertEqual(repeated["status"], "duplicate")
        self.assertNotEqual(first["raw_path"], second["raw_path"])

    def test_foreign_owner_copied_into_inbox_cannot_be_promoted(self):
        saved = self.record(note="待整理经验")
        path = Path(saved["raw_path"])
        text = path.read_text(encoding="utf-8-sig").replace("owner_role: finance-expert", "owner_role: legal-expert")
        path.write_text(text, encoding="utf-8-sig")
        argv = ["promote", "--role", "finance-expert", "--entry", str(path), "--to", "lesson", "--yes"]
        with patch.object(spaces, "CORE_ROOT", self.core), patch.object(sys, "argv", argv), self.assertRaises(promote.PromoteError):
            promote.main()
        self.assertTrue(path.is_file())

    def test_real_cli_as_lesson_then_update_and_delete(self):
        shutil.copytree(REPO / "yggforge-core/scripts", self.core / "scripts")
        shutil.copytree(REPO / "yggforge-core/schemas", self.core / "schemas")
        for name in ("memory.defaults.json", "behavior.defaults.yaml", "core-write.defaults.json"):
            source = REPO / "yggforge-core/config" / name
            if source.exists():
                shutil.copyfile(source, self.core / "config" / name)
        command = [sys.executable, "-X", "utf8", str(self.core / "scripts/cmds/memory/remember.py"), "--role", "finance-expert", "--yes", "--json"]
        process = subprocess.run(command + ["--note", "一次计算校对经验", "--title", "校对经验", "--as", "lesson"], capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)
        saved = json.loads(process.stdout)
        self.assertEqual(saved["status"], "recorded_and_promoted_lesson")
        path = saved["promote"]["result"]["results"][0]["target"]
        updated = subprocess.run(command + ["--update-entry", path, "--note", "更新后的校对经验"], capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertEqual(json.loads(updated.stdout)["status"], "updated")
        removed = subprocess.run(command + ["--delete-entry", path], capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertFalse(Path(path).exists())

    def test_active_rule_changes_require_rule_authorization(self):
        from backends.role_memory import atomic_write_text, refresh_role_memory
        from lib.front_matter import render_with_front_matter
        from policies import behavior
        saved = self.record(note="已批准的规则依据")
        backend = self.backends["finance-expert"]
        path = Path(saved["raw_path"])
        metadata, body = parse_front_matter(path.read_text(encoding="utf-8-sig"))
        metadata.update({"type": "rule", "status": "active"})
        atomic_write_text(path, render_with_front_matter(metadata, body))
        refresh_role_memory(backend.space)
        before = path.read_bytes()
        with patch.object(behavior, "authorize", return_value={"allowed": False}) as gate:
            with self.assertRaises(RoleMemoryError):
                backend.update_entry(str(path), "替换规范")
            with self.assertRaises(RoleMemoryError):
                backend.delete_entry(str(path))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(gate.call_args.args[0], "promote.to_rule")


if __name__ == "__main__":
    unittest.main()
