"""适配关卡回归；所有持久测试素材保留于技能目录外 test_outputs。"""
import base64
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from datetime import datetime

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from adaptation_gate import check_adaptation_plan, initial_plan
from research_plan import check_plan


class AdaptationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = SCRIPTS.parents[1] / "test_outputs"
        root.mkdir(exist_ok=True)
        cls.output = root / ("adaptation_gate_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        cls.output.mkdir()
        cls.image = cls.output / "representative.png"
        cls.image.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="))

    def plan(self):
        plan = initial_plan("proposal")
        page = plan["pages"][0]
        page.update(claim="研究假设", conclusion="拟检验机制", review_note="人工区分计划与结果", no_evidence_reason="无证据概念页")
        page["adaptation"].update(
            decision="reuse", reason="内容量适配现有槽位", content_type="概念说明",
            template_fit="单栏结构匹配", layout_strategy="复用原版式",
            readability_risk="low", fallback="文字拥挤时暂停并请求调整授权",
            acceptance_notes="检查标题、正文和图注均完整且无遮挡")
        return plan

    def assert_rejected(self, plan, path=None, stage="plan"):
        result = check_adaptation_plan(plan, stage)
        self.assertFalse(result["ok"], result)
        if path:
            self.assertTrue(any(e["path"] == path for e in result["errors"]), result)
        return result

    def approve(self, plan):
        plan["pilot"].update(status="approved", note="用户声明已检查代表页", render_paths=[str(self.image)])

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "adaptation_gate.py"), *args], capture_output=True, text=True, encoding="utf-8")

    def test_normal(self):
        self.assertTrue(check_adaptation_plan(self.plan())["ok"])

    def test_missing_page_judgment(self):
        plan = self.plan()
        del plan["pages"][0]["adaptation"]
        self.assert_rejected(plan, "pages[0].adaptation")

    def test_high_reuse(self):
        plan = self.plan()
        plan["pages"][0]["adaptation"]["readability_risk"] = "high"
        self.assert_rejected(plan, "pages[0].adaptation.decision")

    def test_strict_changes_pause(self):
        for decision in ("adjust", "redesign", "split", "hold"):
            with self.subTest(decision=decision):
                plan = self.plan()
                plan["mode"] = "strict"
                plan["pages"][0]["adaptation"].update(decision=decision, actions=["修改布局"])
                self.assert_rejected(plan, "pages[0].adaptation.decision")

    def test_strict_rejects_declared_changes_even_all_reuse(self):
        plan = self.plan()
        plan["mode"] = "strict"
        plan["authorization"].update(reorder_pages=True, source="用户允许重排")
        plan["changes"] = ["reorder_pages"]
        self.assert_rejected(plan, "changes")

    def test_acceptance_notes_required(self):
        for value in ("", " ", None):
            plan = self.plan()
            plan["pages"][0]["adaptation"]["acceptance_notes"] = value
            self.assert_rejected(plan, "pages[0].adaptation.acceptance_notes")

    def test_render_count_and_uniqueness(self):
        plan = self.plan()
        for number in (2, 3):
            page = copy.deepcopy(plan["pages"][0])
            page["page"] = number
            plan["pages"].append(page)
        self.approve(plan)
        plan["pilot"]["representative_pages"] = [1, 2, 3]
        for stage in ("pilot", "final"):
            self.assert_rejected(plan, "pilot.render_paths", stage=stage)
        plan["pilot"]["render_paths"] = [str(self.image)] * 3
        self.assert_rejected(plan, "pilot.render_paths[1]", stage="final")
        paths = [str(self.image)]
        for number in (2, 3):
            image = self.output / f"representative_{number}.png"
            image.write_bytes(self.image.read_bytes())
            paths.append(str(image))
        plan["pilot"]["render_paths"] = paths
        self.assertTrue(check_adaptation_plan(plan, "final")["ok"])

    def test_unauthorized_split(self):
        plan = self.plan()
        plan["changes"] = ["split_pages"]
        plan["pages"][0]["adaptation"].update(decision="split", actions=["拆为两页"])
        self.assert_rejected(plan, "pages[0].adaptation.decision")

    def test_authorized_split(self):
        plan = self.plan()
        plan["authorization"].update(split_pages=True, source="用户明确同意拆页，记录于本次需求")
        plan["changes"] = ["split_pages"]
        plan["pages"][0]["adaptation"].update(decision="split", actions=["拆为两页"])
        self.assertTrue(check_adaptation_plan(plan)["ok"])

    def test_hold(self):
        plan = self.plan()
        plan["pages"][0]["adaptation"].update(decision="hold", actions=["请求用户决定"])
        self.assert_rejected(plan, "pages[0].adaptation.decision")

    def test_missing_representative_pages(self):
        plan = self.plan()
        plan["pilot"]["representative_pages"] = []
        self.assert_rejected(plan, "pilot.representative_pages")

    def test_representative_page_range(self):
        for pages in ([0], [2], [True], [1, 1], ["1"]):
            with self.subTest(pages=pages):
                plan = self.plan()
                plan["pilot"]["representative_pages"] = pages
                self.assert_rejected(plan)

    def test_pilot_not_approved(self):
        self.assert_rejected(self.plan(), "pilot.status", stage="pilot")
        self.assert_rejected(self.plan(), "pilot.status", stage="final")

    def test_final_success(self):
        plan = self.plan()
        self.approve(plan)
        result = check_adaptation_plan(plan, "final")
        self.assertTrue(result["ok"], result)
        self.assertIn("不自动确认人工实际看过", "".join(result["limitations"]))

    def test_base_errors_propagated(self):
        plan = self.plan()
        plan["schema_version"] = 2
        plan["pages"][0]["claim"] = ""
        base_errors = check_plan(plan)["errors"]
        actual = self.assert_rejected(plan)["errors"]
        for error in base_errors:
            self.assertIn(error, actual)

    def test_invalid_types(self):
        fields = {
            "mode": [], "authorization": [], "changes": {}, "pilot": [], "pages": {},
        }
        for key, value in fields.items():
            with self.subTest(key=key):
                plan = self.plan()
                plan[key] = value
                self.assert_rejected(plan, key)
        for plan in ([], None, "plan", 12):
            self.assert_rejected(plan, "$")
        for key in ("decision", "readability_risk", "actions", "reason", "acceptance_notes"):
            plan = self.plan()
            plan["pages"][0]["adaptation"][key] = {}
            self.assert_rejected(plan, "pages[0].adaptation." + key)
        for key in ("required", "status", "note", "render_paths", "representative_pages"):
            plan = self.plan()
            plan["pilot"][key] = {}
            self.assert_rejected(plan, "pilot." + key)
        plan = self.plan()
        plan["changes"] = [{}]
        self.assert_rejected(plan, "changes[0]")
        plan = self.plan()
        plan["authorization"]["local_layout"] = 1
        self.assert_rejected(plan, "authorization.local_layout")

    def test_adjust_requires_declared_change_and_grant(self):
        plan = self.plan()
        plan["pages"][0]["adaptation"].update(decision="adjust", actions=["调整图文比例"])
        self.assert_rejected(plan, "changes")
        plan["changes"] = ["local_layout"]
        self.assertTrue(check_adaptation_plan(plan)["ok"])
        plan["authorization"]["local_layout"] = False
        self.assert_rejected(plan, "pages[0].adaptation.decision")

    def test_expanded_permission_needs_source(self):
        for permission in ("split_pages", "reorder_pages", "chapter_changes"):
            plan = self.plan()
            plan["authorization"][permission] = True
            self.assert_rejected(plan, "authorization.source")

    def test_changes_authorization_and_known_names(self):
        for changes in (["reorder_pages"], ["chapter_changes"], ["unknown"], ["local_layout", "local_layout"]):
            plan = self.plan()
            plan["changes"] = changes
            self.assert_rejected(plan)

    def test_nonreuse_needs_actions(self):
        plan = self.plan()
        plan["pages"][0]["adaptation"]["decision"] = "adjust"
        self.assert_rejected(plan, "pages[0].adaptation.actions")

    def test_required_false_needs_explicit_exemption(self):
        plan = self.plan()
        plan["pilot"]["required"] = False
        self.assert_rejected(plan, "pilot.required")
        plan.update(pilot_exemption_reason="用户明确要求放弃试制", pilot_exemption_source="本次用户原话：无需试制")
        self.assertTrue(check_adaptation_plan(plan)["ok"])
        self.assert_rejected(plan, "pilot.status", stage="final")

    def test_render_requirements(self):
        for value in ("relative.png", str(self.output / "missing.png")):
            plan = self.plan()
            self.approve(plan)
            plan["pilot"]["render_paths"] = [value]
            self.assert_rejected(plan, "pilot.render_paths[0]", stage="pilot")
        plan = self.plan()
        self.approve(plan)
        plan["pilot"]["note"] = " "
        self.assert_rejected(plan, "pilot.note", stage="final")
        if importlib.util.find_spec("PIL"):
            broken = self.output / "invalid.png"
            broken.write_bytes(b"not an image")
            plan["pilot"].update(note="声明已检查", render_paths=[str(broken)])
            self.assert_rejected(plan, "pilot.render_paths[0]", stage="final")

    def test_defaults_and_all_scenarios(self):
        for scenario in ("proposal", "defense", "group_meeting", "project_application"):
            self.assertEqual(initial_plan(scenario)["scenario"], scenario)
        plan = self.plan()
        del plan["mode"]
        del plan["authorization"]
        del plan["pilot"]["required"]
        self.assertTrue(check_adaptation_plan(plan)["ok"])

    def test_cli_init_exclusive_and_check(self):
        path = self.output / "initial.json"
        result = self.cli("init", "--scenario", "proposal", "--output", str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        original = path.read_bytes()
        result = self.cli("init", "--scenario", "proposal", "--output", str(path))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(path.read_bytes(), original)
        result = self.cli("check", str(path))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["stage"], "plan")
        plan = self.plan()
        self.approve(plan)
        final = self.output / "final.json"
        final.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        result = self.cli("check", str(final), "--stage", "final")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
