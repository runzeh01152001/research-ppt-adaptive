"""科研 PPT 页面计划与来源声明检查；不生成 PPT，也不核实科学真伪。"""
import argparse
import json
import os
from pathlib import Path
import sys

SCENARIOS = ("proposal", "defense", "group_meeting", "project_application")
ROLES = {"content", "cover", "agenda", "divider", "closing"}
STATUSES = {"planned", "completed", "literature", "hypothesis", "mixed"}
SOURCE_TYPES = {"own_result", "literature", "planned_schematic", "generated_schematic", "template_identity"}
SCHEMATICS = {"planned_schematic", "generated_schematic"}


def initial_plan(scenario):
    return {
        "schema_version": 1,
        "scenario": scenario,
        "template": None,
        "pages": [{"page": 1, "title": "待填写", "role": "content", "claim": "",
                   "conclusion": "", "statement_status": "planned", "evidence_ids": [],
                   "no_evidence_reason": "", "review_note": ""}],
        "assets": [],
        "forbidden_sources": [],
    }


def check_plan(plan):
    errors, warnings = [], []

    def error(where, message):
        errors.append({"path": where, "message": message})

    def text(value):
        return isinstance(value, str) and bool(value.strip())

    def integer(value):
        return type(value) is int and value > 0

    def source(value, where):
        if not text(value) or not Path(value).is_absolute():
            error(where, "source_file 必须为绝对文件路径")
            return None
        path = Path(value)
        if not path.is_file():
            error(where, "来源文件不存在或不是文件")
        return os.path.normcase(os.path.realpath(value))

    def locator(value, where):
        if not isinstance(value, dict):
            error(where, "locator 必须为含 slide 和 detail 的对象")
            return None
        slide = value.get("slide")
        if "slide" not in value or (slide is not None and not integer(slide)):
            error(where + ".slide", "slide 必须为正整数或 null")
        if not text(value.get("detail")):
            error(where + ".detail", "必须填写定位说明")
        return slide if integer(slide) else None

    if not isinstance(plan, dict):
        return {"ok": False, "errors": [{"path": "$", "message": "计划必须为 JSON 对象"}], "warnings": []}
    if type(plan.get("schema_version")) is not int or plan.get("schema_version") != 1:
        error("schema_version", "仅支持版本 1")
    if not isinstance(plan.get("scenario"), str) or plan.get("scenario") not in SCENARIOS:
        error("scenario", "未知场景")
    collections = {}
    for key in ("pages", "assets", "forbidden_sources"):
        value = plan.get(key)
        if not isinstance(value, list):
            error(key, "必须为数组")
            value = []
        collections[key] = value
    if "template" not in plan:
        error("template", "必须显式记录 template，未使用时为 null")
    template = plan.get("template")
    if template is not None:
        if not isinstance(template, dict):
            error("template", "必须为对象或 null")
        else:
            source(template.get("source_file"), "template.source_file")
            if template.get("read_only") is not True:
                error("template.read_only", "模板源必须声明只读 true")
            if template.get("template_slide") is not None and not integer(template["template_slide"]):
                error("template.template_slide", "必须为正整数或 null")
            if "slots" in template and not isinstance(template["slots"], dict):
                error("template.slots", "仅记录槽位元数据，必须为对象")

    forbidden = []
    for i, item in enumerate(collections["forbidden_sources"]):
        where = f"forbidden_sources[{i}]"
        if not isinstance(item, dict):
            error(where, "必须为对象")
            continue
        path = source(item.get("source_file"), where + ".source_file")
        start, end = item.get("slide_start"), item.get("slide_end")
        if not integer(start) or not integer(end) or start > end:
            error(where, "禁用页区间必须为递增的正整数闭区间")
        elif path:
            forbidden.append((path, start, end))

    assets, origins = {}, {}
    for i, asset in enumerate(collections["assets"]):
        where = f"assets[{i}]"
        if not isinstance(asset, dict):
            error(where, "必须为对象")
            continue
        asset_id = asset.get("id")
        if not text(asset_id):
            error(where + ".id", "素材 ID 必须为非空字符串")
        elif asset_id in assets:
            error(where + ".id", "素材 ID 重复")
        else:
            assets[asset_id] = asset
        source_type = asset.get("source_type")
        if not isinstance(source_type, str) or source_type not in SOURCE_TYPES:
            error(where + ".source_type", "未知素材类型")
        path = source(asset.get("source_file"), where + ".source_file")
        slide = locator(asset.get("locator"), where + ".locator")
        ancestry = [(path, slide)]
        for key in ("caption",):
            if not text(asset.get(key)):
                error(where + "." + key, "必须填写非空文字")
        if not isinstance(asset.get("citation"), str):
            error(where + ".citation", "citation 必须为字符串；非文献允许空字符串")
        if source_type == "literature" and not text(asset.get("citation")):
            error(where + ".citation", "文献素材必须填写引文")
        verification = asset.get("verification_status")
        if verification not in ("verified", "unverified"):
            error(where + ".verification_status", "必须为 verified 或 unverified")
        if not isinstance(asset.get("verification_note"), str):
            error(where + ".verification_note", "必须记录验证说明字符串")
        if verification == "verified" and not text(asset.get("verification_note")):
            error(where + ".verification_note", "verified 必须附人工验证说明")
        if isinstance(source_type, str) and source_type in SCHEMATICS:
            label = asset.get("label")
            if not text(label) or ("示意" not in label and "schematic" not in label.lower()):
                error(where + ".label", "计划或生成示意图必须明确标注‘示意’或 schematic")
        ancestors = asset.get("derived_from_sources")
        if not isinstance(ancestors, list):
            error(where + ".derived_from_sources", "必须为数组，记录全部裁剪、拼接祖先")
        else:
            for j, ancestor in enumerate(ancestors):
                location = where + f".derived_from_sources[{j}]"
                if not isinstance(ancestor, dict):
                    error(location, "祖先必须为含 source_file、locator 的对象")
                    continue
                ancestor_path = source(ancestor.get("source_file"), location + ".source_file")
                ancestor_slide = locator(ancestor.get("locator"), location + ".locator")
                ancestry.append((ancestor_path, ancestor_slide))
        if text(asset_id) and asset_id not in origins:
            origins[asset_id] = ancestry

    pages = collections["pages"]
    if not pages:
        error("pages", "至少需要一页")
    for i, page in enumerate(pages):
        where = f"pages[{i}]"
        if not isinstance(page, dict):
            error(where, "必须为对象")
            continue
        if not integer(page.get("page")) or page.get("page") != i + 1:
            error(where + ".page", "页面必须按顺序从 1 连续编号，不得重复")
        if not text(page.get("title")):
            error(where + ".title", "标题不能为空")
        role = page.get("role")
        if not isinstance(role, str) or role not in ROLES:
            error(where + ".role", "未知页面角色")
        ids = page.get("evidence_ids", [])
        if not isinstance(ids, list):
            error(where + ".evidence_ids", "必须为素材 ID 数组")
            ids = []
        if role == "content":
            for key in ("claim", "conclusion", "review_note"):
                if not text(page.get(key)):
                    error(where + "." + key, "内容页必须填写非空文字")
            status = page.get("statement_status")
            if not isinstance(status, str) or status not in STATUSES:
                error(where + ".statement_status", "未知陈述状态")
            if "evidence_ids" not in page:
                error(where + ".evidence_ids", "内容页必须显式登记证据数组")
            if not ids and not text(page.get("no_evidence_reason")):
                error(where + ".no_evidence_reason", "无素材概念页必须明确说明无证据理由")
            if status == "mixed":
                warnings.append({"path": where + ".statement_status", "message": "混合陈述须人工核查各部分状态，不能自动推断科学正确性"})
        used = []
        for j, asset_id in enumerate(ids):
            location = where + f".evidence_ids[{j}]"
            if not text(asset_id) or asset_id not in assets:
                error(location, "引用未知素材 ID")
                continue
            asset = assets[asset_id]
            used.append(asset)
            if asset.get("verification_status") != "verified":
                error(location, "实际使用的素材必须 verified")
            for path, _source_slide in origins.get(asset_id, []):
                for banned_path, start, end in forbidden:
                    target_page = page.get("page")
                    if path == banned_path and integer(target_page) and start <= target_page <= end:
                        error(location, "素材或裁剪/拼接祖先命中目标页区间的禁用来源")
        if role == "content" and page.get("statement_status") == "completed" and used:
            if all(isinstance(a.get("source_type"), str) and a["source_type"] in SCHEMATICS for a in used):
                error(where + ".statement_status", "已完成结果不能仅引用计划或生成示意图")
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "scope": "仅校验计划及来源声明；不识别图像、不验证科学真伪、不生成 PPT"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="独占创建待填写页面计划")
    init.add_argument("--scenario", choices=SCENARIOS, required=True)
    init.add_argument("--output", required=True)
    check = commands.add_parser("check", help="输出 JSON 校验报告")
    check.add_argument("plan_json")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            with open(args.output, "x", encoding="utf-8") as handle:
                json.dump(initial_plan(args.scenario), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            result = {"ok": True, "output": str(Path(args.output).resolve()), "status": "待填写，尚未通过校验"}
            exit_code = 0
        else:
            with open(args.plan_json, encoding="utf-8-sig") as handle:
                plan = json.load(handle)
            result = check_plan(plan)
            exit_code = 0 if result["ok"] else 1
    except (OSError, ValueError, RecursionError) as exc:
        result = {"ok": False, "execution_error": str(exc)}
        exit_code = 2
    print(json.dumps(result, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
