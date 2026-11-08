---
name: research-ppt-adaptive
description: 面向开题报告、毕业答辩、组会和项目申报PPT的科研自适应仿写技能。用于“沿用模板风格但不要硬套布局”“模板不适合内容时重排”“先判断版式再制作”，以及科研模板稿的适配审查。默认保留母版视觉体系，逐页选择沿用、局部调整、同风格重排、经授权拆页或暂停；提供页面适配关卡、证据登记、代表页确认、几何审计与全页视觉验收。区别于严格逐页复制模板；不替代项目书正文创作。
agent_created: true
---

# 科研 PPT 自适应仿写

作为独立技能执行，不覆盖或修改 imitate-ppt。优先保证论证、证据和可读性，再保留模板视觉语言。先判断模板能否承载当前内容，禁止以“按模板制作”为理由继承不适合的布局。实际PPT读写遵守当前官方PPT流程；本技能的脚本只检查计划/成品结构/验收记录，不负责自动生成或渲染PPT。

## 1. 识别场景、模式与边界

读取 references/research-scenarios.md 对应分支：proposal开题、defense答辩、group_meeting组会、project_application项目申报。四类均正式支持，机构指定结构优先；项目书在此指从项目书提炼汇报，不代替申请书正文。

确定源模板、内容材料、输出版本、听众、时长、禁用来源和页范围。只处理点名文件，所有副本、素材、报告和测试产物置于工作区，源文件只读。无模板时询问或转交新稿流程，不能虚构模板保真。

采用三种模式：
- adaptive（默认）：保留母版、配色、字体层级、标识与章节视觉；允许内容区局部调整和同风格重排。仅在未违反用户现有约束时采用默认权限，并向用户说明。
- strict：仅明确要求逐页原样复刻时使用。检测到布局冲突后暂停并提出方案，不靠缩图缩字完成。
- restructure：用户同意较大改动时使用。此模式本身不代表已获拆页、改页序或章节权限，逐项记录授权。

区分视觉风格与信息布局；不能把六宫格、三栏或五节点时间线当成必须保留的身份特征。默认不拆页、不改页序和章节。遇到机构固定版式、用户明确原位替换时，不能用默认adaptive绕过限制。

## 2. 内容先行与模板基线

按“论点—证据—结论”规划每张内容页，再选模板页，而非先分槽再找内容填。登记已完成/计划/文献/假设/混合状态、来源、图注、支持范围和待确认项；见场景文档。

编辑前运行（命令相对本技能目录，所有输出路径替换为实际工作区绝对路径）：

```bash
python scripts/audit_deck.py "源模板.pptx" --write-baseline "工作区/template-baseline.json"
python scripts/adaptation_gate.py init --scenario proposal --output "工作区/adaptation-plan.json"
```

基线独占创建，记录修改前文件身份；不能编辑后重建掩盖变更。登记源模板页与目标页映射、原槽位及拟调整处，不机械继承旧课题证据。复制形状不等于保住背景、局部字符格式和动画，需单独核查。

## 3. 参考页功能映射与强制适配关卡

不要把参考PPT的页数、章节名或颜色当作版式保真证明。先用 `scripts/template_mapping.py init --output "工作区/template-mapping.json"` 建立参考页—输出页映射。逐页记录参考页功能、新内容功能、布局签名、决定、视觉保真、布局保真、语义适配和可读性状态。功能必须区分分类矩阵、方案比较、因果流程、时间线、系统框图、实验结果、研究计划等关系，而不能只写“研究现状”或“研究内容”。

执行 `python scripts/template_mapping.py check "工作区/template-mapping.json" --stage plan`。所有输出内容页必须有映射；参考页未使用时登记理由；一页拆为多页时使用split并登记页映射；没有对应参考页的输出页使用unmatched并说明原因。reuse仅在参考功能与新内容功能一致且semantic_fit=fit时允许；功能不匹配不得标reuse。final阶段还要填写参考稿—成品来源和逐页视觉对照记录。该脚本只校验记录结构，不能自动识别页面功能或证明视觉保真。

读取 references/adaptation-policy.md。每页在制作前登记：页面功能/证据类型、模板适配判断、风险、决定、布局策略、具体动作、回退方案和验收重点。封面、目录等可简写，但不能遗漏。

在以下五种决定中选择：
1. reuse：结构、容量和证据比例相符，直接沿用。
2. adjust：论证结构相符，调整图位、栏宽、文字量和装饰。
3. redesign：信息关系不符，在同一视觉体系内重排内容区。
4. split：无法单页可读，在明确授权后拆页。
5. hold：关键来源、结构许可或可行布局缺失，暂停该页。

