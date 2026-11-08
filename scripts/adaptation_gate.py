"""科研 PPT 适配声明关卡；通过不等于 PPT 审批或人工视觉验收。

扩展 schema（基础字段见 research_plan.initial_plan/check_plan）：
- mode: strict|adaptive|restructure，可省略，默认 adaptive。
- authorization: 对象；local_layout 默认 true，split_pages/reorder_pages/
  chapter_changes 默认 false；各值必须为 bool。source 为字符串；任何默认
  false 的权限开启时必须非空，记录真实用户授权原话或出处，程序不核实真实性。
- changes: 必填字符串数组，值只能为上述四种权限名称，不得重复；每项必须获授权。
  adjust/redesign 必须声明 local_layout，split 必须声明 split_pages。
  reorder_pages/chapter_changes 不能从页内容自动推断，须如实人工登记。
- pages[*].adaptation: 必填对象。decision 为 reuse|adjust|redesign|split|hold；
  reason/content_type/template_fit/layout_strategy/fallback 为非空字符串；
  readability_risk 为 low|medium|high；actions 为非空字符串数组（reuse
  允许空数组）；acceptance_notes 为非空字符串，记录可验收条件。high 不得
  reuse；hold 阻断；strict 仅 reuse；adjust/redesign 须获 local_layout
  授权，split 须获 split_pages 授权，restructure 同样不能越过授权。
- pilot: 必填对象；required 为 bool，省略默认 true；representative_pages
  为非空、不重复、位于 pages 范围内的正整数数组；status 为
  not_checked|approved|needs_fix；note 为字符串；render_paths 为字符串数组。
  required=false 仅在顶层 pilot_exemption_reason 与 pilot_exemption_source
  均为非空字符串时接受，用于记录明确用户放弃及其出处，不验证真实意愿。
- stage=plan 只校验试制字段结构、代表页与豁免声明，不要求渲染文件已存在。
  stage=pilot/final 均须 status=approved、非空 note、至少一个绝对且存在的
  render_paths 文件路径；图片用 Pillow（可用时）验证，非图片不能充当渲染。
  render_paths 须与 representative_pages 按相同顺序一一对应、数量相等，
  不得重复引用同一文件（解析路径后比较）。strict 模式 changes 必须为空。
  豁免仅表示明确用户不要求等待其确认，不免代表页制作和检查；即使有豁免，
  pilot/final 也不能跳过上述完成条件。approved 是检查者记录，不是用户批准。

人工边界：不解释 reason 的语义、不证明授权真实、不确认有人实际看过渲染，
不检查视觉美感、布局可读性、内容正确性，亦不生成或审批 PPT。
"""
import argparse
import json
from pathlib import Path
import sys

from research_plan import SCENARIOS, check_plan as check_research_plan, initial_plan as initial_research_plan

PERMISSIONS = ("local_layout", "split_pages", "reorder_pages", "chapter_changes")
DECISIONS = ("reuse", "adjust", "redesign", "split", "hold")
LIMITATIONS = [
    "仅检查基础计划、适配与授权声明及阶段材料完整性；通过不等于 PPT 审批。",
    "不核实授权来源与豁免的真实性；source 必须记录用户授权而非检查者自行判断，不判断 reason 语义或高风险缓解是否充分。",
    "approved 是检查者的检查记录，不代表用户已批准；豁免只免等待用户确认，不免代表页制作和检查。",
    "渲染路径按代表页顺序登记，程序只查数量和文件，不自动证明图片内容与页号对应。",
    "不自动确认人工实际看过渲染，不验证视觉质量、可读性或科学正确性。",
    "无法自动推断漏报的页面重排或章节变化；必须由人工如实声明。",
]


def initial_plan(scenario):
    plan = initial_research_plan(scenario)
    plan.update({
        "mode": "adaptive",
        "authorization": {"local_layout": True, "split_pages": False,
                          "reorder_pages": False, "chapter_changes": False, "source": ""},
        "changes": [],
        "pilot": {"required": True, "representative_pages": [1],
                  "status": "not_checked", "note": "", "render_paths": []},
    })
    for page in plan["pages"]:
        page["adaptation"] = {
            "decision": "hold", "reason": "", "content_type": "", "template_fit": "",
            "layout_strategy": "", "readability_risk": "medium", "actions": [],
            "fallback": "", "acceptance_notes": "",
        }
    return plan


