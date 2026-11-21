"""标签写入保留原文并拒绝并发覆盖。"""

from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yggforge-core/scripts"))
from knowledge.tag_manager import TagManager
from knowledge.tag_yaml import load_yaml


JSON_GRAPH = {
    "version": 1,
    "defaults": {"hop": 2, "max_nodes": 64, "说明": {"筛选": ["已审核", "中文"]}},
    "metadata": {
        "范围": "角色记忆",
        "reviewed": "20261121",
        "来源": {"说明": '中文 "原始" 元数据\n保留换行', "verified": False},
        "optional": None,
    },
    "tags": {
        "工程": {
            "related": [{"tag": "排错", "weight": 0.7, "证据": {"来源": "实测", "次数": 2}}],
            "description": "工程经验",
            "aliases": ["工程实践"],
        },
        "排错": {
            "related": [{"tag": "工程", "weight": 0.7, "说明": "反向依据"}],
            "metadata": {"level": 2, "keywords": ["JSON", "图"]},
        },
    },
}


class TagWritesTest(unittest.TestCase):
    def test_read_missing_graph_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph = Path(tmp) / "tag-graph.yaml"
            manager = TagManager(graph, Path(tmp) / "synonyms.yaml")
            self.assertEqual(manager.existing_tags, set())
            self.assertFalse(graph.exists())

    def test_denied_add_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph = Path(tmp) / "tag-graph.yaml"
            manager = TagManager(graph, Path(tmp) / "synonyms.yaml")
            result = manager.add_tags(["research"], force="deny")
            self.assertEqual(result["status"], "denied")
            self.assertFalse(graph.exists())

    def test_allowed_add_creates_complete_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph = Path(tmp) / "tag-graph.yaml"
            manager = TagManager(graph, Path(tmp) / "synonyms.yaml")
            result = manager.add_tags(["research"], force="allow")
            self.assertEqual(result["status"], "updated")
            self.assertTrue(graph.exists())
            self.assertEqual(manager.existing_tags, {"research"})

    def test_add_preserves_original_comments_and_crlf(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph = Path(tmp) / "tag-graph.yaml"
            before = b"# manual comment\r\nversion: 1\r\ndefaults:\r\n  hop: 2\r\n  max_nodes: 64\r\ntags:\r\n  existing:\r\n    related: []\r\n"
            graph.write_bytes(before)
            manager = TagManager(graph, Path(tmp) / "synonyms.yaml")
            result = manager.add_tags(["research"], force="allow")
            self.assertEqual(result["status"], "updated")
            self.assertTrue(graph.read_bytes().startswith(before))
            self.assertEqual(manager.existing_tags, {"existing", "research"})

    def test_add_and_relate_json_graph_preserve_complete_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph = Path(tmp) / "tag-graph.yaml"
            graph.write_bytes((json.dumps(JSON_GRAPH, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
            manager = TagManager(graph, Path(tmp) / "synonyms.yaml")
            result = manager.add_tags(["隐私"], force="allow")
            self.assertEqual(result["status"], "updated")
            expected = copy.deepcopy(JSON_GRAPH)
            expected["tags"]["隐私"] = {"related": []}
            self.assertEqual(json.loads(graph.read_bytes()), expected)
            self.assertEqual(load_yaml(graph), expected)

            result = manager.add_relation("隐私", "工程", weight=0.6, force="allow")
            self.assertTrue(result["changed"])
            expected["tags"]["隐私"]["related"] = [{"tag": "工程", "weight": 0.6}]
            expected["tags"]["工程"]["related"].append({"tag": "隐私", "weight": 0.6})
            self.assertEqual(json.loads(graph.read_bytes()), expected)
            self.assertEqual(load_yaml(graph), expected)
            self.assertIn("隐私", graph.read_text(encoding="utf-8"))
            reloaded = TagManager(graph, Path(tmp) / "synonyms.yaml")
            self.assertEqual(reloaded.existing_tags, {"工程", "排错", "隐私"})
            self.assertEqual(reloaded.related_of("隐私"), ["工程"])

    def test_json_weight_edits_preserve_relation_metadata(self):
        for operation in ("add_relation", "set_relation_weight", "writeback_authority_weight"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                graph = Path(tmp) / "tag-graph.yaml"
                graph.write_bytes((json.dumps(JSON_GRAPH, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
                manager = TagManager(graph, Path(tmp) / "synonyms.yaml")
                result = getattr(manager, operation)("工程", "排错", weight=0.3, force="allow")
                self.assertTrue(result["changed"])
                expected = copy.deepcopy(JSON_GRAPH)
                expected["tags"]["工程"]["related"][0]["weight"] = 0.3
                expected["tags"]["排错"]["related"][0]["weight"] = 0.3
                self.assertEqual(json.loads(graph.read_bytes()), expected)
                self.assertEqual(load_yaml(graph), expected)

    def test_concurrent_changes_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph = Path(tmp) / "tag-graph.yaml"
            graph.write_text("version: 1\ndefaults:\n  hop: 2\n  max_nodes: 64\ntags:\n  existing:\n    related: []\n")
            manager = TagManager(graph, Path(tmp) / "synonyms.yaml")
            changed = graph.read_bytes() + b"# external edit\n"
            graph.write_bytes(changed)
            with self.assertRaises(RuntimeError):
                manager.add_tags(["research"], force="allow")
            self.assertEqual(graph.read_bytes(), changed)


if __name__ == "__main__":
    unittest.main()
