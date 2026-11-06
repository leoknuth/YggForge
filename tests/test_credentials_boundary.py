#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""凭据只允许写入仓库外的本机文件，测试仅使用合成值。"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yggforge-core/scripts"))
from cmds.ops import apply_credentials_mcp as credentials


class CredentialsBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ygg-credentials-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.core = self.repo / "yggforge-core"
        self.example = self.core / "profiles/cursor/mcp.json.example"
        self.example.parent.mkdir(parents=True)
        self.repo.joinpath(".git").mkdir()
        self.example.write_text(json.dumps({"mcpServers": {}}))
        self.secret_root = self.root / "synthetic-credentials"
        self.env = self.secret_root / "cursor/mcp/gitlab_internal.env"
        self.env.parent.mkdir(parents=True)
        self.env.write_text("GITLAB_PERSONAL_ACCESS_TOKEN=AUDIT_SYNTHETIC_VALUE\n")
        for name, value in (("REPO_ROOT", self.repo), ("CORE_ROOT", self.core)):
            patcher = mock.patch.object(credentials, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_main(self, target, env_file=None):
        argv = ["credentials", "--credentials-root", str(self.secret_root), "--example", str(self.example), "--target", str(target)]
        if env_file:
            argv += ["--env-file", env_file]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            return credentials.main()

    def test_symlink_to_truth_is_rejected_without_modifying_example(self):
        target = self.root / "agent/mcp.json"
        target.parent.mkdir()
        try:
            target.symlink_to(self.example)
        except OSError:
            self.skipTest("平台不支持测试用符号链接")
        before = self.example.read_bytes()
        with self.assertRaisesRegex(SystemExit, "outside"):
            self.run_main(target)
        self.assertEqual(self.example.read_bytes(), before)

    def test_direct_core_and_repo_targets_rejected(self):
        for target in (self.core / "config/secret.json", self.repo / "runtime.json"):
            with self.assertRaisesRegex(SystemExit, "outside"):
                self.run_main(target)
            self.assertFalse(target.exists())

    def test_hardlink_to_example_rejected(self):
        target = self.root / "mcp.json"
        try:
            os.link(str(self.example), str(target))
        except OSError:
            self.skipTest("平台不支持测试用硬链接")
        with self.assertRaisesRegex(SystemExit, "example"):
            self.run_main(target)

    def test_outside_target_receives_synthetic_value_atomically(self):
        target = self.root / "agent/mcp.json"
        self.assertEqual(self.run_main(target), 0)
        data = json.loads(target.read_text())
        self.assertEqual(data["mcpServers"]["gitlab_internal"]["env"]["GITLAB_PERSONAL_ACCESS_TOKEN"], "AUDIT_SYNTHETIC_VALUE")
        if os.name != "nt":
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertFalse(list(target.parent.glob(".ygg-mcp-*")))

    def test_deployed_copy_allows_local_target_beside_core_bundle(self):
        agent_home = self.root / "agent-home"
        deployed_core = agent_home / "yggforge-core"
        deployed_core.mkdir(parents=True)
        target = agent_home / "mcp.json"
        with mock.patch.object(credentials, "REPO_ROOT", agent_home), mock.patch.object(credentials, "CORE_ROOT", deployed_core):
            self.assertEqual(credentials.validate_target(target, self.example), target.resolve())

    def test_malformed_env_error_does_not_include_secret(self):
        self.env.write_text("AUDIT_SYNTHETIC_VALUE_WITHOUT_EQUALS\n")
        with self.assertRaises(SystemExit) as error:
            credentials.load_env_file(self.env)
        self.assertNotIn("AUDIT_SYNTHETIC", str(error.exception))
        self.assertIn("line 1", str(error.exception))

    def test_env_file_cannot_escape_credentials_root(self):
        target = self.root / "agent/mcp.json"
        with self.assertRaisesRegex(SystemExit, "inside credentials-root"):
            self.run_main(target, "../../outside.env")
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
