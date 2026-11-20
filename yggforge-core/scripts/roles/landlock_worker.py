"""独立 Linux 执行器：文件白名单继承到所有模型子进程。"""

import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import signal
import stat


def landlock_abi() -> int:
    if not sys.platform.startswith("linux"):
        return 0
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.syscall(444, 0, 0, 1)
    return max(0, int(result))


def restrict_filesystem(read_only, writable) -> None:
    """根用户也不能通过子进程、链接或恢复能力绕过文件范围。"""
    abi = landlock_abi()
    if abi < 1:
        raise RuntimeError("当前 Linux 内核不支持 Landlock，拒绝 enforced 模式。")
    libc = ctypes.CDLL(None, use_errno=True)
    handled = (1 << 13) - 1
    if abi >= 2:
        handled |= 1 << 13
    if abi >= 3:
        handled |= 1 << 14
    class Ruleset(ctypes.Structure):
        _fields_ = [("handled_access_fs", ctypes.c_uint64)]
    class Beneath(ctypes.Structure):
        _pack_ = 1
        _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]
    attrs = Ruleset(handled)
    descriptor = libc.syscall(444, ctypes.byref(attrs), ctypes.sizeof(attrs), 0)
    if descriptor < 0:
        raise OSError(ctypes.get_errno(), "创建 Landlock 规则失败")
    try:
        for raw, write in [(path, False) for path in read_only] + [(path, True) for path in writable]:
            path = Path(raw).resolve()
            if not path.exists():
                continue
            if write:
                allowed = handled
            elif path.is_dir():
                allowed = 1 | (1 << 2) | (1 << 3)
            elif stat.S_ISREG(path.stat().st_mode):
                allowed = 1 | (1 << 2)
            else:
                allowed = (1 << 2) | ((1 << 1) if str(path) in {"/dev/null", "/dev/zero"} else 0)
            fd = os.open(str(path), os.O_PATH | os.O_CLOEXEC)
            try:
                rule = Beneath(allowed, fd)
                if libc.syscall(445, descriptor, 1, ctypes.byref(rule), 0) < 0:
                    raise OSError(ctypes.get_errno(), "添加 Landlock 文件规则失败")
            finally:
                os.close(fd)
        if os.getuid() == 0:
            # 锁定根用户语义并丢弃能力，子进程不能靠 UID=0 恢复特权。
            if libc.prctl(28, 15, 0, 0, 0) != 0:
                raise OSError(ctypes.get_errno(), "设置安全位失败")
            for capability in range(41):
                libc.prctl(24, capability, 0, 0, 0)
            class Header(ctypes.Structure):
                _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int)]
            class Caps(ctypes.Structure):
                _fields_ = [("effective", ctypes.c_uint32), ("permitted", ctypes.c_uint32), ("inheritable", ctypes.c_uint32)]
            header, caps = Header(0x20080522, 0), (Caps * 2)()
            if libc.capset(ctypes.byref(header), ctypes.byref(caps)) != 0:
                raise OSError(ctypes.get_errno(), "清除进程能力失败")
        if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.syscall(446, descriptor, 0) != 0:
            raise OSError(ctypes.get_errno(), "应用 Landlock 文件边界失败")
    finally:
        os.close(descriptor)


def _toml(value):
    if isinstance(value, dict):
        return "{" + ", ".join(json.dumps(str(key)) + " = " + _toml(item) for key, item in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_toml(item) for item in value) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def find_codex() -> Path:
    candidates = list((Path.home() / ".local/share/codex").glob("*/package/vendor/*/bin/codex"))
    if candidates:
        return max(candidates, key=lambda path: path.stat().st_mtime).resolve()
    found = shutil.which("codex")
    if found and Path(found).read_bytes()[:4] == b"\x7fELF":
        return Path(found).resolve()
    raise RuntimeError("找不到独立 Codex Linux 二进制。")


