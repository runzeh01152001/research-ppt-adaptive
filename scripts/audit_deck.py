"""Read-only structural PPTX audit; warnings are not visual approval."""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import posixpath
import sys
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import zipfile

from pptx import Presentation

NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
LIMITATIONS = ["不验证图片或内容来源", "仅检测非空文本框bbox相交候选，不检测真实字形重叠", "不执行渲染或视觉验收",
               "越界仅为无旋转几何候选；不推断有意出血", "仅检查显式字号，不推导继承字号",
               "白像素比例不是留白结论；结构审计通过不代表视觉通过",
               "不执行图片文字OCR，不覆盖全部图表或SmartArt文字",
               "母版及版式数量一致不代表其内容保真", "未在PowerPoint或WPS等目标软件中验证"]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stats(deck):
    return dict(pages=len(deck.slides), masters=len(deck.slide_masters),
                layouts=sum(len(m.slide_layouts) for m in deck.slide_masters),
                width=int(deck.slide_width), height=int(deck.slide_height))


def issue(report, severity, code, **details):
    report["issues"].append(dict(severity=severity, code=code, **details))


def walk(shapes, report, page, sx=1, sy=1, tx=0, ty=0, valid=True):
    for shape in shapes:
        context = dict(page=page, shape_id=shape.shape_id)
        if shape.shape_type == 6:
            x = shape._element.grpSpPr.xfrm
            reason = None
            if x is None or any(getattr(x, k) is None for k in ("off", "ext", "chOff", "chExt")):
                reason = "组合变换缺失"
            elif x.chExt.cx <= 0 or x.chExt.cy <= 0 or x.ext.cx <= 0 or x.ext.cy <= 0:
                reason = "组合ext或chExt为零或负数"
            elif float(x.get("rot", "0")) != 0 or any(x.get(k) in ("1", "true") for k in ("flipH", "flipV")):
                reason = "组合旋转或翻转"
            if reason or not valid:
                if reason:
                    issue(report, "skip", "group_geometry_skipped", reason=reason, **context)
                yield from walk(shape.shapes, report, page, valid=False)
            else:
                nsx, nsy = sx * x.ext.cx / x.chExt.cx, sy * x.ext.cy / x.chExt.cy
                yield from walk(shape.shapes, report, page, nsx, nsy,
                                tx + sx * x.off.x - nsx * x.chOff.x,
                                ty + sy * x.off.y - nsy * x.chOff.y)
        else:
            box = None
            if valid and all(v is not None for v in (shape.left, shape.top, shape.width, shape.height)):
                box = (tx + sx * shape.left, ty + sy * shape.top, sx * shape.width, sy * shape.height)
            elif valid:
                issue(report, "skip", "shape_geometry_skipped", **context)
            yield shape, box


def package_checks(path, report, args):
    try:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                issue(report, "error", "zip_crc_failed", part=bad)
                return False
            names = set(archive.namelist())
            for name in sorted(names):
                if not name.endswith((".xml", ".rels")):
                    continue
                try:
                    root = ET.fromstring(archive.read(name))
                except ET.ParseError as exc:
                    issue(report, "error", "invalid_xml", part=name, message=str(exc))
                    continue
                if name.endswith(".rels"):
                    base = posixpath.dirname(posixpath.dirname(name))
                    for rel in root:
                        if rel.get("TargetMode") == "External":
                            continue
                        target = unquote(rel.get("Target", "").split("#", 1)[0])
                        resolved = posixpath.normpath(posixpath.join(base, target)).lstrip("/")
                        if not target or resolved not in names:
                            issue(report, "error", "missing_relationship_target", part=name,
                                  relationship=rel.get("Id"), target=target)
                if name.startswith(("ppt/slides/slide", "ppt/slideMasters/slideMaster", "ppt/slideLayouts/slideLayout")) and name.endswith(".xml"):
                    # Paragraph concatenation catches words split across runs, including table cells.
                    text = "\n".join("".join(t.text or "" for t in p.findall(".//a:t", NS))
                                     for p in root.findall(".//a:p", NS))
                    for term in args.forbidden:
                        if term and term in text:
                            issue(report, "error", "forbidden_text", part=name, term=term, count=text.count(term))
                    for props in root.iter():
                        if props.tag in {"{%s}%s" % (NS["a"], k) for k in ("rPr", "defRPr", "endParaRPr")} and props.get("sz"):
                            size = float(props.get("sz")) / 100
                            if size < args.min_font_pt:
                                issue(report, "warning", "explicit_small_font", part=name, size_pt=size)
                if name.startswith("ppt/slides/slide") and name.endswith(".xml"):
                    ids = {e.get("id") for e in root.findall(".//p:cNvPr", NS)}
                    for target in root.findall(".//p:timing//p:spTgt", NS):
                        if target.get("spid") not in ids:
                            issue(report, "error", "dangling_animation_target", part=name, shape_id=target.get("spid"))
        return True
    except zipfile.BadZipFile as exc:
        issue(report, "error", "invalid_zip", message=str(exc))
        return False


