# research-ppt-adaptive

> 科研 PPT 的自适应模板仿写技能：**沿用模板的视觉体系，但不硬套模板的版式结构。**

面向开题报告、毕业答辩、组会汇报、项目申报四类科研场景。它要解决的核心问题不是"怎么把内容塞进模板"，而是**"这一页的内容，模板到底能不能装得下；装不下时该怎么改"**。

---

## 为什么需要它

大多数"套模板"的做法会这样工作：打开模板 → 数一数每页有几个图槽 → 把素材一个个填进去 → 放不下就缩小。

结果就是科研汇报里最常见的一类废页：

- 一张整版多面板 Figure 被压成 3 cm 宽，坐标轴完全不可读；
- 三栏并列的工艺流程被用来装因果链，读者找不到先后关系；
- 六宫格被硬塞进六个不同层级的对象（三个是填料、三个是基体），分类逻辑被抹平；
- 为了填满第四个图槽，从别处找一张"看起来相关"的图，其实不支持本页论点。

这个技能把上面每一条都变成**可以阻断交付的检查项**，而不是"建议注意"。

## 设计原则

按优先级排序，冲突时上层覆盖下层：

1. **科研真实性与用户约束** —— 已完成的不能写成计划，文献不能写成自己的结果
2. **论证关系与可读性** —— 结论先成立，图要读得清
3. **模板视觉体系** —— 母版、配色、字体层级、页眉标识
4. **网格对称与装饰** —— 最不重要，可删可改

关键区分：**视觉风格保真 ≠ 布局保真。** 保留母版配色和字体，不等于保留"必须四栏""必须六图"。六宫格、三栏、五节点时间线都不是模板的身份特征。

## 工作流程

```
0. 定场景 / 模式 / 边界
      ↓
1. 内容先行：每页先写 论点 → 证据 → 结论，再去找模板页
      ↓
2. 参考页功能映射：参考第 N 页是"分类矩阵"还是"方案比较"？
      ↓
3. 逐页适配决策：reuse / adjust / redesign / split / hold
      ↓
4. 代表页试制 → 单独渲染 → 检查 → 再批量铺开
      ↓
5. 素材核验与安全编辑
      ↓
6. 分层验收：机器审计 + 全页 2 倍渲染 + 逐页四项记录
```

### 五种适配决策

| 决策 | 什么时候用 |
|---|---|
| `reuse` | 结构、容量、证据比例都相符，直接沿用 |
| `adjust` | 论证结构相符，只调图位、栏宽、文字量、装饰 |
| `redesign` | 信息关系不符，在同一视觉体系内重排内容区 |
| `split` | 单页无法读清，**需明确授权**后拆页 |
| `hold` | 关键来源、结构许可或可行布局缺失，暂停该页 |

### 硬套停止条件

出现以下任一情况，必须停下来改结构，而不是继续缩：

- 关键图例 / 坐标不可读
- 必须裁掉证据才能填进图槽
- 并列布局被用来装因果流程
- 对称版式拆散了必要的对照关系
- 缺素材而遗留旧课题的图
- 持续缩字 / 压图 / 叠框

> 几何审计没有报错，**不能**推翻上面任何一条。

## 页面功能分类

技能要求逐页登记参考页与成品页的功能，而不是只写"研究现状""研究内容"：

`cover` `agenda` `problem` `comparison` `classification` `process` `timeline` `system_diagram` `result` `plan` `closing` `other`

`reuse` 只在**参考功能 = 内容功能**且 `semantic_fit = fit` 时才允许。功能不一致却标 `reuse` 会被关卡拦下。

## 脚本

| 脚本 | 作用 |
|---|---|
| `scripts/audit_deck.py` | 结构几何审计：越界、图片宽高比偏差、文本框 bbox 交集候选、低 DPI、内部关系、动画目标残留 |
| `scripts/review_deck.py` | 逐页视觉验收记录：图片几何 / 文字遮挡 / 可读性 / 内容对应四项 |
| `scripts/research_plan.py` | 科研计划与证据登记：证据类型、文献引用、禁用来源与派生祖先 |
| `scripts/adaptation_gate.py` | 逐页适配关卡：决策、授权、代表页、最终阶段渲染路径 |
| `scripts/template_mapping.py` | 参考页—成品页功能映射与参考稿对照关卡 |

五个脚本都是**只读检查器**，不生成、不渲染、不修改 PPT。它们校验的是"记录是否完整、是否自相矛盾"，不是"版式是否好看"。

## 安装

这个技能有两种使用方式。

### 方式一：作为 WorkBuddy / Claude 技能

把整个目录放到技能目录下：

