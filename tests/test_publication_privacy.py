#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布隐私回归：默认准入、精确标签、附件继承和链接边界。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yggforge-core/scripts"))
from policies.publication import evaluate_file, markdown_tags, select_files


class PublicationPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def write(self, name, content, *, bom=False):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8-sig" if bom else "utf-8")
        return path

    def test_no_privacy_tag_is_shared_without_shared_tag(self):
        for name, text in (("plain.md", "正文讨论隐私，并没有贴标签。"), ("tagged.md", "---\ntags: [python, 隐私说明, privacy]\n---\n可公开\n"), ("empty.md", "---\ntags: []\n---\n可公开\n"), ("config.json", '{"tags":["python"],"private":true}')):
            with self.subTest(name=name):
                self.assertTrue(evaluate_file(self.write(name, text), self.root).allowed)

    def test_markdown_privacy_inline_block_chinese_and_bom(self):
        variants = [
            '---\ntags: [python, "隐私"]\n---\n秘密\n',
            "---\ntags:\n  - python\n  - '隐私' # 本地内容\n---\n秘密\n",
            '---\ntags: ["\\u9690\\u79c1"]\n---\n秘密\n',
            '---\ntags: [\n  python,\n  "隐私"\n]\n---\n秘密\n',
            '---\ntags: [隐私-家庭]\n---\n秘密\n',
        ]
        for i, text in enumerate(variants):
            with self.subTest(index=i):
                result = evaluate_file(self.write(str(i) + ".md", text, bom=True), self.root)
                self.assertFalse(result.allowed)
                self.assertEqual(result.reason, "PRIVACY_TAG")

    def test_public_quoted_tag_comments_parse_correctly(self):
        self.assertEqual(markdown_tags("---\ntags:\n - 'public' # comment\n - \"a#b\" # comment\n---\n"), {"public", "a#b"})

    def test_nested_and_mixed_json_privacy_reject_entire_file(self):
        variants = [{"tags": ["隐私"]}, [{"tags": ["public"]}, {"tags": ["隐私"]}], {"data": {"entries": [{"tags": {"visibility": "隐私"}}]}}, {"tags": {"隐私": False}}]
        for i, obj in enumerate(variants):
            with self.subTest(index=i):
                result = evaluate_file(self.write(str(i) + ".json", json.dumps(obj, ensure_ascii=False), bom=True), self.root)
                self.assertEqual(result.reason, "PRIVACY_TAG")

    def test_framework_is_not_exempt_from_tags_or_sensitive_marker(self):
        tagged = self.write("framework/guide.md", "---\ntags: [隐私]\n---\n框架内容")
        marked = self.write("framework/tool.py", "-----BEGIN PRIVATE KEY-----\nsynthetic-test-only\n")
        self.assertEqual(evaluate_file(tagged, self.root).reason, "PRIVACY_TAG")
        self.assertEqual(evaluate_file(marked, self.root).reason, "SENSITIVE_MARKER")
        self.assertNotIn("synthetic-test-only", str(evaluate_file(marked, self.root)))

    def test_assets_inherit_private_markdown_and_json_references(self):
        image = self.write("assets/photo.png", b"fake-image")
        svg = self.write("assets/diagram.svg", "<svg/>")
        data = self.write("assets/data.json", '{"assets":["photo.png"]}')
        public_rule = self.write("rules/public.md", "公共规则")
        self.write("notes/private.md", '---\ntags: [隐私]\n---\n![图](../assets/photo.png)\n<img src="../assets/diagram.svg">\n[公共规则](../rules/public.md)\n')
        self.write("private.json", json.dumps({"tags": ["隐私"], "assets": ["assets/data.json"]}, ensure_ascii=False))
        decisions = dict(select_files(self.root))
        for name in ("assets/photo.png", "assets/diagram.svg", "assets/data.json"):
            self.assertEqual(decisions[name].reason, "INHERITED_PRIVACY")
        self.assertTrue(decisions["rules/public.md"].eligible)
        self.assertFalse(decisions["rules/public.md"].allowed)
        self.assertEqual(evaluate_file(image, self.root, inherited_tags=["隐私"]).reason, "INHERITED_PRIVACY")

    def test_reference_style_and_encoded_asset_path_inherit(self):
        self.write("assets/a b.png", b"asset")
        self.write("private.md", '---\ntags: [隐私]\n---\n![image][ref]\n[ref]: assets/a%20b.png\n')
        self.assertEqual(dict(select_files(self.root))["assets/a b.png"].reason, "INHERITED_PRIVACY")

    def test_runtime_git_and_generated_are_excluded_without_tags(self):
        names = ["yggforge-runtime/config.json", "yggforge-generated/report.md", ".git/config", "runtime/note.md", "generated/output.json"]
        for name in names:
            self.assertEqual(evaluate_file(self.write(name, "{}"), self.root).reason, "EXCLUDED_PATH")
        self.assertEqual(select_files(self.root), [])

    def test_role_memories_are_private_in_repo_and_core_layouts(self):
        names = [
            "yggforge-core/roles/finance-expert/memories/facts.md",
            "roles/legal-expert/memories/cases/note.json",
            "roles/finance-expert/memories/asset.png",
            "Roles/finance-expert/Memories/note.md",
        ]
        for name in names:
            with self.subTest(path=name):
                path = self.write(name, "{}")
                self.assertEqual(evaluate_file(path, self.root).reason, "ROLE_MEMORY")
                decisions = dict(select_files(self.root, [path], approved_items=[name], framework_paths=[Path(name).parent]))
                self.assertEqual(decisions[name].reason, "ROLE_MEMORY")
                self.assertFalse(decisions[name].eligible)
        config = self.write("yggforge-core/roles/finance-expert/AGENTS.md", "角色工作约定")
        self.assertEqual(evaluate_file(config, self.root).reason, "ROLE_DATA")
        nearby = self.write("roles/finance-expert/memories-template/guide.md", "模板说明")
        self.assertEqual(evaluate_file(nearby, self.root).reason, "ROLE_DATA")
        template = self.write("roles/_templates/financing/guide.md", "框架模板")
        self.assertTrue(evaluate_file(template, self.root).allowed)
        document = self.write("docs/roles/finance-expert/memories/guide.md", "目录示例")
        self.assertTrue(evaluate_file(document, self.root).allowed)

    def test_role_projects_profiles_skills_and_config_are_private_without_tags(self):
        names = [
            "yggforge-core/roles/finance-expert/projects/project.json",
            "yggforge-core/roles/finance-expert/USER.md",
            "yggforge-core/roles/finance-expert/role.yaml",
            "yggforge-core/roles/finance-expert/skills/analysis/SKILL.md",
            "roles/legal-expert/projects/case.json",
            "YGGFORGE-CORE/ROLES/FINANCE-EXPERT/TOOLS.md",
        ]
        for name in names:
            with self.subTest(path=name):
                path = self.write(name, "{}")
                self.assertEqual(evaluate_file(path, self.root).reason, "ROLE_DATA")
                decisions = dict(select_files(self.root, [path], approved_items=[name], framework_paths=[Path(name).parent]))
                self.assertEqual(decisions[name].reason, "ROLE_DATA")
                self.assertFalse(decisions[name].eligible)
        for name in ("yggforge-core/roles/README.md", "yggforge-core/scripts/roles/registry.py", "knowledge/templates/roles/finance-expert/guide.md"):
            self.assertTrue(evaluate_file(self.write(name, "框架说明"), self.root).allowed)

    def test_role_data_cannot_change_publication_root(self):
        name = "yggforge-core/roles/finance-expert/projects/research/STATE.md"
        path = self.write(name, "项目状态")
        for root in (self.root, self.root / "yggforge-core", path.parents[2], path.parents[1], path.parent):
            with self.subTest(root=root):
                relative = path.relative_to(root).as_posix()
                self.assertEqual(evaluate_file(path, root).reason, "ROLE_DATA")
                self.assertEqual(dict(select_files(root, approved_items=[relative], framework_paths=[path.parent]))[relative].reason, "ROLE_DATA")

    def test_role_profile_attachment_references_inherit_privacy(self):
        self.write("assets/figure.png", b"asset")
        self.write("assets/linked.png", b"asset")
        self.write("assets/data.json", '{"assets":["linked.png"]}')
        self.write("yggforge-core/roles/finance-expert/USER.md", "![图](../../../assets/figure.png)\n[data](../../../assets/data.json)\n")
        decisions = dict(select_files(self.root, [Path("assets/figure.png"), Path("assets/linked.png"), Path("assets/data.json")], approved_items=["assets/figure.png", "assets/linked.png", "assets/data.json"], framework_paths=[Path("assets")]))
        for name in ("assets/figure.png", "assets/linked.png", "assets/data.json"):
            self.assertEqual(decisions[name].reason, "INHERITED_PRIVACY")
            self.assertFalse(decisions[name].allowed)

    def test_role_project_alias_and_external_asset_alias_are_private(self):
        private = self.write("yggforge-core/roles/finance-expert/projects/result.json", "{}")
        external = self.write("assets/result.json", "{}")
        public_alias = self.root / "framework/project.json"
        public_alias.parent.mkdir()
        private_alias = self.root / "yggforge-core/roles/finance-expert/projects/external.json"
        try:
            public_alias.symlink_to(private)
            private_alias.symlink_to(external)
        except OSError:
            self.skipTest("当前平台无创建符号链接权限")
        self.assertEqual(evaluate_file(public_alias, self.root).reason, "ROLE_DATA")
        decisions = dict(select_files(self.root, [public_alias, external], approved_items=["framework/project.json", "assets/result.json"], framework_paths=[Path("framework"), Path("assets")]))
        self.assertEqual(decisions["framework/project.json"].reason, "ROLE_DATA")
        self.assertEqual(decisions["assets/result.json"].reason, "INHERITED_PRIVACY")

    def test_role_project_directory_alias_protects_selected_external_children(self):
        asset = self.write("assets/project/data.json", "{}")
        alias = self.root / "yggforge-core/roles/finance-expert/projects/shared-assets"
        alias.parent.mkdir(parents=True)
        try:
            alias.symlink_to(self.root / "assets/project", target_is_directory=True)
        except OSError:
            self.skipTest("当前平台无创建符号链接权限")
        self.assertEqual(evaluate_file(alias, self.root).reason, "ROLE_DATA")
        decision = dict(select_files(self.root, [asset], framework_paths=[Path("assets")]))["assets/project/data.json"]
        self.assertEqual(decision.reason, "INHERITED_PRIVACY")

    def test_canonical_role_memory_cannot_change_publication_root(self):
        name = "yggforge-core/roles/finance-expert/memories/cases/note.md"
        memory = self.write(name, "长期经验")
        roots = [self.root, self.root / "yggforge-core", memory.parents[2], memory.parents[1], memory.parent]
        for root in roots:
            with self.subTest(root=root):
                relative = memory.relative_to(root).as_posix()
                self.assertEqual(evaluate_file(memory, root).reason, "ROLE_MEMORY")
                decisions = dict(select_files(root, approved_items=[relative], framework_paths=[memory.parent]))
                self.assertEqual(decisions[relative].reason, "ROLE_MEMORY")

    def test_role_memory_approval_by_id_cannot_override_private_path(self):
        name = "yggforge-core/roles/legal-expert/memories/practice.md"
        self.write(name, "---\nid: memory-id\n---\n长期经验\n")
        for framework in ([], [Path("yggforge-core/roles")]):
            decisions = dict(select_files(self.root, approved_items=["memory-id", name], framework_paths=framework))
            self.assertEqual(decisions[name].reason, "ROLE_MEMORY")
            self.assertFalse(decisions[name].allowed)

    def test_role_memory_alias_cannot_escape_private_path(self):
        memory = self.write("yggforge-core/roles/finance-expert/memories/note.md", "长期经验")
        alias = self.root / "framework/alias.md"
        alias.parent.mkdir()
        try:
            alias.symlink_to(memory)
        except OSError:
            self.skipTest("当前平台无创建符号链接权限")
        self.assertEqual(evaluate_file(alias, self.root).reason, "ROLE_MEMORY")
        decisions = dict(select_files(self.root, [alias], approved_items=["framework/alias.md"], framework_paths=[Path("framework")]))
        self.assertEqual(decisions["framework/alias.md"].reason, "ROLE_MEMORY")

    def test_role_memory_assets_inherit_privacy_without_tags(self):
        self.write("assets/plot.png", b"asset")
        self.write("assets/linked.png", b"asset")
        self.write("assets/data.json", '{"assets":["linked.png"]}')
        self.write("yggforge-core/roles/finance-expert/memories/note.md", "![图](../../../../assets/plot.png)\n[data](../../../../assets/data.json)\n")
        decisions = dict(select_files(self.root, [Path("assets/plot.png"), Path("assets/linked.png"), Path("assets/data.json")], approved_items=["assets/plot.png", "assets/linked.png", "assets/data.json"], framework_paths=[Path("assets")]))
        for name in ("assets/plot.png", "assets/linked.png", "assets/data.json"):
            self.assertEqual(decisions[name].reason, "INHERITED_PRIVACY")
            self.assertFalse(decisions[name].allowed)

    def test_role_memory_link_protects_its_external_asset(self):
        asset = self.write("assets/record.json", '{"content":"长期经验"}')
        alias = self.root / "roles/finance-expert/memories/record.json"
        alias.parent.mkdir(parents=True)
        try:
            alias.symlink_to(asset)
        except OSError:
            self.skipTest("当前平台无创建符号链接权限")
        self.assertEqual(evaluate_file(alias, self.root).reason, "ROLE_MEMORY")
        decisions = dict(select_files(self.root, [asset], approved_items=["assets/record.json"], framework_paths=[Path("assets")]))
        self.assertEqual(decisions["assets/record.json"].reason, "INHERITED_PRIVACY")

    def test_symlink_outside_and_runtime_alias_cannot_escape(self):
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "secret.md"
            external.write_text("synthetic-private-content", encoding="utf-8")
            try:
                (self.root / "outside.md").symlink_to(external)
                runtime = self.write("yggforge-runtime/private.md", "runtime")
                (self.root / "alias.md").symlink_to(runtime)
                (self.root / "directory").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("当前平台无创建符号链接权限")
            self.assertEqual(evaluate_file(self.root / "outside.md", self.root).reason, "PATH_ESCAPE")
            self.assertEqual(evaluate_file(self.root / "alias.md", self.root).reason, "EXCLUDED_PATH")
            self.assertFalse(dict(select_files(self.root))["directory"].allowed)

    def test_asset_alias_uses_real_path_for_privacy_inheritance(self):
        self.write("assets/original.png", b"asset")
        try:
            (self.root / "alias.png").symlink_to(self.root / "assets/original.png")
        except OSError:
            self.skipTest("当前平台无创建符号链接权限")
        self.write("private.md", '---\ntags: [隐私]\n---\n![image](alias.png)\n')
        decisions = dict(select_files(self.root))
        self.assertEqual(decisions["assets/original.png"].reason, "INHERITED_PRIVACY")
        self.assertEqual(decisions["alias.png"].reason, "INHERITED_PRIVACY")

    def test_metadata_parse_error_is_fail_closed_without_content(self):
        for name, body in (("invalid.md", "---\ntags: *secret_alias\n---\nsecret-content"), ("invalid.json", '{"tags":["隐私"],invalid-secret')):
            result = evaluate_file(self.write(name, body), self.root)
            self.assertFalse(result.allowed)
            self.assertEqual(result.reason, "METADATA_INVALID")
            self.assertNotIn("secret", str(result))

    def test_explicit_path_list_and_parent_escape_are_checked(self):
        self.write("good.md", "public")
        self.assertTrue(dict(select_files(self.root, [Path("good.md")], approved_items=["good.md"]))["good.md"].allowed)
        self.assertEqual(evaluate_file(Path("../escape.md"), self.root).reason, "PATH_ESCAPE")

    def test_eligible_memory_still_requires_individual_approval(self):
        self.write("memory.md", "---\nid: entry-1\ntags: [python]\n---\n经验\n")
        candidate = dict(select_files(self.root))["memory.md"]
        self.assertFalse(candidate.allowed)
        self.assertTrue(candidate.eligible)
        self.assertEqual(candidate.reason, "APPROVAL_REQUIRED")
        self.assertTrue(dict(select_files(self.root, approved_items=["entry-1"]))["memory.md"].allowed)
        self.assertTrue(dict(select_files(self.root, approved_items=["memory.md"]))["memory.md"].allowed)

    def test_approval_and_framework_cannot_override_privacy(self):
        self.write("framework/private.md", "---\nid: secret-id\ntags: [隐私]\n---\n本地\n")
        self.write("framework/public.py", "print('public')\n")
        self.write("notes/public.md", "经验\n")
        decisions = dict(select_files(self.root, approved_items=["secret-id", "framework/private.md"], framework_paths=[Path("framework")]))
        self.assertFalse(decisions["framework/private.md"].allowed)
        self.assertEqual(decisions["framework/private.md"].reason, "PRIVACY_TAG")
        self.assertTrue(decisions["framework/public.py"].allowed)
        self.assertEqual(decisions["notes/public.md"].reason, "APPROVAL_REQUIRED")

    def test_approved_entry_assets_are_allowed_unless_private_elsewhere(self):
        self.write("images/shared.png", b"asset")
        self.write("images/public.png", b"asset")
        self.write("public.md", "---\nid: approved\n---\n![image](images/shared.png)\n![public](images/public.png)\n")
        self.write("private.md", "---\ntags: [隐私]\n---\n![private](images/shared.png)\n")
        decisions = dict(select_files(self.root, approved_items=["approved"]))
        self.assertTrue(decisions["public.md"].allowed)
        self.assertTrue(decisions["images/public.png"].allowed)
        self.assertFalse(decisions["images/shared.png"].allowed)

    def test_duplicate_ids_and_directory_approval_are_not_item_approval(self):
        for name in ("a.md", "b.md"):
            self.write("notes/" + name, "---\nid: duplicate\n---\n经验\n")
        decisions = dict(select_files(self.root, approved_items=["duplicate", "notes"]))
        self.assertFalse(decisions["notes/a.md"].allowed)
        self.assertFalse(decisions["notes/b.md"].allowed)
        self.assertTrue(dict(select_files(self.root, approved_items=["notes/a.md"]))["notes/a.md"].allowed)

    def test_forbidden_terms_are_generic_and_cannot_be_approved(self):
        forbidden = "synthetic-internal-name"
        self.write("framework/file.md", "text " + forbidden)
        self.write(forbidden + ".md", "public")
        decisions = dict(select_files(self.root, approved_items=["framework/file.md"], framework_paths=[Path("framework")], forbidden_terms=[forbidden]))
        self.assertFalse(decisions["framework/file.md"].allowed)
        self.assertEqual(decisions["framework/file.md"].reason, "FORBIDDEN_TERM")
        self.assertEqual(decisions[forbidden + ".md"].reason, "FORBIDDEN_TERM")
        self.assertNotIn(forbidden, str(decisions["framework/file.md"]))

    def test_unselected_private_source_still_blocks_selected_asset(self):
        self.write("image.png", b"asset")
        self.write("private.md", "---\ntags: [隐私]\n---\n![private](image.png)\n")
        self.assertEqual(dict(select_files(self.root, [Path("image.png")], approved_items=["image.png"]))["image.png"].reason, "INHERITED_PRIVACY")

    def test_invalid_tags_and_bad_url_do_not_lose_private_asset_references(self):
        self.write("image.png", b"asset")
        self.write("private.md", "---\ntags: *unresolved\n---\n![bad](http://[bad])\n![private](image.png)\n")
        self.assertEqual(dict(select_files(self.root, approved_items=["image.png"]))["image.png"].reason, "INHERITED_PRIVACY")

    def test_private_attachment_directory_and_media_attributes_inherit(self):
        self.write("assets/image.png", b"asset")
        self.write("poster.png", b"asset")
        self.write("another.png", b"asset")
        self.write("private.json", json.dumps({"tags": ["隐私"], "attachments": ["assets/"]}, ensure_ascii=False))
        self.write("private.md", '---\ntags: [隐私]\n---\n<video poster="poster.png"><source srcset="another.png 2x"></video>\n')
        decisions = dict(select_files(self.root, framework_paths=[Path("assets")], approved_items=["poster.png", "another.png"]))
        for name in ("assets/image.png", "poster.png", "another.png"):
            self.assertEqual(decisions[name].reason, "INHERITED_PRIVACY")


if __name__ == "__main__":
    unittest.main()
