#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Doctor 触发协议回归：只诊断缓存，不能声称匹配本轮或泄漏原文。"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yggforge-core/scripts"))
from cmds.ops import doctor


class TriggerDoctorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.now = 1000
        self.patch = patch.object(doctor, "RUNTIME_ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self.patch.stop)

    def cache(self, cid="A", age=1, **changes):
        prompt = "secret-prompt-value-must-not-be-printed"
        payload = {"protocol_version": 2, "conversation_id": cid, "message_id": "m", "created_at_unix": self.now - age, "created_at": "2026-11-06T00:00:00+00:00", "prompt": prompt, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "should_trigger": True, "action": "remember"}
        payload.update(changes)
        target = self.root / "cache/triggers" / hashlib.sha256(cid.encode()).hexdigest() / "latest.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")
        return target

    def inspect(self):
        with patch.object(doctor.time, "time", return_value=self.now):
            return doctor._check_last_trigger()

    def test_fresh_v2_cache_is_diagnostic_not_current_message_match(self):
        self.cache()
        result = self.inspect()
        message = "\n".join(text for _level, text in result)
        self.assertTrue(any(level == "green" for level, _ in result))
        self.assertIn("本轮仍须 --read-trigger", message)
        self.assertNotIn("secret-prompt-value", message)
        self.assertNotIn("validation=matched", message)

    def test_expired_cache_warns_and_has_no_green(self):
        self.cache(age=301)
        result = self.inspect()
        self.assertTrue(any("超过 5 分钟" in message for _, message in result))
        self.assertFalse(any(level == "green" for level, _ in result))

    def test_legacy_cache_is_not_read_or_treated_as_active_hook(self):
        path = self.root / "cache/last_trigger.json"
        path.parent.mkdir()
        path.write_text("secret-invalid-json", encoding="utf-8")
        result = self.inspect()
        self.assertTrue(any("旧全局" in message for _, message in result))
        self.assertFalse(any(level in ("green", "red") for level, _ in result))
        self.assertNotIn("secret-invalid-json", str(result))

    def test_invalid_schema_digest_and_future_timestamp_are_red(self):
        for changes in ({"protocol_version": 1}, {"prompt_sha256": "wrong"}, {"message_id": ""}, {"created_at_unix": 1100}, {"created_at_unix": float("nan")}, {"should_trigger": "true"}):
            with self.subTest(changes=changes):
                self.cache(**changes)
                self.assertTrue(any(level == "red" for level, _ in self.inspect()))

    def test_corrupt_json_does_not_echo_input(self):
        self.cache().write_text('secret-invalid-json', encoding="utf-8")
        result = self.inspect()
        self.assertTrue(any(level == "red" for level, _ in result))
        self.assertNotIn("secret-invalid-json", str(result))

    def test_failed_detector_is_reported_without_error_payload(self):
        self.cache(parse_error="secret-error-detail", detector_stderr="secret-stderr")
        result = self.inspect()
        self.assertTrue(any("检测失败" in message for _, message in result))
        self.assertNotIn("secret-error-detail", str(result))
        self.assertNotIn("secret-stderr", str(result))

    def test_symlink_outside_runtime_is_not_read(self):
        directory = self.root / "cache/triggers"
        directory.parent.mkdir()
        with tempfile.TemporaryDirectory() as outside:
            try:
                directory.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("当前平台没有创建符号链接权限")
            result = self.inspect()
            self.assertTrue(any(level == "red" and "越界" in message for level, message in result))


if __name__ == "__main__":
    unittest.main()
