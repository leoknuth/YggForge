#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共同目录上的图读写锁：跨 Windows／WSL 使用原子独占创建。"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import socket
import threading
import time
from typing import Optional
import uuid

from knowledge.graph_models import GraphError

_held = threading.local()


def lock_path(root: Path, config: Optional[dict] = None) -> Path:
    """锁位置由空间解析器设置；普通全局调用按内容根派生。"""
    config = config or {}
    root = Path(root).resolve()
    is_role = root.name == "memories" and root.parent.parent.name == "roles"
    identity = str(config.get("space_id", "role:" + root.parent.name if is_role else "shared"))
    name = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    repository = root.parents[3] if is_role else root.parent
    base = Path(config.get("lock_root", repository / "yggforge-runtime/locks/graphs"))
    return base / (name + ".lock")


@contextmanager
def graph_lock(root: Path, config: Optional[dict] = None, timeout: float = 30.0):
    """所有索引读写共享此锁；同线程嵌套重入，故障不自动抢占别人的锁。"""
    path = lock_path(root, config)
    key = str(path.resolve())
    held = getattr(_held, "paths", {})
    if key in held:
        held[key] += 1
        try:
            yield
        finally:
            held[key] -= 1
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    deadline = time.monotonic() + timeout
    while True:
        try:
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump({"pid": os.getpid(), "host": socket.gethostname(), "token": token}, handle)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise GraphError("知识空间正被占用，或上次进程中断留下锁: {0}".format(path))
            time.sleep(0.025)
    held[key] = 1
    _held.paths = held
    try:
        yield
    finally:
        held.pop(key, None)
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("token") == token:
                path.unlink()
        except (OSError, ValueError):
            pass