def geometry_reason(shape, box, text=False):
    if box is None or box[2] <= 0 or box[3] <= 0:
        return "几何缺失或组合变换不支持"
    xfrm = shape._element.find("./p:spPr/a:xfrm", NS)
    if shape.rotation or (xfrm is not None and any(xfrm.get(k) in ("1", "true") for k in ("flipH", "flipV"))):
        return "对象旋转或翻转"
    if text:
        props = shape.text_frame._txBody.bodyPr
        if float(props.get("rot", "0")) != 0 or props.get("vert", "horz") != "horz":
            return "文字旋转或竖排"
    return None


def image_checks(shape, box, report, args, context):
    counts = report["counts"]
    counts["images_total"] += 1
    checked = False
    reason = geometry_reason(shape, box)
    try:
        from PIL import Image
        with Image.open(io.BytesIO(shape.image.blob)) as image:
            iw, ih = image.size
            left, right, top, bottom = shape.crop_left, shape.crop_right, shape.crop_top, shape.crop_bottom
            visible_w, visible_h = iw * (1 - left - right), ih * (1 - top - bottom)
            if visible_w <= 0 or visible_h <= 0:
                reason = "图片裁剪后尺寸无效"
                issue(report, "warning", "invalid_image_crop", **context)
                return
            blip_fill = shape._element.find("./p:blipFill", NS)
            if blip_fill is None or blip_fill.find("a:tile", NS) is not None:
                reason = "图片填充变换不支持"
            elif blip_fill.find("a:stretch/a:fillRect", NS) is None or any(
                    float(v) != 0 for v in blip_fill.find("a:stretch/a:fillRect", NS).attrib.values()):
                reason = "图片填充矩形变换不支持"
            if min(left, right, top, bottom) < 0:
                reason = "不支持负裁剪区域"
            if reason is None:
                source_ratio = visible_w / visible_h
                display_ratio = box[2] / box[3]
                deviation = abs(display_ratio / source_ratio - 1)
                checked = True
                counts["images_detectable"] += 1
                if deviation > getattr(args, "image_aspect_warning", 0.05):
                    severity = "error" if deviation > getattr(args, "image_aspect_error", 0.20) else "warning"
                    issue(report, severity, "image_aspect_distortion", deviation=deviation,
                          deviation_percent=deviation * 100, source_ratio=source_ratio,
                          display_ratio=display_ratio, box_emu=list(box), **context)
            if box and box[2] > 0 and box[3] > 0:
                dpi = min(visible_w * 914400 / box[2], visible_h * 914400 / box[3])
                if dpi < args.min_dpi:
                    issue(report, "warning", "low_image_dpi", dpi=round(dpi, 1), **context)
            crop = (max(0, round(left * iw)), max(0, round(top * ih)),
                    min(iw, round((1 - right) * iw)), min(ih, round((1 - bottom) * ih)))
            if crop[2] <= crop[0] or crop[3] <= crop[1]:
                issue(report, "warning", "empty_visible_image_crop", **context)
                return
            visible = image.crop(crop).convert("RGB")
            visible.thumbnail((512, 512))
            pixels = list(visible.getdata())
            ratio = sum(min(pixel) > 242 for pixel in pixels) / len(pixels)
            if ratio >= args.blank_threshold:
                issue(report, "warning", "high_white_pixel_ratio", ratio=round(ratio, 4),
                      message="白像素比例仅供检查，不等同于留白", **context)
    except Exception as exc:
        reason = reason or "图片解码或属性读取失败"
        issue(report, "warning", "image_decode_failed", message=str(exc), **context)
    finally:
        if not checked:
            counts["images_skipped"] += 1
            issue(report, "skip", "image_aspect_skipped", reason=reason or "图片比例不可检测", **context)


