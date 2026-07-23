#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YggForge 脚本公共工具函数。

本模块汇集在多个脚本里逐字重复的通用辅助函数，集中到一处维护，避免
散落各处的副本随时间 diverge。只依赖标准库，不 import 任何本地模块，
因此可被 scripts/ 下任意脚本（包括被 subprocess 直接拉起的叶子 CLI）
安全 import，无需额外 sys.path 操作。

提供三个函数：

- ``load_json``：读取 UTF-8（可带 BOM）的 JSON 文件。YggForge 的配置文件
  （``config/*.defaults.json``、``*.local.json``）在 Windows 上常带 BOM，
  故统一用 ``utf-8-sig`` 解码以兼容有无 BOM 两种情况。
- ``deep_merge_dict``：深度合并两个字典，子 dict 递归合并而非整体替换。
  用于 ``defaults + local`` 配置叠加：本机 ``*.local.json`` 覆盖仓库默认
  ``*.defaults.json``，嵌套键逐层合并。
- ``normalize_tag``：tag 规范化（去首尾空白、转小写、压缩内部空白）。
  所有 tag 在写入倒排索引与查询时都先过此函数，保证 ``Latte`` / `` latte ``
  / ``latte``  归一到同一键。用 ``str(tag)`` 防御非字符串入参。

设计原则：本模块保持无本地依赖、纯函数、无副作用，便于任何脚本顶层 import。
"""

import json
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path) -> Dict[str, Any]:
    """读取 JSON 文件，兼容 UTF-8 with BOM（Windows 习惯）。

    用 ``utf-8-sig`` 解码：有 BOM 时自动剥除，无 BOM 时按普通 UTF-8 读，
    两种情况都能正确解析。用于读取 ``config/*.defaults.json`` 与
    ``*.local.json`` 等配置文件。

    例子::

        cfg = load_json(CORE_ROOT / "config" / "deploy.defaults.json")

    不会捕获异常——文件不存在或 JSON 非法时直接抛出，由调用方决定处理。
    """
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def deep_merge_dict(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """深度合并两个字典：``override`` 覆盖 ``base``，子 dict 递归合并。

    非 dict 值（含 list）整体替换，不做元素级合并——这与 YggForge 配置语义
    一致（``*.local.json`` 的 list 是完整覆盖默认，而非拼接）。

    返回新字典，不修改入参。用于 ``defaults + local`` 叠加::

        policy = deep_merge_dict(
            load_json(DEFAULTS_PATH),
            load_json(LOCAL_PATH),   # 本机覆盖
        )
    """
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def normalize_tag(tag: str) -> str:
    """规范化 tag：去首尾空白、转小写、压缩内部空白。

    ``"  Latte  "`` / ``"latte"`` / ``"LA TTE"`` 都归一为 ``"latte"``，
    保证写入倒排索引与查询时键一致。用 ``str(tag)`` 防御非字符串入参
    （如 ``None`` 或数字），统一按字符串处理。

    注意：此函数只做字面规范化，不做同义词归并——同义词映射由
    ``tag_manager._canonical_tag`` 在此基础上叠加。
    """
    return " ".join(str(tag).strip().lower().split())
