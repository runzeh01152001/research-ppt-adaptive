"""测试产物全部保留在工作区 test_outputs，不使用或清理临时目录。"""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research_plan.py"
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("research_plan", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResearchPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert ROOT.is_dir()
        output_root = ROOT / "test_outputs"
        output_root.mkdir(exist_ok=True)
        cls.output = output_root / ("research_plan_" + uuid.uuid4().hex)
        cls.output.mkdir()
        cls.source = cls.output / "source.txt"
        cls.source.write_text("测试来源占位，不代表已核实科研事实。", encoding="utf-8")

    def plan(self):
        plan = MODULE.initial_plan("proposal")
        plan["pages"][0].update(title="概念说明", claim="拟研究一个机制", conclusion="尚待验证",
                                review_note="人工确认仅为研究计划", no_evidence_reason="概念性研究问题，无实验图")
        return plan

    def asset(self, **updates):
        result = {"id": "a1", "source_type": "own_result", "source_file": str(self.source),
                  "locator": {"slide": 2, "detail": "测试图 A"}, "caption": "测试素材",
                  "citation": "", "verification_status": "verified", "verification_note": "已人工检查来源声明",
                  "derived_from_sources": []}
        result.update(updates)
        return result

    def with_asset(self, **updates):
        plan = self.plan()
        plan["assets"] = [self.asset(**updates)]
        plan["pages"][0]["evidence_ids"] = ["a1"]
        return plan

    def assert_invalid(self, plan, phrase):
        report = MODULE.check_plan(plan)
        self.assertFalse(report["ok"], report)
        self.assertIn(phrase, json.dumps(report, ensure_ascii=False))

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)],
                              capture_output=True, encoding="utf-8", env=self.cli_env())

    @staticmethod
    def cli_env():
        import os
        return dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")

    def save(self, plan):
        path = self.output / (uuid.uuid4().hex + ".json")
        path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        return path

    def test_init_all_four_scenarios(self):
        for scenario in MODULE.SCENARIOS:
            with self.subTest(scenario=scenario):
                path = self.output / (scenario + ".json")
                result = self.cli("init", "--scenario", scenario, "--output", path)
                self.assertEqual(result.returncode, 0, result.stderr)
                plan = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(plan["scenario"], scenario)
                self.assert_invalid(plan, "claim")

    def test_init_exclusive_no_overwrite(self):
        path = self.save({"preserve": True})
        before = path.read_bytes()
        result = self.cli("init", "--scenario", "proposal", "--output", path)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(path.read_bytes(), before)

    def test_cli_exit_codes_and_json(self):
        for plan, code in ((self.plan(), 0), (MODULE.initial_plan("defense"), 1)):
            result = self.cli("check", self.save(plan))
            self.assertEqual(result.returncode, code, result.stderr)
            self.assertEqual(json.loads(result.stdout)["ok"], code == 0)
        invalid = self.output / "invalid.json"
        invalid.write_text("{", encoding="utf-8")
        for path in (invalid, self.output / "absent.json"):
            result = self.cli("check", path)
            self.assertEqual(result.returncode, 2)
            self.assertIn("execution_error", json.loads(result.stdout))

    def test_concept_page_allowed_with_reason(self):
        self.assertTrue(MODULE.check_plan(self.plan())["ok"])
        plan = self.plan()
        plan["pages"][0]["no_evidence_reason"] = ""
        self.assert_invalid(plan, "无证据理由")

    def test_unknown_evidence(self):
        plan = self.plan()
        plan["pages"][0]["evidence_ids"] = ["unknown"]
        self.assert_invalid(plan, "未知素材")

    def test_duplicate_and_noncontinuous_pages(self):
        plan = self.plan()
        plan["pages"].append(copy.deepcopy(plan["pages"][0]))
        self.assert_invalid(plan, "连续编号")
        plan["pages"][1]["page"] = 3
        self.assert_invalid(plan, "连续编号")

    def test_duplicate_asset_ids(self):
        plan = self.with_asset()
        plan["assets"].append(self.asset())
        self.assert_invalid(plan, "素材 ID 重复")

    def test_literature_requires_citation(self):
        plan = self.with_asset(source_type="literature")
        self.assert_invalid(plan, "文献素材必须填写引文")
        plan["assets"][0]["citation"] = "作者，标题，年份，DOI 待人工确认"
        self.assertTrue(MODULE.check_plan(plan)["ok"])

    def test_generated_requires_schematic_label(self):
        plan = self.with_asset(source_type="generated_schematic")
        self.assert_invalid(plan, "明确标注")
        plan["assets"][0]["label"] = "AI 生成示意图，非实验结果"
        self.assertTrue(MODULE.check_plan(plan)["ok"])

    def test_verified_requires_note(self):
        self.assert_invalid(self.with_asset(verification_note=""), "人工验证说明")

    def test_used_assets_must_be_verified_on_any_page(self):
        plan = self.with_asset(verification_status="unverified", verification_note="")
        self.assert_invalid(plan, "实际使用")
        plan["pages"][0]["role"] = "cover"
        self.assert_invalid(plan, "实际使用")
        plan["pages"][0]["evidence_ids"] = []
        self.assertTrue(MODULE.check_plan(plan)["ok"])

    def test_completed_schematic_only_rejected(self):
        for source_type in MODULE.SCHEMATICS:
            plan = self.with_asset(source_type=source_type, label="示意图")
            plan["pages"][0]["statement_status"] = "completed"
            self.assert_invalid(plan, "已完成结果不能仅引用")
        plan = self.with_asset()
        plan["pages"][0]["statement_status"] = "completed"
        self.assertTrue(MODULE.check_plan(plan)["ok"])

    def test_mixed_warns(self):
        plan = self.plan()
        plan["pages"][0]["statement_status"] = "mixed"
        report = MODULE.check_plan(plan)
        self.assertTrue(report["ok"])
        self.assertEqual(len(report["warnings"]), 1)

    def test_direct_forbidden_source_normalized(self):
        plan = self.with_asset(locator={"slide": 99, "detail": "源文件第99页"})
        plan["forbidden_sources"] = [{"source_file": str(self.output / ".." / self.output.name / "source.txt"),
                                       "slide_start": 1, "slide_end": 10}]
        self.assert_invalid(plan, "目标页区间的禁用来源")
        plan["assets"][0]["locator"]["slide"] = None
        self.assert_invalid(plan, "目标页区间的禁用来源")
        plan["assets"][0]["locator"]["slide"] = 1
        plan["pages"] = [{"page": i, "title": "概念页", "role": "divider"} for i in range(1, 11)] + [
            dict(plan["pages"][0], page=11)]
        self.assertTrue(MODULE.check_plan(plan)["ok"])

    def test_derived_forbidden_source(self):
        plan = self.with_asset(locator={"slide": 5, "detail": "拼接输出"},
                               derived_from_sources=[{"source_file": str(self.source),
                                                      "locator": {"slide": 2, "detail": "裁剪祖先"}}])
        plan["forbidden_sources"] = [{"source_file": str(self.source), "slide_start": 1, "slide_end": 10}]
        self.assert_invalid(plan, "裁剪/拼接祖先")
        plan["pages"][0]["evidence_ids"] = []
        self.assertTrue(MODULE.check_plan(plan)["ok"])

    def test_source_absolute_and_existing(self):
        self.assert_invalid(self.with_asset(source_file="relative.txt"), "绝对文件路径")
        self.assert_invalid(self.with_asset(source_file=str(self.output / "absent.txt")), "不存在")

    def test_template_read_only_metadata(self):
        plan = self.plan()
        plan["template"] = {"source_file": str(self.source), "read_only": True,
                            "template_slide": 2, "slots": {"title": "形状名称"}}
        self.assertTrue(MODULE.check_plan(plan)["ok"])
        plan["template"]["read_only"] = False
        self.assert_invalid(plan, "只读")

    def test_malformed_json_values_are_validation_errors(self):
        for plan in (None, [], {}, {"schema_version": True, "scenario": [], "pages": [None],
                                   "assets": [None], "forbidden_sources": [None]}):
            self.assertFalse(MODULE.check_plan(plan)["ok"])
        for key in ("source_type", "id", "locator", "verification_status", "derived_from_sources"):
            with self.subTest(key=key):
                plan = self.with_asset(**{key: {}})
                self.assertFalse(MODULE.check_plan(plan)["ok"])


if __name__ == "__main__":
    unittest.main()