def run_codex(request) -> int:
    cwd = Path(request["workspace"]).resolve()
    codex = find_codex()
    home = cwd / ".codex"
    home.mkdir(exist_ok=True)
    source_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    if not source_home.is_dir():
        source_home = Path.home() / ".codex"
    auth = source_home / "auth.json"
    local_auth = home / "auth.json"
    if auth.is_file():
        shutil.copyfile(auth, local_auth)
        local_auth.chmod(0o600)
    config = source_home / "config.toml"
    selected = {}
    if config.is_file():
        import tomllib
        source = tomllib.loads(config.read_text(encoding="utf-8-sig"))
        selected = {key: source[key] for key in ("model", "model_provider", "model_reasoning_effort", "model_providers") if key in source}
    local_config = home / "config.toml"
    local_config.write_text("\n".join(key + " = " + _toml(value) for key, value in selected.items()) + "\n", encoding="utf-8")
    local_config.chmod(0o600)
    (cwd / "tmp").mkdir(exist_ok=True)
    env = dict(os.environ, CODEX_HOME=str(home), TMPDIR=str(cwd / "tmp"), TMP=str(cwd / "tmp"), TEMP=str(cwd / "tmp"))
    read_only = ["/usr", "/bin", "/lib", "/lib64", "/etc/ssl/certs", "/etc/resolv.conf", "/etc/hosts", "/etc/nsswitch.conf", "/etc/passwd", "/dev/null", "/dev/zero", "/dev/random", "/dev/urandom", str(codex.parent)]
    restrict_filesystem(read_only, [cwd])
    argv = [str(codex), "exec", "--ephemeral", "--ignore-rules", "--skip-git-repo-check", "--sandbox", "workspace-write", "-c", 'approval_policy="never"', "-c", 'shell_environment_policy.inherit="none"', "--json", "-C", str(cwd), "-o", str(cwd / "final.txt"), "-"]
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", start_new_session=True)
    process.stdin.write(request["prompt"])
    process.stdin.close()
    # 客户端完成启动后移除认证和配置快照，模型工具无原凭据路径访问权。
    errors = []
    def read_output():
        for line in process.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                event = {}
            if event.get("type") == "thread.started":
                local_auth.unlink(missing_ok=True)
                local_config.unlink(missing_ok=True)
            print(line, end="", flush=True)
    def read_error():
        errors.append(process.stderr.read())
    readers = [threading.Thread(target=read_output), threading.Thread(target=read_error)]
    for reader in readers:
        reader.start()
    try:
        try:
            status = process.wait(timeout=int(request.get("timeout", 170)))
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            status = process.wait()
        for reader in readers:
            reader.join(timeout=3)
        if status:
            print("".join(errors)[:2000], file=sys.stderr)
        return status
    finally:
        local_auth.unlink(missing_ok=True)
        local_config.unlink(missing_ok=True)


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--probe":
        print(json.dumps({"landlock_abi": landlock_abi(), "codex_binary": str(find_codex())}))
        return 0
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if request.get("action") == "probe-files":
        restrict_filesystem(request.get("read_only", []), request.get("writable", []))
        results = {}
        for path in request["attempts"]:
            try:
                Path(path).read_bytes()
                results[path] = "allowed"
            except PermissionError:
                results[path] = "denied"
        for path in request.get("child_attempts", []):
            child = subprocess.run(["/bin/cat", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            results["child:" + path] = "allowed" if child.returncode == 0 else "denied"
        print(json.dumps(results))
        return 0
    provider_environment = Path.home() / ".config/codex/provider-env.sh"
    if provider_environment.is_file() and not os.environ.get("YGG_ROLE_ENV_READY"):
        # 在 Linux 内传递位置参数，避免 Windows/WSL 对 shell 引号的二次处理。
        os.execv("/bin/sh", ["sh", "-c", '. "$1"; export YGG_ROLE_ENV_READY=1; exec "$2" "$3" "$4"', "role-bootstrap", str(provider_environment), sys.executable, str(Path(__file__).resolve()), str(Path(sys.argv[1]).resolve())])
    return run_codex(request)


if __name__ == "__main__":
    raise SystemExit(main())
