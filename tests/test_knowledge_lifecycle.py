#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在临时核心包中验证知识索引、记忆晋升与治理边界。"""

import io
import json
import random
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "yggforge-core" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from backends.file_backend import FileMemoryBackend
from cmds.graph import graph_index
from cmds.memory import remember
from cmds.pipeline import promote
from knowledge.graph_build import build_indexes, check_indexes, index_records
from knowledge.graph_query import KnowledgeGraphIndex
from knowledge.shard_store import SortedShardStore
from knowledge.tag_graph import TagGraph
from lib.front_matter import dump_front_matter_lines, parse_front_matter
from policies import behavior


class TemporaryCore(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ygg-knowledge-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "graph").mkdir()
        (self.root / "graph/tag-graph.yaml").write_text("tags: {}\n", encoding="utf-8")
        self.config = {"paths": {"tag_graph": "graph/tag-graph.yaml",
                                 "catalog_dir": "graph/catalog",
                                 "tag_inverted_dir": "graph/tag-inverted"}}

    def entry(self, name="probe", kind="rule", status="active", title=None, tags=None):
        folders = {"rule": "rules", "reference": "reference", "lesson": "lessons"}
        path = self.root / "knowledge" / folders[kind] / (name + ".md")
        path.parent.mkdir(parents=True, exist_ok=True)
        metadata = {"id": name, "title": title or name, "type": kind, "status": status,
                    "confidence": "high", "last_reviewed": "2026-11-06", "tags": tags or ["probe"]}
        path.write_text("---\n" + "\n".join(dump_front_matter_lines(metadata)) + "\n---\n正文。\n",
                        encoding="utf-8-sig")
        return path


class FrontMatterTests(unittest.TestCase):
    def test_inline_lists_quoted_commas_and_comments(self):
        metadata, _ = parse_front_matter('---\ntags: [git, "a,b", \'it\'\'s\', 中文] # 注释\nrelated: [one, two]\n---\n')
        self.assertEqual(metadata["tags"], ["git", "a,b", "it's", "中文"])
        self.assertEqual(metadata["related"], ["one", "two"])

    def test_dump_round_trip_windows_path_and_escaped_title(self):
        original = {"path": "C:\\Users\\my\\文档\\memory.md", "title": '含有 "引号"\n第二行',
                    "tags": ["a,b", "x#y"], "literal": "false"}
        text = "---\n" + "\n".join(dump_front_matter_lines(original)) + "\n---\n"
        self.assertEqual(parse_front_matter(text)[0], original)

    def test_bom_and_crlf(self):
        self.assertEqual(parse_front_matter("\ufeff---\r\ntags: [a, b]\r\n---\r\n")[0]["tags"], ["a", "b"])

    def test_comments_do_not_terminate_block_lists(self):
        metadata, _ = parse_front_matter("---\ntags:\n  # 标签说明\n  - git\n---\n")
        self.assertEqual(metadata["tags"], ["git"])


class TagGraphTests(unittest.TestCase):
    def test_preserves_shorter_route_when_reliable_route_uses_hop_budget(self):
        graph = TagGraph({"s": [("x", .5), ("a", .9)], "a": [("x", .9)], "x": [("goal", .9)]})
        output = graph.expand(["s"], hop=2)
        self.assertEqual(output["goal"].path, ["s", "x", "goal"])
        self.assertAlmostEqual(output["goal"].strength, .45)

    def test_random_small_graphs_match_exhaustive_routes(self):
        rng = random.Random(7)
        for _ in range(30):
            nodes = [str(i) for i in range(6)]
            adjacency = {node: [] for node in nodes}
            for left in nodes:
                for right in nodes:
                    if left != right and rng.random() < .35:
                        adjacency[left].append((right, rng.choice([.2, .4, .7, .9, 1.])))
            expected = {"0": 1.}
            frontier = [("0", 1.)]
            for _hop in range(3):
                following = []
                for node, strength in frontier:
                    for neighbor, weight in adjacency[node]:
                        score = strength * weight
                        expected[neighbor] = max(expected.get(neighbor, 0), score)
                        following.append((neighbor, score))
                frontier = following
            output = TagGraph(adjacency).expand(["0"], hop=3)
            self.assertEqual(set(output), set(expected))
            for node, strength in expected.items():
                self.assertAlmostEqual(output[node].strength, strength)


