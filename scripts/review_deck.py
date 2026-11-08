#!/usr/bin/env python3
"""只读检查人工逐页验收记录；不渲染或修改演示文稿。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image
from pptx import Presentation


ITEMS = ("image_geometry", "text_occlusion", "readability", "content_alignment")
LIMITATIONS = "本工具仅校验验收记录与文件一致性，不能证明人工实际查看、目标软件实际打开、内容质量、截图来自对应页面或截图未经低分辨率上采样；不会渲染、修改PPT或自动填入通过状态及截图哈希。"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def deck_info(path):
    deck = Presentation(str(path))
    width, height = int(deck.slide_width), int(deck.slide_height)
    if width <= 0 or height <= 0:
        raise ValueError("PPT页面尺寸必须为正数")
    return {
        "sha256": sha256(path),
        "slide_count": len(deck.slides),
        "slide_size_emu": {"width": width, "height": height},
        "titles": [slide.shapes.title.text if slide.shapes.title is not None else ""
                   for slide in deck.slides],
    }


def create_checklist(pptx_path, output):
    if Path(pptx_path).resolve() == Path(output).resolve():
        raise ValueError("输出不能指向输入PPT文件")
    info = deck_info(pptx_path)
    ratio = info["slide_size_emu"]["height"] / info["slide_size_emu"]["width"]
    data = {
        "schema_version": 1,
        "pptx_sha256": info["sha256"],
        "slide_count": info["slide_count"],
        "slide_size_emu": info["slide_size_emu"],
        "render_requirements": {
            "baseline_width": 1280, "baseline_height": round(1280 * ratio),
            "minimum_width": 2560, "minimum_height": round(2560 * ratio),
            "aspect_ratio_tolerance": 0.01,
        },
        "target_software": {"name": "", "open_verified": False},
        "slides": [
            {"slide_number": index, "title": title, "render_path": "",
             "render_sha256": "", "actual_scale_checked": False,
             "checks": {item: {"status": "not_checked", "note": ""} for item in ITEMS}}
            for index, title in enumerate(info["titles"], 1)
        ],
        "limitations": LIMITATIONS,
    }
    # 独占创建，既有文件、符号链接及硬链接都不会被覆盖。
    with Path(output).open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return {"status": "initialized", "checklist": str(Path(output).resolve()),
            "slide_count": info["slide_count"], "limitations": LIMITATIONS}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def check_checklist(pptx_path, checklist):
    info = deck_info(pptx_path)
    with Path(checklist).open(encoding="utf-8") as stream:
        data = json.load(stream)
    errors = []
    if not isinstance(data, dict):
        return {"status": "incomplete", "errors": ["清单必须为JSON对象"], "limitations": LIMITATIONS}
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        errors.append("不支持的schema_version")
    if data.get("pptx_sha256") != info["sha256"]:
        errors.append("PPT SHA256不匹配，清单可能已过期")
    if type(data.get("slide_count")) is not int or data["slide_count"] != info["slide_count"]:
        errors.append("页数不匹配")
    if data.get("slide_size_emu") != info["slide_size_emu"]:
        errors.append("PPT页面尺寸不匹配")
    software = data.get("target_software")
    if not isinstance(software, dict) or not nonempty(software.get("name")) or software.get("open_verified") is not True:
        errors.append("必须声明目标软件名称且open_verified为true")
    slides = data.get("slides")
    if not isinstance(slides, list):
        slides = []
        errors.append("slides必须为数组")
    seen = set()
    expected_ratio = info["slide_size_emu"]["width"] / info["slide_size_emu"]["height"]
    minimum_height = round(2560 / expected_ratio)
    for position, slide in enumerate(slides, 1):
        prefix = f"记录{position}"
        if not isinstance(slide, dict):
            errors.append(f"{prefix}必须为对象")
            continue
        number = slide.get("slide_number")
        if type(number) is not int or not 1 <= number <= info["slide_count"]:
            errors.append(f"{prefix}页码无效")
        else:
            prefix = f"第{number}页"
            if number in seen:
                errors.append(f"{prefix}重复")
            seen.add(number)
            if slide.get("title") != info["titles"][number - 1]:
                errors.append(f"{prefix}标题与PPT不匹配")
        if slide.get("actual_scale_checked") is not True:
            errors.append(f"{prefix}未声明按实际比例检查")
        checks = slide.get("checks")
        if not isinstance(checks, dict):
            checks = {}
        for item in ITEMS:
            entry = checks.get(item)
            if not isinstance(entry, dict):
                errors.append(f"{prefix}.{item}记录缺失")
                continue
            status = entry.get("status")
            if status not in ("pass", "needs_fix", "not_checked"):
                errors.append(f"{prefix}.{item}状态无效")
            elif status != "pass":
                errors.append(f"{prefix}.{item}尚未通过：{status}")
            if not nonempty(entry.get("note")):
                errors.append(f"{prefix}.{item}需要非空note")
        render_path = slide.get("render_path")
        if not nonempty(render_path) or not Path(render_path).is_absolute():
            errors.append(f"{prefix}render_path必须为绝对路径")
            continue
        image_path = Path(render_path)
        if not image_path.is_file():
            errors.append(f"{prefix}截图文件不存在")
            continue
        try:
            actual_hash = sha256(image_path)
            with Image.open(image_path) as image:
                width, height = image.size
                image.verify()
            if width < 2560 or height < minimum_height:
                errors.append(f"{prefix}截图分辨率不足，至少2560×{minimum_height}")
            if abs((width / height) / expected_ratio - 1) > 0.01:
                errors.append(f"{prefix}截图宽高比误差超过1%")
            if slide.get("render_sha256") != actual_hash:
                errors.append(f"{prefix}截图SHA256缺失或不一致")
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            errors.append(f"{prefix}截图无法验证：{exc}")
    missing = sorted(set(range(1, info["slide_count"] + 1)) - seen)
    if missing:
        errors.append(f"缺少页面：{missing}")
    return {"status": "complete" if not errors else "incomplete",
            "errors": errors, "slide_count": info["slide_count"], "limitations": LIMITATIONS}


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None):
    parser = JsonArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("pptx")
    init.add_argument("--output", required=True)
    check = commands.add_parser("check")
    check.add_argument("pptx")
    check.add_argument("--checklist", required=True)
    try:
        args = parser.parse_args(argv)
        if args.command == "init":
            result = create_checklist(args.pptx, args.output)
            code = 0
        else:
            result = check_checklist(args.pptx, args.checklist)
            code = 0 if result["status"] == "complete" else 1
    except Exception as exc:
        result = {"status": "error", "error": str(exc), "limitations": LIMITATIONS}
        code = 2
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
