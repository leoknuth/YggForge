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
