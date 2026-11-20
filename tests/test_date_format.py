#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证八位日期写入、历史日期读取与同秒记忆防重。"""

from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "yggforge-core" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from backends import file_backend
from cmds.pipeline import promote
from knowledge.schema import validate_front_matter
from lib.front_matter import dump_front_matter_lines, parse_front_matter, render_with_front_matter

try:
    import yaml
except ImportError:
    yaml = None


class DateFormatTests(unittest.TestCase):
    def test_raw_and_inbox_use_string_date_without_losing_microsecond_names(self):
        with tempfile.TemporaryDirectory(prefix="ygg-date-test-") as directory:
            root = Path(directory)
            backend = file_backend.FileMemoryBackend(root / "core", {}, runtime_root=root / "runtime")
            instants = [datetime(2026, 11, 20, 15, 30, 0, 123), datetime(2026, 11, 20, 15, 30, 0, 124)]
            with patch.object(file_backend, "datetime") as clock:
                clock.now.side_effect = instants
                records = [backend.record_observation("日期测试。", title="日期", allow_duplicate=True)
                           for _ in instants]

            self.assertNotEqual(records[0]["raw_path"], records[1]["raw_path"])
            for record in records:
                for key in ("raw_path", "lesson_draft_path"):
                    path = Path(record[key])
                    metadata, _body = parse_front_matter(path.read_text(encoding="utf-8-sig"))
                    self.assertEqual(metadata["recorded_at"], "20261120")
                    self.assertIsInstance(metadata["recorded_at"], str)
                    self.assertIn("20261120-153000-00012", path.name)

    def test_all_promotion_types_write_eight_digit_review_date(self):
        with tempfile.TemporaryDirectory(prefix="ygg-review-date-test-") as directory:
            root = Path(directory)
            with patch.object(promote, "CONTENT_ROOT", root), patch.object(promote, "datetime") as clock:
                clock.now.return_value = datetime(2026, 11, 20, 15, 30)
                for kind in ("rule", "template", "lesson", "reference", "decision"):
                    with self.subTest(kind=kind):
                        lines = ['title: "日期测试"']
                        update = getattr(promote, "update_" + kind + "_front_matter")
                        update(lines, root / "knowledge" / (kind + "s") / "date-test.md")
                        metadata, _body = parse_front_matter("---\n" + "\n".join(lines) + "\n---\n")
                        self.assertEqual(metadata["last_reviewed"], "20261120")
                        self.assertEqual(metadata["type"], kind)
                        self.assertIsInstance(metadata["last_reviewed"], str)

    def test_schema_accepts_new_dates_and_preserves_original_historical_dates(self):
        for value in ("20261120", "2026-11-20"):
            with self.subTest(value=value):
                metadata = {"type": "lesson", "status": "draft", "recorded_at": value, "last_reviewed": value}
                errors, _warnings = validate_front_matter(metadata, require_index_fields=False)
                self.assertEqual(errors, [])
                self.assertEqual(metadata["recorded_at"], value)

    def test_schema_rejects_partial_or_extra_date_components(self):
        for value in ("2026112", "202611200", "2026/11/20", "20261120 15:30"):
            with self.subTest(value=value):
                errors, _warnings = validate_front_matter(
                    {"type": "lesson", "status": "draft", "recorded_at": value},
                    require_index_fields=False,
                )
                self.assertEqual(len(errors), 1)
                self.assertIn("YYYYMMDD", errors[0])

    def test_numeric_strings_are_quoted_in_scalars_and_lists(self):
        metadata = {"recorded_at": "20261112", "dates": ["20261120", "00000123"],
                    "enabled": True, "flags": [False, "false", True, "123"]}
        lines = dump_front_matter_lines(metadata)
        self.assertIn('recorded_at: "20261112"', lines)
        self.assertIn('  - "20261120"', lines)
        self.assertIn('  - "00000123"', lines)
        self.assertIn('  - "123"', lines)
        self.assertIn("enabled: true", lines)
        self.assertIn("  - false", lines)
        text = render_with_front_matter(metadata, "原始正文。\n")
        parsed, body = parse_front_matter(text)
        self.assertEqual(parsed, metadata)
        self.assertEqual(body, "原始正文。\n")

    @unittest.skipIf(yaml is None, "当前环境未安装可选 PyYAML")
    def test_pyyaml_preserves_date_strings_and_booleans(self):
        metadata = {"recorded_at": "20261112", "last_reviewed": "20261120",
                    "dates": ["20261120", "00000123"], "enabled": True,
                    "flags": [False, "false", True, "123"]}
        text = "\n".join(dump_front_matter_lines(metadata))
        parsed = yaml.safe_load(text)
        self.assertEqual(parsed, metadata)
        self.assertIsInstance(parsed["recorded_at"], str)
        self.assertIsInstance(parsed["last_reviewed"], str)
        self.assertIsInstance(parsed["enabled"], bool)


if __name__ == "__main__":
    unittest.main()
