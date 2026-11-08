"""仅在临时目录创建合成演示文稿，测试只读审计CLI。"""
from contextlib import nullcontext
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from pptx import Presentation
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'audit_deck.py'
OUTPUTS = ROOT.parent / 'test_outputs'


def main():
    count = 0
    OUTPUTS.mkdir(exist_ok=True)
    with nullcontext(tempfile.mkdtemp(prefix='ppt-audit-test-', dir=OUTPUTS)) as folder:
        root = Path(folder)
        source, output, baseline = (root / n for n in ('source.pptx', 'output.pptx', 'baseline.json'))
        deck = Presentation()
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        deck.save(source)
        deck.save(output)

        def run(expected, *args, code=None):
            nonlocal count
            result = subprocess.run([sys.executable, str(SCRIPT), str(output), '--image-aspect-warning', '2', '--image-aspect-error', '2', *map(str, args)], capture_output=True, encoding='utf-8')
            assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
            data = json.loads(result.stdout)
            assert data['exit_code'] == expected
            if code:
                assert any(i['code'] == code for i in data['issues']), data
            count += 1
            return data

        run(0, '--source', source, '--write-baseline', baseline)
        run(0, '--source', source, '--baseline', baseline)
        standalone_baseline = root / 'standalone.json'
        run(0, '--write-baseline', standalone_baseline)
        conflict = root / 'conflict.json'
        run(2, '--write-baseline', conflict, '--report', conflict, code='execution_error')
        assert not conflict.exists()
        run(2, '--source', source, '--write-baseline', baseline, code='execution_error')
        original = source.read_bytes()
        deck.core_properties.title = 'changed'
        deck.save(source)
        run(1, '--source', source, '--baseline', baseline, code='source_hash_changed')
        source.write_bytes(original)
        deck.slides.add_slide(deck.slide_layouts[6])
        deck.save(output)
        run(1, '--source', source, '--baseline', baseline, code='stat_mismatch')
        run(0, '--source', source, '--baseline', baseline, '--expected-pages', 2)
        table = slide.shapes.add_table(1, 1, Inches(1), Inches(1), Inches(2), Inches(1)).table
        table.cell(0, 0).text = '禁止残留词'
        deck.save(output)
        run(1, '--forbidden', '禁止残留词', code='forbidden_text')
        timing = OxmlElement('p:timing')
        target = OxmlElement('p:spTgt')
        target.set('spid', '99999')
        timing.append(target)
        slide._element.append(timing)
        deck.save(output)
        run(1, code='dangling_animation_target')
        slide._element.remove(timing)
        slide.shapes.add_textbox(-Inches(1), Inches(1), Inches(2), Inches(1)).text = '出界'
        deck.save(output)
        data = run(0, code='out_of_bounds_candidate')
        assert data['status'] == 'warnings'
        report = root / 'report.json'
        run(0, '--report', report)
        assert json.loads(report.read_text(encoding='utf-8'))['status'] == 'warnings'
        for protected, flags in [(output, []), (source, ['--source', source]), (baseline, ['--source', source, '--baseline', baseline])]:
            before = protected.read_bytes()
            run(2, *flags, '--report', protected, code='execution_error')
            assert protected.read_bytes() == before
        group = slide.shapes.add_group_shape()
        group.shapes.add_textbox(0, 0, Inches(1), Inches(1)).text = 'group'
        group._element.grpSpPr.xfrm.chExt.cx = 0
        deck.save(output)
        run(0, code='group_geometry_skipped')
        group._element.grpSpPr.xfrm.chExt.cx = Inches(1)
        group.rotation = 30
        deck.save(output)
        run(0, code='group_geometry_skipped')
        group.rotation = 0
        group._element.grpSpPr.xfrm.remove(group._element.grpSpPr.xfrm.chExt)
        deck.save(output)
        run(0, code='group_geometry_skipped')
        master_shape = deck.slide_masters[0].shapes[0]
        master_shape.text = '母版禁词'
        deck.slide_layouts[0].shapes[0].text = '版式禁词'
        textbox = slide.shapes.add_textbox(0, 0, Inches(1), Inches(1))
        textbox.text = 'small'
        textbox.text_frame.paragraphs[0].runs[0].font.size = Pt(6)
        image_path = root / 'white.png'
        Image.new('RGB', (40, 40), 'white').save(image_path)
        picture = slide.shapes.add_picture(str(image_path), 0, 0, Inches(1), Inches(1))
        picture.crop_left = .25
        picture.crop_right = .25
        deck.save(output)
        run(1, '--forbidden', '母版禁词', code='forbidden_text')
        run(1, '--forbidden', '版式禁词', code='forbidden_text')
        run(0, code='explicit_small_font')
        data = run(0, code='low_image_dpi')
        assert any(i['code'] == 'low_image_dpi' and i['dpi'] == 20 for i in data['issues'])
        run(0, code='high_white_pixel_ratio')
        picture.image._blob = b'unreadable'
        picture.part.related_part(picture._element.blip_rId)._blob = b'unreadable'
        deck.save(output)
        run(0, code='image_decode_failed')
        slide.shapes.add_textbox(0, 0, 100, 100).text = 'collapsed'
        deck.save(output)
        run(1, code='collapsed_text')
        output.write_bytes(b'not zip')
        run(1, code='invalid_zip')
        output = root / 'previously_missing.pptx'
        run(2, code='execution_error')
        deck.save(output)
        with zipfile.ZipFile(output, 'a') as archive:
            archive.writestr('ppt/_rels/broken.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="missing.xml" Type="test"/></Relationships>')
        run(1, code='missing_relationship_target')
    print(f'PASS: {count} 原回归CLI检查；生成物保留于 {root}')


if __name__ == '__main__':
    main()
