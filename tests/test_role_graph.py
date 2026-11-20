#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""角色图空间、共享范围、索引新鲜度和中断发布回归。"""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
import io
import types
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yggforge-core/scripts"))
from knowledge.graph_build import build_indexes, check_indexes
from knowledge.graph_models import GraphError
from knowledge.graph_query import KnowledgeGraphIndex
from knowledge.shard_store import SortedShardStore
from knowledge.space_lock import lock_path
from knowledge.spaces import role_space, shared_space, shared_space_for_role


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig", newline="\n")


def note(entry_id, title, tags="financing", kind="reference", status="active"):
    return "---\nid: {0}\ntitle: {1}\ntype: {2}\nstatus: {3}\nconfidence: high\nlast_reviewed: \"20261120\"\ntags: [{4}]\nrelated: []\n---\n\n# {1}\n\n来源正文\n".format(entry_id, title, kind, status, tags)


GRAPH = "version: 1\ntags:\n  financing:\n    related:\n      - {tag: private-only, weight: 0.8}\n  private-only:\n    related: []\n"


class RoleGraphTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.core = Path(self.temporary.name) / "yggforge-core"
        write(self.core / "config/graph.defaults.json", "{}")
        write(self.core / "config/roles.defaults.json", json.dumps({"allowed_shared_paths": ["knowledge/reference/public.md"]}))
        write(self.core / "graph/tag-graph.yaml", GRAPH)
        write(self.core / "graph/tag-synonyms.yaml", "version: 1\nsynonyms: {}\n")
        write(self.core / "knowledge/reference/public.md", note("same-id", "共享资料"))
        write(self.core / "knowledge/reference/secret.md", note("private-id", "未授权秘密标题", "financing, private-only"))
        for role_id in ("finance-expert", "legal-expert"):
            role = self.core / "roles" / role_id
            write(role / "role.yaml", json.dumps({"id": role_id, "shared_paths": ["knowledge/reference/public.md"]}))
            write(role / "memories/graph/tag-graph.yaml", GRAPH)
            write(role / "memories/graph/tag-synonyms.yaml", "version: 1\nsynonyms: {}\n")
            write(role / "memories/notes/reference/own.md", note("same-id", role_id + " 私有记录"))
        build_indexes(space=shared_space(self.core))
        self.finance = role_space("finance-expert", self.core)
        self.legal = role_space("legal-expert", self.core)
        build_indexes(space=self.finance)
        build_indexes(space=self.legal)

    def test_same_id_stays_in_two_independent_role_spaces(self):
        for space in (self.finance, self.legal):
            hits, meta = KnowledgeGraphIndex(space=space).associate(["financing"])
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0].entry.id, "same-id")
            self.assertEqual(hits[0].entry.space_id, space.space_id)
            self.assertIn(space.owner_role, hits[0].entry.title)
            self.assertEqual(meta["space_id"], space.space_id)
        write(self.finance.note_root / "lessons/inbox/draft.md", note("draft-id", "角色草稿", kind="lesson", status="draft"))
        build_indexes(space=self.finance)
        hits, _ = KnowledgeGraphIndex(space=self.finance).associate(["financing"])
        self.assertEqual({hit.entry.id for hit in hits}, {"same-id", "draft-id"})

    def test_shared_view_hides_titles_tags_and_ids_before_return(self):
        view = shared_space_for_role("finance-expert", self.core)
        index = KnowledgeGraphIndex(space=view)
        hits, meta = index.associate(["financing"], hop=2)
        self.assertEqual([hit.entry.title for hit in hits], ["共享资料"])
        self.assertNotIn("private-only", meta["expanded_tags"])
        self.assertEqual(index.ids_for_tag("private-only"), [])
        self.assertIsNone(index.get_entry("private-id"))
        with self.assertRaises(GraphError):
            build_indexes(space=view)

    def test_changes_only_invalidate_own_notes_and_graph(self):
        write(self.finance.note_root / "reference/new.md", note("new-id", "新增经验"))
        self.assertEqual(check_indexes(space=self.finance)["index_status"], "stale")
        self.assertEqual(check_indexes(space=self.legal)["index_status"], "consistent")
        _, meta = KnowledgeGraphIndex(space=self.finance).associate(["financing"])
        self.assertTrue(meta["index_stale"])
        build_indexes(space=self.finance)
        write(self.finance.graph_root / "tag-graph.yaml", GRAPH + "  finance:\n    related: []\n")
        self.assertEqual(check_indexes(space=self.finance)["index_status"], "stale")

    def test_bad_identity_and_graph_path_cannot_select_another_role(self):
        for role_id in ("../legal-expert", "Finance", "missing-role"):
            with self.subTest(role=role_id), self.assertRaises(GraphError):
                role_space(role_id, self.core)
        path = self.core / "roles/finance-expert/role.yaml"
        write(path, json.dumps({"id": "finance-expert", "graph": {"paths": {"catalog_dir": "../legal-expert"}}}))
        with self.assertRaises(GraphError):
            role_space("finance-expert", self.core)
        write(path, json.dumps({"id": "finance-expert", "shared_paths": ["knowledge/reference"]}))
        with self.assertRaises(GraphError):
            shared_space_for_role("finance-expert", self.core)

    def test_invalid_role_yaml_does_not_echo_configuration_body(self):
        path = self.core / "roles/finance-expert/role.yaml"
        write(path, "id: [private-config-marker")
        with self.assertRaises(GraphError) as caught:
            role_space("finance-expert", self.core)
        self.assertNotIn("private-config-marker", str(caught.exception))

    def test_failed_build_keeps_both_old_indexes_readable(self):
        old_catalog = (self.finance.graph_root / "catalog/_all.tsv").read_bytes()
        old_tags = (self.finance.graph_root / "tag-inverted/_all.tsv").read_bytes()
        write(self.finance.note_root / "reference/new.md", note("new-id", "新增"))
        original = SortedShardStore.write_records
        calls = []
        def fail_second(store, *args, **kwargs):
            calls.append(store)
            if len(calls) == 2:
                raise OSError("模拟中断")
            return original(store, *args, **kwargs)
        with patch.object(SortedShardStore, "write_records", fail_second), self.assertRaises(OSError):
            build_indexes(space=self.finance)
        self.assertEqual((self.finance.graph_root / "catalog/_all.tsv").read_bytes(), old_catalog)
        self.assertEqual((self.finance.graph_root / "tag-inverted/_all.tsv").read_bytes(), old_tags)
        self.assertFalse(lock_path(self.finance.root, self.finance.config).exists())
        self.assertFalse(any(self.finance.graph_root.glob(".graph-build-*")))

    def test_lock_identity_is_independent_of_windows_and_wsl_root_strings(self):
        config = {"space_id": "role:finance-expert", "lock_root": str(Path(self.temporary.name) / "locks")}
        self.assertEqual(lock_path(Path("E:/work/project"), config), lock_path(Path("/mnt/e/work/project"), config))

    def test_foreign_index_manifest_is_rejected(self):
        path = self.finance.graph_root / "catalog/manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["space_id"] = self.legal.space_id
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(check_indexes(space=self.finance)["index_status"], "stale")
        with self.assertRaises(GraphError):
            KnowledgeGraphIndex(space=self.finance).associate(["financing"])

    def test_shared_alias_cannot_read_non_authorized_real_source(self):
        alias = self.core / "knowledge/reference/public.md"
        alias.unlink()
        try:
            alias.symlink_to(self.core / "knowledge/reference/secret.md")
        except OSError:
            self.skipTest("当前平台无符号链接权限")
        index = KnowledgeGraphIndex(space=shared_space_for_role("finance-expert", self.core))
        self.assertIsNone(index.get_entry("same-id"))
        hits, _ = index.associate(["financing"])
        self.assertEqual(hits, [])

    def test_role_tag_cli_only_updates_own_graph_and_refreshes_snapshot(self):
        from cmds.graph import tag_cli
        global_before = (self.core / "graph/tag-graph.yaml").read_bytes()
        other_before = (self.legal.graph_root / "tag-graph.yaml").read_bytes()
        module = types.ModuleType("backends.role_memory")
        module.refresh_role_memory = lambda space: build_indexes(space=space)
        output = io.StringIO()
        argv = ["tag_cli.py", "--role", "finance-expert", "--add", "own-new-tag", "--yes", "--json"]
        with patch.object(tag_cli, "role_space", return_value=self.finance), patch.object(sys, "argv", argv), patch.dict(sys.modules, {"backends.role_memory": module}), redirect_stdout(output):
            self.assertEqual(tag_cli.main(), 0)
        self.assertEqual(json.loads(output.getvalue())["space_id"], self.finance.space_id)
        self.assertIn("own-new-tag", (self.finance.graph_root / "tag-graph.yaml").read_text())
        self.assertEqual((self.core / "graph/tag-graph.yaml").read_bytes(), global_before)
        self.assertEqual((self.legal.graph_root / "tag-graph.yaml").read_bytes(), other_before)
        self.assertEqual(check_indexes(space=self.finance)["index_status"], "consistent")

    def test_role_suggestions_only_scan_own_notes_and_use_local_role_output(self):
        from knowledge.tag_suggest import compute_suggestions, write_suggestions
        payload = compute_suggestions(space=self.finance)
        self.assertEqual(payload["space_id"], self.finance.space_id)
        self.assertEqual(payload["n_entries"], 1)
        out = write_suggestions(payload, space=self.finance)
        out.relative_to(Path(self.temporary.name) / "yggforge-generated")
        self.assertIn("finance-expert", out.parts)
        self.assertEqual(json.loads(out.read_text())["space_id"], self.finance.space_id)

    def test_unsupported_role_export_rejects_before_any_write(self):
        from cmds.graph import graph_index, index_knowledge
        for module, argv in (
            (graph_index, ["graph_index.py", "--role", "finance-expert", "--build", "--with-by-tag"]),
            (index_knowledge, ["index_knowledge.py", "--role", "finance-expert"]),
        ):
            with self.subTest(module=module.__name__), patch.object(sys, "argv", argv), self.assertRaises(SystemExit) as caught:
                module.main()
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