def text_overlap_checks(entries, report, args, page, title):
    counts = report["counts"]
    for i, (first, box1) in enumerate(entries):
        for second, box2 in entries[i + 1:]:
            counts["text_pairs_total"] += 1
            if box1 is None or box2 is None:
                counts["text_pairs_skipped"] += 1
                continue
            counts["text_pairs_checked"] += 1
            x1, y1, w1, h1 = box1
            x2, y2, w2, h2 = box2
            area = max(0, min(x1 + w1, x2 + w2) - max(x1, x2)) * max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
            area_pt2 = area / 12700 ** 2
            ratio = area / min(w1 * h1, w2 * h2)
            if area_pt2 > getattr(args, "text_overlap_area_pt2", 1.0) and ratio > getattr(args, "text_overlap_ratio", 0.01):
                counts["text_overlap_candidates"] += 1
                issue(report, "warning", "text_bbox_overlap_candidate", page=page, page_title=title,
                      intersection_area_pt2=area_pt2, smaller_box_ratio=ratio,
                      shapes=[dict(**first, box_pt=[v / 12700 for v in box1]),
                              dict(**second, box_pt=[v / 12700 for v in box2])],
                      message="文本框bbox相交候选，不代表真实字形碰撞")


def audit(args, report):
    if not package_checks(args.pptx, report, args):
        return
    deck = Presentation(args.pptx)
    report["stats"] = current = stats(deck)
    reference = None
    if args.source or args.write_baseline:
        source = args.source or args.pptx
        report["source_sha256"] = sha256(source)
        reference = stats(Presentation(source))
    if args.write_baseline:
        baseline = dict(schema_version=1, source_sha256=report["source_sha256"], **reference)
        # Exclusive creation prevents a later run from silently replacing the evidence.
        if any(i["severity"] == "error" for i in report["issues"]):
            issue(report, "error", "baseline_not_written", reason="输入结构检查失败")
        else:
            with open(args.write_baseline, "x", encoding="utf-8") as stream:
                json.dump(baseline, stream, ensure_ascii=False, indent=2)
            report["baseline_written"] = str(Path(args.write_baseline).resolve())
    if args.baseline:
        with open(args.baseline, encoding="utf-8") as stream:
            baseline = json.load(stream)
        keys = ("pages", "masters", "layouts", "width", "height")
        if baseline.get("schema_version") != 1 or any(type(baseline.get(k)) is not int or baseline[k] <= 0 for k in keys):
            raise ValueError("基线格式无效")
        digest = baseline.get("source_sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("基线SHA256无效")
        if report["source_sha256"] != digest:
            issue(report, "error", "source_hash_changed", expected=digest, actual=report["source_sha256"])
        reference = {k: baseline[k] for k in keys}
    elif args.source and not args.write_baseline:
        issue(report, "warning", "source_integrity_unverified", message="未提供既有基线，当前源哈希不能证明源文件未改动")
    expected = dict(reference or {})
    if args.expected_pages is not None:
        expected["pages"] = args.expected_pages
    for key, value in expected.items():
        if current[key] != value:
            issue(report, "error", "stat_mismatch", field=key, expected=value, actual=current[key])
    report["counts"] = dict(images_total=0, images_detectable=0, images_skipped=0,
                          text_boxes_total=0, text_boxes_detectable=0, text_boxes_skipped=0,
                          text_pairs_total=0, text_pairs_checked=0, text_pairs_skipped=0,
                          text_overlap_candidates=0)
    for index, slide in enumerate(deck.slides, 1):
        title = slide.shapes.title.text if slide.shapes.title is not None else ""
        entries = []
        shapes = list(walk(slide.shapes, report, index))
        title_source = "title_placeholder" if title.strip() else "none"
        if not title.strip():
            title = next((shape.text.strip().split("\n", 1)[0][:160]
                          for shape, _ in shapes if shape.has_text_frame and shape.text.strip()), "")
            title_source = "first_nonempty_text_fallback" if title else "none"
        for shape, box in shapes:
            text = shape.text.strip().split("\n", 1)[0][:160] if shape.has_text_frame else ""
            context = dict(page=index, page_title=title, shape_id=shape.shape_id,
                           shape_name=shape.name, text=text)
            if shape.has_text_frame and shape.text.strip():
                report["counts"]["text_boxes_total"] += 1
                reason = geometry_reason(shape, box, text=True)
                if reason:
                    report["counts"]["text_boxes_skipped"] += 1
                    issue(report, "skip", "text_bbox_skipped", reason=reason, **context)
                else:
                    report["counts"]["text_boxes_detectable"] += 1
                entries.append((dict(shape_id=shape.shape_id, shape_name=shape.name, text=text), None if reason else box))
            if box:
                x, y, w, h = box
                content = shape.text if shape.has_text_frame else ""
                if shape.has_table:
                    content += "".join(c.text for row in shape.table.rows for c in row.cells)
                if content.strip() and (w < 25400 or h < 12700):
                    issue(report, "error", "collapsed_text", **context)
                if shape.rotation:
                    issue(report, "skip", "rotated_shape_bounds_skipped", **context)
                elif x < -1 or y < -1 or x + w > deck.slide_width + 1 or y + h > deck.slide_height + 1:
                    issue(report, "warning", "out_of_bounds_candidate", box_emu=list(box), **context)
            if shape._element.tag == "{%s}pic" % NS["p"]:
                image_checks(shape, box, report, args, context)
        text_overlap_checks(entries, report, args, index, title)


def same_path(a, b):
    return Path(a).resolve() == Path(b).resolve() or (os.path.exists(a) and os.path.exists(b) and os.path.samefile(a, b))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx")
    parser.add_argument("--source")
    parser.add_argument("--forbidden", nargs="*", default=[])
    parser.add_argument("--blank-threshold", type=float, default=0.85)
    parser.add_argument("--min-font-pt", type=float, default=10)
    parser.add_argument("--min-dpi", type=float, default=150)
    parser.add_argument("--image-aspect-warning", type=float, default=0.05, help="图片比例相对偏差警告阈值（0.05=5%%）")
    parser.add_argument("--image-aspect-error", type=float, default=0.20, help="图片比例相对偏差错误阈值（0.20=20%%）")
    parser.add_argument("--text-overlap-area-pt2", type=float, default=1.0, help="文本框相交面积阈值（平方pt）")
    parser.add_argument("--text-overlap-ratio", type=float, default=0.01, help="交集占较小文本框面积比例阈值")
    parser.add_argument("--write-baseline")
    parser.add_argument("--baseline")
    parser.add_argument("--expected-pages", type=int)
    parser.add_argument("--report")
    args = parser.parse_args(argv)
    report = dict(input=str(Path(args.pptx).resolve()), issues=[], limitations=LIMITATIONS)
    code = 0
    report_safe = False
    try:
        if args.baseline and not args.source:
            raise ValueError("--baseline 必须同时提供 --source")
        if args.baseline and args.write_baseline:
            raise ValueError("--baseline 和 --write-baseline 不能同时使用")
        if args.expected_pages is not None and args.expected_pages <= 0:
            raise ValueError("--expected-pages 必须大于零")
        if not 0 <= args.blank_threshold <= 1 or any(not math.isfinite(v) or v <= 0 for v in (args.min_font_pt, args.min_dpi)):
            raise ValueError("检查阈值无效")
        thresholds = (args.image_aspect_warning, args.image_aspect_error, args.text_overlap_area_pt2, args.text_overlap_ratio)
        if any(not math.isfinite(v) or v < 0 for v in thresholds) or args.image_aspect_error < args.image_aspect_warning or args.text_overlap_ratio > 1:
            raise ValueError("比例或交集阈值无效")
        protected = [p for p in (args.pptx, args.source, args.baseline, args.write_baseline) if p]
        if args.report and any(same_path(args.report, p) for p in protected):
            raise ValueError("--report 不得覆盖输入、源文件或基线")
        report_safe = True
        audit(args, report)
        code = int(any(i["severity"] == "error" for i in report["issues"]))
    except Exception as exc:
        issue(report, "error", "execution_error", message=str(exc))
        code = 2
    report["exit_code"] = code
    report["status"] = "error" if code else ("warnings" if report["issues"] else "pass")
    if args.report and report_safe:
        try:
            with open(args.report, "w", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
        except Exception as exc:
            issue(report, "error", "report_write_failed", message=str(exc))
            code = report["exit_code"] = 2
            report["status"] = "error"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
