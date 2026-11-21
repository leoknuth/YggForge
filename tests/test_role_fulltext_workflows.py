"""完整角色文本、固定首入口、工作流与业务记录边界回归。"""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "yggforge-core/scripts"
sys.path.insert(0, str(SCRIPTS))
from knowledge.graph_build import build_indexes
from knowledge.spaces import shared_space
from roles.executor import execute
from roles.loader import load_task, prepare_context
from roles.registry import RoleError, create_role, load_role
from roles.skills import resources, select
from cmds.roles import role_cli


class FullRoleWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.core = self.root / "yggforge-core"
        (self.core / "config").mkdir(parents=True)
        (self.core / "config/roles.defaults.json").write_text(
            json.dumps({"allowed_shared_paths": [],
                        "retrieval": {"shared_limit": 5, "role_limit": 5, "max_chars": 2000, "skill_limit": 4}}),
            encoding="utf-8",
        )
        (self.core / "graph").mkdir()
        (self.core / "graph/tag-graph.yaml").write_text('{"tags":{}}', encoding="utf-8")
        (self.core / "schemas").mkdir()
        shutil.copyfile(SCRIPTS.parent / "schemas/role.schema.yaml", self.core / "schemas/role.schema.yaml")
        self.role = create_role("analyst", "完整研究角色", "仅临时夹具，不含真实用户资料", self.core)
        self.config = json.loads((self.role.root / "role.yaml").read_text(encoding="utf-8"))
        self.long_body = ("完整方法、矩阵、公式与检查门禁。\n" * 4000) + "正文尾部完整标记"
        self.skill_names = [f"method-{i}" for i in range(6)]
        for name in self.skill_names:
            directory = self.role.root / "skills" / name
            directory.mkdir()
            (directory / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: 完整专业方法\nmetadata: {{\"tags\":[\"research\"]}}\n---\n" + self.long_body,
                encoding="utf-8",
            )
        # 特殊根级入口须按自身name定位，不能扫描并列技能与业务数据。
        self.entry = self.role.root / "skills/SKILL.md"
        self.entry.write_text("---\nname: study-buddy\ndescription: 根级学习方法\n---\n根级方法完整标记", encoding="utf-8")
        (self.role.root / "skills/LICENSE").write_text("保留必要许可", encoding="utf-8")
        (self.role.root / "skills/data").mkdir()
        (self.role.root / "skills/data/client.json").write_text('{"private":"不属于根技能资源"}', encoding="utf-8")
        self.config["skills"] = ["skills/SKILL.md"] + ["skills/" + name for name in self.skill_names]
        self.config["default_skills"] = ["skills/SKILL.md"]
        self.config["skill_workflows"] = {"natal": ["skills/" + name for name in self.skill_names],
                                         "brief": ["skills/method-0"]}
        self.config["context_files"] = ["SOUL.md", "USER.md", "TOOLS.md"]
        for filename in self.config["context_files"]:
            (self.role.root / filename).write_text(self.long_body + filename, encoding="utf-8")
        self.record = self.role.root / "records/research/case-one"
        self.record.mkdir(parents=True)
        (self.record / "STATE.md").write_text(self.long_body + "状态尾部完整标记", encoding="utf-8")
        (self.record / "data.txt").write_text("本记录获准原始数据", encoding="utf-8")
        self.config["records"] = {"case-one": {"path": "records/research/case-one", "state": "STATE.md"}}
        self.save()
        build_indexes(space=shared_space(self.core))

    def save(self):
        (self.role.root / "role.yaml").write_text(json.dumps(self.config), encoding="utf-8")
        self.role = load_role("analyst", self.core)

    def task(self, **fields):
        task = {"task_id": "fulltext", "prompt": "完成完整研究", "tags": ["research"], "project_id": "case-one"}
        task.update(fields)
        return task

    def test_fulltext_over_32kb_survives_bundle_prompt_and_snapshots(self):
        task = self.task(skills=["method-0"], files=["data.txt"])
        bundle = prepare_context("analyst", task, self.core)
        original = (self.role.root / "skills/method-0/SKILL.md").read_text(encoding="utf-8")
        self.assertGreater(len(original.encode("utf-8")), 32768)
        self.assertEqual(bundle.skills[0]["body"], original)
        for item in bundle.context_files:
            self.assertEqual(item["body"], (self.role.root / item["path"]).read_text(encoding="utf-8"))
            self.assertFalse(item["truncated"])
        self.assertEqual(bundle.record_state["body"], (self.record / "STATE.md").read_text(encoding="utf-8"))
        self.assertFalse(bundle.record_state["truncated"])
        self.assertIn("状态尾部完整标记", bundle.prompt())
        self.assertNotIn("最终用中文给出简洁结论", bundle.prompt())
        self.assertNotIn("project_state", bundle.as_dict())
        self.assertEqual(bundle.context.project_id, "case-one")
        with patch("roles.executor.HOST_RUNTIME_ROOT", self.root / "runtime"):
            result = execute(bundle, backend="prepare")
        workspace = Path(result["workspace"])
        self.assertEqual((workspace / "skills/method-0/SKILL.md").read_text(encoding="utf-8-sig"), original)
        self.assertEqual((workspace / "record/STATE.md").read_text(encoding="utf-8-sig"), bundle.record_state["body"])
        self.assertEqual((workspace / "record/data.txt").read_text(encoding="utf-8-sig"), "本记录获准原始数据")
        self.assertFalse((workspace / "project").exists())

    def test_workflow_more_than_four_and_default_router_are_not_cut(self):
        _, active = select(self.role, self.task(workflow="natal"))
        self.assertEqual([item["name"] for item in active], ["study-buddy"] + self.skill_names)
        self.assertTrue(all(item["body"].endswith("正文尾部完整标记") for item in active[1:]))
        _, brief = select(self.role, self.task(workflow="brief"))
        self.assertEqual([item["name"] for item in brief], ["study-buddy", "method-0"])

    def test_more_than_four_defaults_survive_optional_budget(self):
        self.config["default_skills"] = ["skills/" + name for name in self.skill_names]
        self.save()
        _, active = select(self.role, self.task(tags=["unmatched"], prompt="未命中其他技能"))
        self.assertEqual([item["name"] for item in active], self.skill_names)

    def test_explicit_user_skills_override_workflow_and_default(self):
        _, active = select(self.role, self.task(workflow="natal", skills=["method-5"]))
        self.assertEqual([item["name"] for item in active], ["method-5"])
        _, all_explicit = select(self.role, self.task(skills=self.skill_names))
        self.assertEqual([item["name"] for item in all_explicit], self.skill_names)

    def test_unknown_default_workflow_and_legacy_projects_fail(self):
        with self.assertRaises(RoleError):
            select(self.role, self.task(workflow="unknown"))
        for field, value in [("default_skills", ["skills/missing"]),
                             ("skill_workflows", {"natal": ["skills/missing"]}),
                             ("projects", {})]:
            with self.subTest(field=field):
                original = dict(self.config)
                self.config[field] = value
                with self.assertRaises(RoleError):
                    self.save()
                self.config = original
                self.save()

    def test_root_entry_name_and_path_are_unambiguous_and_resources_stay_local(self):
        for requested in ["study-buddy", "skills/SKILL.md"]:
            _, active = select(self.role, self.task(skills=[requested]))
            self.assertEqual(active[0]["name"], "study-buddy")
            actual = [Path(path).relative_to(self.role.root / "skills").as_posix()
                      for path in active[0]["resource_paths"]]
            self.assertEqual(actual, ["LICENSE"])
        with self.assertRaises(RoleError):
            select(self.role, self.task(skills=["skills"]))
        with self.assertRaises(RoleError):
            resources(self.entry, ["method-0"])

    def test_standard_nested_resources_are_respected_with_and_without_pyyaml(self):
        support = self.role.root / "skills/references"
        support.mkdir()
        (support / "method.md").write_text("根技能自身参考", encoding="utf-8")
        self.entry.write_text("---\nname: study-buddy\nmetadata:\n  resources:\n    - references/method.md\n---\n完整入口",
                              encoding="utf-8")
        for without_yaml in [False, True]:
            with self.subTest(without_yaml=without_yaml):
                with patch.dict(sys.modules, {"yaml": None}) if without_yaml else patch.dict(sys.modules, {}):
                    _, active = select(self.role, self.task(skills=["study-buddy"]))
                self.assertEqual(active[0]["resource_paths"], [str(support / "method.md")])
        self.entry.write_text("---\nname: study-buddy\nmetadata:\n  resources: []\n---\n完整入口", encoding="utf-8")
        with patch.dict(sys.modules, {"yaml": None}):
            _, active = select(self.role, self.task(skills=["study-buddy"]))
        self.assertEqual(active[0]["resource_paths"], [])

    def test_record_metadata_and_private_roots_are_bounded(self):
        self.assertEqual(self.role.metadata()["records"], ["case-one"])
        self.assertNotIn("projects", self.role.metadata())
        self.config["records"]["case-one"]["path"] = "../analyst/records/research/case-one"
        with self.assertRaises(RoleError):
            self.save()
        self.config["records"]["case-one"]["path"] = "records/research/case-one"
        self.save()
        other = self.core / "roles/other/records/case-one"
        other.mkdir(parents=True)
        (other / "STATE.md").write_text("另一角色私有事实", encoding="utf-8")
        with self.assertRaises(RoleError):
            prepare_context("analyst", self.task(project_root=str(other), files=["STATE.md"]), self.core)
        with self.assertRaises(RoleError):
            prepare_context("analyst", self.task(project_root=str(self.role.root)), self.core)

    def test_cli_workflow_overrides_task_file_and_preserves_project_scope(self):
        file = self.root / "task.json"
        file.write_text(json.dumps(self.task(workflow="brief")), encoding="utf-8")
        loaded = load_task(file, workflow="natal")
        self.assertEqual(loaded["workflow"], "natal")
        self.assertEqual(loaded["project_id"], "case-one")
        parsed = role_cli.parser().parse_args(["prepare", "analyst", "--workflow", "natal", "--tag", "research", "--task", "完整研究"])
        self.assertEqual(parsed.workflow, "natal")


if __name__ == "__main__":
    unittest.main()
