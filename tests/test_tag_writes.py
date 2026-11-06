"""标签写入保留原文并拒绝并发覆盖。"""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yggforge-core/scripts"))
from knowledge.tag_manager import TagManager


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
