#!/usr/bin/env python3
"""验证统一 CLI 参数、只读入口和来源流水线。"""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "yggforge-core/scripts"
sys.path.insert(0, str(SCRIPTS))
from cli.intent import infer_intent
from cli.routes import route_explicit
from cli.errors import YggError
from knowledge import knowledge_id


def load_leaf(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ingest = load_leaf("test_ingest_leaf", "cmds/pipeline/ingest.py")
distill = load_leaf("test_distill_leaf", "cmds/pipeline/distill.py")


class CliRoutesTest(unittest.TestCase):
    def test_memory_payload_preserves_deploy_word(self):
        self.assertEqual(infer_intent("请帮我记住先验证再部署"), ("remember", ["先验证再部署"]))

    def test_association_extracts_tags(self):
        self.assertEqual(infer_intent("按标签联想 git，python"), ("associate", ["--tag", "git", "--tag", "python"]))

    def test_deploy_question_is_read_only(self):
        self.assertEqual(infer_intent("怎么部署 codex"), ("status", ["codex"]))

    def test_natural_deploy_preserves_control_flags(self):
        for flag in ("--dry-run", "--no", "--yes", "--backup"):
            with self.subTest(flag=flag):
                action, arguments = infer_intent("部署 codex " + flag)
                self.assertEqual(action, "deploy")
                self.assertIn(flag, arguments)

    def test_negative_deploy_does_not_run_leaf(self):
        action, arguments = infer_intent("请不要部署 codex")
        with patch("cli.routes.run_python") as run:
            self.assertEqual(route_explicit(action, arguments), 0)
        run.assert_not_called()

    def test_complex_natural_deploy_does_not_drop_parameters(self):
        for text in ("部署 codex --project-root /tmp/project", "部署 codex--dry-run"):
            with self.subTest(text=text), self.assertRaises(YggError):
                infer_intent(text)

    def test_rule_negation_is_not_escalated_by_router(self):
        with patch("cli.routes.run_python", return_value=0) as run:
            route_explicit("remember", ["不要写成规则，这只是候选经验"])
        arguments = run.call_args[0][1]
        self.assertNotIn("--as", arguments)
        self.assertNotIn("--standing", arguments)

    def test_mode_and_all_agent_targets(self):
        self.assertEqual(infer_intent("部署 copy openclaw"), ("deploy", ["copy", "openclaw"]))
        self.assertEqual(infer_intent("部署 link claude"), ("deploy", ["link", "claude"]))

    def test_rebuild_index_routes_to_graph(self):
        self.assertEqual(infer_intent("重建索引"), ("graph", ["build"]))

    def test_natural_promotion_preserves_entry(self):
        self.assertEqual(infer_intent("晋升 draft.md 为规则"), ("promote", ["rule", "draft.md"]))

    def test_deploy_dry_run_reaches_leaf_and_skips_git(self):
        with patch("cli.routes.run_python", return_value=0) as run, patch("cli.routes.behavior_gate") as gate:
            self.assertEqual(route_explicit("deploy", ["--dry-run", "codex"]), 0)
        self.assertIn("--dry-run", run.call_args[0][1])
        run.assert_called_once()
        gate.assert_not_called()

    def test_deploy_no_does_not_run_leaf(self):
        with patch("cli.routes.run_python") as run:
            self.assertEqual(route_explicit("deploy", ["--no", "codex"]), 0)
        run.assert_not_called()

    def test_import_dry_run_is_preview(self):
        with patch("cli.routes.run_python", return_value=0) as run:
            route_explicit("import", ["--dry-run", "codex"])
        self.assertIn("--preview-only", run.call_args[0][1])

    def test_objective_is_boolean_flag(self):
        with patch("cli.routes.run_python", return_value=0) as run:
            route_explicit("promote", ["reference", "draft.md", "--auto", "--objective"])
        args = run.call_args[0][1]
        self.assertEqual(args.count("--entry"), 1)
        self.assertIn("--objective", args)

    def test_unknown_promote_option_rejected(self):
        with self.assertRaises(YggError):
            route_explicit("promote", ["reference", "draft.md", "--made-up"])

    def test_history_flags_forwarded(self):
        with patch("cli.routes.run_python", return_value=0) as run:
            route_explicit("recall", ["--type", "rule", "--include-inactive"])
            self.assertIn("--include-inactive", run.call_args[0][1])
            route_explicit("associate", ["--tag", "git", "--include-inactive"])
            self.assertIn("--include-inactive", run.call_args[0][1])

    def test_missing_target_option_values_rejected(self):
        for action in ("status", "deploy", "import"):
            with self.subTest(action=action), self.assertRaises(YggError):
                route_explicit(action, ["--project-root"])

    def test_read_only_root_does_not_create_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            core = Path(temporary) / "yggforge-core"
            shutil.copytree(SCRIPTS, core / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            proc = subprocess.run([sys.executable, str(core / "scripts/ygg.py"), "graph", "check", "--dry-run", "--json"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse((core / "graph").exists())
            self.assertFalse((core.parent / "yggforge-generated").exists())
            self.assertFalse((core.parent / "yggforge-runtime").exists())


class SourcePipelineTest(unittest.TestCase):
    def test_ingest_yaml_preserves_quoted_multiline_title(self):
        title = 'Windows C:\\Users\\example-user\nstatus: active "quoted"'
        extracted = {"title": title, "url": "https://example.org/a", "author": "test\\author", "publish_time": "unknown", "images": [], "source_type": "generic", "text": "Body"}
        asset = ingest.CONTENT_ROOT / "knowledge/sources/inbox/assets/example.txt"
        text = ingest.render_inbox_markdown("source-id", extracted, asset, None)
        from lib.front_matter import parse_front_matter
        metadata, _body = parse_front_matter(text)
        self.assertEqual(metadata["title"], title)
        self.assertEqual(metadata["status"], "draft")
        try:
            import yaml
        except ImportError:
            return
        header = text.split("---", 2)[1]
        self.assertEqual(yaml.safe_load(header)["title"], title)

    def test_distilled_yaml_preserves_windows_path(self):
        title = 'Windows C:\\Users\\example-user "quoted"'
        entry = {"title": title, "source": "https://example.org/a", "author": "test", "raw_text": "Windows C:\\Users\\example-user 的目录权限需要在部署前进行检查。", "path": str(distill.CONTENT_ROOT / "knowledge/sources/inbox/example.md")}
        text = distill.render_distilled(entry, "example", "source-id")
        from lib.front_matter import parse_front_matter
        metadata, _body = parse_front_matter(text)
        self.assertEqual(metadata["title"], title)
        try:
            import yaml
        except ImportError:
            return
        self.assertEqual(yaml.safe_load(text.split("---", 2)[1])["title"], title)

    def test_generic_article_excludes_script_and_navigation(self):
        data = ingest.extract_content("https://example.org/article", "<html><head><title>Memory</title></head><body><nav>noise</nav><main><h1>Memory</h1><p>Traceable facts.</p><script>hidden()</script></main></body></html>")
        self.assertIn("Traceable facts.", data["text"])
        self.assertNotIn("noise", data["text"])
        self.assertNotIn("hidden", data["text"])
        self.assertEqual(data["source_type"], "generic")

    def test_github_markdown_and_source_identity(self):
        url = "https://github.com/example/memory"
        self.assertEqual(ingest.resolve_fetch_url(url), "https://raw.githubusercontent.com/example/memory/HEAD/README.md")
        data = ingest.extract_content(url, "# Memory\n\nUse <vector> in examples.")
        self.assertEqual(data["url"], url)
        self.assertIn("<vector>", data["text"])

    def test_ingest_names_stay_inside_inbox_and_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            core = Path(temporary) / "yggforge-core"
            inbox = core / "knowledge/sources/inbox"
            original = knowledge_id.generate_knowledge_id
            with patch.object(ingest, "CONTENT_ROOT", core), patch.object(ingest, "INBOX_ROOT", inbox), patch.object(ingest, "ASSET_ROOT", inbox / "assets"), patch.object(ingest, "fetch_url", return_value="# Research\n\nSource body."), patch.object(knowledge_id, "generate_knowledge_id", side_effect=lambda path, title: original(path, title, repo_root=core)):
                first = ingest.ingest_url("https://example.org/source.md", "../../escape", False)
                second = ingest.ingest_url("https://example.org/source.md", "../../escape", False)
            self.assertNotEqual(first["markdown_path"], second["markdown_path"])
            self.assertTrue(Path(first["markdown_path"]).exists())
            self.assertTrue(Path(second["markdown_path"]).exists())
            self.assertEqual(Path(first["markdown_path"]).parent, inbox)

    def test_distill_latest_excludes_navigation(self):
        with tempfile.TemporaryDirectory() as temporary:
            inbox = Path(temporary)
            article = inbox / "2026-11-06-source.md"
            article.write_text("## 抽取正文\n来源", encoding="utf-8")
            (inbox / "README.md").write_text("# Navigation", encoding="utf-8")
            with patch.object(distill, "INBOX_ROOT", inbox):
                self.assertEqual(distill.choose_input_path(None, True), article)


if __name__ == "__main__":
    unittest.main()
