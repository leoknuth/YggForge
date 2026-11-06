#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YggForge 强制检索钩子（beforeSubmitPrompt）。

每条用户消息提交前由 Cursor 调用。流程：
1. 从 stdin 读取 JSON，取用户 prompt 文本；
2. 运行 trigger_detector.py 判断 should_trigger；
3. 按会话与消息原子保存带身份和 UTC 时间的结果，供验证入口读取；
4. 返回 {"continue": true, "user_message": "..."} 放行消息，触发时提示用户。

设计原则：fail open。检测器/落盘任何异常都不阻断用户消息；
agent 侧协议约定读不到文件即视为 skip（跳过 ygg 检索），仍执行三源综合回答策略。

路径定位：兼容仓库内（yggforge-core）与部署后（~/.cursor/yggforge-core）两种环境，
通过向上查找 yggforge-core 目录并复用 repo_paths 定位 runtime。

---------------------------------------------------------------------------
Cursor Windows stdin 编码 bug（本文件大量逻辑都在绕过它）
---------------------------------------------------------------------------

现象（系统代码页非 UTF-8，如中文 Windows CP936/GBK）：
  - hook stdin JSON 里非 ASCII 字段（尤其 ``prompt``）被双重编码成乱码，或被
    替换成 ``?`` / U+FFFD；ASCII 字段（路径、id）通常完好。
  - Cursor 内部 / execution.log / transcript JSONL 里中文往往是正确的——污染
    发生在「写 hook 子进程 stdin」这一层（常经 Windows PowerShell 5.1）。

官方/社区确认与跟踪（Cursor Forum）：
  - 双重编码（GBK 误读 UTF-8 再当 UTF-8）：
    https://forum.cursor.com/t/hook-stdin-pipe-double-encodes-non-ascii-on-non-utf-8-windows/159259
    （官方回复：可开系统 Beta UTF-8，或安装 ``pwsh`` 让 Cursor 走 PS7）
  - stdin 污染、建议读 transcript_path（本仓库主绕过）：
    https://forum.cursor.com/t/windows-cursor-hooks-stdin-corrupts-utf-8-text-before-hook-script-receives-it/162295
  - 中文被替换成 ``?``：
    https://forum.cursor.com/t/windows-cursor-hooks-corrupt-chinese-utf-8-characters-in-stdin-replaced-with-question-marks/142878
  - execution.log 正确、stdin 已是 ``?``：
    https://forum.cursor.com/t/on-windows-chinese-prompt-in-hooks-stdin-becomes-while-execution-log-shows-correct-text/146604

本仓库绕过（按优先级）：
  1. 优先保留本轮 stdin 文本；缺失/明确损坏时仅在消息 ID 匹配后
     从 ``transcript_path`` 的 UTF-8 JSONL 恢复 ``<user_query>``——文件本身是合法 UTF-8（见 #162295）。
  2. 若只能用 stdin ``prompt``：二进制读 + 多编码试探 + mbcs/surrogateescape
     回环修复（见 ``_fix_windows_mojibake``）。
  3. 系统侧：Beta UTF-8 或 ``pwsh``（见 docs/guide/install.md）。
  4. Windows hooks 用 ``py -X utf8``（hooks.windows.json），避免 Python 按
     系统代码页把已污染的 stdin 再错解一层。

