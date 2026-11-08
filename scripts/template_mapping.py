"""参考模板页到成品页的显式映射关卡（仅校验声明，不代替人工审查）。

每个 output_page 只能映射一次；同一 template_page 多次出现时必须全部为 split。
unmatched 表示成品页没有参考页，template_page 必须为 null，reference_function
必须为 other；登记模板页未使用时须填 unused_template_pages 及原因。
comparison 为顶层对象，final 需要 reviewed、非空 notes 和绝对且存在的来源文件。
"""
import argparse
import json
from pathlib import Path
import sys

FUNCTIONS = ("cover", "agenda", "problem", "comparison", "classification", "process",
             "timeline", "system_diagram", "result", "plan", "closing", "other")
DECISIONS = ("reuse", "adjust", "redesign", "split", "unmatched")
LIMITATIONS = [
    "不能自动识别页面功能或判断模板与成品的视觉对应，所有功能与保真字段必须由人工核实。",
    "只核验映射声明、页号覆盖和来源文件，不验证来源实际页数、科学内容或视觉质量。",
    "reviewed 和 readability 是人工声明，不证明实际审阅，不代表用户批准。",
]


def initial_plan():
    """返回须填写才能通过检查的映射草稿。"""
    return {
        "template_pages": [{"template_page": 1, "title": "", "function": "other",
                            "layout_signature": "", "notes": ""}],
        "content_pages": [{"output_page": 1, "title": "", "content_function": "other", "claim": ""}],
        "mappings": [{"template_page": 1, "output_page": 1, "decision": "adjust", "reason": "",
                      "reference_function": "other", "content_function": "other",
                      "visual_fidelity": "adapted", "layout_fidelity": "adapted",
                      "semantic_fit": "partial", "readability": "not_checked",
                      "change_summary": "", "review_note": ""}],
        "unused_template_pages": [],
        "comparison": {"template_source": "", "output_source": "",
                       "visual_review_status": "not_checked", "notes": ""},
        "limitations": list(LIMITATIONS),
    }


