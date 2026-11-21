"""将获准快照送入原生 Linux 临时目录，再安全回收模型结果。"""

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile


def read_regular(path: Path, limit: int = 64 * 1024 * 1024) -> bytes:
    """回收文件不跟随模型创建的链接，不读取超限或特殊文件。"""
    descriptor = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("角色输出不是普通文件或超出上限。")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
            if len(data) > limit:
                raise ValueError("角色输出增长超过上限。")
            return data
    finally:
        os.close(descriptor)


def main():
    original = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    storage = Path(original["workspace"]).resolve()
    if not storage.is_dir():
        raise ValueError("角色运行收据目录不存在。")
    with tempfile.TemporaryDirectory(prefix="ygg-role-", dir="/tmp") as directory:
        native = Path(directory)
        native.chmod(0o700)
        for name in ("AGENTS.md", "context.json", "prompt.txt"):
            (native / name).write_bytes(read_regular(storage / name))
        identity = storage / "IDENTITY.md"
        if identity.is_file():
            (native / "IDENTITY.md").write_bytes(read_regular(identity))
        for name in ("SOUL.md", "USER.md", "TOOLS.md"):
            if (storage / name).is_file():
                (native / name).write_bytes(read_regular(storage / name))
        context = json.loads(read_regular(storage / "context.json").decode("utf-8-sig"))
        for item in context.get("context_files", []):
            relative = Path(item["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("补充设定快照路径不合法。")
            source = storage / relative
            source.resolve().relative_to(storage)
            target = native / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(read_regular(source))
        for folder in ("skills", "memories", "shared", "inputs", "project"):
            source = storage / folder
            if not source.is_dir() or source.is_symlink():
                continue
            for path in source.rglob("*"):
                if path.is_symlink() or not path.is_file():
                    continue
                path.resolve().relative_to(storage)
                target = native / path.relative_to(storage)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(read_regular(path))
        request = dict(original, workspace=str(native))
        request_path = native / "worker-request.json"
        request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        worker = Path(__file__).with_name("landlock_worker.py")
        result = subprocess.run([sys.executable, str(worker), str(request_path)], capture_output=True, timeout=int(original.get("timeout", 170)) + 8)
        sys.stdout.buffer.write(result.stdout)
        sys.stderr.buffer.write(result.stderr)
        if result.returncode:
            return result.returncode
        output = read_regular(native / "final.txt")
        (storage / "final.txt").write_bytes(output)
        # 只回收普通工作成果；认证快照和内部请求不进入成果目录。
        artifacts = storage / "artifacts"
        excluded = {"AGENTS.md", "IDENTITY.md", "SOUL.md", "USER.md", "TOOLS.md", "context.json", "prompt.txt", "worker-request.json", "final.txt"}
        count = 0
        for path in native.rglob("*"):
            relative = path.relative_to(native)
            if path.is_symlink() or any(part.startswith(".") for part in relative.parts) or relative.parts[0] in {"tmp", "skills", "memories", "shared", "inputs", "project"} or relative.as_posix() in excluded or not path.is_file():
                continue
            if path.resolve().relative_to(native) != relative:
                continue
            count += 1
            if count > 100:
                raise ValueError("角色工作成果数量超出上限。")
            target = artifacts / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(read_regular(path))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
