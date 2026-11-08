"""工作区隔离测试：原始回归及新增几何审计。"""
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from PIL import Image
from pptx import Presentation
from pptx.util import Inches

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'audit_deck.py'
BASE = ROOT / 'tests' / 'test_audit_legacy.py'
OUTPUTS = ROOT.parent / 'test_outputs'


def legacy():
    spec = importlib.util.spec_from_file_location('legacy_audit_tests', BASE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()


def main():
    legacy()
    count = 0
    OUTPUTS.mkdir(exist_ok=True)
    with nullcontext(tempfile.mkdtemp(prefix='geometry-tests-', dir=OUTPUTS)) as directory:
        root = Path(directory)
        image = root / 'image.png'
        Image.new('RGB', (800, 400), 'navy').save(image)
        output = root / 'fixture.pptx'

        def deck():
            ppt = Presentation()
            return ppt, ppt.slides.add_slide(ppt.slide_layouts[6])

        def run(ppt, expected=0, *args):
            nonlocal count
            ppt.save(output)
            result = subprocess.run([sys.executable, str(SCRIPT), str(output), *args], capture_output=True, encoding='utf-8')
            assert result.returncode == expected, (result.stdout, result.stderr)
            count += 1
            return json.loads(result.stdout)

        def issues(data, code):
            return [i for i in data['issues'] if i['code'] == code]

        for width, expected, severity in [(2, 0, None), (2.5, 1, 'error'), (2.2, 0, 'warning')]:
            ppt, slide = deck()
            slide.shapes.add_picture(str(image), 0, 0, Inches(width), Inches(1))
            data = run(ppt, expected)
            found = issues(data, 'image_aspect_distortion')
            assert bool(found) == bool(severity)
            assert data['counts']['images_detectable'] == 1
            if severity:
                assert found[0]['severity'] == severity
                assert abs(found[0]['deviation'] - (width / 2 - 1)) < 1e-6
                assert found[0]['source_ratio'] == 2
                assert found[0]['display_ratio'] == width
        data = run(ppt, 0, '--image-aspect-warning', '0.15')
        assert not issues(data, 'image_aspect_distortion')
        run(ppt, 2, '--image-aspect-warning', '0.3')
        run(ppt, 2, '--text-overlap-ratio', 'nan')

        ppt, slide = deck()
        picture = slide.shapes.add_picture(str(image), 0, 0, Inches(1), Inches(1))
        picture.crop_left = picture.crop_right = .25
        data = run(ppt)
        assert not issues(data, 'image_aspect_distortion')
        picture.rotation = 30
        data = run(ppt)
        assert data['counts']['images_skipped'] == 1
        assert issues(data, 'image_aspect_skipped')
        picture.rotation = 0
        picture.crop_left = -.1
        data = run(ppt)
        assert data['counts']['images_skipped'] == 1

        ppt, slide = deck()
        group = slide.shapes.add_group_shape()
        group.shapes.add_picture(str(image), 0, 0, Inches(2), Inches(1))
        group.width = Inches(2.5)
        data = run(ppt, 1)
        assert abs(issues(data, 'image_aspect_distortion')[0]['deviation'] - .25) < 1e-8
        group.rotation = 30
        data = run(ppt)
        assert data['counts']['images_skipped'] == 1
        assert not issues(data, 'image_aspect_distortion')
        group.rotation = 0
        group._element.grpSpPr.xfrm.chExt.cx = 0
        data = run(ppt)
        assert data['counts']['images_skipped'] == 1

        # 相交、包含、相切、不相交；每页只有两框，计数无歧义。
        for x, y, w, h, collision in [(1, .5, 2, 1, True), (.5, .25, .5, .5, True), (2, 0, 1, 1, False), (3, 0, 1, 1, False)]:
            ppt, slide = deck()
            slide.shapes.add_textbox(0, 0, Inches(2), Inches(1)).text = '第一框\n更多内容'
            second = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
            second.text = '第二框'
            data = run(ppt)
            found = issues(data, 'text_bbox_overlap_candidate')
            assert bool(found) == collision
            assert data['counts']['text_pairs_checked'] == 1
            if collision:
                assert found[0]['intersection_area_pt2'] > 1
                assert found[0]['shapes'][0]['text'] == '第一框'
                assert 'box_pt' in found[0]['shapes'][1]
                assert 'page_title' in found[0]
            second.rotation = 20
            data = run(ppt)
            assert data['counts']['text_pairs_skipped'] == 1
            assert not issues(data, 'text_bbox_overlap_candidate')

        ppt, slide = deck()
        group = slide.shapes.add_group_shape()
        group.shapes.add_textbox(0, 0, Inches(1), Inches(1)).text = '组合文字'
        group.left = Inches(1)
        group.width = Inches(2)
        slide.shapes.add_textbox(Inches(2), 0, Inches(1), Inches(1)).text = '外部文字'
        data = run(ppt)
        found = issues(data, 'text_bbox_overlap_candidate')
        assert len(found) == 1 and found[0]['smaller_box_ratio'] == 1
        assert found[0]['shapes'][0]['box_pt'] == [72, 0, 144, 72]
        data = run(ppt, 0, '--text-overlap-area-pt2', '10000')
        assert not issues(data, 'text_bbox_overlap_candidate')
        data = run(ppt, 0, '--text-overlap-ratio', '1')
        assert not issues(data, 'text_bbox_overlap_candidate')
        group.rotation = 15
        data = run(ppt)
        assert data['counts']['text_pairs_skipped'] == 1
    print(f'PASS: {count} 新增CLI检查；生成物保留于 {root}')


if __name__ == '__main__':
    main()