transcript 身份无法核对时保守跳过恢复，不能把上一轮用户消息当成本轮命令。
"""

from __future__ import print_function

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _stdout_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


MAX_STDIN_BYTES = 4 * 1024 * 1024
TRIGGER_MAX_AGE_SECONDS = 300


class InputLimitError(ValueError):
    """输入超过明确上限；不能把截断的 JSON 当作本次用户消息。"""


def _read_stdin_bytes() -> bytes:
    """循环二进制读取到 EOF，最多 4 MiB；超限明确失败并由 hook 放行。"""
    chunks = []
    size = 0
    try:
        fd = sys.stdin.fileno()
    except (AttributeError, OSError, ValueError):
        fd = None
    stream = getattr(sys.stdin, "buffer", None)
    while True:
        count = min(65536, MAX_STDIN_BYTES - size + 1)
        if fd is not None:
            block = os.read(fd, count)
        elif stream is not None:
            block = stream.read(count)
        else:
            return b""
        if not block:
            break
        chunks.append(block)
        size += len(block)
        if size > MAX_STDIN_BYTES:
            raise InputLimitError("hook stdin 超过 4 MiB 上限")
    data = b"".join(chunks)
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data


def _decode_stdin(data: bytes) -> str:
    """把 stdin 字节解码为文本。

    Cursor 在非 UTF-8 Windows 上可能喂入：
      - 合法 UTF-8；或
      - 已被 PowerShell/管道按系统代码页双重编码后的字节（#159259）；或
      - 无法表示字符已被换成 ``?`` 的残缺串（#142878 / #146604）。

    对每种候选解码：要求能 ``json.loads``；再对 prompt 做 mojibake 修复并打分，
    选 PUA/替换符最少、CJK 更合理的那个。最终 prompt 仅在身份匹配时由 transcript 恢复（见
    ``_extract_prompt``），此处只尽量保住 JSON 外壳可解析。
    """
    if not data:
        return ""

    # 合法 UTF-8 JSON 不参与其它编码的启发式竞争，避免损坏正确的本轮文本。
    try:
        text = data.decode("utf-8-sig")
        if isinstance(json.loads(text), dict):
            return text
    except (UnicodeDecodeError, ValueError):
        pass

    def score_text(text: str) -> tuple:
        try:
            obj = json.loads(text)
        except Exception:
            return None
        if not isinstance(obj, dict):
            return None
        prompt, _ = _extract_prompt(obj)  # 已含 mojibake fix
        pua = sum(1 for c in prompt if "\ue000" <= c <= "\uf8ff" or c == "\ufffd")
        cjk = sum(1 for c in prompt if "\u4e00" <= c <= "\u9fff")
        # 分越高越好：少 PUA、有 prompt、有 CJK
        return (prompt != "", -pua, cjk, len(prompt), text)

    best = None
    best_text = None
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk", "mbcs"):
        try:
            text = data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        sc = score_text(text)
        if sc is None:
            continue
        if best is None or sc[:-1] > best[:-1]:
            best = sc
            best_text = text
    if best_text is not None:
        return best_text
    # 兜底
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="surrogateescape")


def _read_stdin() -> str:
    """稳健读取 stdin：二进制读 + ``_decode_stdin``（勿用文本模式）。"""
    return _decode_stdin(_read_stdin_bytes())


def _maybe_debug_stdin(raw: str, force: bool = False) -> None:
    """把 raw stdin 落盘到 ``~/.cursor/ygg_debug_stdin.txt``。

    - ``YGG_DEBUG_STDIN=1``：始终落盘
    - ``force=True``：提取 prompt 失败时强制落盘（便于定位字段名/类型）
    """
    if not force and os.environ.get("YGG_DEBUG_STDIN", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        return
    try:
        debug_path = Path.home() / ".cursor" / "ygg_debug_stdin.txt"
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        # 截断超长内容，避免附件路径爆炸把磁盘写满
        text = raw if len(raw) <= 20000 else raw[:20000] + "\n...[truncated]...\n"
        debug_path.write_text(text, encoding="utf-8")
    except Exception:
        pass


def _write_heartbeat(raw: str = "", prompt_ok: bool = False, keys: Optional[List[str]] = None) -> None:
    """每次 hook 被调用时写 heartbeat 到 ``~/.cursor/ygg_hook_heartbeat.txt``。

    用于判断 Cursor 是否真正调用了 hook 以及 stdin 是否拿到内容：
    - 文件时间戳随消息提交更新 → hook 被 Cursor 调用了
    - 时间戳不更新 → hook 未被 Cursor 加载/触发（需重启 Cursor，或检查
      ``python``/``py`` 是否在 Cursor GUI 进程的 PATH 里）
    - 更新了但 ``raw_len=0`` → stdin 没拿到内容（编码/协议问题）
    - ``prompt_ok=False`` 且 ``raw_len>0`` → JSON 有内容但字段提取失败（看 ygg_debug_stdin.txt）
    """
    try:
        from datetime import datetime

        hb = Path.home() / ".cursor" / "ygg_hook_heartbeat.txt"
        hb.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().isoformat(timespec="seconds")
        key_part = ",".join(keys[:20]) if keys else "-"
        hb.write_text(
            "{0} | raw_len={1} | prompt_ok={2} | keys={3}\n".format(
                ts, len(raw), prompt_ok, key_part
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _fix_windows_mojibake(text: str) -> str:
    """尽力还原 Cursor stdin 双重编码乱码（transcript 不可用时的兜底）。

    背景：非 UTF-8 Windows 上 Cursor hook 管道常把 UTF-8 prompt 按 mbcs/GBK
    误解后再写成 JSON 字符串（官方确认：
    https://forum.cursor.com/t/hook-stdin-pipe-double-encodes-non-ascii-on-non-utf-8-windows/159259 ）。

    例：「第四次测试 ygg」→「绗洓娆℃祴璇?ygg」。非法 UTF-8 残余字节在 JSON
    里会变成 ``?`` / U+FFFD，对应 Python surrogateescape 的 ``\\udcXX``。

    修复：``encode('mbcs', surrogateescape).decode('utf-8')``；对 ``?`` 回填
    残余字节后，用「再污染」一致性校验（把候选重新 utf-8→mbcs 误读，应回到
    原乱码）过滤误匹配。正确中文回环失败则原样返回。

    注意：若 Cursor 已把字符换成 ``?`` 且未保留残余字节（#142878），此处无法
    无损还原——应改用 ``transcript_path``（#162295）。
    """
    if not text:
        return text

    def attempt(s: str) -> str:
        if not s:
            return ""
        encoders = ("mbcs", "gbk", "cp936") if sys.platform.startswith("win") else ()
        for enc in encoders + ("latin-1",):
            try:
                fixed = s.encode(enc, errors="surrogateescape").decode("utf-8")
                if fixed and fixed != text and "\ufffd" not in fixed:
                    return fixed
            except Exception:
                continue
        return ""

    def recorrupt_norm(fixed: str) -> str:
        """把候选按同样路径再污染，surrogate 归一成 ?。"""
        try:
            re_moj = fixed.encode("utf-8").decode("mbcs", errors="surrogateescape")
        except Exception:
            return ""
        return "".join("?" if "\udc80" <= c <= "\udcff" else c for c in re_moj)

    def consistent(fixed: str, garbled: str) -> bool:
        g = garbled.replace("\ufffd", "?")
        norm = recorrupt_norm(fixed)
        if not norm:
            return False
        if norm == g:
            return True
        # Cursor 常丢掉残余字节旁的空格：'? ygg' vs '?ygg'
        if norm.replace("? ", "?") == g or norm.replace(" ?", "?") == g:
            return True
        if g.replace("? ", "?") == norm or g.replace(" ?", "?") == norm:
            return True
        return False

    def score(fixed: str) -> tuple:
        cjk = sum(1 for c in fixed if "\u4e00" <= c <= "\u9fff")
        spaces = fixed.count(" ")
        glued = 0
        for i in range(len(fixed) - 1):
            a, b = fixed[i], fixed[i + 1]
            if ("\u4e00" <= a <= "\u9fff") and b.isascii() and b.isalnum():
                glued += 1
            if a.isascii() and a.isalnum() and ("\u4e00" <= b <= "\u9fff"):
                glued += 1
        # 常见词加权：残余字节丢失后 试/证/诀 等都能「再污染」成同一乱码，
        # 靠词表打破平局（覆盖 ygg 测试常用词即可，可继续扩充）
        common = (
            "测试", "试用", "试验", "一下", "查询", "区别", "问题", "功能", "记忆",
            "联想", "部署", "钩子", "触发", "编码", "乱码", "修复", "验证",
            "拿铁", "卡布", "奇诺", "奶泡", "第几次", "第一次", "第二次",
            "第三次", "第四次", "第五次", "是否", "使用", "回答", "上次",
        )
        words = sum(1 for w in common if w in fixed)
        return (words, spaces, cjk, -glued, len(fixed))

    candidates = []
    got = attempt(text)
    if got:
        candidates.append(got)

    work = text.replace("\ufffd", "?")
    if "?" in work:
        parts = work.split("?")
        if 2 <= len(parts) <= 3:
            from itertools import product

            n = len(parts) - 1
            surrogates = [chr(0xDC00 + b) for b in range(0x80, 0x100)]
            for surs in product(surrogates, repeat=n):
                trial_a = parts[0]
                trial_b = parts[0]
                for i, sur in enumerate(surs):
                    trial_a += sur + parts[i + 1]
                    trial_b += sur + " " + parts[i + 1]
                for trial in (trial_a, trial_b):
                    got = attempt(trial)
                    if got:
                        candidates.append(got)

    if not candidates:
        return text

    uniq = list(dict.fromkeys(candidates))
    consistent_hits = [c for c in uniq if consistent(c, text)]
    pool = consistent_hits if consistent_hits else uniq
    return max(pool, key=score)


def _coerce_text(value: Any) -> str:
    """把可能的 prompt 形态压成纯文本。

    兼容：
    - str
    - list[str] / list[{"type":"text","text":"..."}]（多模态 content blocks）
    - dict 含 text / content / prompt / message
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                for k in ("text", "content", "prompt", "message", "value"):
                    t = _coerce_text(item.get(k))
                    if t:
                        parts.append(t)
                        break
        return "\n".join(parts).strip()
    if isinstance(value, dict):
        for k in ("text", "content", "prompt", "message", "value", "body"):
            t = _coerce_text(value.get(k))
            if t:
                return t
        return ""
    return str(value).strip()


