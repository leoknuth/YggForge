#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YggForge 强制检索钩子（beforeSubmitPrompt）。

每条用户消息提交前由 Cursor 调用。流程：
1. 从 stdin 读取 JSON，取用户 prompt 文本；
2. 运行 trigger_detector.py 判断 should_trigger；
3. 把检测结果落盘到 yggforge-runtime/cache/last_trigger.json，供 agent 读取；
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
  1. Windows 上优先用 stdin 里的 ``transcript_path``（ASCII 路径）打开 JSONL，
     取最近 ``<user_query>``——文件本身是合法 UTF-8（见 #162295）。
  2. 若只能用 stdin ``prompt``：二进制读 + 多编码试探 + mbcs/surrogateescape
     回环修复（见 ``_fix_windows_mojibake``）。
  3. 系统侧：Beta UTF-8 或 ``pwsh``（见 docs/guide/install.md）。
  4. Windows hooks 用 ``py -X utf8``（hooks.windows.json），避免 Python 按
     系统代码页把已污染的 stdin 再错解一层。

Cursor 修好 stdin 管道后，transcript 优先路径仍安全（多一次文件读）；
届时可考虑收紧为「仅 ``_looks_garbled`` 时才读 transcript」。
"""

from __future__ import print_function

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _stdout_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _read_stdin_bytes() -> bytes:
    """从 stdin 读取原始字节（不解码）。

    必须走二进制：中文 Windows 文本模式会按 GBK 解码 Cursor 喂入的 UTF-8，
    造成二次损坏。相关 Cursor bug 见模块 docstring 链接（#159259 等）。
    """
    data = b""
    try:
        data = os.read(sys.stdin.fileno(), 1 << 22)
    except Exception:
        data = b""
    if not data:
        try:
            data = sys.stdin.buffer.read() or b""
        except Exception:
            data = b""
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
    选 PUA/替换符最少、CJK 更合理的那个。最终 prompt 仍优先走 transcript（见
    ``_extract_prompt``），此处只尽量保住 JSON 外壳可解析。
    """
    if not data:
        return ""

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
        except UnicodeDecodeError:
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
    if "?" in text or "\ufffd" in text:
        return True
    # 私有使用区字符常见于 mbcs 误读（#159259 类双重编码）
    if any("\ue000" <= c <= "\uf8ff" for c in text):
        return True
    # 含 CJK 但「再污染」能还原成别的串 → 多半是乱码（已在 fix 里处理）；
    # 这里额外：CJK 很少却有很多非常见汉字时可疑——略过，交给 transcript。
    return False


def _prompt_from_transcript(transcript_path: str) -> str:
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
        # 大文件只扫尾部，避免拖慢 hook
        data = path.read_bytes()
        if len(data) > 2_000_000:
            data = data[-2_000_000:]
        text = data.decode("utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("role") != "user":
                continue
            msg = obj.get("message") or {}
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

    官方字段是顶层 ``prompt``。因 Cursor 在非 UTF-8 Windows 上会污染该字段
    （#159259 / #142878 / #146604），本函数在 Windows 上**优先**改读
    ``transcript_path`` JSONL（#162295），仅在无 transcript 时用 stdin +
    mojibake 兜底。返回 (prompt, matched_path)，matched_path 便于诊断
    （如 ``prompt_field: transcript_path``）。
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

    # 主绕过：#162295 —— transcript 文件是真 UTF-8；路径字段为 ASCII 不会被污染。
    # Windows 上只要能读到 user_query，就优先用它（即使 stdin prompt「看起来」可读）。
    tp = data.get("transcript_path")
    if isinstance(tp, str) and tp.strip():
        from_tr = _prompt_from_transcript(tp.strip())
        if from_tr:
            if (
                not prompt
                or _looks_garbled(prompt)
                or sys.platform.startswith("win")
            ):
                return from_tr, "transcript_path"

    return prompt, matched


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


def main() -> int:
    _stdout_utf8()

    core_root = _bootstrap_core()
    detector = core_root / "scripts" / "hooks" / "trigger_detector.py"

    cache_file = None
    try:
        from lib.repo_paths import RUNTIME_ROOT

        cache_file = RUNTIME_ROOT / "cache" / "last_trigger.json"
    except Exception:
        cache_file = core_root / "yggforge-runtime" / "cache" / "last_trigger.json"

    # 二进制读 stdin：对照 Cursor Windows 管道实际字节（#159259 / #142878）
    raw_bytes = _read_stdin_bytes()
    raw = _decode_stdin(raw_bytes)
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
            m = re.search(rb'"transcript_path"\s*:\s*"([^"]+)"', raw_bytes)
            if m:
                tp = m.group(1).decode("utf-8", errors="replace")
                data = {"transcript_path": tp}
                parse_error = parse_error + " [transcript_path recovered from raw bytes]"
        except Exception:
            pass

    prompt, matched = _extract_prompt(data)
    key_desc = _describe_keys(data) if data else []
    _write_heartbeat(raw, prompt_ok=bool(prompt), keys=key_desc)

    # 有 raw 却提不出 prompt → 强制落盘，便于下次对照真实字段
    if raw.strip() and not prompt:
        _maybe_debug_stdin(raw, force=True)

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

    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    out = {"continue": True}
    if result.get("should_trigger"):
        out["user_message"] = (
            "[ygg 钩子] should_trigger=true (action={})，已写入 {}。"
            "agent 将先读取检索结果再回答。"
        ).format(result.get("action"), cache_file)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