class GraphLifecycleTests(TemporaryCore):
    def test_check_missing_index_never_creates_files(self):
        self.entry()
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        result = check_indexes(self.root, self.config)
        self.assertEqual(result["index_status"], "stale")
        after = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_build_check_and_source_body_staleness(self):
        source = self.entry()
        build_indexes(self.root, self.config)
        self.assertEqual(check_indexes(self.root, self.config)["source_consistency"], "full")
        source.write_text(source.read_text(encoding="utf-8-sig") + "修改正文。\n", encoding="utf-8-sig")
        before = (self.root / "graph/catalog/_all.tsv").read_bytes()
        self.assertEqual(check_indexes(self.root, self.config)["index_status"], "stale")
        self.assertEqual((self.root / "graph/catalog/_all.tsv").read_bytes(), before)

    def test_legacy_format_reports_migration_without_false_semantic_mismatch(self):
        self.entry()
        expected = index_records(self.root, self.config)
        options = dict(shard_max_bytes=100000, shard_max_lines=1000, full_load_max_bytes=100000)
        catalog = {key: "\t".join(value.split("\t")[:6]) for key, value in expected["catalog"].items()}
        SortedShardStore(self.root / "graph/catalog", **options).write_records(catalog)
        SortedShardStore(self.root / "graph/tag-inverted", **options).write_records(expected["tag_inverted"])
        result = check_indexes(self.root, self.config)
        self.assertEqual(result["index_status"], "migration_required")
        self.assertEqual(result["consistency_errors"], [])
        self.assertEqual(result["source_consistency"], "metadata_only")
        hits, meta = KnowledgeGraphIndex(self.root, self.config).associate(["probe"])
        self.assertEqual(hits[0].entry.status, "active")
        self.assertTrue(meta["index_stale"])

    def test_check_cli_calls_read_only_api(self):
        self.entry()
        output = io.StringIO()
        with patch.object(graph_index, "load_graph_config", return_value=self.config), \
                patch.object(graph_index, "check_indexes", side_effect=lambda **kw: check_indexes(self.root, self.config)), \
                patch.object(graph_index, "build_indexes", side_effect=AssertionError("检查不得调用构建")), \
                patch.object(sys, "argv", ["graph_index", "--check", "--json"]), redirect_stdout(output):
            self.assertEqual(graph_index.main(), 1)
        self.assertEqual(json.loads(output.getvalue())["index_status"], "stale")
        self.assertFalse((self.root / "graph/catalog").exists())

    def test_status_metadata_and_immediate_rule_revocation(self):
        source = self.entry()
        build_indexes(self.root, self.config)
        index = KnowledgeGraphIndex(self.root, self.config)
        hits, meta = index.associate(["probe"])
        self.assertEqual(hits[0].entry.confidence, "high")
        self.assertEqual(hits[0].entry.last_reviewed, "2026-11-06")
        self.assertFalse(meta["index_stale"])
        source.write_text(source.read_text(encoding="utf-8-sig").replace("status: active", "status: deprecated"), encoding="utf-8-sig")
        self.assertEqual(index.associate(["probe"])[0], [])
        self.assertEqual(index.associate(["probe"], include_inactive=True)[0][0].entry.status, "deprecated")

    def test_default_associate_limit_and_full_internal_query(self):
        for number in range(12):
            self.entry("entry" + str(number))
        build_indexes(self.root, self.config)
        index = KnowledgeGraphIndex(self.root, self.config)
        hits, metadata = index.associate(["probe"])
        self.assertEqual(len(hits), 10)
        self.assertEqual(metadata["total_hit_count"], 12)
        self.assertTrue(metadata["truncated"])
        self.assertEqual(len(index.associate(["probe"], limit=None)[0]), 12)

    def test_missing_source_is_not_returned_from_stale_index(self):
        source = self.entry()
        build_indexes(self.root, self.config)
        source.unlink()
        hits, meta = KnowledgeGraphIndex(self.root, self.config).associate(["probe"])
        self.assertEqual(hits, [])
        self.assertEqual(meta["missing_entries"], ["probe"])

    def test_inactive_rules_are_not_built_as_formal_rules(self):
        for status in ("draft", "deprecated", "superseded"):
            self.entry(status, status=status)
        self.assertEqual(build_indexes(self.root, self.config)["entries"], 0)