def _looks_garbled(text: str) -> bool:
    """启发式：stdin prompt 是否像 Cursor Windows 双重编码 / ``?`` 替换乱码。

    用于决定是否丢弃 stdin ``prompt``、改读 transcript（#162295）。
    """
    if not text:
        return True
    if "\ufffd" in text:
        return True
    # 私有使用区字符常见于 mbcs 误读（#159259 类双重编码）
    if any("\ue000" <= c <= "\uf8ff" or "\ud800" <= c <= "\udfff" for c in text):
        return True
    # 含 CJK 但「再污染」能还原成别的串 → 多半是乱码（已在 fix 里处理）；
    # 这里额外：CJK 很少却有很多非常见汉字时可疑——略过，交给 transcript。
    return False


def _event_identity(data: Dict[str, Any], kind: str) -> str:
    """读取宿主提供的消息身份；不把用户 prompt 内容当作会话身份。"""
    keys = ("conversation_id", "session_id", "chat_id") if kind == "conversation" else (
        "message_id", "generation_id", "request_id", "id", "uuid"
    )
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _prompt_from_transcript(
    transcript_path: str, expected_message_id: str = "", expected_conversation_id: str = ""
) -> str:
    """从 Cursor transcript JSONL 读取最近一条用户消息（UTF-8 真源）。

    这是绕过 Cursor Windows hook stdin 编码 bug 的主路径：
      https://forum.cursor.com/t/windows-cursor-hooks-stdin-corrupts-utf-8-text-before-hook-script-receives-it/162295
    stdin 里的 ``prompt`` 可能已乱码，但 ``transcript_path`` 是 ASCII 路径，
    磁盘上的 JSONL 由 Cursor 以合法 UTF-8 写入，含完整 ``<user_query>``。
    """
    path = Path(transcript_path)
    if not path.is_file():
        return ""
    last = ""
    try:
        # 大文件实际只读尾部，避免先将完整 transcript 放进内存。
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            stream.seek(max(0, stream.tell() - 2_000_000))
            data = stream.read(2_000_000)
        text = data.decode("utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict) or obj.get("role") != "user":
                continue
            msg = obj.get("message") or {}
            if not isinstance(msg, dict):
                continue
            if expected_message_id:
                actual = _event_identity(obj, "message") or _event_identity(msg, "message")
                if actual != expected_message_id:
                    continue
            if expected_conversation_id:
                actual = _event_identity(obj, "conversation") or _event_identity(msg, "conversation")
                if actual and actual != expected_conversation_id:
                    continue
            content = msg.get("content")
            blobs: List[str] = []
            if isinstance(content, str):
                blobs.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, str):
                        blobs.append(part)
                    elif isinstance(part, dict) and part.get("type") == "text":
                        blobs.append(str(part.get("text") or ""))
            blob = "\n".join(blobs)
            m = re.search(r"<user_query>\s*(.*?)\s*</user_query>", blob, re.DOTALL)
            if m:
                last = m.group(1).strip()
            elif blob.strip():
                last = blob.strip()
    except Exception:
        return ""
    return last


