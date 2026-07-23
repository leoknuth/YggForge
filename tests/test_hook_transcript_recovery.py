#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最小测试：hook P0-A fail-open（transcript_path 字节级恢复）。

三庭合议 P2-3：覆盖 Cursor Windows stdin 编码污染导致 json.loads 失败时，
从 raw bytes 正则抽出 ASCII transcript_path，并从 JSONL 还原最近 <user_query>。
纯标准库，pytest 与 `py -X utf8` 均可跑。

跑法：
    py -X utf8 tests\test_hook_transcript_recovery.py
    # 或 pytest tests\test_hook_transcript_recovery.py
"""
import json
import re
import sys
import tempfile
from pathlib import Path

_HOOK = Path(__file__).resolve().parent.parent / "yggforge-core" / "profiles" / "cursor" / "hooks"
if str(_HOOK) not in sys.path:
    sys.path.insert(0, str(_HOOK))

# 被测主绕过函数
from ygg_pre_submit import _prompt_from_transcript  # noqa: E402

# P0-A fail-open 的核心正则（与 ygg_pre_submit.main 内联一致）
_TP_RE = re.compile(rb'"transcript_path"\s*:\s*"([^"]+)"')


def test_recover_transcript_path_from_corrupted_bytes():
    # 模拟 Cursor Windows stdin 污染：合法 JSON 外壳里混入非法字节（0x80）
    payload = b'{"prompt":"\x80garbage","transcript_path":"C:/transcript.jsonl"}'
    # json.loads 应失败
    try:
        json.loads(payload.decode("utf-8", errors="replace"))
        # 若碰巧能解析，构造一个必然失败的版本
        payload = b'{"prompt":"\x80\x81garbage","transcript_path":"C:/transcript.jsonl"'
    except Exception:
        pass
    m = _TP_RE.search(payload)
    assert m is not None, "应能从损坏字节中正则抽出 transcript_path"
    tp = m.group(1).decode("utf-8", errors="replace")
    assert tp == "C:/transcript.jsonl"


def test_recover_when_prompt_field_garbled():
    # prompt 字段全是乱码字节，transcript_path 完好
    payload = b'{"prompt":"\xff\xfe??","transcript_path":"D:/t.jsonl","other":123}'
    m = _TP_RE.search(payload)
    assert m is not None
    assert m.group(1).decode("utf-8", errors="replace") == "D:/t.jsonl"


def test_prompt_from_transcript_reads_latest_user_query():
    # 构造合法 UTF-8 JSONL transcript，含多条 user 消息
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".jsonl", delete=False, prefix="ygg_test_tp_"
    ) as f:
        # 旧 user 消息（无 user_query 标签，取整段）
        f.write((json.dumps({"role": "user", "message": {"content": "old hello"}}) + "\n").encode("utf-8"))
        # assistant 消息（应被忽略）
        f.write((json.dumps({"role": "assistant", "message": {"content": "hi"}}) + "\n").encode("utf-8"))
        # 最新 user 消息（带 <user_query> 标签）
        latest = {
            "role": "user",
            "message": {"content": "<user_query>狞猫是什么</user_query>"},
        }
        f.write((json.dumps(latest, ensure_ascii=False) + "\n").encode("utf-8"))
        path = f.name
    try:
        got = _prompt_from_transcript(path)
        assert got == "狞猫是什么", "应取最近一条 user 的 <user_query> 内容（UTF-8 真源）"
    finally:
        Path(path).unlink(missing_ok=True)


def test_prompt_from_transcript_handles_list_content():
    # content 为 list[{"type":"text","text":...}]
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".jsonl", delete=False, prefix="ygg_test_tp_"
    ) as f:
        obj = {
            "role": "user",
            "message": {"content": [{"type": "text", "text": "<user_query>list case</user_query>"}]},
        }
        f.write((json.dumps(obj) + "\n").encode("utf-8"))
        path = f.name
    try:
        assert _prompt_from_transcript(path) == "list case"
    finally:
        Path(path).unlink(missing_ok=True)


def test_prompt_from_transcript_missing_file_returns_empty():
    assert _prompt_from_transcript("Z:/no/such/file_xyz.jsonl") == ""


def _run_all():
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS  {0}".format(name))
            except AssertionError as exc:
                failures += 1
                print("FAIL  {0}: {1}".format(name, exc))
    return failures


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)
