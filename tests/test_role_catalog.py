"""角色标签只筛选发现目录，不改变角色资料或执行权限。"""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yggforge-core/scripts"))
from cmds.roles import role_cli
from roles.registry import create_role, load_role, RoleError


class RoleCatalogTests(unittest.TestCase):
    def test_brief_filters_all_tags_without_loading_skill_bodies(self):
        base = {"revision": 1, "description": "角色用途", "skills": ["skills/method"], "records": ["case"], "shared_paths": [], "context_files": []}
        roles = [dict(base, id="one", name="甲", tags=["research", "finance"]), dict(base, id="two", name="乙", tags=["research"])]
        output = io.StringIO()
        with patch.object(sys, "argv", ["role_cli", "list", "--brief", "--tag", "research", "--tag", "finance"]), patch.object(role_cli, "list_roles", return_value=roles), contextlib.redirect_stdout(output):
            self.assertEqual(role_cli.main(), 0)
        found = json.loads(output.getvalue())["roles"]
        self.assertEqual([item["id"] for item in found], ["one"])
        self.assertEqual((found[0]["skill_count"], found[0]["record_count"]), (1, 1))
        self.assertNotIn("project_count", found[0])
        self.assertNotIn("skills", found[0])

    def test_unknown_tags_produce_no_candidate(self):
        with patch.object(sys, "argv", ["role_cli", "list", "--tag", "absent"]), patch.object(role_cli, "list_roles", return_value=[{"id": "one", "tags": []}]), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(role_cli.main(), 0)
        self.assertEqual(json.loads(output.getvalue())["roles"], [])

    def test_registry_rejects_invalid_tags(self):
        with tempfile.TemporaryDirectory() as temporary:
            core = Path(temporary) / "yggforge-core"
            (core / "graph").mkdir(parents=True)
            (core / "graph/tag-graph.yaml").write_text('{"tags":{}}', encoding="utf-8")
            role = create_role("sample", "样例", "标签验证", core)
            config = json.loads((role.root / "role.yaml").read_text(encoding="utf-8"))
            config["tags"] = ["research"]
            (role.root / "role.yaml").write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual(load_role("sample", core).tags, ("research",))
            config["tags"] = [""]
            (role.root / "role.yaml").write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(RoleError):
                load_role("sample", core)


if __name__ == "__main__":
    unittest.main()