def _extract_prompt(data: Dict[str, Any]) -> Tuple[str, str]:
    """从 Cursor beforeSubmitPrompt 的 JSON 中提取用户文本。

    保留可读的本轮 stdin；只有缺失/明确损坏且 transcript 消息 ID 匹配时才恢复。
    无法核对身份时保守返回空文本，不把上一轮消息当成本轮命令。
    """
    prompt = ""
    matched = ""

    top_keys = (
        "prompt",
        "message",
        "user_prompt",
        "userPrompt",
        "user_message",
        "userMessage",
        "text",
        "query",
        "input",
        "content",
    )
    for key in top_keys:
        if key not in data:
            continue
        text = _coerce_text(data.get(key))
        if text:
            # stdin 字段可能已是双重编码；先尝试回环修复（#159259）
            prompt = _fix_windows_mojibake(text)
            matched = key
            break

    if not prompt:
        for wrap in ("payload", "data", "body", "request", "event", "params"):
            nested = data.get(wrap)
            if not isinstance(nested, dict):
                continue
            for key in top_keys:
                if key not in nested:
                    continue
                text = _coerce_text(nested.get(key))
                if text:
                    prompt = _fix_windows_mojibake(text)
                    matched = "{0}.{1}".format(wrap, key)
                    break
            if prompt:
                break

    if prompt and not _looks_garbled(prompt):
        return prompt, matched

    # transcript_path 指向的最后消息可能仍是上一轮，必须核对本次消息身份。
    tp = data.get("transcript_path")
    message_id = _event_identity(data, "message")
    if isinstance(tp, str) and tp.strip() and message_id:
        from_tr = _prompt_from_transcript(
            tp.strip(), expected_message_id=message_id,
            expected_conversation_id=_event_identity(data, "conversation")
        )
        if from_tr:
            return from_tr, "transcript_path"

    return "", ""