def check_template_mapping(plan, stage="plan"):
    errors = []

    def error(path, message):
        errors.append({"path": path, "message": message})

    def text(value):
        return isinstance(value, str) and bool(value.strip())

    def choice(value, options):
        return isinstance(value, str) and value in options

    def positive(value):
        return type(value) is int and value > 0

    def required_text(obj, keys, where):
        for key in keys:
            if not text(obj.get(key)):
                error(where + "." + key, "必须填写非空字符串")

    def enum(obj, key, options, where):
        if not choice(obj.get(key), options):
            error(where + "." + key, "未知枚举值，允许：" + ", ".join(options))

    def array(key, nonempty=False):
        value = plan.get(key)
        if not isinstance(value, list):
            error(key, "必须为数组")
            return []
        if nonempty and not value:
            error(key, "数组不得为空")
        return value

    if stage not in ("plan", "final"):
        error("stage", "阶段必须为 plan 或 final")
    if not isinstance(plan, dict):
        error("plan", "计划必须为对象")
        plan = {}

    templates = {}
    outputs = {}
    for key, number_key, function_key, target, fields in (
        ("template_pages", "template_page", "function", templates, ("title", "layout_signature", "notes")),
        ("content_pages", "output_page", "content_function", outputs, ("title", "claim")),
    ):
        for i, page in enumerate(array(key, True)):
            where = f"{key}[{i}]"
            if not isinstance(page, dict):
                error(where, "页登记必须为对象")
                continue
            required_text(page, fields, where)
            enum(page, function_key, FUNCTIONS, where)
            number = page.get(number_key)
            if not positive(number):
                error(where + "." + number_key, "页号必须为正整数，不能为布尔值")
            elif number in target:
                error(where + "." + number_key, "页号不得重复登记")
            else:
                target[number] = page

    mapped_outputs = set()
    template_uses = {}
    pairs = set()
    for i, mapping in enumerate(array("mappings", True)):
        where = f"mappings[{i}]"
        if not isinstance(mapping, dict):
            error(where, "映射必须为对象")
            continue
        required_text(mapping, ("reason", "change_summary", "review_note"), where)
        enum(mapping, "decision", DECISIONS, where)
        enum(mapping, "reference_function", FUNCTIONS, where)
        enum(mapping, "content_function", FUNCTIONS, where)
        for key in ("visual_fidelity", "layout_fidelity"):
            enum(mapping, key, ("preserved", "adapted", "not_applicable"), where)
        enum(mapping, "semantic_fit", ("fit", "partial", "mismatch"), where)
        enum(mapping, "readability", ("pass", "needs_review", "not_checked"), where)
        template = mapping.get("template_page")
        output = mapping.get("output_page")
        decision = mapping.get("decision")
        if not positive(output) or output not in outputs:
            error(where + ".output_page", "须引用已登记的正整数成品页号")
        else:
            if output in mapped_outputs:
                error(where + ".output_page", "一个成品页只能有一个映射")
            mapped_outputs.add(output)
            if mapping.get("content_function") != outputs[output].get("content_function"):
                error(where + ".content_function", "必须与成品页登记功能一致")
        if decision == "unmatched":
            if template is not None:
                error(where + ".template_page", "unmatched 不得引用模板页，须明确填 null")
            if "template_page" not in mapping:
                error(where + ".template_page", "unmatched 须明确填 null")
            if mapping.get("reference_function") != "other":
                error(where + ".reference_function", "unmatched 无参考功能，须填 other")
        elif not positive(template) or template not in templates:
            error(where + ".template_page", "须引用已登记的正整数模板页号；无参考页只能用 unmatched")
        else:
            template_uses.setdefault(template, []).append((where, decision))
            if mapping.get("reference_function") != templates[template].get("function"):
                error(where + ".reference_function", "必须与模板页登记功能一致")
        if positive(template) and positive(output):
            pair = (template, output)
            if pair in pairs:
                error(where, "模板页与成品页映射对不得重复")
            pairs.add(pair)
        if decision == "reuse":
            if mapping.get("reference_function") != mapping.get("content_function"):
                error(where + ".decision", "reuse 必须保证参考与内容功能一致")
            if mapping.get("semantic_fit") != "fit":
                error(where + ".semantic_fit", "reuse 必须为 fit，不能为 partial 或 mismatch")

    for template, uses in template_uses.items():
        if len(uses) > 1:
            for where, decision in uses:
                if decision != "split":
                    error(where + ".decision", "同一模板页映射多个成品页时，每项都必须为 split")

    unused = set()
    for i, item in enumerate(array("unused_template_pages")):
        where = f"unused_template_pages[{i}]"
        if not isinstance(item, dict):
            error(where, "未使用模板页必须为对象")
            continue
        required_text(item, ("reason",), where)
        number = item.get("template_page")
        if not positive(number) or number not in templates:
            error(where + ".template_page", "须引用已登记模板页号")
        else:
            if number in unused:
                error(where + ".template_page", "未使用模板页不得重复登记")
            if number in template_uses:
                error(where + ".template_page", "已映射模板页不能声明未使用")
            unused.add(number)
    for number in sorted(set(templates) - set(template_uses) - unused):
        error("unused_template_pages", f"模板页 {number} 未映射，须登记未使用原因")
    for number in sorted(set(outputs) - mapped_outputs):
        error("mappings", f"成品页 {number} 缺少映射（无参考页须明确 unmatched）")

    comparison = plan.get("comparison")
    if not isinstance(comparison, dict):
        error("comparison", "必须提供对照审查对象")
    else:
        enum(comparison, "visual_review_status", ("not_checked", "reviewed"), "comparison")
        for key in ("template_source", "output_source", "notes"):
            if not isinstance(comparison.get(key), str):
                error("comparison." + key, "必须为字符串")
        if stage == "final":
            if comparison.get("visual_review_status") != "reviewed":
                error("comparison.visual_review_status", "final 须记录人工 reviewed 声明")
            required_text(comparison, ("notes",), "comparison")
            for key in ("template_source", "output_source"):
                value = comparison.get(key)
                if not text(value):
                    error("comparison." + key, "final 须提供绝对且存在的来源文件路径")
                    continue
                try:
                    path = Path(value)
                    exists = path.is_absolute() and path.is_file()
                except (OSError, ValueError):
                    exists = False
                if not exists:
                    error("comparison." + key, "final 来源必须为绝对且存在的文件路径")
    return {"ok": not errors, "stage": stage, "errors": errors, "warnings": [],
            "coverage": {"template_pages": len(templates), "mapped_template_pages": len(template_uses),
                         "unused_template_pages": len(unused), "content_pages": len(outputs),
                         "mapped_content_pages": len(mapped_outputs)},
            "scope": "仅校验模板—成品映射声明及对照审查材料，不代替人工验收", "limitations": list(LIMITATIONS)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="独占创建待填写映射计划")
    init.add_argument("--output", required=True)
    check = commands.add_parser("check", help="检查映射覆盖及阶段材料")
    check.add_argument("plan_json")
    check.add_argument("--stage", choices=("plan", "final"), default="plan")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            with open(args.output, "x", encoding="utf-8") as handle:
                json.dump(initial_plan(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            result = {"ok": True, "output": str(Path(args.output).resolve()),
                      "status": "待填写，尚未通过校验", "limitations": list(LIMITATIONS)}
            code = 0
        else:
            with open(args.plan_json, encoding="utf-8-sig") as handle:
                plan = json.load(handle)
            result = check_template_mapping(plan, args.stage)
            code = 0 if result["ok"] else 1
    except (OSError, ValueError, RecursionError) as exc:
        result = {"ok": False, "execution_error": str(exc), "limitations": list(LIMITATIONS)}
        code = 2
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
