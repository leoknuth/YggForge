"""导入角色后的渐进技能、支持资源、项目状态与工具未授权边界。"""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yggforge-core/scripts"))
from knowledge.graph_build import build_indexes
from knowledge.spaces import shared_space
from roles.registry import create_role, load_role, RoleError
from roles.loader import prepare_context
from roles.executor import execute
from roles.skills import catalog, select
from roles.tools import run_tool


class RoleImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.core = Path(self.temp.name) / "yggforge-core"
        (self.core / "config").mkdir(parents=True)
        (self.core / "config/roles.defaults.json").write_text('{"allowed_shared_paths":[],"retrieval":{"shared_limit":5,"role_limit":5,"max_chars":2000}}')
        (self.core / "graph").mkdir()
        (self.core / "graph/tag-graph.yaml").write_text('{"tags":{}}')
        self.role = create_role("finance-expert", "金融专家", "用于导入能力验证", self.core)
        self.config = json.loads((self.role.root / "role.yaml").read_text())
        for name, tag in (("charts", "chart"), ("research", "research")):
            directory = self.role.root / "skills" / name
            (directory / "references").mkdir(parents=True)
            body = "方法正文" * 2300 + "完整结束标记"
            metadata = json.dumps({"tags":[tag],"requires":[]}, ensure_ascii=False)
            (directory / "SKILL.md").write_text('---\nname: '+name+'\ndescription: '+name+'\nmetadata: '+metadata+'\n---\n'+body, encoding="utf-8")
            (directory / "references/detail.md").write_text("可按需读取的支持资源", encoding="utf-8")
            (directory / ".env").write_text("不得投影的秘密占位")
        self.config["skills"] = ["skills/charts", "skills/research"]
        (self.role.root / "SOUL.md").write_text("简洁研究原则", encoding="utf-8")
        self.config["context_files"] = ["SOUL.md"]
        self.project = self.role.root / "projects/research-one"
        self.project.mkdir(parents=True)
        (self.project / "STATE.md").write_text("导入研究未复算；缺失输入须先核验", encoding="utf-8")
        (self.project / "data.txt").write_text("项目限定的数据", encoding="utf-8")
        (self.project / "chart.png").write_bytes(b"opaque-image-asset")
        self.config["projects"] = {"research-one":{"path":"projects/research-one","state":"STATE.md"}}
        (self.role.root / "role.yaml").write_text(json.dumps(self.config))
        self.role = load_role("finance-expert", self.core)
        build_indexes(space=shared_space(self.core))

    def task(self, **extra):
        value = {"task_id":"import-test", "prompt":"请检查研究进度", "tags":["research"], "project_id":"research-one"}
        value.update(extra)
        return value

    def test_metadata_catalog_and_only_selected_complete_entry(self):
        inventory, active = select(self.role, self.task(skills=["research"]))
        self.assertEqual(len(inventory), 2)
        self.assertEqual([item["name"] for item in active], ["research"])
        self.assertTrue(active[0]["body"].endswith("完整结束标记"))
        self.assertGreater(len(active[0]["body"]), 8192)
        self.assertFalse(any(Path(path).name == ".env" for path in active[0]["resource_paths"]))

    def test_auto_selection_uses_task_tags(self):
        inventory, active = select(self.role, self.task(tags=["chart"], prompt="画图"))
        self.assertEqual(active[0]["name"], "charts")

    def test_unknown_explicit_skill_is_rejected(self):
        with self.assertRaises(RoleError):
            select(self.role, self.task(skills=["unknown"]))

    def test_project_state_and_assets_are_owned_and_snapshotted(self):
        bundle = prepare_context("finance-expert", self.task(files=["data.txt", "chart.png"], skills=["research"]), self.core)
        self.assertEqual(bundle.project_state["project_id"], "research-one")
        self.assertIn("未复算", bundle.project_state["body"])
        self.assertNotIn("source_path", json.dumps(bundle.as_dict()))
        with patch("roles.executor.HOST_RUNTIME_ROOT", Path(self.temp.name) / "runtime"):
            result = execute(bundle, backend="prepare")
        root = Path(result["workspace"])
        self.assertTrue((root / "skills/research/references/detail.md").exists())
        self.assertFalse((root / "skills/research/.env").exists())
        self.assertTrue((root / "SOUL.md").exists())
        self.assertEqual((root / "project/chart.png").read_bytes(), b"opaque-image-asset")
        self.assertEqual((root / "project/data.txt").read_text(encoding="utf-8-sig"), "项目限定的数据")
        self.assertFalse((root / "skills/charts").exists())

    def test_other_role_project_cannot_be_declared_as_this_project(self):
        other = self.core / "roles/legal-expert/projects/other"
        other.mkdir(parents=True)
        with self.assertRaises(RoleError):
            prepare_context("finance-expert", self.task(project_root=str(other)), self.core)

    def test_provider_business_query_is_blocked_before_login(self):
        settings = {"tools":{"hithink-finance":{"roles":["finance-expert"],"installed":True,"authenticated":False,"command":["node","client"]}}}
        with patch("roles.tools.load_role", return_value=self.role), patch("roles.tools.configuration", return_value=settings), patch("roles.tools.subprocess.run") as run:
            with self.assertRaises(RoleError):
                run_tool("finance-expert", "hithink-finance", ["market","snapshot"])
            with self.assertRaises(RoleError):
                run_tool("finance-expert", "hithink-finance", ["auth","login"])
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