def _describe_keys(data: Dict[str, Any]) -> List[str]:
    """返回顶层 key:type 描述，便于诊断。"""
    out: List[str] = []
    for k, v in data.items():
        if isinstance(v, str):
            out.append("{0}:str({1})".format(k, len(v)))
        elif isinstance(v, list):
            out.append("{0}:list({1})".format(k, len(v)))
        elif isinstance(v, dict):
            out.append("{0}:dict({1})".format(k, len(v)))
        elif v is None:
            out.append("{0}:null".format(k))
        else:
            out.append("{0}:{1}".format(k, type(v).__name__))
    return out


def _bootstrap_core() -> Path:
    """定位 core 根（含 scripts/hooks/trigger_detector.py），把 scripts 加入 sys.path。返回 core_root。"""
    env = os.environ.get("YGGFORGE_CORE_ROOT", "").strip()
    candidates = []
    if env:
        candidates.append(Path(env).resolve())
    start = Path(__file__).resolve().parent
    for p in [start] + list(start.parents):
        candidates.append(p / "yggforge-core")
        if (p / "scripts" / "hooks" / "trigger_detector.py").exists():
            candidates.append(p)
    for cand in (Path.home() / ".cursor" / "yggforge-core", Path.home() / ".codex" / "yggforge-core"):
        candidates.append(cand)
    for cand in candidates:
        try:
            cand = cand.resolve()
        except Exception:
            continue
        if (cand / "scripts" / "hooks" / "trigger_detector.py").exists():
            scripts = str(cand / "scripts")
            if scripts not in sys.path:
                sys.path.insert(0, scripts)
            return cand
    return start