```bash
# 用户级（所有项目可用）
~/.workbuddy/skills/research-ppt-adaptive/

# 或项目级
<项目>/.workbuddy/skills/research-ppt-adaptive/
```

目录结构保持原样即可，`SKILL.md` 是入口。

### 方式二：只用脚本

不需要技能机制，直接把 `scripts/` 里的文件当普通 Python 工具用：

```bash
python scripts/audit_deck.py "deck.pptx" --report "audit.json"
python scripts/review_deck.py init deck.pptx --output review.json
python scripts/adaptation_gate.py init --scenario proposal --output plan.json
python scripts/template_mapping.py init --output mapping.json
```

每个脚本都支持 `--help`，参数以实际接口为准。

### 依赖

```bash
pip install -r requirements.txt
```

- Python ≥ 3.9
- `python-pptx`（读写 pptx 结构）
- `Pillow`（图片 DPI 与像素统计）

## 快速上手

```bash
# 1. 记录源模板基线（改动前，独占创建）
python scripts/audit_deck.py template.pptx --write-baseline baseline.json

# 2. 建适配计划
python scripts/adaptation_gate.py init --scenario proposal --output plan.json

# 3. 建参考页映射
python scripts/template_mapping.py init --output mapping.json

# 4. 填完计划后过 plan 关
python scripts/adaptation_gate.py check plan.json --stage plan
python scripts/template_mapping.py check mapping.json --stage plan

# 5. 代表页做完，过 pilot 关
python scripts/adaptation_gate.py check plan.json --stage pilot

# 6. 成品出来后：机器审计 + 逐页记录
python scripts/audit_deck.py final.pptx --source template.pptx \
    --baseline baseline.json --report audit.json
python scripts/review_deck.py init final.pptx --output review.json
python scripts/review_deck.py check final.pptx --checklist review.json
```

## 测试

```bash
cd tests
python test_adaptation_gate.py
python test_research_plan.py
python test_review_deck.py
python test_template_mapping.py
python test_audit_deck_revision.py   # 含 28 项原有回归 + 24 项新增几何检查
```

当前状态：**144 项检查全部通过**（不依赖 pytest，纯 `unittest`）。

## 能力边界（重要）

这个技能明确**不做**以下事情，请不要把它当万能排版器：

- ❌ 不自动识别页面功能，不自动判断模板与成品的视觉对应 —— 功能与保真字段必须人工核实
- ❌ 不自动生成 PPT、不渲染、不做版式合成
- ❌ 不自动识别图源、不判断科学真伪
- ❌ 不能证明用户真的批准过、也不能证明检查者真的逐页看过
- ❌ 不会自动填 `pass`，不因为 ZIP 打得开就声称 PowerPoint 能打开

同时需要知道几处容易误读的地方：

- **文本框 bbox 相交 ≠ 字形真的碰撞。** 脚本报的是候选，需要人看图确认。
- **哈希未命中 ≠ 图源合规。** 裁剪、压缩、拼接后的局部仍继承原始来源。
- **总览缩略图 ≠ 逐页验收。** 必须 2 倍逐页渲染并逐页填记录。

## 路线图

- [ ] **最终文件指纹绑定** —— 把最终 PPT 的 SHA-256 同步写入 adaptation / mapping / audit / review 四份记录，任何一份对不上就阻断交付
- [ ] **高风险动作完成检查** —— `actions` 未逐项标记已执行时不允许 final 通过
- [ ] **`redesign` 有效性判定** —— 仅换图换字不算 redesign，需检出实际布局变化
- [ ] 支持 `.pptx` 之外的导出格式作为验收主体

## 相关技能

- `imitate-ppt` —— 严格模板仿写，用于"必须逐页原样复刻"的场合
- 本技能与它是互补关系，不是替代关系。**改动本技能不会影响 `imitate-ppt`。**

## License

MIT，见 [LICENSE](LICENSE)。

---

## English

**research-ppt-adaptive** is a skill for building academic presentation decks (proposal defense, thesis defense, group meeting, grant reporting) from an existing institutional template — without blindly inheriting the template's layout.

The premise: *visual identity* (master, palette, type scale, section markers) should be preserved; *layout structure* (column counts, image slots, panel grids) should be re-decided per page based on what the content actually needs to argue.

Each page gets one of five decisions — `reuse`, `adjust`, `redesign`, `split`, `hold` — plus a function label (`classification`, `comparison`, `process`, `timeline`, `system_diagram`, `result`, …). A page may only be marked `reuse` when the reference page's function matches the new content's function.

Five read-only Python checkers validate the plan, the deck geometry, and the per-page visual review records. They check *record completeness and consistency*, not taste. They do not generate slides, do not render, and do not judge scientific validity.
