import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image
from pptx import Presentation
from pptx.util import Inches


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "review_deck.py"
spec = importlib.util.spec_from_file_location("review_deck", SCRIPT)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class ReviewDeckTests(unittest.TestCase):
    def setUp(self):
        # 保留工作区测试产物，不触发宿主安全回收或删除既有文件。
        self.folder = Path(tempfile.mkdtemp(prefix="review_test_", dir=ROOT))
        self.pptx = self.folder / "deck.pptx"
        self.checklist = self.folder / "review.json"
        deck = Presentation()
        deck.slide_width, deck.slide_height = Inches(16), Inches(9)
        for title in ("第一页", "第二页"):
            deck.slides.add_slide(deck.slide_layouts[0]).shapes.title.text = title
        deck.save(self.pptx)
        review.create_checklist(self.pptx, self.checklist)
        self.data = json.loads(self.checklist.read_text(encoding="utf-8"))

    def complete(self):
        self.data["target_software"] = {"name": "PowerPoint 桌面版", "open_verified": True}
        for slide in self.data["slides"]:
            image = self.folder / f"slide-{slide['slide_number']}.png"
            Image.new("RGB", (2560, 1440), "white").save(image)
            slide.update(render_path=str(image.resolve()), render_sha256=review.sha256(image),
                         actual_scale_checked=True)
            for entry in slide["checks"].values():
                entry.update(status="pass", note="人工检查记录示例，仅用于自动测试")

    def validate(self):
        self.checklist.write_text(json.dumps(self.data), encoding="utf-8")
        return review.check_checklist(self.pptx, self.checklist)

    def test_init_unchecked(self):
        self.assertEqual(self.data["render_requirements"]["minimum_height"], 1440)
        self.assertEqual(self.data["slides"][0]["title"], "第一页")
        self.assertEqual(self.data["slides"][0]["render_sha256"], "")
        self.assertEqual(self.data["slides"][0]["checks"]["readability"]["status"], "not_checked")
        self.assertEqual(self.validate()["status"], "incomplete")

    def test_complete_and_read_only(self):
        self.complete()
        before = self.pptx.read_bytes()
        self.assertEqual(self.validate()["status"], "complete")
        self.assertEqual(before, self.pptx.read_bytes())

    def test_missing_page(self):
        self.complete()
        self.data["slides"].pop()
        self.assertIn("缺少页面", str(self.validate()["errors"]))

    def test_duplicate_page(self):
        self.complete()
        self.data["slides"].append(self.data["slides"][0])
        self.assertIn("重复", str(self.validate()["errors"]))

    def test_not_checked_and_needs_fix(self):
        self.complete()
        for status in ("not_checked", "needs_fix", "invented"):
            with self.subTest(status=status):
                self.data["slides"][0]["checks"]["readability"]["status"] = status
                self.assertEqual(self.validate()["status"], "incomplete")

    def test_empty_note(self):
        self.complete()
        self.data["slides"][0]["checks"]["readability"]["note"] = "  "
        self.assertIn("非空note", str(self.validate()["errors"]))

    def test_stale_ppt_hash(self):
        self.complete()
        deck = Presentation(self.pptx)
        deck.slides[0].shapes.title.text = "修改后的标题"
        deck.save(self.pptx)
        self.assertIn("清单可能已过期", str(self.validate()["errors"]))

    def test_low_resolution(self):
        self.complete()
        slide = self.data["slides"][0]
        Image.new("RGB", (1280, 720)).save(slide["render_path"])
        slide["render_sha256"] = review.sha256(slide["render_path"])
        self.assertIn("分辨率不足", str(self.validate()["errors"]))

    def test_bad_aspect_ratio(self):
        self.complete()
        slide = self.data["slides"][0]
        Image.new("RGB", (2560, 1700)).save(slide["render_path"])
        slide["render_sha256"] = review.sha256(slide["render_path"])
        self.assertIn("宽高比", str(self.validate()["errors"]))

    def test_render_hash_mismatch(self):
        self.complete()
        self.data["slides"][0]["render_sha256"] = "0" * 64
        self.assertIn("截图SHA256", str(self.validate()["errors"]))

    def test_missing_image(self):
        self.complete()
        self.data["slides"][0]["render_path"] = str(self.folder / "missing.png")
        self.assertIn("截图文件不存在", str(self.validate()["errors"]))

    def test_actual_scale_and_software(self):
        self.complete()
        self.data["target_software"]["open_verified"] = False
        self.data["slides"][0]["actual_scale_checked"] = False
        errors = str(self.validate()["errors"])
        self.assertIn("目标软件", errors)
        self.assertIn("实际比例", errors)

    def test_output_protection(self):
        for path in (self.pptx, self.checklist):
            before = path.read_bytes()
            with self.assertRaises((ValueError, FileExistsError)):
                review.create_checklist(self.pptx, path)
            self.assertEqual(path.read_bytes(), before)

    def test_cli_exit_codes(self):
        def run(*arguments):
            result = subprocess.run([sys.executable, str(SCRIPT), *map(str, arguments)],
                                    capture_output=True, encoding="utf-8")
            json.loads(result.stdout)
            return result.returncode
        self.assertEqual(run(), 2)
        self.assertEqual(run("check", self.pptx, "--checklist", self.checklist), 1)
        self.complete()
        self.validate()
        self.assertEqual(run("check", self.pptx, "--checklist", self.checklist), 0)
        self.assertEqual(run("init", self.pptx, "--output", self.pptx), 2)
        self.assertEqual(run("init", self.pptx, "--output", self.folder / "new.json"), 0)


if __name__ == "__main__":
    unittest.main()
