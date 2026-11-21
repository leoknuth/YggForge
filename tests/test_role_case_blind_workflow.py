"""新命例工序、分术准备与冻结汇总的业务隔离回归。"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "yggforge-core/scripts"
sys.path.insert(0, str(SCRIPTS))
from knowledge.graph_build import build_indexes
from knowledge.spaces import role_space, shared_space
from roles.cases import initialize_case, add_track, freeze_track, check_case, save_outputs, resolve_record
from roles.executor import execute
from roles.loader import load_task, prepare_context
from roles.registry import create_role, load_role, RoleError, validate_record_id


class CaseBlindWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.core = self.repo / "yggforge-core"
        self.write(self.core / "config/roles.defaults.json", {"allowed_shared_paths": ["knowledge/rules/shared.md"], "retrieval": {"shared_limit": 5, "role_limit": 10, "max_chars": 10000}})
        self.write(self.core / "knowledge/rules/shared.md", "---\nid: common\ntitle: 共同方法\ntype: rule\nstatus: active\nconfidence: high\ntags: [agent]\n---\nSHARED_METHOD\n")
        self.write(self.core / "graph/tag-graph.yaml", {"tags": {"agent": {"related": []}}})
        role = create_role("test-reader", "测试角色", "不含真实人物的工序验证", self.core)
        for skill in ("central", "bazi", "ziwei"):
            self.write(role.root / "skills" / skill / "SKILL.md", "---\nname: " + skill + "\ndescription: agent方法\n---\n完整专业流程 " + skill + "\n")
        self.write(role.root / "SOUL.md", "完整专业人格，不含客户结果。")
        self.write(role.root / "TOOLS.md", "PRIVATE_TOOLS_OTHER_CASE_RESULT_MUST_NOT_LEAK")
        self.write(role.root / "templates/blind-tools.md", "SAFE_TOOL_METHOD_PROJECTION")
        self.write(role.root / "USER.md", "PRIVATE_USER_HISTORY_MUST_NOT_LEAK")
        template = {"schema_version": 1, "input_files": ["input/facts.json", "input/questions.md"], "tracks": {track: {"skills": ["skills/" + track + "/SKILL.md"], "required_inputs": ["input/facts.json", "input/questions.md"], "required_calculations": ["calculations/" + track + "/chart.json"]} for track in ("bazi", "ziwei")}, "optional_tracks": {"mbti": {"skills": ["skills/central/SKILL.md"], "required_inputs": ["input/facts.json"], "required_calculations": ["calculations/mbti/sources.json"]}}, "synthesis_skills": ["skills/central/SKILL.md"], "blind_context_files": ["SOUL.md", "templates/blind-tools.md"], "reference_roots": ["records/library/classics"], "supplements": {"name": {"mode": "optional", "status": "pending"}, "mbti": {"mode": "independent-multisource", "status": "pending"}}}
        self.write(role.root / "templates/natal.case.json", template)
        config = json.loads((role.root / "role.yaml").read_text())
        config.update({"skills": ["skills/" + name + "/SKILL.md" for name in ("central", "bazi", "ziwei")], "default_skills": ["skills/central/SKILL.md"], "skill_workflows": {"natal": ["skills/bazi/SKILL.md", "skills/ziwei/SKILL.md"]}, "context_files": ["SOUL.md", "TOOLS.md", "USER.md"], "case_template": "templates/natal.case.json"})
        self.write(role.root / "role.yaml", config)
        self.role = load_role(role.id, self.core)
        initialized = initialize_case(self.role, "example-case")
        self.root = Path(initialized["path"])
        self.role = load_role(role.id, self.core)
        self.write(self.role.root / "records/library/classics/method.md", "纯典籍原文 CLASSIC_SOURCE")
        for name, project, tags, body in (("method", "", "agent", "ELIGIBLE_METHOD"), ("case", "scope-example", "agent", "OTHER_TRACK_PRIVATE_NOTE"), ("prediction", "", "agent,prediction", "UNTAGGED_PROJECT_PREDICTION")):
            self.write(self.role.root / "memories/notes/rules" / (name + ".md"), "---\nid: " + name + "\ntitle: " + name + "\ntype: rule\nstatus: active\nconfidence: high\nproject_id: " + json.dumps(project) + "\ntags: [" + tags + "]\n---\n" + body + "\n")
        build_indexes(space=shared_space(self.core))
        build_indexes(space=role_space(self.role.id, self.core))

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value, encoding="utf-8")

    def task(self, **extra):
        return {"task_id": "blind-test", "prompt": "仅按本术独立分析", "project_id": "scope-example", "record_id": "example-case", "stage": "blind", "track": "bazi", "tags": ["agent"], **extra}

    def complete_inputs(self):
        self.write(self.root / "input/facts.json", {"source_status": "user-supplied", "facts": {"description": "显式测试资料"}})
        self.write(self.root / "input/questions.md", "用户明确问题与原始口径。")

    def complete_track(self, track):
        self.write(self.root / "calculations" / track / "chart.json", {"source_status": "verified-calculation", "test_symbols": [track]})
        self.write(self.root / "analyses" / track / "report.md", "# 独立完整报告\n\n" + track + " 自身计算与引证。")
        self.write(self.root / "analyses" / track / "evidence.json", {"schema_version": 1, "track": track, "status": "completed", "source_status": "traditional-interpretation", "claims": [{"id": "claim-1", "text": "明确是待现实验证的传统解释", "basis": ["calculations/" + track + "/chart.json"]}]})

    def test_new_case_only_has_pending_skeleton_and_no_fake_facts(self):
        self.assertEqual(check_case(self.root)["status"], "pending")
        self.assertEqual(json.loads((self.root / "input/facts.json").read_text())["facts"], {})
        for name in ("overview", "assessment", "classical-reflections", "conflicts", "report"):
            self.assertIn("pending", (self.root / "synthesis" / (name + ".md")).read_text(encoding="utf-8-sig"))
        self.assertFalse(list((self.root / "deliverables").iterdir()))
        with self.assertRaises(RoleError):
            initialize_case(self.role, "example-case")

    def test_blind_bundle_does_not_leak_other_track_state_user_or_notes(self):
        self.complete_inputs()
        self.complete_track("bazi")
        self.complete_track("ziwei")
        self.write(self.root / "analyses/ziwei/report.md", "OTHER_TRACK_SECRET_REPORT")
        self.write(self.root / "STATE.md", "OTHER_TRACK_SECRET_STATE")
        bundle = prepare_context(self.role.id, self.task(), self.core).as_dict()
        body = json.dumps(bundle, ensure_ascii=False)
        for marker in ("OTHER_TRACK_SECRET_REPORT", "OTHER_TRACK_SECRET_STATE", "PRIVATE_USER_HISTORY_MUST_NOT_LEAK", "PRIVATE_TOOLS_OTHER_CASE_RESULT_MUST_NOT_LEAK", "OTHER_TRACK_PRIVATE_NOTE", "UNTAGGED_PROJECT_PREDICTION"):
            self.assertNotIn(marker, body)
        self.assertIn("ELIGIBLE_METHOD", body)
        self.assertIn("SHARED_METHOD", body)
        self.assertEqual(bundle["skills"][0]["name"], "bazi")
        self.assertEqual(len(bundle["skills"]), 1)
        self.assertFalse(bundle["record_state"])
        self.assertEqual(bundle["role_summary"]["projection"], "blind-method-only")
        self.assertTrue(bundle["case_policy"]["fresh_context_required"])
        self.assertNotIn("_source_root", body)
        self.assertNotIn("USER.md", body)
        self.assertNotIn("TOOLS.md", body)
        self.assertIn("SAFE_TOOL_METHOD_PROJECTION", body)

    def test_cross_track_files_skills_dependencies_and_library_parent_are_rejected(self):
        self.complete_inputs()
        for fields in ({"files": ["analyses/ziwei/report.md"]}, {"skills": ["skills/ziwei/SKILL.md"]}, {"dependency_results": [{"output": "其它术结果"}]}, {"references": ["records/clients/example-case/analyses/ziwei/report.md"]}):
            with self.assertRaises(RoleError):
                prepare_context(self.role.id, self.task(**fields), self.core)
        with self.assertRaises(RoleError):
            prepare_context(self.role.id, self.task(stage="", track=""), self.core)

    def test_explicit_classic_reference_is_snapshotted_without_granting_role_root(self):
        self.complete_inputs()
        bundle = prepare_context(self.role.id, self.task(references=["records/library/classics/method.md"]), self.core)
        with patch("roles.executor.HOST_RUNTIME_ROOT", self.repo / "runtime"):
            prepared = execute(bundle, backend="prepare", isolation="logical")
        workspace = Path(prepared["workspace"])
        self.assertIn("CLASSIC_SOURCE", (workspace / "references/records/library/classics/method.md").read_text(encoding="utf-8-sig"))
        self.assertFalse((workspace / "record/analyses/ziwei/report.md").exists())
        self.assertFalse((workspace / "USER.md").exists())
        self.assertFalse((workspace / "TOOLS.md").exists())
        self.assertIn("SAFE_TOOL_METHOD_PROJECTION", (workspace / "templates/blind-tools.md").read_text(encoding="utf-8-sig"))

    def test_safe_projection_cannot_escape_or_select_original_user_and_tools(self):
        self.complete_inputs()
        manifest_path = self.root / "CASE.json"
        original = json.loads(manifest_path.read_text())
        for value in ("../USER.md", "USER.md", "TOOLS.md", "../other-reader/TOOLS.md"):
            manifest = dict(original, blind_context_files=[value])
            self.write(manifest_path, manifest)
            with self.assertRaises(RoleError):
                prepare_context(self.role.id, self.task(), self.core)
        self.write(manifest_path, original)

    def test_synthesis_requires_every_track_frozen_and_preserves_originals(self):
        self.complete_inputs()
        self.complete_track("bazi")
        with self.assertRaises(RoleError):
            prepare_context(self.role.id, self.task(stage="synthesis", track=""), self.core)
        frozen = freeze_track(self.root, "bazi")
        self.assertEqual(frozen["source_status"], "traditional-interpretation")
        with self.assertRaises(RoleError):
            freeze_track(self.root, "bazi")
        self.complete_track("ziwei")
        freeze_track(self.root, "ziwei")
        bundle = prepare_context(self.role.id, self.task(stage="synthesis", track=""), self.core).as_dict()
        paths = {item["snapshot_path"] for item in bundle["task"]["files"]}
        self.assertIn("record/analyses/bazi/report.md", paths)
        self.assertIn("record/analyses/ziwei/report.md", paths)
        self.assertEqual(check_case(self.root, True)["status"], "frozen")
        self.write(self.root / "calculations/bazi/chart.json", {"changed": True})
        with self.assertRaises(RoleError):
            prepare_context(self.role.id, self.task(stage="synthesis", track=""), self.core)

    def test_pending_inputs_evidence_and_frozen_output_replacement_are_rejected(self):
        self.complete_track("bazi")
        with self.assertRaises(RoleError):
            freeze_track(self.root, "bazi")
        self.complete_inputs()
        self.write(self.root / "analyses/bazi/evidence.json", {"schema_version": 1, "track": "bazi", "status": "completed", "claims": []})
        with self.assertRaises(RoleError):
            freeze_track(self.root, "bazi")
        self.complete_track("bazi")
        bundle = prepare_context(self.role.id, self.task(), self.core)
        freeze_track(self.root, "bazi")
        with self.assertRaises(RoleError):
            save_outputs(bundle.case_policy, self.repo / "artifacts")

    def test_record_id_remains_separate_from_project_scope_and_default_flow(self):
        file = self.repo / "task.json"
        self.write(file, self.task())
        loaded = load_task(file)
        self.assertEqual(loaded["project_id"], "scope-example")
        self.assertEqual(loaded["record_id"], "example-case")
        plain = {"task_id": "plain", "prompt": "完整原工作流", "project_id": "", "tags": ["agent"], "workflow": "natal"}
        bundle = prepare_context(self.role.id, plain, self.core)
        self.assertEqual({skill["name"] for skill in bundle.skills}, {"central", "bazi", "ziwei"})

    def test_optional_multisource_track_is_independent_and_does_not_mutate_frozen_track(self):
        self.complete_inputs()
        self.complete_track("bazi")
        freeze_track(self.root, "bazi")
        original = (self.root / "analyses/bazi/report.md").read_bytes()
        add_track(self.role, "example-case", "mbti")
        self.assertEqual(check_case(self.root)["tracks"]["bazi"], "frozen")
        self.assertEqual(original, (self.root / "analyses/bazi/report.md").read_bytes())
        bundle = prepare_context(self.role.id, self.task(track="mbti"), self.core).as_dict()
        self.assertNotIn("record/analyses/bazi/report.md", {item["snapshot_path"] for item in bundle["task"]["files"]})
        self.assertIn("pending", (self.root / "analyses/mbti/report.md").read_text(encoding="utf-8-sig"))

    def test_stale_snapshot_and_unknown_output_do_not_replace_case_results(self):
        self.complete_inputs()
        bundle = prepare_context(self.role.id, self.task(), self.core)
        artifacts = self.repo / "artifacts"
        self.write(artifacts / "outputs/bazi/report.md", "完成的本术正文")
        original = (self.root / "analyses/bazi/report.md").read_bytes()
        self.write(artifacts / "outputs/bazi/other/report.md", "非本术契约产物")
        with self.assertRaises(RoleError):
            save_outputs(bundle.case_policy, artifacts)
        self.assertEqual(original, (self.root / "analyses/bazi/report.md").read_bytes())
        self.write(self.root / "input/facts.json", {"corrected": True})
        with self.assertRaises(RoleError):
            save_outputs(bundle.case_policy, artifacts)
        self.assertEqual(original, (self.root / "analyses/bazi/report.md").read_bytes())

    def test_freeze_rejects_cross_track_claim_basis(self):
        self.complete_inputs()
        self.complete_track("bazi")
        evidence_path = self.root / "analyses/bazi/evidence.json"
        evidence = json.loads(evidence_path.read_text())
        evidence["claims"][0]["basis"] = ["analyses/ziwei/report.md"]
        self.write(evidence_path, evidence)
        with self.assertRaises(RoleError):
            freeze_track(self.root, "bazi")

    def test_every_own_calculation_is_frozen_including_extra_engine_artifacts(self):
        self.complete_inputs()
        self.complete_track("bazi")
        self.write(self.root / "calculations/bazi/engine-details.json", {"assumptions": ["测试口径"]})
        receipt = freeze_track(self.root, "bazi")
        self.assertIn("calculations/bazi/engine-details.json", receipt["files"])
        self.write(self.root / "calculations/bazi/engine-details.json", {"changed": True})
        with self.assertRaises(RoleError):
            check_case(self.root)

    def test_old_case_review_uses_only_approved_history_and_blind_cannot_read_it(self):
        self.complete_inputs()
        self.write(self.root / "history/approved-prior.md", "APPROVED_OLD_CASE_REPORT")
        self.write(self.root / "history/unapproved.md", "UNAPPROVED_HISTORY")
        manifest_path = self.root / "CASE.json"
        manifest = json.loads(manifest_path.read_text())
        manifest.update(review_files=["history/approved-prior.md"], review_skills=["skills/central/SKILL.md"])
        self.write(manifest_path, manifest)
        review = prepare_context(self.role.id, self.task(stage="review", track=""), self.core)
        body = json.dumps(review.as_dict(), ensure_ascii=False)
        self.assertIn("APPROVED_OLD_CASE_REPORT", body)
        self.assertNotIn("UNAPPROVED_HISTORY", body)
        self.assertIn("明确非盲回访", body)
        self.assertFalse(list((self.root / "provenance").glob("*.frozen.json")))
        blind = prepare_context(self.role.id, self.task(), self.core).as_dict()
        self.assertNotIn("APPROVED_OLD_CASE_REPORT", json.dumps(blind, ensure_ascii=False))
        with self.assertRaises(RoleError):
            prepare_context(self.role.id, self.task(files=["history/approved-prior.md"]), self.core)
        with self.assertRaises(RoleError):
            prepare_context(self.role.id, self.task(stage="review", track="", files=["history/unapproved.md"]), self.core)

    def test_review_artifacts_get_new_round_path_and_keep_frozen_original(self):
        self.complete_inputs()
        self.complete_track("bazi")
        freeze_track(self.root, "bazi")
        original_report = (self.root / "analyses/bazi/report.md").read_bytes()
        original_receipt = (self.root / "provenance/bazi.frozen.json").read_bytes()
        manifest_path = self.root / "CASE.json"
        manifest = json.loads(manifest_path.read_text())
        manifest.update(review_files=["analyses/bazi/report.md"], review_skills=["skills/central/SKILL.md"])
        self.write(manifest_path, manifest)
        review = prepare_context(self.role.id, self.task(stage="review", track=""), self.core)
        artifacts = self.repo / "review-artifacts"
        self.write(artifacts / "outputs/review/report.md", "非盲回访核验，保留旧判。")
        saved = save_outputs(review.case_policy, artifacts)
        self.assertEqual(saved, ["validation/case/reviews/" + review.context.run_id + "/report.md"])
        self.assertEqual(original_report, (self.root / "analyses/bazi/report.md").read_bytes())
        self.assertEqual(original_receipt, (self.root / "provenance/bazi.frozen.json").read_bytes())
        with self.assertRaises(RoleError):
            save_outputs(review.case_policy, artifacts)

    def test_underscore_case_ids_and_registered_alias_keep_role_and_track_ids_strict(self):
        created = initialize_case(self.role, "example_1994")
        role = load_role(self.role.id, self.core)
        self.assertIn("example_1994", role.records)
        self.assertEqual(check_case(Path(created["path"]))["case_id"], "example_1994")
        from cmds.roles.role_cli import parser
        args = parser().parse_args(["case-check", role.id, "example_1994"])
        self.assertEqual(args.case_id, "example_1994")
        from contextlib import redirect_stdout
        import io
        from cmds.roles.role_cli import main
        output = io.StringIO()
        with patch("cmds.roles.role_cli.load_role", return_value=role), patch("sys.argv", ["role_cli.py", "case-check", role.id, "example_1994"]), redirect_stdout(output):
            self.assertEqual(main(), 0)
        self.assertEqual(json.loads(output.getvalue())["case_id"], "example_1994")
        self.complete_inputs()
        manifest_path = self.root / "CASE.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["case_id"] = "legacy_1998"
        self.write(manifest_path, manifest)
        registered_id, record = resolve_record(role, "legacy_1998")
        self.assertEqual(registered_id, "example-case")
        self.assertEqual(record["root"], self.root)
        task_file = self.repo / "underscore-task.json"
        self.write(task_file, self.task(record_id="legacy_1998"))
        bundle = prepare_context(role.id, load_task(task_file), self.core).as_dict()
        self.assertEqual(bundle["task"]["record_id"], "example-case")
        self.assertEqual(bundle["case_policy"]["case_id"], "legacy_1998")
        for invalid in ("../case", "case.name", "c:drive", "con", "com1", "Case_ID"):
            with self.assertRaises(RoleError):
                validate_record_id(invalid)
        from knowledge.spaces import validate_role_id
        from knowledge.graph_models import GraphError
        with self.assertRaises(GraphError):
            validate_role_id("role_id")


@unittest.skipUnless(sys.platform.startswith("linux"), "受控文件隔离需Linux Landlock，Windows原生仅逻辑隔离")
class CaseLandlockTests(CaseBlindWorkflowTests):
    def test_actual_landlock_denies_other_track_notes_and_input_writes(self):
        from roles.landlock_worker import landlock_abi
        if not landlock_abi():
            self.skipTest("内核不支持Landlock，不能降级宣称文件隔离")
        self.complete_inputs()
        self.complete_track("bazi")
        self.complete_track("ziwei")
        bundle = prepare_context(self.role.id, self.task(), self.core)
        with patch("roles.executor.HOST_RUNTIME_ROOT", self.repo / "runtime"):
            prepared = execute(bundle, backend="prepare", isolation="logical")
        workspace = Path(prepared["workspace"])
        own = workspace / "record/calculations/bazi/chart.json"
        other = self.root / "analyses/ziwei/report.md"
        note = self.role.root / "memories/notes/rules/case.md"
        facts = workspace / "record/input/facts.json"
        output = workspace / "outputs/bazi/report.md"
        request = self.repo / "landlock-request.json"
        self.write(request, {"action": "probe-files", "read_only": ["/usr", "/bin", "/lib", "/lib64", "/dev/null", str(workspace)], "writable": [str(output.parent)], "attempts": [str(own), str(other), str(note)], "child_attempts": [str(other), str(note)], "write_attempts": [str(facts), str(output)]})
        process = subprocess.run([sys.executable, str(SCRIPTS / "roles/landlock_worker.py"), str(request)], capture_output=True, text=True, timeout=20)
        self.assertEqual(process.returncode, 0, process.stderr)
        receipt = json.loads(process.stdout)
        self.assertEqual(receipt[str(own)], "allowed")
        for denied in (str(other), str(note), "child:" + str(other), "child:" + str(note), "write:" + str(facts)):
            self.assertEqual(receipt[denied], "denied")
        self.assertEqual(receipt["write:" + str(output)], "allowed")
        print("CASE_LANDLOCK_RECEIPT=" + json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
