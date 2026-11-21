"""技能显式资源声明只收窄资料，不接受越界、秘密或特殊文件。"""

import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yggforge-core/scripts"))
from roles.registry import RoleError
from roles.skills import resources, select


class RoleResourceSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.skill = self.root / "skills/research"
        self.skill.mkdir(parents=True)
        self.entry = self.skill / "SKILL.md"
        self.write("SKILL.md", "---\nname: research\ndescription: 研究方法\n---\n入口正文")
        self.write("references/method.md", "静态方法")
        self.write("references/nested/schema.json", '{"type":"object"}')
        self.write("assets/sample.txt", "静态样本")
        self.write("clients/private.md", "本轮没有选取的客户记录")
        self.write("LICENSE", "许可资料")

    def write(self, relative, text):
        path = self.skill / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def relative(self, values):
        return [path.relative_to(self.skill).as_posix() for path in values]

    def test_declared_subtree_and_file_only_include_selected_resources(self):
        self.assertEqual(self.relative(resources(self.entry, ["references", "LICENSE"])), ["LICENSE", "references/method.md", "references/nested/schema.json"])
        self.assertEqual(self.relative(resources(self.entry, ["assets/sample.txt"])), ["assets/sample.txt"])
        self.assertEqual(resources(self.entry, []), [])

    def test_metadata_resource_list_controls_actual_skill_selection(self):
        metadata = json.dumps({"tags": ["research"], "resources": ["references/method.md"]})
        self.write("SKILL.md", "---\nname: research\ndescription: 研究方法\nmetadata: " + metadata + "\n---\n完整正文")
        role = types.SimpleNamespace(root=self.root, skills=(self.entry,), retrieval={"skill_limit": 4}, metadata=lambda: {"skills": ["skills/research/SKILL.md"]})
        inventory, active = select(role, {"skills": ["research"]})
        self.assertEqual(inventory[0]["resources"], ["references/method.md"])
        self.assertEqual(self.relative([Path(value) for value in active[0]["resource_paths"]]), ["references/method.md"])

    def test_undeclared_resources_retain_safe_directory_scan(self):
        self.write(".env", "不投影的占位秘密")
        self.write("node_modules/package.txt", "依赖缓存")
        self.write("__pycache__/cache.pyc", "缓存")
        actual = self.relative(resources(self.entry))
        self.assertIn("clients/private.md", actual)
        self.assertIn("references/method.md", actual)
        self.assertIn("assets/sample.txt", actual)
        self.assertNotIn("SKILL.md", actual)
        self.assertNotIn(".env", actual)
        self.assertFalse(any("node_modules" in value or "__pycache__" in value for value in actual))

    def test_invalid_shapes_and_outside_paths_are_rejected(self):
        values = [None, "references", [None], [""], ["../outside.md"], ["references/../../outside.md"], ["/absolute.md"], ["C:\\absolute.md"], ["C:relative.md"], ["\\\\server\\share\\file.md"], ["references/method.md:stream"], ["."]]
        for value in values:
            with self.subTest(value=value), self.assertRaises(RoleError):
                resources(self.entry, value)

    def test_declared_blocked_resources_and_unsafe_subtree_are_rejected(self):
        for name in [".env", ".env.production", "credentials.json", "auth.json", "token.json", ".cache/item.txt", "cache/item.txt", "node_modules/item.txt", "data.zip", "data.tar.gz", "data.7z", "__pycache__/compiled.pyc"]:
            self.write(name, "不可投影的资料占位")
            with self.subTest(name=name), self.assertRaises(RoleError):
                resources(self.entry, [name])
        self.write("references/.env", "不可投影的资料占位")
        with self.assertRaises(RoleError):
            resources(self.entry, ["references"])

    def test_declared_links_inside_or_outside_root_are_rejected(self):
        outside = self.root / "outside.md"
        outside.write_text("没有选取的外部资料", encoding="utf-8")
        links = [(self.skill / "outside-link.md", outside), (self.skill / "inside-link.md", self.skill / "references/method.md"), (self.skill / "directory-link", self.skill / "references")]
        try:
            for path, target in links:
                path.symlink_to(target, target_is_directory=target.is_dir())
        except OSError as exc:
            self.skipTest("本机没有创建符号链接的权限: " + str(exc))
        for path, _target in links:
            with self.subTest(path=path.name), self.assertRaises(RoleError):
                resources(self.entry, [path.name])
        with self.assertRaises(RoleError):
            resources(self.entry, ["directory-link/method.md"])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "本平台没有 FIFO")
    def test_special_file_is_rejected_without_reading_it(self):
        os.mkfifo(self.skill / "pipe")
        with self.assertRaises(RoleError):
            resources(self.entry, ["pipe"])
        self.assertNotIn("pipe", self.relative(resources(self.entry)))


if __name__ == "__main__":
    unittest.main()
