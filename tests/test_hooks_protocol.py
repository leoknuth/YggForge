#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hook 协议回归：真实管道、跨平台文本、消息隔离、原子写及失效结果。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
HOOKS = REPO / "yggforge-core/profiles/cursor/hooks"
sys.path.insert(0, str(HOOKS))
import ygg_pre_submit as hook
import ygg_session_protocol as session


class HookProtocolTests(unittest.TestCase):
    def test_utf8_prompt_survives_on_linux(self):
        payload = json.dumps({"prompt": "记住中文约定?"}, ensure_ascii=False).encode()
        with patch.object(sys, "platform", "linux"):
            self.assertEqual(json.loads(hook._decode_stdin(payload))["prompt"], "记住中文约定?")
            # 非 UTF-8 输入也不会因为平台缺少 mbcs 编码器而崩溃。
            self.assertIsInstance(hook._decode_stdin(b'\xff{"prompt":"x"}'), str)

    def test_reads_all_pipe_chunks_and_both_hooks_share_limit(self):
        class Stdin:
            def fileno(self):
                return 99
        for read in (hook._read_stdin_bytes, session._read_stdin):
            with patch.object(sys, "stdin", Stdin()), patch.object(hook.os, "read", side_effect=[b'{"prompt":', b'"hello"}', b'']):
                got = read()
                self.assertEqual(got, b'{"prompt":"hello"}' if read is hook._read_stdin_bytes else '{"prompt":"hello"}')
            with patch.object(sys, "stdin", Stdin()), patch.object(hook, "MAX_STDIN_BYTES", 10), patch.object(hook.os, "read", return_value=b'x' * 11):
                with self.assertRaises(hook.InputLimitError):
                    read()

    def test_valid_current_prompt_never_replaced_by_previous_transcript(self):
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td) / "chat.jsonl"
            tp.write_text(json.dumps({"role": "user", "message_id": "old", "message": {"content": "记住旧约定"}}, ensure_ascii=False) + "\n", encoding="utf-8")
            for platform in ("linux", "win32"):
                with patch.object(sys, "platform", platform):
                    for prompt in ("What is Ubuntu?", "这次不要记忆"):
                        self.assertEqual(hook._extract_prompt({"prompt": prompt, "transcript_path": str(tp), "message_id": "new"})[0], prompt)
            self.assertEqual(hook._extract_prompt({"transcript_path": str(tp)})[0], "")
            self.assertEqual(hook._extract_prompt({"transcript_path": str(tp), "message_id": "new"})[0], "")
            self.assertEqual(hook._extract_prompt({"prompt": "\ufffd", "transcript_path": str(tp), "message_id": "old"})[0], "记住旧约定")

    def test_transcript_must_match_conversation_if_present(self):
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td) / "chat.jsonl"
            tp.write_text(json.dumps({"role": "user", "conversation_id": "B", "message_id": "m", "message": {"content": "记住B"}}, ensure_ascii=False) + "\n", encoding="utf-8")
            self.assertEqual(hook._extract_prompt({"transcript_path": str(tp), "conversation_id": "A", "message_id": "m"})[0], "")

    def test_validates_identity_prompt_expiry_and_ignores_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = {"protocol_version": 2, "conversation_id": "A", "message_id": "m", "created_at_unix": 1000, "prompt": "记住A", "prompt_sha256": hook._digest("记住A"), "should_trigger": True, "action": "remember"}
            hook._atomic_json(hook._trigger_path(root, "A"), payload)
            hook._atomic_json(hook._trigger_path(root, "A", "m"), payload)
            self.assertEqual(hook.read_trigger(root, "A", prompt="记住A", now=1001)["validation"], "matched")
            self.assertEqual(hook.read_trigger(root, "A", message_id="m", now=1001)["validation"], "matched")
            for kwargs in ({"prompt": "你好", "now": 1001}, {"message_id": "other", "now": 1001}, {"prompt": "记住A", "now": 1400}, {"prompt": "记住A", "now": 900}):
                self.assertFalse(hook.read_trigger(root, "A", **kwargs)["should_trigger"])
            self.assertFalse(hook.read_trigger(root, "B", prompt="记住A", now=1001)["should_trigger"])
            self.assertFalse(hook.read_trigger(root, "A", now=1001)["should_trigger"])
            (root / "cache/last_trigger.json").write_text(json.dumps(payload), encoding="utf-8")
            self.assertFalse(hook.read_trigger(root, "B", prompt="记住A", now=1001)["should_trigger"])

    def test_atomic_failure_preserves_complete_previous_result(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "result.json"
            hook._atomic_json(target, {"action": "skip"})
            with patch.object(hook.os, "replace", side_effect=OSError("test interruption")):
                with self.assertRaises(OSError):
                    hook._atomic_json(target, {"action": "remember"})
            self.assertEqual(json.loads(target.read_text())["action"], "skip")
            self.assertEqual(list(Path(td).glob("*.tmp")), [])

    def test_cache_keys_cannot_escape_runtime(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = hook._trigger_path(root, "../../outside", "../message")
            target.relative_to(root / "cache/triggers")
            self.assertNotIn("..", target.relative_to(root).parts)

    def test_session_protocol_uses_core_cli_and_no_global_fallback(self):
        import types
        with tempfile.TemporaryDirectory() as td:
            core = Path(td) / "yggforge-core"
            paths = types.ModuleType("lib.repo_paths")
            paths.RUNTIME_ROOT = Path(td) / "runtime"
            for event in ({"conversation_id": "A"}, {}):
                with patch.object(session, "_bootstrap_core", return_value=core), patch.object(session, "_read_stdin", return_value=json.dumps(event)), patch.dict(sys.modules, {"lib.repo_paths": paths}), patch("builtins.print") as output:
                    self.assertEqual(session.main(), 0)
                    protocol = json.loads(output.call_args.args[0])["additional_context"]
                    self.assertIn(str(core / "scripts/ygg.sh"), protocol)
                    self.assertNotIn("用 Read 工具读取", protocol)
                    if event:
                        self.assertIn("--read-trigger", protocol)
                    else:
                        self.assertIn("宿主未提供会话 ID", protocol)

    def test_real_hook_pipeline_and_validator_work_from_other_cwd(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            core = root / "yggforge-core"
            (core / "scripts/hooks").mkdir(parents=True)
            (core / "scripts/lib").mkdir()
            (core / "scripts/lib/__init__.py").touch()
            shutil.copyfile(REPO / "yggforge-core/scripts/lib/repo_paths.py", core / "scripts/lib/repo_paths.py")
            (core / "scripts/hooks/trigger_detector.py").write_text('import json, os\np=os.environ["YGG_TRIGGER_PROMPT"]\nprint(json.dumps({"action":"remember" if p.startswith("记住") else "skip", "should_trigger":p.startswith("记住")}))\n', encoding="utf-8")
            env = dict(os.environ, YGGFORGE_CORE_ROOT=str(core), YGG_TEST_HOME=str(root), PYTHONDONTWRITEBYTECODE="1")
            # 限定 heartbeat/debug 到临时用户目录，不改真实部署。
            runner = 'import os,sys; from pathlib import Path; Path.home=classmethod(lambda cls:Path(os.environ["YGG_TEST_HOME"])); sys.path.insert(0,' + repr(str(HOOKS)) + '); import ygg_pre_submit; raise SystemExit(ygg_pre_submit.main())'
            prompt = "记住" + "长输入" * 5000
            for cid, mid, text in (("A", "a", prompt), ("B", "b", "你好")):
                proc = subprocess.run([sys.executable, "-c", runner], input=json.dumps({"conversation_id": cid, "message_id": mid, "prompt": text}, ensure_ascii=False).encode(), capture_output=True, cwd=root, env=env, timeout=10)
                self.assertEqual(proc.returncode, 0, proc.stderr.decode())
                self.assertTrue(json.loads(proc.stdout)["continue"])
            self.assertEqual(hook.read_trigger(root / "yggforge-runtime", "A", prompt=prompt)["action"], "remember")
            self.assertEqual(hook.read_trigger(root / "yggforge-runtime", "B", prompt="你好")["action"], "skip")
            self.assertFalse((root / "yggforge-runtime/cache/last_trigger.json").exists())
            validated = subprocess.run([sys.executable, "-c", runner, "--read-trigger", "--conversation-id", "A", "--message-id", "a", "--prompt-from-env"], env=dict(env, YGG_TRIGGER_PROMPT=prompt), cwd=root, capture_output=True, timeout=10)
            self.assertEqual(json.loads(validated.stdout)["validation"], "matched")


if __name__ == "__main__":
    unittest.main()
