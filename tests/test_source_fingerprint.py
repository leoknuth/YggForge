"""源文档指纹与 Git 换行规范保持一致。"""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yggforge-core/scripts"))
from lib.front_matter import source_text_fingerprint
from knowledge.graph_build import build_indexes, check_indexes


class SourceFingerprintTest(unittest.TestCase):
    def test_line_endings_have_same_fingerprint(self):
        self.assertEqual(source_text_fingerprint(b"first\r\nsecond\r\n"), source_text_fingerprint(b"first\nsecond\n"))

    def test_content_change_invalidates_fingerprint(self):
        self.assertNotEqual(source_text_fingerprint(b"first\n"), source_text_fingerprint(b"changed\n"))

    def test_checkout_line_endings_do_not_make_index_stale(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entry = root / "knowledge/rules/eol.md"
            entry.parent.mkdir(parents=True)
            text = "---\nid: 20261106120000-kr$$$$-eol$$$$$-test\ntitle: EOL\ntype: rule\nstatus: active\nconfidence: high\nlast_reviewed: 2026-11-06\ntags:\n  - eol\nrelated: []\n---\n\n# EOL\n"
            entry.write_bytes(text.replace("\n", "\r\n").encode())
            build_indexes(root, {})
            entry.write_bytes(text.encode())
            self.assertEqual(check_indexes(root, {})["index_status"], "consistent")


if __name__ == "__main__":
    unittest.main()