def check_adaptation_plan(plan, stage="plan"):
    result = check_research_plan(plan)
    errors = list(result["errors"])
    warnings = list(result["warnings"])

    def error(path, message):
        errors.append({"path": path, "message": message})

    def text(value):
        return isinstance(value, str) and bool(value.strip())

    def choice(value, options):
        return isinstance(value, str) and value in options

    if stage not in ("plan", "pilot", "final"):
        error("stage", "阶段必须为 plan、pilot 或 final")
    if isinstance(plan, dict):
        mode = plan.get("mode", "adaptive")
        if not choice(mode, ("strict", "adaptive", "restructure")):
            error("mode", "模式必须为 strict、adaptive 或 restructure")
        authorization = plan.get("authorization", {})
        if not isinstance(authorization, dict):
            error("authorization", "必须为对象")
            authorization = {}
        grants = {}
        for permission in PERMISSIONS:
            value = authorization.get(permission, permission == "local_layout")
            if type(value) is not bool:
                error("authorization." + permission, "权限必须为布尔值")
            grants[permission] = value is True
        if not isinstance(authorization.get("source", ""), str):
            error("authorization.source", "授权来源必须为字符串")
        if any(grants[p] for p in PERMISSIONS[1:]) and not text(authorization.get("source")):
            error("authorization.source", "扩大权限须记录真实用户授权说明或出处（真实性由人工核实）")
        changes = plan.get("changes")
        declared = set()
        if not isinstance(changes, list):
            error("changes", "必须为权限名称数组")
        else:
            for i, change in enumerate(changes):
                where = f"changes[{i}]"
                if not choice(change, PERMISSIONS):
                    error(where, "未知更改类型")
                    continue
                if change in declared:
                    error(where, "更改类型不得重复")
                declared.add(change)
                if not grants[change]:
                    error(where, "更改未获对应权限授权")
        if mode == "strict" and isinstance(changes, list) and changes:
            error("changes", "strict 模式不得声明任何更改，须暂停并请求用户决定")
        pages = plan.get("pages")
        pages = pages if isinstance(pages, list) else []
        for i, page in enumerate(pages):
            if not isinstance(page, dict):
                continue
            where = f"pages[{i}].adaptation"
            adaptation = page.get("adaptation")
            if not isinstance(adaptation, dict):
                error(where, "每页必须有适配判断对象")
                continue
            decision = adaptation.get("decision")
            if not choice(decision, DECISIONS):
                error(where + ".decision", "未知适配决策")
            for key in ("reason", "content_type", "template_fit", "layout_strategy", "fallback"):
                if not text(adaptation.get(key)):
                    error(where + "." + key, "必须填写非空字符串")
            if not text(adaptation.get("acceptance_notes")):
                error(where + ".acceptance_notes", "须记录非空验收条件")
            risk = adaptation.get("readability_risk")
            if not choice(risk, ("low", "medium", "high")):
                error(where + ".readability_risk", "风险必须为 low、medium 或 high")
            actions = adaptation.get("actions")
            if not isinstance(actions, list) or any(not text(action) for action in actions):
                error(where + ".actions", "必须为非空字符串构成的数组")
            elif decision != "reuse" and not actions:
                error(where + ".actions", "非 reuse 决策必须列出具体动作")
            if risk == "high" and decision == "reuse":
                error(where + ".decision", "高可读性风险不得直接复用")
            if decision == "hold":
                error(where + ".decision", "hold 暂停后续制作，须先解决适配判断")
            if mode == "strict" and decision != "reuse":
                error(where + ".decision", "strict 模式只允许 reuse，否则暂停并请求用户决定")
            permission = "local_layout" if decision in ("adjust", "redesign") else "split_pages" if decision == "split" else None
            if permission:
                if not grants[permission]:
                    error(where + ".decision", "该决策缺少 " + permission + " 授权")
                if permission not in declared:
                    error("changes", "逐页决策对应的 " + permission + " 更改必须声明")
        pilot = plan.get("pilot")
        if not isinstance(pilot, dict):
            error("pilot", "必须为独立的试制检查对象")
        else:
            required = pilot.get("required", True)
            if type(required) is not bool:
                error("pilot.required", "必须为布尔值")
            for key in ("pilot_exemption_reason", "pilot_exemption_source"):
                if key in plan and not text(plan[key]):
                    error(key, "豁免声明必须为非空字符串")
            if required is False and not all(text(plan.get(k)) for k in ("pilot_exemption_reason", "pilot_exemption_source")):
                error("pilot.required", "不得关闭试制绕过关卡；须记录明确用户放弃的理由及出处")
            selected = pilot.get("representative_pages")
            if not isinstance(selected, list) or not selected:
                error("pilot.representative_pages", "必须选择非空代表页数组")
            else:
                seen = set()
                for i, number in enumerate(selected):
                    where = f"pilot.representative_pages[{i}]"
                    if type(number) is not int or not 1 <= number <= len(pages):
                        error(where, "代表页须为计划范围内的正整数页号")
                    elif number in seen:
                        error(where, "代表页不得重复")
                    else:
                        seen.add(number)
            if not choice(pilot.get("status"), ("not_checked", "approved", "needs_fix")):
                error("pilot.status", "未知试制状态")
            if not isinstance(pilot.get("note"), str):
                error("pilot.note", "必须为字符串")
            paths = pilot.get("render_paths")
            if not isinstance(paths, list) or any(not text(path) for path in paths):
                error("pilot.render_paths", "必须为非空路径字符串构成的数组")
                paths = []
            if stage in ("pilot", "final"):
                if pilot.get("status") != "approved":
                    error("pilot.status", "须先记录代表页人工试制 approved 声明")
                if not text(pilot.get("note")):
                    error("pilot.note", "须记录非空人工验收说明")
                if not paths:
                    error("pilot.render_paths", "须提供代表页渲染文件")
                if isinstance(selected, list) and len(paths) != len(selected):
                    error("pilot.render_paths", "渲染须与代表页同顺序一一对应，文件数量必须相等")
                seen_paths = set()
                for i, value in enumerate(paths):
                    where = f"pilot.render_paths[{i}]"
                    path = Path(value)
                    if not path.is_absolute() or not path.is_file():
                        error(where, "渲染必须为绝对且存在的文件路径")
                        continue
                    resolved = path.resolve()
                    if resolved in seen_paths:
                        error(where, "代表页渲染不可重复引用同一文件")
                    seen_paths.add(resolved)
                    if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"):
                        error(where, "渲染文件须为图片格式")
                        continue
                    try:
                        from PIL import Image
                    except ImportError:
                        warnings.append({"path": where, "message": "未安装 Pillow，未验证图片编码；须人工检查"})
                    else:
                        try:
                            with Image.open(path) as image:
                                image.verify()
                        except (OSError, ValueError, SyntaxError) as exc:
                            error(where, "图片无法通过编码验证：" + str(exc))
    return {"ok": not errors, "stage": stage, "errors": errors, "warnings": warnings,
            "scope": result.get("scope", "仅校验计划及声明"), "limitations": list(LIMITATIONS)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="独占创建待填写适配计划")
    init.add_argument("--scenario", choices=SCENARIOS, required=True)
    init.add_argument("--output", required=True)
    check = commands.add_parser("check", help="检查声明与阶段材料，不代表 PPT 审批")
    check.add_argument("plan_json")
    check.add_argument("--stage", choices=("plan", "pilot", "final"), default="plan")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            with open(args.output, "x", encoding="utf-8") as handle:
                json.dump(initial_plan(args.scenario), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            result = {"ok": True, "output": str(Path(args.output).resolve()), "status": "待填写，尚未通过校验", "limitations": list(LIMITATIONS)}
            code = 0
        else:
            with open(args.plan_json, encoding="utf-8-sig") as handle:
                plan = json.load(handle)
            result = check_adaptation_plan(plan, args.stage)
            code = 0 if result["ok"] else 1
    except (OSError, ValueError, RecursionError) as exc:
        result = {"ok": False, "execution_error": str(exc), "limitations": list(LIMITATIONS)}
        code = 2
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
