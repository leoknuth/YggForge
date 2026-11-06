#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""部署身份、三方导入、预演与失败恢复的标准库回归测试。"""

import argparse
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "yggforge-core/scripts"
sys.path.insert(0, str(SCRIPTS))
from cmds.ops import deploy
from lib import repo_paths


class DeploySafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ygg-deploy-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.core = self.repo / "yggforge-core"
        self.rules = self.core / "profiles/cursor/rules"
        self.rules.mkdir(parents=True)
        self.rules.joinpath("old.mdc").write_text("old", encoding="utf-8")
        self.entry = self.core / "profiles/codex/AGENTS.md"
        self.entry.parent.mkdir(parents=True)
        self.entry.write_text("canonical", encoding="utf-8")
        self.core.joinpath("knowledge").mkdir()
        self.core.joinpath("knowledge/note.md").write_text("note", encoding="utf-8")
        for module in (deploy, repo_paths):
            for name, value in {
                "CORE_ROOT": self.core, "REPO_ROOT": self.repo,
                "GENERATED_ROOT": self.repo / "yggforge-generated",
                "RUNTIME_ROOT": self.repo / "yggforge-runtime",
            }.items():
                patcher = mock.patch.object(module, name, value)
                patcher.start()
                self.addCleanup(patcher.stop)
        for name, value in {
            "MANIFEST_ROOT": self.repo / "yggforge-generated/deploy-manifests",
            "RENDER_ROOT": self.repo / "yggforge-generated/rendered",
            "IMPORT_ROOT": self.repo / "yggforge-generated/imports",
        }.items():
            patcher = mock.patch.object(deploy, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.dependencies = mock.patch.object(deploy, "_check_deps_for_deploy")
        self.check_dependencies = self.dependencies.start()
        self.addCleanup(self.dependencies.stop)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def copied_rules(self):
        target = self.root / "agent/rules"
        target.parent.mkdir()
        shutil.copytree(self.rules, target)
        return target, deploy.snapshot_path(target)

    def args(self, action, mode="copy", scope="user", project=None, dry=False):
        return argparse.Namespace(action=action, mode=mode, scope=scope,
                                  project_root=str(project) if project else None,
                                  targets=["codex"], backup=False, preview_only=False,
                                  preview_lines=0, install_deps=False, dry_run=dry)

    def run_entry(self, action, mode, project):
        config = {"codex": deploy.DeploySpec(True, "codex", [
            deploy.MappingSpec("agents_entry", "profiles/codex/AGENTS.md", "<project>/AGENTS.md")])}
        with mock.patch.object(deploy, "load_config", return_value=config):
            return deploy.run(self.args(action, mode, "project", project))

    def test_unchanged_copy_preserves_new_canonical_rule(self):
        target, baseline = self.copied_rules()
        self.rules.joinpath("new.mdc").write_text("new")
        deploy.copy_into_destination(target, self.rules, baseline)
        self.assertEqual(self.rules.joinpath("new.mdc").read_text(), "new")

    def test_independent_changes_merge_and_copy_deletions_apply(self):
        target, baseline = self.copied_rules()
        self.rules.joinpath("canonical.mdc").write_text("canonical-only")
        target.joinpath("old.mdc").unlink()
        target.joinpath("target.mdc").write_text("target-only")
        deploy.copy_into_destination(target, self.rules, baseline)
        self.assertFalse(self.rules.joinpath("old.mdc").exists())
        self.assertTrue(self.rules.joinpath("canonical.mdc").exists())
        self.assertEqual(self.rules.joinpath("target.mdc").read_text(), "target-only")

    def test_two_sided_change_rejected_before_write(self):
        target, baseline = self.copied_rules()
        self.rules.joinpath("old.mdc").write_text("canonical-change")
        target.joinpath("old.mdc").write_text("target-change")
        with self.assertRaisesRegex(deploy.DeployError, "conflict"):
            deploy.copy_into_destination(target, self.rules, baseline)
        self.assertEqual(self.rules.joinpath("old.mdc").read_text(), "canonical-change")

    def test_directory_deletion_cannot_erase_new_canonical_descendant(self):
        folder = self.rules / "folder"
        folder.mkdir()
        folder.joinpath("old.mdc").write_text("old")
        target, baseline = self.copied_rules()
        shutil.rmtree(target / "folder")
        folder.joinpath("new.mdc").write_text("new")
        with self.assertRaisesRegex(deploy.DeployError, "conflict"):
            deploy.copy_into_destination(target, self.rules, baseline)
        self.assertTrue(folder.joinpath("new.mdc").exists())

    def test_staging_failure_keeps_original(self):
        target, baseline = self.copied_rules()
        target.joinpath("old.mdc").write_text("change")
        with mock.patch.object(deploy.shutil, "copy2", side_effect=OSError("copy failed")):
            with self.assertRaises(OSError):
                deploy.copy_into_destination(target, self.rules, baseline)
        self.assertEqual(self.rules.joinpath("old.mdc").read_text(), "old")

    def test_replacement_failure_restores_original(self):
        target, baseline = self.copied_rules()
        target.joinpath("old.mdc").write_text("change")
        replace = deploy.os.replace

        def fail_incoming(source, destination):
            if Path(source).name == "incoming":
                raise OSError("replace failed")
            return replace(source, destination)

        with mock.patch.object(deploy.os, "replace", side_effect=fail_incoming):
            with self.assertRaisesRegex(deploy.DeployError, "original restored"):
                deploy.copy_into_destination(target, self.rules, baseline)
        self.assertEqual(self.rules.joinpath("old.mdc").read_text(), "old")

    def test_symlink_in_copy_tree_rejected(self):
        target, baseline = self.copied_rules()
        try:
            target.joinpath("linked.mdc").symlink_to(self.entry)
        except OSError:
            self.skipTest("平台不支持测试用符号链接")
        with self.assertRaisesRegex(deploy.DeployError, "link"):
            deploy.copy_into_destination(target, self.rules, baseline)

    def test_baseline_path_traversal_rejected(self):
        target, baseline = self.copied_rules()
        baseline["../outside"] = "file:fake"
        with self.assertRaisesRegex(deploy.DeployError, "Unsafe"):
            deploy.copy_into_destination(target, self.rules, baseline)

    def test_project_manifests_are_distinct_and_render_stays_in_review(self):
        project_a, project_b = self.root / "a", self.root / "b"
        self.run_entry("deploy", "render", project_a)
        self.run_entry("deploy", "copy", project_b)
        project_a.joinpath("AGENTS.md").write_text("rendered edit")
        self.run_entry("import", "copy", project_a)
        self.assertEqual(self.entry.read_text(), "canonical")
        key_a = deploy.manifest_key("codex", "project", project_a)
        key_b = deploy.manifest_key("codex", "project", project_b)
        self.assertNotEqual(key_a, key_b)
        self.assertEqual(deploy.import_review_path(key_a, "agents_entry", self.entry).read_text(), "rendered edit")
        self.assertEqual(key_a, deploy.manifest_key("codex", "project", project_a / "nested/.."))

    def test_manifest_identity_mismatch_rejected(self):
        project = self.root / "project"
        self.run_entry("deploy", "copy", project)
        key = deploy.manifest_key("codex", "project", project)
        path = deploy.manifest_path(key)
        manifest = json.loads(path.read_text())
        manifest["project_root"] = str(self.root / "other")
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(deploy.DeployError, "identity"):
            self.run_entry("import", "copy", project)

    def test_render_reimport_preserves_reviewer_changes_when_target_unchanged(self):
        project = self.root / "project"
        self.run_entry("deploy", "render", project)
        project.joinpath("AGENTS.md").write_text("target edit")
        self.run_entry("import", "render", project)
        review = deploy.import_review_path(deploy.manifest_key("codex", "project", project), "agents_entry", self.entry)
        review.write_text("reviewer edit")
        self.run_entry("import", "render", project)
        self.assertEqual(review.read_text(), "reviewer edit")
        self.assertEqual(self.entry.read_text(), "canonical")

    def test_copy_core_import_only_allowed_subtrees_and_preserves_baselines(self):
        target = self.root / "agent/core"
        config = {"codex": deploy.DeploySpec(True, "codex", [deploy.MappingSpec("yggforge_core", ".", str(target))])}
        with mock.patch.object(deploy, "load_config", return_value=config):
            deploy.run(self.args("deploy"))
            self.core.joinpath("config").mkdir()
            self.core.joinpath("config/guard.json").write_text("canonical")
            target.joinpath("config").mkdir()
            target.joinpath("config/guard.json").write_text("must not import")
            self.core.joinpath("knowledge/new.md").write_text("canonical-new")
            target.joinpath("knowledge/note.md").write_text("target-edit")
            deploy.run(self.args("import"))
            self.assertEqual(self.core.joinpath("knowledge/note.md").read_text(), "target-edit")
            self.assertEqual(self.core.joinpath("knowledge/new.md").read_text(), "canonical-new")
            self.assertEqual(self.core.joinpath("config/guard.json").read_text(), "canonical")
            self.core.joinpath("knowledge/note.md").write_text("later-canonical-change")
            deploy.run(self.args("import"))
            self.assertEqual(self.core.joinpath("knowledge/note.md").read_text(), "later-canonical-change")

    def test_link_copy_fallback_records_and_imports_actual_mode(self):
        target = self.root / "agent/AGENTS.md"
        config = {"codex": deploy.DeploySpec(True, "codex", [deploy.MappingSpec("agents_entry", "profiles/codex/AGENTS.md", str(target))])}
        with mock.patch.object(deploy, "load_config", return_value=config):
            with mock.patch.object(Path, "symlink_to", side_effect=OSError("no privilege")), mock.patch.object(deploy.os, "link", side_effect=OSError("cross volume")):
                deploy.run(self.args("deploy", "link"))
            manifest = deploy.read_manifest("codex")
            self.assertEqual(manifest["mappings"][0]["actual_mode"], "copy")
            self.assertTrue(manifest["requires_import"])
            target.write_text("copied edit")
            deploy.run(self.args("import"))
        self.assertEqual(self.entry.read_text(), "copied edit")

    def test_disagreeing_core_and_entry_copies_conflict_before_any_write(self):
        target = self.root / "agent/core"
        thin = self.root / "agent/AGENTS.md"
        config = {"codex": deploy.DeploySpec(True, "codex", [
            deploy.MappingSpec("yggforge_core", ".", str(target)),
            deploy.MappingSpec("agents_entry", "profiles/codex/AGENTS.md", str(thin))])}
        with mock.patch.object(deploy, "load_config", return_value=config):
            deploy.run(self.args("deploy"))
            target.joinpath("profiles/codex/AGENTS.md").write_text("core-copy-edit")
            thin.write_text("thin-copy-edit")
            with self.assertRaisesRegex(deploy.DeployError, "deployed copies"):
                deploy.run(self.args("import"))
        self.assertEqual(self.entry.read_text(), "canonical")

    def test_copy_deployment_rejects_source_target_overlap(self):
        for target in (self.rules, self.rules / "child", self.core):
            with self.assertRaisesRegex(deploy.DeployError, "overlap"):
                deploy.copy_deployment(self.rules, target)
        self.assertEqual(self.rules.joinpath("old.mdc").read_text(), "old")

    def test_link_rejects_self_ancestor_and_descendant_before_backup(self):
        before = deploy.snapshot_path(self.core)
        for target in (self.rules, self.rules.parent, self.rules / "nested/child"):
            with self.subTest(target=str(target)):
                with self.assertRaisesRegex(deploy.DeployError, "overlap"):
                    deploy.link_deployment(self.rules, target, backup=True)
                self.assertEqual(deploy.snapshot_path(self.core), before)
                self.assertFalse(deploy.RUNTIME_ROOT.exists())
        self.assertFalse(self.rules.joinpath("nested").exists())

    def test_correct_existing_directory_link_is_noop_with_backup(self):
        target = self.root / "linked-rules"
        try:
            target.symlink_to(self.rules, target_is_directory=True)
        except OSError:
            self.skipTest("平台不支持测试用符号链接")
        before = deploy.snapshot_path(self.core)
        self.assertEqual(deploy.link_deployment(self.rules, target, backup=True), "link")
        self.assertEqual(deploy.snapshot_path(self.core), before)
        self.assertFalse(deploy.RUNTIME_ROOT.exists())

    def test_link_rejects_overlap_resolved_through_parent_symlink(self):
        alias = self.root / "core-alias"
        try:
            alias.symlink_to(self.core, target_is_directory=True)
        except OSError:
            self.skipTest("平台不支持测试用符号链接")
        before = deploy.snapshot_path(self.core)
        with self.assertRaisesRegex(deploy.DeployError, "overlap"):
            deploy.link_deployment(self.rules, alias / "profiles/cursor", backup=True)
        self.assertEqual(deploy.snapshot_path(self.core), before)
        self.assertFalse(deploy.RUNTIME_ROOT.exists())

    def test_render_preserves_json_and_script_bytes(self):
        for name, data in (("hooks.json", b'{"hooks":{}}\n'), ("hook.py", b'#!/usr/bin/env python3\nprint("ok")\n')):
            source = self.core / name
            source.write_bytes(data)
            result = deploy.render_source(source, "cursor", name)
            self.assertEqual(result.read_bytes(), data)
        rendered = deploy.render_source(self.entry, "codex", "entry")
        self.assertTrue(rendered.read_text(encoding="utf-8-sig").startswith("# Rendered Entrypoint"))

    def test_dry_run_has_no_filesystem_or_dependency_writes(self):
        project = self.root / "never-created"
        config = {"codex": deploy.DeploySpec(True, "codex", [deploy.MappingSpec("agents_entry", "profiles/codex/AGENTS.md", "<project>/AGENTS.md")])}
        with mock.patch.object(deploy, "load_config", return_value=config):
            deploy.run(self.args("deploy", "render", "project", project, True))
        self.assertFalse(project.exists())
        self.assertFalse(deploy.GENERATED_ROOT.exists())
        self.assertFalse(deploy.RUNTIME_ROOT.exists())
        self.check_dependencies.assert_not_called()

    def test_old_copy_without_baseline_refuses_different_content(self):
        target, _baseline = self.copied_rules()
        target.joinpath("old.mdc").write_text("edited")
        with self.assertRaisesRegex(deploy.DeployError, "baseline"):
            deploy.copy_into_destination(target, self.rules)
        self.assertEqual(self.rules.joinpath("old.mdc").read_text(), "old")

    def test_real_cli_dry_run_is_zero_write_in_isolated_repo(self):
        # 真实入口及其子进程只在临时副本运行，覆盖路由到叶子脚本的参数传递。
        shutil.copytree(SCRIPTS, self.core / "scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(SCRIPTS.parent / "config", self.core / "config")
        project = self.root / "cli-project"
        result = subprocess.run([
            sys.executable, str(self.core / "scripts/ygg.py"), "deploy", "--dry-run",
            "--scope", "project", "--project-root", str(project), "codex"],
            cwd=str(self.repo), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(project.exists())
        self.assertFalse(deploy.GENERATED_ROOT.exists())
        self.assertFalse(deploy.RUNTIME_ROOT.exists())


if __name__ == "__main__":
    unittest.main()