运行 `python scripts/adaptation_gate.py check "工作区/adaptation-plan.json" --stage plan`。缺适配决定、hold、风险高却reuse、strict下改布局、未经授权改动均阻断关卡。不得用模糊授权说明冒充用户许可，不能为过检降低风险等级或编造fit理由。

将以下情况作为停止硬套的条件：关键图例/坐标不可读、必须裁掉证据才能填槽、并列布局硬装因果流程、对称拆散必要对照、缺素材而遗留旧课题图、持续缩字/压图/叠框。几何无报错不能推翻这些条件。

## 4. 代表页确认后再批量制作

选取能覆盖当前稿件主要信息类型的代表页，例如文献现状、实验结果、技术路线；根据实际内容选，不强制每稿恰好三页。先制作、渲染并查看代表页，再呈交用户确认尺寸密度和调整方向。用户已有明确委托自行判断时，记录该授权及实际检查依据，不虚构用户批准。

填入pilot状态、代表页、渲染图路径与观察说明；执行 `adaptation_gate.py check PLAN --stage pilot`。未通过前不批量铺开。仅用户明确放弃代表页确认时登记豁免和授权依据，仍不得豁免成品逐页验收。

## 5. 素材核验与安全编辑

使用research_plan登记assets、evidence_ids、forbidden_sources，字段见research-scenarios.md；adaptation_gate同步调用基础计划校验，无须另造一份互相矛盾的来源清单。

核对原PDF正文与图注，英文提取先归一化连字。记录裁剪、拼接、重绘参考的全部来源；禁用区间按目标PPT页判断。哈希和相似度仅作筛查，未命中不等于图源合规。无法确认的科研图不填verified。

优先选择直接支持论点的完整子图。采用等比完整呈现，不默认居中裁切；裁白边不裁坐标、单位、比例尺或实验含义。生成图明确标示意，不冒充曲线/显微图/实验结果。

保持母版视觉并按适配决定执行。放不下时精简冗余、选关键子图、调已授权栏位，再按授权拆页或暂停；不能无限缩小。碰到动画引用、组合变换、填充修饰与媒体关系问题先读pitfalls.md。

## 6. 最终分层验收

1. 将计划回填到实际页序和素材位置，复核适配动作是否真正执行；拆页后重新编号并重评禁用目标页范围。执行 `adaptation_gate.py check PLAN --stage final`。脚本只验证记录与授权声明，不证明布局合适或成品与计划一致。
2. 执行机器审计：

```bash
python scripts/audit_deck.py "最终稿.pptx" --source "源模板.pptx" --baseline "工作区/template-baseline.json" --report "工作区/audit.json"
```

仅获准改页数时添加--expected-pages。检查裁剪/组合缩放后的图片宽高比（默认>5%警告、>20%错误）、文本框bbox交集候选（>1平方pt且>1%小框）、低DPI、越界、内部关系和动画目标等。复核所有warning/skip，不把bbox相交等同字形遮挡，不把无错误当视觉通过。
3. 用目标软件实际打开最终文件。全部页面逐页2倍渲染：基准宽1280、高按页面比例；至少2560宽，16:9为2560×1440。包含封面、目录、过渡和结束页，禁止总览缩略图或抽查代替。
4. 运行 `review_deck.py init FINAL --output REVIEW`，每页填写image_geometry/text_occlusion/readability/content_alignment四项的pass/needs_fix/not_checked与实际观察note、渲染图路径与hash、actual_scale_checked和目标软件验证。
5. 按基准实际显示尺度检查关键内容可读性，不能只放大检查。运行 `review_deck.py check FINAL --checklist REVIEW`；漏页、未检查、需改、低分辨率、文件过期或未验目标软件不能称完成。
6. 修改最终文件后重渲染受影响页并重新绑定记录；未变化页迁移须有依据，不允许只改hash保留全部pass。

## 7. 交付与能力边界

交付成品、适配修改摘要、来源/验收必要记录和未解决项，说明哪些沿用、哪些重排、为何调整。只审查模式不修改PPT；不得顺带编辑其他稿。

所有校验只覆盖可确定的字段/几何和记录一致性。没有自动语义排版器、槽位提取器或计划驱动PPT构建器；不会自动识别图源、判断科学真伪、证明用户真的批准或检查者真的看图。不自动生成pass，不承诺包ZIP有效就代表PowerPoint可打开。

资源：scripts/template_mapping.py（参考页—成品页功能映射与对照关卡）；scripts/adaptation_gate.py（逐页适配关卡）；scripts/research_plan.py（证据计划）；scripts/audit_deck.py（结构几何，需python-pptx/Pillow）；scripts/review_deck.py（逐页记录，需python-pptx/Pillow）；references/adaptation-policy.md、research-scenarios.md、pitfalls.md。执行前查看各脚本--help，参数以实际接口为准。
