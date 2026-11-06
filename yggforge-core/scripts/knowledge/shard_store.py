#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""有序分片 TSV 存储。"""

from __future__ import print_function

import bisect
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from knowledge.graph_models import GraphError

GENERATED_BANNER = "# 由 ygg graph build 自动生成，请勿手改。\n"


class SortedShardStore(object):
    """按主键有序存储的分片 TSV 仓库。

    每行格式：key\\tpayload（TSV；payload 内多值用 |）

    未超阈值时整表一个文件 ``_all.tsv``，例如 tag-inverted::

        agent\\t20260701231701-kr$$$$-acd$$$$$-e3p8|20260701165030-kr$$$$-gwfaa$$$-rjdq
        git\\t20260701165030-kr$$$$-gwfaa$$$-rjdq|20260701165030-kr$$$$-mapw$$$$-ktcc

    超过 shard_max_bytes / shard_max_lines 时，按 key **字典序前缀**裂变
    （先 1 字符，仍过大再加深到 max_prefix_len），例如::

        tag-inverted: a.tsv / g.tsv / m.tsv …
        catalog:      2026.tsv → 202607.tsv → 20260701.tsv …（id 时间在前）

    查询：读 manifest 按 prefix 定位分片 → 分片内对有序行二分；
    总字节未超 full_load_max_bytes 时可整目录载入内存。
    """

    def __init__(
        self,
        root_dir: Path,
        shard_max_bytes: int,
        shard_max_lines: int,
        full_load_max_bytes: int,
        max_prefix_len: int = 8,
    ) -> None:
        self.root_dir = root_dir
        self.shard_max_bytes = shard_max_bytes
        self.shard_max_lines = shard_max_lines
        self.full_load_max_bytes = full_load_max_bytes
        self.max_prefix_len = max_prefix_len
        self.manifest_path = root_dir / "manifest.json"
        self._memory: Optional[Dict[str, str]] = None
        self._manifest: Optional[Dict[str, Any]] = None
        self._shard_cache: OrderedDict = OrderedDict()

    def write_records(self, records: Dict[str, str], source_digest: Optional[str] = None) -> Dict[str, Any]:
        """将 records 按 key 排序后写入分片，并生成 manifest。"""
        self.root_dir.mkdir(parents=True, exist_ok=True)
        # 清理旧分片
        for old in self.root_dir.glob("*.tsv"):
            old.unlink()
        if self.manifest_path.exists():
            self.manifest_path.unlink()

        items = sorted(records.items(), key=lambda pair: pair[0])
        shards = self._partition(items)
        files_meta: List[Dict[str, Any]] = []
        total_bytes = 0
        for prefix, shard_items in shards:
            filename = "_all.tsv" if prefix == "" else "{0}.tsv".format(prefix)
            path = self.root_dir / filename
            lines = ["{0}\t{1}\n".format(key, payload) for key, payload in shard_items]
            text = "".join(lines)
            path.write_text(text, encoding="utf-8")
            size = path.stat().st_size
            total_bytes += size
            files_meta.append(
                {
                    "file": filename,
                    "prefix": prefix,
                    "lines": len(shard_items),
                    "bytes": size,
                    "first_key": shard_items[0][0] if shard_items else "",
                    "last_key": shard_items[-1][0] if shard_items else "",
                }
            )

        manifest = {
            "format": "tsv-sorted-shards-v1",
            "key_order": "lexicographic",
            "total_records": len(items),
            "total_bytes": total_bytes,
            "shard_max_bytes": self.shard_max_bytes,
            "shard_max_lines": self.shard_max_lines,
            "full_load_max_bytes": self.full_load_max_bytes,
            "files": files_meta,
            "banner": GENERATED_BANNER.strip(),
        }
        if source_digest is not None:
            manifest["source_digest"] = source_digest
        with self.manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        self._manifest = manifest
        self._memory = None
        self._shard_cache.clear()
        return manifest

    def _partition(
        self, items: List[Tuple[str, str]]
    ) -> List[Tuple[str, List[Tuple[str, str]]]]:
        """按阈值递归拆分，直到每个分片不超过阈值。"""
        if not items:
            return [("", [])]
        return self._partition_with_prefix(items, prefix_len=0)

    def _partition_with_prefix(
        self, items: List[Tuple[str, str]], prefix_len: int
    ) -> List[Tuple[str, List[Tuple[str, str]]]]:
        # 估算当前整桶大小
        est_bytes = sum(len(k) + 1 + len(v) + 1 for k, v in items)
        if (
            len(items) <= self.shard_max_lines
            and est_bytes <= self.shard_max_bytes
        ) or prefix_len >= self.max_prefix_len:
            prefix = items[0][0][:prefix_len] if prefix_len > 0 else ""
            # 同一 prefix_len 下可能有多个不同前缀，需再按实际前缀分组
            if prefix_len == 0:
                return [("", items)]
            grouped: Dict[str, List[Tuple[str, str]]] = {}
            for key, payload in items:
                p = key[:prefix_len] if len(key) >= prefix_len else key
                grouped.setdefault(p, []).append((key, payload))
            return sorted(grouped.items(), key=lambda pair: pair[0])

        # 需要拆分：提高到 prefix_len+1
        next_len = prefix_len + 1
        buckets: Dict[str, List[Tuple[str, str]]] = {}
        for key, payload in items:
            p = key[:next_len] if len(key) >= next_len else key
            buckets.setdefault(p, []).append((key, payload))

        result: List[Tuple[str, List[Tuple[str, str]]]] = []
        for prefix in sorted(buckets.keys()):
            bucket = buckets[prefix]
            b_bytes = sum(len(k) + 1 + len(v) + 1 for k, v in bucket)
            if (
                len(bucket) > self.shard_max_lines or b_bytes > self.shard_max_bytes
            ) and next_len < self.max_prefix_len:
                result.extend(self._partition_with_prefix(bucket, next_len))
            else:
                result.append((prefix, bucket))
        return result

    def _load_manifest(self) -> Dict[str, Any]:
        if self._manifest is not None:
            return self._manifest
        if not self.manifest_path.exists():
            raise GraphError("缺少索引 manifest: {0}".format(self.manifest_path))
        with self.manifest_path.open("r", encoding="utf-8") as handle:
            self._manifest = json.load(handle)
        return self._manifest

    def _ensure_memory_if_small(self) -> Optional[Dict[str, str]]:
        """索引总大小未超阈值时，全量载入内存。"""
        if self._memory is not None:
            return self._memory
        manifest = self._load_manifest()
        total = int(manifest.get("total_bytes", 0))
        if total > self.full_load_max_bytes:
            return None
        memory: Dict[str, str] = {}
        for file_meta in manifest.get("files", []):
            path = self.root_dir / str(file_meta["file"])
            if not path.exists():
                raise GraphError("索引分片缺失: {0}".format(path))
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith("#"):
                    continue
                key, sep, payload = line.partition("\t")
                if not sep:
                    continue
                memory[key] = payload
        self._memory = memory
        return memory

    def get(self, key: str) -> Optional[str]:
        """按主键查询 payload；小文件走内存，大文件走分片二分。"""
        memory = self._ensure_memory_if_small()
        if memory is not None:
            return memory.get(key)

        manifest = self._load_manifest()
        shard_path = self._locate_shard(key, manifest)
        if shard_path is None:
            return None
        return self._bisect_file(shard_path, key)

    def keys(self) -> List[str]:
        """返回全部主键（有序）。大索引时会读全部分片。"""
        memory = self._ensure_memory_if_small()
        if memory is not None:
            return sorted(memory.keys())
        keys: List[str] = []
        manifest = self._load_manifest()
        for file_meta in manifest.get("files", []):
            path = self.root_dir / str(file_meta["file"])
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith("#"):
                    continue
                key, sep, _ = line.partition("\t")
                if sep:
                    keys.append(key)
        return keys

    def items(self) -> List[Tuple[str, str]]:
        """返回全部 (key, payload)。"""
        memory = self._ensure_memory_if_small()
        if memory is not None:
            return sorted(memory.items(), key=lambda pair: pair[0])
        result: List[Tuple[str, str]] = []
        manifest = self._load_manifest()
        for file_meta in manifest.get("files", []):
            path = self.root_dir / str(file_meta["file"])
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith("#"):
                    continue
                key, sep, payload = line.partition("\t")
                if sep:
                    result.append((key, payload))
        return result

    def _locate_shard(self, key: str, manifest: Dict[str, Any]) -> Optional[Path]:
        """根据 key 前缀定位分片文件。"""
        files = manifest.get("files", [])
        if not files:
            return None
        # 单文件 _all.tsv
        if len(files) == 1 and files[0].get("prefix", "") == "":
            return self.root_dir / str(files[0]["file"])
        # 选最长匹配前缀
        best = None
        best_len = -1
        for file_meta in files:
            prefix = str(file_meta.get("prefix", ""))
            if key.startswith(prefix) and len(prefix) > best_len:
                best = file_meta
                best_len = len(prefix)
        if best is None:
            return None
        return self.root_dir / str(best["file"])

    def _bisect_file(self, path: Path, key: str) -> Optional[str]:
        """在有序 TSV 文件中对行做二分查找。"""
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        cached = self._shard_cache.get(path)
        if cached is not None and cached[0] == signature:
            _, lines, keys = cached
            self._shard_cache.move_to_end(path)
        else:
            lines = [line for line in path.read_text(encoding="utf-8").splitlines()
                     if line and not line.startswith("#")]
            keys = [line.partition("\t")[0] for line in lines]
            self._shard_cache[path] = (signature, lines, keys)
            self._shard_cache.move_to_end(path)
            while len(self._shard_cache) > 8:
                self._shard_cache.popitem(last=False)
        idx = bisect.bisect_left(keys, key)
        if idx < len(keys) and keys[idx] == key:
            return lines[idx].partition("\t")[2]
        return None