def _runtime_root(core_root: Path) -> Path:
    """复用部署路径定位，验证入口无需依赖调用方的当前目录。"""
    try:
        from lib.repo_paths import RUNTIME_ROOT
        return RUNTIME_ROOT
    except Exception:
        return core_root.parent / "yggforge-runtime"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _trigger_path(runtime_root: Path, conversation_id: str, message_id: str = "") -> Path:
    """ID 仅作哈希键，不允许宿主 ID 影响文件路径边界。"""
    directory = runtime_root / "cache" / "triggers" / _digest(conversation_id)
    return directory / ((_digest(message_id) + ".json") if message_id else "latest.json")


def _atomic_json(path: Path, result: Dict[str, Any]) -> None:
    """原子替换 JSON，读者只会看见完整的旧文件或新文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".trigger-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_trigger(
    runtime_root: Path, conversation_id: str, *, prompt: Optional[str] = None,
    message_id: str = "", now: Optional[float] = None
) -> Dict[str, Any]:
    """校验本会话、本条消息和 5 分钟时效；失败只返回 skip，不信任旧全局缓存。"""
    def skip(reason: str) -> Dict[str, Any]:
        return {"should_trigger": False, "action": "skip", "validation": reason}
    if not conversation_id or (prompt is None and not message_id):
        return skip("缺少会话或本轮消息身份；请按本次消息重新检测")
    try:
        result = json.loads(_trigger_path(runtime_root, conversation_id, message_id).read_text(encoding="utf-8"))
        if not isinstance(result, dict) or result.get("protocol_version") != 2:
            return skip("不支持的触发协议")
        if result.get("conversation_id") != conversation_id:
            return skip("会话不匹配")
        if message_id and result.get("message_id") != message_id:
            return skip("消息不匹配")
        if not result.get("message_id"):
            return skip("缺少消息 ID")
        issued = float(result["created_at_unix"])
        age = (time.time() if now is None else now) - issued
        if not math.isfinite(issued) or age < -5 or age > TRIGGER_MAX_AGE_SECONDS:
            return skip("触发结果已过期或时间无效")
        saved_prompt = result.get("prompt")
        if not isinstance(saved_prompt, str) or result.get("prompt_sha256") != _digest(saved_prompt.strip()):
            return skip("触发文本校验失败")
        if prompt is not None and result.get("prompt_sha256") != _digest(prompt.strip()):
            return skip("本轮文本不匹配")
        result["validation"] = "matched"
        return result
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        return skip("没有可用的本轮触发结果")


def _read_trigger_cli() -> int:
    parser = argparse.ArgumentParser(description="校验当前会话/消息的 hook 触发结果")
    parser.add_argument("--read-trigger", action="store_true")
    parser.add_argument("--conversation-id", required=True)
    parser.add_argument("--message-id", default="")
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-from-env", action="store_true", help="从 YGG_TRIGGER_PROMPT 读本轮原文")
    args = parser.parse_args()
    prompt = os.environ.get("YGG_TRIGGER_PROMPT") if args.prompt_from_env else args.prompt
    core_root = _bootstrap_core()
    result = read_trigger(_runtime_root(core_root), args.conversation_id, prompt=prompt, message_id=args.message_id)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def main() -> int:
    _stdout_utf8()

    if "--read-trigger" in sys.argv[1:]:
        return _read_trigger_cli()

    core_root = _bootstrap_core()
    detector = core_root / "scripts" / "hooks" / "trigger_detector.py"

    runtime_root = _runtime_root(core_root)

    # 二进制读 stdin：对照 Cursor Windows 管道实际字节（#159259 / #142878）
    try:
        raw_bytes = _read_stdin_bytes()
        raw = _decode_stdin(raw_bytes)
    except Exception as exc:
        print(json.dumps({"continue": True, "user_message": "[ygg 钩子] 输入读取失败，已跳过本次检测: {}".format(exc)}, ensure_ascii=False))
        return 0
    _maybe_debug_stdin(raw)
    # 调试模式才落盘原始字节，便于对照 Cursor 实际编码（截断到 64KB）
    if os.environ.get("YGG_DEBUG_STDIN", "").strip().lower() in ("1", "true", "yes"):
        try:
            (Path.home() / ".cursor" / "ygg_stdin_raw.bin").write_bytes(raw_bytes[:65536])
        except Exception:
            pass

    parse_error = ""
    data: Dict[str, Any] = {}
    try:
        if raw.strip():
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                data = loaded
            else:
                parse_error = "json root is {0}, not object".format(type(loaded).__name__)
    except Exception as e:
        parse_error = str(e)
        data = {}
        # P0-A fail-open（三庭合议裁定）：JSON 外壳坏时，transcript_path 是
        # ASCII 路径字段，不受 Cursor Windows stdin 编码污染（#162295）。
        # 字节级正则抽出后注入 data，让 _extract_prompt 的 transcript 主绕过
        # 仍能工作——避免 json.loads 失败即恒 skip、default_trigger 静默失效。
        try:
            # 同时恢复消息 ID，不能只根据 transcript_path 取上一轮消息。
            for key in ("transcript_path", "conversation_id", "session_id", "message_id", "generation_id", "request_id"):
                pattern = rb'"' + key.encode("ascii") + rb'"\s*:\s*("(?:\\.|[^"\\])*")'
                match = re.search(pattern, raw_bytes)
                if match:
                    data[key] = json.loads(match.group(1).decode("utf-8"))
        except Exception:
            pass

    prompt, matched = _extract_prompt(data)
    key_desc = _describe_keys(data) if data else []
    _write_heartbeat(raw, prompt_ok=bool(prompt), keys=key_desc)

    result = {
        "should_trigger": False,
        "confidence": 0,
        "reason": "hook 未取到 prompt",
        "action": "skip",
        "prompt": prompt,
        "chat_default_trigger": None,
    }
    if parse_error:
        result["parse_error"] = parse_error[:300]
    if key_desc and not prompt:
        result["stdin_keys"] = key_desc
        result["reason"] = "hook 未取到 prompt（stdin 有内容但字段不匹配，见 stdin_keys / ~/.cursor/ygg_debug_stdin.txt）"
    elif not raw.strip():
        result["reason"] = "hook 未取到 prompt（stdin 为空）"

    if prompt and detector.exists():
        try:
            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "utf-8"
            # 经环境变量传全文，避免 Windows argv 对长中文截断/乱码
            # （与 Cursor stdin bug 无关，但是同机二次损坏的常见坑）
            env["YGG_TRIGGER_PROMPT"] = prompt
            proc = subprocess.run(
                [sys.executable, str(detector), "--from-env"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
                env=env,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                det = json.loads(proc.stdout)
                if isinstance(det, dict):
                    result = dict(det)
                    result["prompt"] = prompt
                    if matched:
                        result["prompt_field"] = matched
            else:
                result = {
                    "should_trigger": False,
                    "confidence": 0,
                    "reason": "detector 非零退出或空输出",
                    "action": "skip",
                    "prompt": prompt,
                    "chat_default_trigger": None,
                    "detector_stderr": (proc.stderr or "")[:500],
                }
        except Exception as e:
            result = {
                "should_trigger": False,
                "confidence": 0,
                "reason": "detector 调用异常: {}".format(e),
                "action": "skip",
                "prompt": prompt,
                "chat_default_trigger": None,
            }

    out = {"continue": True}
    conversation_id = _event_identity(data, "conversation")
    if conversation_id:
        supplied_message_id = _event_identity(data, "message")
        message_id = supplied_message_id or uuid.uuid4().hex
        created_at = time.time()
        result.update({
            "protocol_version": 2, "conversation_id": conversation_id,
            "message_id": message_id, "message_id_source": "host" if supplied_message_id else "generated",
            "created_at": datetime.fromtimestamp(created_at, timezone.utc).isoformat(),
            "created_at_unix": created_at, "prompt_sha256": _digest(prompt.strip()),
        })
        try:
            _atomic_json(_trigger_path(runtime_root, conversation_id, message_id), result)
            _atomic_json(_trigger_path(runtime_root, conversation_id), result)
            if result.get("should_trigger"):
                out["user_message"] = "[ygg 钩子] action={}，已保存本会话触发结果；消费前需校验本轮消息。".format(result.get("action"))
        except (OSError, ValueError, UnicodeError):
            out["user_message"] = "[ygg 钩子] 触发结果保存失败；请按本次消息重新检测。"
    else:
        out["user_message"] = "[ygg 钩子] 宿主未提供会话 ID；未写全局缓存，请按本次消息重新检测。"
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
