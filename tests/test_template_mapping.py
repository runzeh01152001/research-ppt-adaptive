"""模板映射关卡回归；测试素材保留于工作区 test_outputs，不自动删除。"""
import copy
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from template_mapping import check_template_mapping, initial_plan


class TemplateMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = SCRIPTS.parents[1] / "test_outputs"
        root.mkdir(exist_ok=True)
        cls.output = root / ("template_mapping_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        cls.output.mkdir()
        cls.source = cls.output / "reference.txt"
        cls.source.write_text("测试来源文件，仅检验路径存在性", encoding="utf-8")

    def plan(self):
        plan = initial_plan()
        plan["template_pages"][0].update(title="问题", function="problem", layout_signature="左文右图", notes="人工登记功能")
        plan["content_pages"][0].update(title="研究问题", content_function="problem", claim="待检验的问题")
        plan["mappings"][0].update(decision="reuse", reason="功能一致", reference_function="problem", content_function="problem",
                                    semantic_fit="fit", visual_fidelity="preserved", layout_fidelity="preserved",
                                    readability="pass", change_summary="替换研究内容", review_note="人工核对标题与图注")
        return plan

    def rejected(self, plan, path=None, stage="plan"):
        result = check_template_mapping(plan, stage)
        self.assertFalse(result["ok"], result)
        if path:
            self.assertTrue(any(e["path"] == path for e in result["errors"]), result)
        return result

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "template_mapping.py"), *args], capture_output=True, text=True, encoding="utf-8")

    def test_valid_plan(self):
        result = check_template_mapping(self.plan())
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["coverage"]["mapped_content_pages"], 1)
        self.assertTrue(result["limitations"])

    def test_initial_requires_filling(self):
        self.rejected(initial_plan())

    def test_duplicate_template_registration(self):
        plan = self.plan()
        plan["template_pages"].append(copy.deepcopy(plan["template_pages"][0]))
        self.rejected(plan, "template_pages[1].template_page")

    def test_duplicate_content_registration(self):
        plan = self.plan()
        plan["content_pages"].append(copy.deepcopy(plan["content_pages"][0]))
        self.rejected(plan, "content_pages[1].output_page")

    def test_duplicate_mapping(self):
        plan = self.plan()
        plan["mappings"].append(copy.deepcopy(plan["mappings"][0]))
        self.rejected(plan, "mappings[1].output_page")

    def test_missing_output_mapping(self):
        plan = self.plan()
        plan["content_pages"].append(dict(plan["content_pages"][0], output_page=2))
        self.rejected(plan, "mappings")

    def test_missing_template_usage_reason(self):
        plan = self.plan()
        plan["template_pages"].append(dict(plan["template_pages"][0], template_page=2))
        self.rejected(plan, "unused_template_pages")

    def test_valid_unused_template(self):
        plan = self.plan()
        plan["template_pages"].append(dict(plan["template_pages"][0], template_page=2))
        plan["unused_template_pages"] = [{"template_page": 2, "reason": "不适合本次内容"}]
        self.assertTrue(check_template_mapping(plan)["ok"])

    def test_used_template_cannot_be_unused(self):
        plan = self.plan()
        plan["unused_template_pages"] = [{"template_page": 1, "reason": "声明冲突"}]
        self.rejected(plan, "unused_template_pages[0].template_page")

    def test_unused_requires_reason(self):
        plan = self.plan()
        plan["unused_template_pages"] = [{"template_page": 2, "reason": " "}]
        self.rejected(plan, "unused_template_pages[0].reason")

    def test_unknown_template_reference(self):
        plan = self.plan()
        plan["mappings"][0]["template_page"] = 99
        self.rejected(plan, "mappings[0].template_page")

    def test_unknown_output_reference(self):
        plan = self.plan()
        plan["mappings"][0]["output_page"] = 99
        self.rejected(plan, "mappings[0].output_page")

    def test_reuse_different_function(self):
        plan = self.plan()
        plan["content_pages"][0]["content_function"] = "process"
        plan["mappings"][0]["content_function"] = "process"
        self.rejected(plan, "mappings[0].decision")

    def test_reuse_semantic_mismatch(self):
        plan = self.plan()
        plan["mappings"][0]["semantic_fit"] = "mismatch"
        self.rejected(plan, "mappings[0].semantic_fit")

    def test_reuse_semantic_partial(self):
        plan = self.plan()
        plan["mappings"][0]["semantic_fit"] = "partial"
        self.rejected(plan, "mappings[0].semantic_fit")

    def test_declared_reference_function_must_match_registry(self):
        plan = self.plan()
        plan["mappings"][0].update(reference_function="cover", decision="adjust")
        self.rejected(plan, "mappings[0].reference_function")

    def test_declared_content_function_must_match_registry(self):
        plan = self.plan()
        plan["mappings"][0].update(content_function="cover", decision="adjust")
        self.rejected(plan, "mappings[0].content_function")

    def split_plan(self):
        plan = self.plan()
        plan["content_pages"].append(dict(plan["content_pages"][0], output_page=2))
        plan["mappings"][0]["decision"] = "split"
        plan["mappings"].append(dict(plan["mappings"][0], output_page=2))
        return plan

    def test_split_valid(self):
        self.assertTrue(check_template_mapping(self.split_plan())["ok"])

    def test_multi_output_requires_all_split(self):
        plan = self.split_plan()
        plan["mappings"][1]["decision"] = "adjust"
        self.rejected(plan, "mappings[1].decision")

    def unmatched_plan(self):
        plan = self.plan()
        plan["mappings"][0].update(template_page=None, decision="unmatched", reference_function="other", reason="新增无对应模板的问题页")
        plan["unused_template_pages"] = [{"template_page": 1, "reason": "不沿用此模板页"}]
        return plan

    def test_unmatched_valid(self):
        self.assertTrue(check_template_mapping(self.unmatched_plan())["ok"])

    def test_unmatched_requires_reason(self):
        plan = self.unmatched_plan()
        plan["mappings"][0]["reason"] = ""
        self.rejected(plan, "mappings[0].reason")

    def test_unmatched_cannot_reference_template(self):
        plan = self.unmatched_plan()
        plan["mappings"][0]["template_page"] = 1
        self.rejected(plan, "mappings[0].template_page")

    def test_null_template_requires_unmatched(self):
        plan = self.plan()
        plan["mappings"][0]["template_page"] = None
        self.rejected(plan, "mappings[0].template_page")

    def test_invalid_types_do_not_crash(self):
        for value in (None, [], True, "错误"):
            with self.subTest(value=value):
                self.rejected(value)
        for key in ("template_pages", "content_pages", "mappings", "unused_template_pages", "comparison"):
            plan = self.plan()
            plan[key] = False
            with self.subTest(key=key):
                self.rejected(plan, key)

    def test_invalid_rows(self):
        for key in ("template_pages", "content_pages", "mappings", "unused_template_pages"):
            plan = self.plan()
            plan[key] = [None]
            with self.subTest(key=key):
                self.rejected(plan, key + "[0]")

    def test_bool_is_not_page_number(self):
        plan = self.plan()
        plan["template_pages"][0]["template_page"] = True
        self.rejected(plan, "template_pages[0].template_page")

    def test_unhashable_enum_is_rejected(self):
        for key in ("decision", "reference_function", "semantic_fit", "readability", "visual_fidelity", "layout_fidelity"):
            plan = self.plan()
            plan["mappings"][0][key] = []
            with self.subTest(key=key):
                self.rejected(plan, "mappings[0]." + key)

    def test_required_text(self):
        for key in ("reason", "review_note", "change_summary"):
            plan = self.plan()
            plan["mappings"][0][key] = " "
            with self.subTest(key=key):
                self.rejected(plan, "mappings[0]." + key)

    def test_final_requires_review(self):
        self.rejected(self.plan(), "comparison.visual_review_status", "final")

    def final_plan(self):
        plan = self.plan()
        plan["comparison"].update(template_source=str(self.source), output_source=str(self.source),
                                  visual_review_status="reviewed", notes="人工已核对映射与视觉关系")
        return plan

    def test_final_valid(self):
        result = check_template_mapping(self.final_plan(), "final")
        self.assertTrue(result["ok"], result)

    def test_final_requires_review_notes(self):
        plan = self.final_plan()
        plan["comparison"]["notes"] = " "
        self.rejected(plan, "comparison.notes", "final")

    def test_final_sources_absolute_exist_files(self):
        for value in ("relative.txt", str(self.output / "missing.txt"), str(self.output), ""):
            plan = self.final_plan()
            plan["comparison"]["template_source"] = value
            with self.subTest(value=value):
                self.rejected(plan, "comparison.template_source", "final")

    def test_invalid_stage(self):
        self.rejected(self.plan(), "stage", "pilot")

    def test_cli_init_exclusive(self):
        target = self.output / "initialized.json"
        first = self.cli("init", "--output", str(target))
        self.assertEqual(first.returncode, 0, first.stderr)
        original = target.read_bytes()
        second = self.cli("init", "--output", str(target))
        self.assertEqual(second.returncode, 2)
        self.assertEqual(target.read_bytes(), original)
        self.assertFalse(json.loads(second.stdout)["ok"])

    def test_cli_check_default_and_final(self):
        target = self.output / "valid.json"
        target.write_text(json.dumps(self.plan(), ensure_ascii=False), encoding="utf-8-sig")
        result = self.cli("check", str(target))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["stage"], "plan")
        self.assertEqual(self.cli("check", str(target), "--stage", "final").returncode, 1)

    def test_cli_bad_json(self):
        target = self.output / "malformed.json"
        target.write_text("{", encoding="utf-8")
        result = self.cli("check", str(target))
        self.assertEqual(result.returncode, 2)
        self.assertIn("execution_error", json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
