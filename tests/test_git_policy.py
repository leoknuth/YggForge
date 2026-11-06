#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Git 风险策略必须读取 runtime 的本机覆盖。"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yggforge-core/scripts"))
from cmds.ops.git_risk_check import load_policy


class GitPolicyTests(unittest.TestCase):
    def test_runtime_override_merges_security_policy_and_gitlab_settings(self):
        with tempfile.TemporaryDirectory(prefix="ygg-policy-test-") as temporary:
            repo = Path(temporary)
            core = repo / "yggforge-core/config"
            runtime = repo / "yggforge-runtime/config"
            core.mkdir(parents=True)
            runtime.mkdir(parents=True)
            core.joinpath("sync.defaults.json").write_text(json.dumps({
                "push_safety": {"on_unable_to_check_permissions": "continue", "enable_warning": True},
                "gitlab": {"api_url": "", "token_env": "YGG_GITLAB_TOKEN"}}))
            runtime.joinpath("sync.local.json").write_text(json.dumps({
                "push_safety": {"on_unable_to_check_permissions": "deny"},
                "gitlab": {"api_url": "https://example.invalid/api/v4", "token_env": "TEST_TOKEN_ENV"}}))
            core.joinpath("sync.local.json").write_text(json.dumps({"push_safety": {"on_unable_to_check_permissions": "continue"}}))
            result = load_policy(repo)
            self.assertEqual(result["push_safety"]["on_unable_to_check_permissions"], "deny")
            self.assertTrue(result["push_safety"]["enable_warning"])
            self.assertEqual(result["gitlab"]["token_env"], "TEST_TOKEN_ENV")


if __name__ == "__main__":
    unittest.main()
