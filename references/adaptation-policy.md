# 模板适配决策与停止规则

## 优先级

遵守科学真实性与用户明确约束，其次保证论证和可读性，再保留视觉身份，最后考虑网格对称与装饰。出现不可同时满足的约束时暂停冲突页并请求决策，不静默牺牲可读性或原版约束。

保持模板原文件只读。新技能独立使用本包模块，不要求修改或覆盖旧imitate-ppt。

## 三种模式

strict：仅用户明确指定时采用。发现内容与固定布局不匹配，记录hold并给出替代方案；不要宣称强行缩小的成品合格。
adaptive：默认沿用视觉风格、允许内容区适配，不自动授权增页/删页/改页序/改章节。用户说“原位替换，不动版式”时以用户要求为准。
restructure：允许提出更大重排，但必须逐项登记授权。模式名不是授权凭证。

## 参考页功能映射

在适配判断前先描述参考PPT页面的功能和布局签名，不仅记录章节名。推荐功能枚举：cover、agenda、problem、comparison、classification、process、timeline、system_diagram、result、plan、closing、other。布局签名用可核对的关系描述，例如“顶部标题+三列比较卡+底部结论条”，不能只写“参考模板页”。再描述新内容功能，判断二者fit/partial/mismatch。

建立template_page→output_page映射。每个输出内容页必须有映射；参考页不用时登记unused理由；输出页无法对应时登记unmatched理由；一页拆成多页时使用split并列出全部输出页。reuse只有在reference_function与content_function一致且semantic_fit=fit时成立。adjust/redesign可在partial时采用；mismatch应redesign、split或unmatched，不能为了保留页数标reuse。

最终对照必须同时记录visual_fidelity（视觉体系）、layout_fidelity（结构关系）、semantic_fit（内容适配）和readability。四者不是同一件事：颜色页眉保留不代表布局保留，布局保留也不代表内容适配。对照来源、页面标题和修改摘要要能定位；人工逐页核查不能由页数相同替代。

## 适配判断

逐页先问：
1. 这页是对比、因果、流程、时间演进、实测结果、概念还是讨论？模板表达的是同一种关系吗？
2. 证据需要哪些图例/坐标/对照一起出现？现有槽位比例能否完整承载？
3. 按实际放映尺度，关键读数能否读清？不要只看源像素和高倍预览。
4. 文字量能否在合理字体下容纳？有没有重复论点、模板遗留或装饰挤占？
5. 哪些调整已经授权？哪项改动会触及机构规定结构？

决定：reuse=直接沿用；adjust=局部尺寸/位置/文字量调整；redesign=同风格重排内容区；split=经授权拆页；hold=暂停。

每页记录reason（为什么）、content_type（证据/关系类型）、template_fit（适合或冲突处）、layout_strategy（怎么做）、readability_risk、actions（动作清单）、fallback（失败如何处理）、acceptance_notes（检查重点）。非reuse不能只写“优化布局”，要写能核对的动作；高风险不能选reuse。

changes登记真实变动类别及授权。拆页须同时登记split_pages，不能仅说redesign；涉及改页序/章节额外申报对应权限。机器不能识别实际PPT里未申报的变化，人工对照最终页映射不可省略。

## 典型实例

- 六宫格原放六张照片，待填六张复杂多面板Figure：不能因六张数量匹配就reuse。选关键子图并adjust，或申请拆页。不能缩到坐标看不清。
- 模板三栏并列，研究内容是"制备→驱动→验证"的先后链：评估是否应该redesign为流程；若三栏能保留明确因果也可adjust，但必须解释。
- 模板竖图槽，现有宽曲线：优先改槽或另选同风格布局，不压扁、不默认居中截掉坐标。
- 对照与实验组必须同页：即使拆页更大也不能切断对照关系；先削减冗余或用同风格大图布局。
- 模板有旧课题SEM但用户无对应图：删除旧证据并记录缺口，不能当装饰保留，也不能生成SEM补齐。
- strict且无法放下：hold，呈现“保留版式但需精简哪些内容”与“申请允许哪项调整”，等待用户选择。

## 代表页关卡

按实际稿件覆盖主要版式风险选代表页；不机械固定三页。先出代表页、渲染、按实际显示尺度检查，再得到用户确认；若用户授权自主判断，记录授权来源和实际检查，不伪造确认。approved仅为记录声明，不是能验证用户真实同意的电子签名。

用户豁免的是等待其确认，不是免做代表页和人工检查。任何豁免不得跳过来源与最终全页验收。更换模板或主要信息类型后重新评估代表页；修改计划后旧代表页记录是否仍有效必须人工判断，脚本不具备修改语义追踪。

## 脚本与人工职责

adaptation_gate.py读取同一份证据计划，额外检查模式、逐页适配字段、权限、暂停项和代表页状态；plan阶段允许代表页尚未批准，pilot/final阶段不允许。init生成待填写骨架，不自动放行。

具体记录接口：
- 顶层mode取strict/adaptive/restructure，默认adaptive；authorization记录local_layout（默认true）、split_pages/reorder_pages/chapter_changes（默认false）及source。扩大默认权限须填真实授权来源。
- 顶层changes记录实际变化类别，值为上述四种权限名的数组。adjust/redesign必须声明local_layout，split必须声明split_pages；strict不接受布局/结构更改声明。
- 每页adaptation记录decision、reason、content_type、template_fit、layout_strategy、readability_risk、actions、fallback、acceptance_notes。
- 顶层pilot记录required、representative_pages、status、note、render_paths。pilot/final阶段渲染路径须与代表页按顺序一一对应且不重复。路径编码验证不能证明画面与页码对应，须人工核对。
- pilot.required=false仅用于记录用户明确不需等待其确认，顶层另填pilot_exemption_reason和pilot_exemption_source；仍必须完成代表页制作、检查和渲染记录。

校验不能证明template_fit判断合理、图真的可读、动作真正执行、授权声明真实或渲染图对应计划页面。不要把字段写满视为科学设计通过。最终仍执行机器几何审计与全页逐张四项视觉记录。
