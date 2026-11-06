#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YggForge 统一 CLI 入口与路由器。

解析 ``ygg <action> [args]`` 并转发到对应叶子 CLI（subprocess）或内联策略模块：

- 显式 action 按 ``cli.routes.route_explicit`` 路由。
- 首 token 不在显式 action 集时，走 ``cli.intent.infer_intent`` 自然语言路由。

写操作前经 behavior 门禁（ask/allow/deny）。叶子 CLI 在 scripts/cmds/<领域>/；
库模块在 lib/policies/knowledge/backends/cli 子包。

本文件只保留入口解析；运行时辅助见 ``cli.runtime``，路由见 ``cli.routes``，
意图推断见 ``cli.intent``。
"""

from __future__ import annotations

import argparse
import sys

from cli.errors import YggError
from cli.intent import infer_intent
from cli.routes import route_explicit

EXPLICIT_ACTIONS = {
    "status",
    "deploy",
    "import",
    "sync",
    "push",
    "ingest",
    "distill",
    "dream",
    "recall",
    "remember",
    "promote",
    "index",
    "graph",
    "associate",
    "tag",
    "behavior",
    "project",
    "doctor",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified YggForge entrypoint. Supports explicit commands and a first-pass natural-language router."
    )
    parser.add_argument("tokens", nargs=argparse.REMAINDER)
    return parser


def _stdout_utf8() -> None:
    """Windows 非 UTF-8 终端下避免中文 mojibake（三庭合议 P2-2）。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main() -> int:
    _stdout_utf8()
    parser = build_parser()
    args = parser.parse_args()

    try:
        tokens = list(args.tokens)
        if not tokens:
            raise YggError("Usage: ygg <action|intent>")

        first = tokens[0].lower()
        if first in EXPLICIT_ACTIONS:
            return route_explicit(first, tokens[1:])

        intent_text = " ".join(tokens)
        action, routed_args = infer_intent(intent_text)
        print("ygg route      : {0}".format(action))
        if routed_args:
            print("ygg route args : {0}".format(" ".join(routed_args)))
        return route_explicit(action, routed_args)
    except YggError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
