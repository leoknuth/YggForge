#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共用真源的宿主状态、记忆和导入边界回归。"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "yggforge-core/scripts"
sys.path.insert(0, str(SCRIPTS))
from cmds.ops import deploy
from lib import repo_paths


class HostStateTests(unittest.TestCase):
    def test_host_names_are_distinct_and_safe(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(repo_paths.getpass, "getuser", return_value="my"), patch.object(repo_paths.socket, "gethostname", return_value="host"):
            with patch.object(repo_paths.sys, "platform", "win32"):
                windows = repo_paths.current_host_id()
            with patch.object(repo_paths.sys, "platform", "linux"), patch.dict(os.environ, {"WSL_DISTRO_NAME": "Ubuntu-24.04"}):
                wsl = repo_paths.current_host_id()
            self.assertEqual(windows, "windows-host-my")
            self.assertNotEqual(windows, wsl)
            self.assertTrue(wsl.startswith("wsl-ubuntu-24-04-my-"))
            for value in ("../other", "a/b", "a\\b", "", "..", "a" * 129):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    repo_paths.host_runtime_root(Path("repo"), value)

    def test_two_hosts_keep_local_policy_receipts_and_shared_memory(self):
        with tempfile.TemporaryDirectory(prefix="ygg-shared-hosts-") as temporary:
            repo = Path(temporary) / "repo"
            core = repo / "yggforge-core"
            shutil.copytree(SCRIPTS, core / "scripts")
            (core / "config").mkdir()
            (repo / ".git").mkdir()
            (core / "config/memory.defaults.json").write_text('{"backend":{"type":"file"}}', encoding="utf-8")
            (core / "config/sync.defaults.json").write_text('{"push_safety":{"enable_warning":true}}', encoding="utf-8")
            old = repo / "yggforge-generated/deploy-manifests"
            old.mkdir(parents=True)
            (old / "codex.json").write_text('{"host_id":"old-host","target":"stale"}', encoding="utf-8")
            runner = '''
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from lib.repo_paths import HOST_ID, HOST_RUNTIME_ROOT, HOST_GENERATED_ROOT, REPO_ROOT, ensure_layout
from cmds.ops import deploy
from cli.runtime import read_deploy_manifest
from cmds.ops.git_risk_check import load_policy
from backends.factory import get_memory_backend
ensure_layout()
policy = {"push_safety":{"host_marker":HOST_ID}}
(HOST_RUNTIME_ROOT / "config/sync.local.json").write_text(json.dumps(policy))
spec = deploy.DeploySpec(True, "codex", [])
deploy.write_manifest("codex", spec, "deploy", "link", [{"target_path":HOST_ID}])
memory = get_memory_backend()
print(json.dumps({"host_id":HOST_ID,"manifest":str(deploy.manifest_path("codex")),"local":str(HOST_RUNTIME_ROOT),"generated":str(HOST_GENERATED_ROOT),"raw":str(memory.raw_root),"marker":load_policy(REPO_ROOT)["push_safety"]["host_marker"],"receipt":read_deploy_manifest("codex")["mappings"][0]["target_path"]}))
'''
            results = []
            for host_id in ("windows-test", "wsl-test"):
                env = dict(os.environ, YGG_HOST_ID=host_id, PYTHONDONTWRITEBYTECODE="1")
                proc = subprocess.run([sys.executable, "-c", runner, str(core / "scripts")], env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                results.append(json.loads(proc.stdout))
            windows, wsl = results
            self.assertNotEqual(windows["manifest"], wsl["manifest"])
            self.assertNotEqual(windows["local"], wsl["local"])
            self.assertEqual(windows["raw"], wsl["raw"])
            self.assertEqual(windows["raw"], str(repo / "yggforge-runtime/memory/raw"))
            for result in results:
                self.assertEqual(result["marker"], result["host_id"])
                self.assertEqual(result["receipt"], result["host_id"])
                self.assertEqual(json.loads(Path(result["manifest"]).read_text())["host_id"], result["host_id"])
            self.assertEqual(json.loads((old / "codex.json").read_text())["target"], "stale")

    def test_foreign_manifest_and_import_review_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            own = repo / "yggforge-generated/hosts/windows-test/imports"
            foreign = repo / "yggforge-generated/hosts/wsl-test/imports"
            manifests = repo / "yggforge-generated/hosts/windows-test/deploy-manifests"
            manifests.mkdir(parents=True)
            (manifests / "codex.json").write_text('{"host_id":"wsl-test"}', encoding="utf-8")
            with patch.object(deploy, "REPO_ROOT", repo), patch.object(deploy, "IMPORT_ROOT", own), patch.object(deploy, "MANIFEST_ROOT", manifests), patch.object(deploy, "HOST_ID", "windows-test"):
                deploy.assert_import_allowed(own / "codex/entry.md")
                with self.assertRaises(deploy.DeployError):
                    deploy.assert_import_allowed(foreign / "codex/entry.md")
                with self.assertRaises(deploy.DeployError):
                    deploy.read_manifest("codex")


if __name__ == "__main__":
    unittest.main()
