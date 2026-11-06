#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MDC 生命周期回归：退役撤销、手写保留及投影路径边界。"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yggforge-core/scripts"))
from cmds.project import project_mdc as mdc


class MdcProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.core = self.repo / "yggforge-core"
        self.rules = self.core / "knowledge/rules"
        self.rules.mkdir(parents=True)
        self.patches = [patch.object(mdc, "CORE_ROOT", self.core), patch.object(mdc, "REPO_ROOT", self.repo)]
        for item in self.patches:
            item.start()
        self.addCleanup(self.temp.cleanup)
        for item in self.patches:
            self.addCleanup(item.stop)

    def source(self, *, status="active", always="true", kind="rule"):
        path = self.rules / "r.md"
        path.write_text(f"---\nid: r\ntitle: R\ntype: {kind}\nstatus: {status}\nalways_apply: {always}\n---\n# R\n", encoding="utf-8-sig")
        return path

    def run_project(self, *, check=False, write=False):
        with contextlib.redirect_stdout(io.StringIO()):
            return mdc.run(check_only=check, write=write)

    def test_deprecated_and_non_rules_are_not_forced(self):
        self.source(status="deprecated")
        self.assertEqual(mdc.iter_always_apply_rules(), [])
        self.source(kind="lesson")
        self.assertEqual(mdc.iter_always_apply_rules(), [])

    def test_retired_and_deleted_sources_report_then_remove_generated_only(self):
        rule = self.source()
        self.run_project(write=True)
        generated = self.core / "profiles/cursor/rules/r.mdc"
        manual = generated.parent / "manual.mdc"
        manual.write_text("---\nalwaysApply: true\n---\nhand written\n", encoding="utf-8")
        self.source(status="deprecated", always="false")
        self.assertEqual(self.run_project(check=True), 1)
        self.assertTrue(generated.exists())
        self.run_project(write=True)
        self.assertFalse(generated.exists())
        self.assertTrue(manual.exists())
        self.source()
        self.run_project(write=True)
        rule.unlink()
        self.assertEqual(self.run_project(check=True), 1)
        self.run_project(write=True)
        self.assertFalse(generated.exists())

    def test_manual_marker_never_cleaned(self):
        target = self.core / "profiles/cursor/rules/manual.mdc"
        target.parent.mkdir(parents=True)
        content = "<!-- ygg-project: manual -->\n<!-- ygg-project: sync | source: knowledge/rules/missing.md -->\n"
        target.write_text(content, encoding="utf-8")
        self.run_project(write=True)
        self.assertEqual(target.read_text(), content)

    def test_rejects_absolute_parent_and_non_projection_paths(self):
        rule = self.source()
        outside = self.repo / "outside.mdc"
        outside.write_text("preserve", encoding="utf-8")
        for item in (str(outside), "../outside.mdc", "profiles/cursor/rules/../../outside.mdc", "C:/outside.mdc", "knowledge/rules/wrong.mdc"):
            with self.subTest(item=item), self.assertRaises(mdc.ProjectError):
                mdc.project_one(rule, {"projection": [item], "projection_mode": "sync"}, "overwrite", write=True)
        self.assertEqual(outside.read_text(), "preserve")

    def test_symlink_escape_is_rejected(self):
        rule = self.source()
        parent = self.core / "profiles/cursor/rules"
        parent.mkdir(parents=True)
        outside = self.repo / "outside"
        outside.mkdir()
        try:
            (parent / "linked").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("当前平台没有创建符号链接权限")
        with self.assertRaises(mdc.ProjectError):
            mdc.project_one(rule, {"projection": ["profiles/cursor/rules/linked/escape.mdc"], "projection_mode": "sync"}, "bad", write=True)
        self.assertFalse((outside / "escape.mdc").exists())


if __name__ == "__main__":
    unittest.main()