class ShardCacheTests(TemporaryCore):
    def test_repeated_large_index_lookups_read_same_shard_once(self):
        store = SortedShardStore(self.root / "cache", shard_max_bytes=10000, shard_max_lines=1000, full_load_max_bytes=0)
        store.write_records({"a": "one", "b": "two"})
        original = Path.read_text
        reads = []
        def observed(path, *args, **kwargs):
            if path.suffix == ".tsv":
                reads.append(path)
            return original(path, *args, **kwargs)
        with patch.object(Path, "read_text", observed):
            self.assertEqual(store.get("a"), "one")
            self.assertEqual(store.get("b"), "two")
            self.assertEqual(store.get("missing"), None)
        self.assertEqual(len(reads), 1)


class RecallTests(TemporaryCore):
    def test_reference_metadata_is_searchable(self):
        self.entry(kind="reference", title="Reference needle")
        results = FileMemoryBackend(self.root, {}).search_memories("needle", kinds=["reference"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "active")
        self.assertEqual(results[0]["confidence"], "high")

    def test_deprecated_rule_requires_explicit_inactive_query(self):
        self.entry(status="deprecated")
        backend = FileMemoryBackend(self.root, {})
        self.assertEqual(backend.search_memories("probe"), [])
        self.assertEqual(len(backend.search_memories("probe", include_inactive=True)), 1)

    def test_inbox_is_not_duplicated_by_lessons_root(self):
        path = self.root / "knowledge/lessons/inbox/draft.md"
        path.parent.mkdir(parents=True)
        path.write_text("---\ntitle: draftneedle\ntype: lesson\nstatus: draft\n---\n记忆正文。\n")
        results = FileMemoryBackend(self.root, {}).search_memories("draftneedle")
        self.assertEqual(len(results), 1)


class PromotionTests(TemporaryCore):
    def setUp(self):
        super().setUp()
        self.destinations = {kind: self.root / "knowledge" / folder for kind, folder in
                             (("rule", "rules"), ("lesson", "lessons"), ("reference", "reference"),
                              ("template", "templates"), ("decision", "decisions"))}
        for root in self.destinations.values():
            root.mkdir(parents=True)
        self.inbox = self.destinations["lesson"] / "inbox"
        self.inbox.mkdir()
        self.patches = [patch.object(promote, "CONTENT_ROOT", self.root),
                        patch.object(promote, "LESSONS_INBOX", self.inbox),
                        patch.dict(promote.DESTINATION_ROOTS, self.destinations),
                        patch.dict(promote.README_PATHS, {kind: root / "README.md" for kind, root in self.destinations.items()}),
                        patch.object(behavior, "authorize", return_value={"allowed": True})]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_rejects_absolute_parent_and_windows_path_names(self):
        for name in ("../rules/escaped.md", "..\\rules\\escaped.md", "/tmp/escaped.md", "C:\\temp\\escaped.md", "C:escaped.md"):
            with self.subTest(name=name), self.assertRaises(promote.PromoteError):
                promote.resolve_destination(self.destinations["lesson"], name)

    def test_rejects_symlink_escape(self):
        link = self.destinations["lesson"] / "link"
        try:
            link.symlink_to(self.destinations["rule"], target_is_directory=True)
        except OSError:
            self.skipTest("当前系统无法创建符号链接")
        with self.assertRaises(promote.PromoteError):
            promote.resolve_destination(self.destinations["lesson"], "link/escaped.md")

    def test_valid_promotion_moves_only_to_selected_root(self):
        source = self.inbox / "draft.md"
        source.write_text("---\ntitle: 新的经验\ntype: lesson\nstatus: draft\n---\n正文。\n")
        output = io.StringIO()
        with patch.object(sys, "argv", ["promote", "--entry", str(source), "--to", "lesson", "--name", "topic/new.md", "--yes", "--json"]), redirect_stdout(output):
            self.assertEqual(promote.main(), 0)
        result = json.loads(output.getvalue())["results"][0]
        self.assertEqual(result["write"], "ok")
        self.assertFalse(source.exists())
        self.assertTrue((self.destinations["lesson"] / "topic/new.md").exists())

    def test_invalid_promotion_keeps_source_draft(self):
        source = self.inbox / "draft.md"
        source.write_text("---\ntitle: 经验\n---\n正文。\n")
        with patch.object(sys, "argv", ["promote", "--entry", str(source), "--to", "lesson", "--name", "../rules/escaped.md", "--auto", "--yes", "--json"]), self.assertRaises(promote.PromoteError):
            promote.main()
        self.assertTrue(source.exists())
        self.assertFalse((self.destinations["rule"] / "escaped.md").exists())


class RememberTests(unittest.TestCase):
    def test_chinese_titles_have_distinct_rule_names(self):
        self.assertNotEqual(remember._slug_name("新增中文要求"), remember._slug_name("另一中文要求"))
        self.assertNotEqual(remember._slug_name("新增中文要求"), "standing-preference.md")

    def run_remember(self, items, source="user", note="以后一直这样", flags=()):
        class Backend:
            def record_observation(self, **kwargs):
                return {"status": "recorded", "title": "中文要求", "lesson_draft_path": "/tmp/unused-draft.md"}
        output = io.StringIO()
        promotion = {"status": "ok", "result": {"results": items}}
        with patch.object(remember, "get_memory_backend", return_value=Backend()), \
                patch.object(behavior, "authorize", return_value={"allowed": True}), \
                patch.object(remember, "_auto_promote_standing", return_value=promotion), \
                patch.object(sys, "argv", ["remember", "--note", note, "--source", source, "--yes", "--json"] + list(flags)), redirect_stdout(output):
            remember.main()
        return json.loads(output.getvalue())

    def test_duplicate_result_is_pending_not_promoted(self):
        result = self.run_remember([{"status": "duplicate", "write": "skipped"}])
        self.assertEqual(result["status"], "recorded_promote_pending")

    def test_empty_result_is_pending(self):
        self.assertEqual(self.run_remember([])["status"], "recorded_promote_pending")

    def test_only_actual_write_is_reported_as_promoted(self):
        self.assertEqual(self.run_remember([{"status": "active", "write": "ok"}])["status"], "recorded_and_promoted_rule")

    def test_external_text_is_not_human_standing_confirmation(self):
        result = self.run_remember([], source="external")
        self.assertFalse(result["standing"])
        self.assertEqual(result["status"], "recorded")

    def test_negative_or_quoted_intent_never_auto_promotes(self):
        notes = ["不要写成规则，这只是候选经验", "这次不需要作为规则", "文中提到“必须遵守”，这里只是摘录",
                 "不要把它升级成规则", "暂时不晋升为规则", "以后一直这样，但不要写成规则",
                 "这不是要求你写成规则", "\"make this a rule\"", "示例：make this a rule",
                 "don't make this a rule", "do not promote to rule", "原文写道：以后一直这样",
                 "`写成规则`", "```text\n以后一直这样\n```", "必须遵守项目规范", "“\n请写成规则\n”",
                 "这次作为规则不需要"]
        for note in notes:
            with self.subTest(note=note):
                self.assertFalse(remember.detect_standing_intent(note))
                result = self.run_remember([], note=note)
                self.assertFalse(result["standing"])
                self.assertEqual(result["status"], "recorded")

    def test_clear_positive_standing_intents_remain_supported(self):
        for note in ("以后一直这样", "请写成规则", "把这条写进规则", "升级成规则", "今后一律使用中文注释",
                     "from now on always use this", "please always do this", "make this a rule"):
            with self.subTest(note=note):
                self.assertTrue(remember.detect_standing_intent(note))

    def test_explicit_kind_or_standing_flag_is_authoritative(self):
        for flags in (("--as", "rule"), ("--standing",)):
            with self.subTest(flags=flags):
                result = self.run_remember([], note="仅作候选经验，不自动晋升规则", flags=flags)
                self.assertTrue(result["standing"])
                self.assertEqual(result["status"], "recorded_promote_pending")

    def test_explicit_standing_still_obeys_behavior_gate(self):
        output = io.StringIO()
        with patch.object(remember, "get_memory_backend") as backend, \
                patch.object(behavior, "authorize", return_value={"allowed": False, "mode": "deny"}) as authorize, \
                patch.object(sys, "argv", ["remember", "--note", "仅供摘录", "--as", "rule", "--json"]), redirect_stdout(output):
            self.assertEqual(remember.main(), 2)
        self.assertTrue(json.loads(output.getvalue())["standing"])
        self.assertEqual(authorize.call_args.args[0], "memory.kinds.rule")
        self.assertIsNone(authorize.call_args.kwargs["force"])
        backend.assert_not_called()


if __name__ == "__main__":
    unittest.main()
