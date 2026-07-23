#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询 tag 规范语言（en/zh）。

供 agent 在生成 seed tags 或新增 tag 前调用，确定该用什么语言写 tag。
配置见 graph/tag-synonyms.yaml 的 language 字段（缺省 en）。
真源约定见 knowledge/rules/seed-tag-language.md。

用法：
  python scripts/cmds/graph/tag_language.py            # 输出: en
  python scripts/cmds/graph/tag_language.py --json     # 输出: {"language": "en"}
  ygg tag --language                        # 经 ygg 入口
"""

from __future__ import print_function

from pathlib import Path
import sys

# cmds/<domain>/<script>.py → scripts/
SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
SCRIPT_DIR = SCRIPTS_ROOT

import argparse
import json

from knowledge.tag_manager import load_tag_language  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print configured tag language (en/zh)."
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()
    lang = load_tag_language()
    if args.json:
        json.dump({"language": lang}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(lang)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
