---
name: report-local-html
description: >-
  美团搜索结果页本地 HTML 报告生成 Skill。用于在 phase4 问题证据标注完成后生成或重建单词明细 HTML、跨词治理 HTML
  看板；批量看板必须调用项目内确定性生成器，不得让 Agent 自由设计 HTML。只处理本地 reports/ 产物；用户需要
  NoCode 数据库看板或线上部署时，改用 phase5-report/nocode-dashboard/SKILL.md。
metadata:
  author: qianjing16
  version: "3.3"
  domain: 美团搜索结果页综合质量评估
---

# 综合评测汇总报告（泛化版）

## 定位

本 Skill 是评测工作流 phase5 的**渲染层**，不执行评测、不计算分数。**待优化问题的唯一口径是 `rating ∈ {达标, 不达标}`；只有“优秀”不作为问题呈现。**Phase4 为带合法坐标的待优化问题生成保持原图尺寸的整页红框证据图；没有坐标的评测项级待优化结论必须以文字呈现，禁止虚构红框。归一化与加权求和已在工作流 JS 侧确定性完成（避免依赖 LLM 算术）。你接收一个 JSON 结构，按本文件描述的版式生成一份合并 HTML。

---

## 输入结构（工作流传入）

```
{
  "query": "搜索词",
  "tabs": ["全部","外卖","团购"],
  "images": [ { "original":"/绝对路径/原图.png", "annotated":"/绝对路径/标注图.png" } ],  // 从文件名解析截图词与屏次
  "overall": [ { "tab":"全部", "normalizedScore":72.2, "verdict":"✅良好" }, ... ],   // 跨维度均分
  "dimensions": [
    {
      "dimension": "phase3-card_or_component-eval",          // 维度文件夹名
      "perTab": { "全部": { "raw":3, "min":-10, "max":8, "normalized":72.2, "verdict":"✅良好" }, ... },
      "skills": [ { "skill":"eval-1-...", "title":"供给呈现质量", "extra":"" }, ... ],
      "evals":  [ { "dimension":..., "skill":"eval-1-...", "units":[ { "tab":"全部","rating":"优秀","weightedScore":0,"reason":"..." }, ... ] } ]
    },
    ...
  ]
}
```

关键字段：
- `images[]`：本轮评测的原图与可选 Phase2 全量标注图绝对路径。轻量识别时全量标注图可不存在，渲染时需优雅降级。
- `overall[].normalizedScore`：该 Tab 跨所有维度的归一化均分（0-100，1 位小数）。
- `dimensions[].perTab[tab]`：该维度该 Tab 的 `raw`（加权原始分）/ `min`/`max`（该维度理论最低/最高原始分）/ `normalized`（0-100）/ `verdict`。
- `dimensions[].skills[]`：该维度各评测项的目录名、中文名 `title`、`extra`（非空表示该项评级需人工确认）。
- `dimensions[].evals[]`：该维度各评测项的 `units`，每 Tab 一条含 `rating`/`weightedScore`/`reason`；其 `details` 已经过工作流确定性验收。Phase4 回写的 `issues[].evidenceImage` 是问题证据的唯一图像来源；同一原始截图内的所有问题共用一张保持原尺寸、以红框汇总标出全部问题位置的证据图。

---

## 归一化规则（已由工作流算好，这里仅供你理解数字含义）

每个维度独立归一化，不跨维度混算：

```
raw      = 该维度该 Tab 下所有评测项 weightedScore 之和
maxRaw   = 该维度所有评测项 weight 的「最大值」之和
minRaw   = 该维度所有评测项 weight 的「最小值」之和
normalized = (raw - minRaw) / (maxRaw - minRaw) × 100   （maxRaw=minRaw 时记 0）
```

每个评测项的 `weight` 来自其 SKILL.md frontmatter（形如 `{ "优秀":1, "达标":0, "不达标":-1 }`），三级评级一律映射到 优秀/达标/不达标。原始评级若为高线/中线/低线（eval-5）或按问题数 N（eval-6），已在评测阶段完成映射。

跨维度综合分 = 该 Tab 各维度 normalized 的算术平均。

### 质量判定阈值（verdict）

| 归一化分数 | 判定 |
|---|---|
| 80-100 | ⭐ 优质 |
| 60-79 | ✅ 良好 |
| 40-59 | ⚠️ 一般 |
| 20-39 | ❗ 较差 |
| 0-19 | 🚫 极差 |

---

## 输入校验、修复边界与参数化纪律（阻断）

- Phase5 只消费已通过 Phase2 `validate_element_manifest.py`、Phase3/4 `validate_eval_results.py` 的当前批次产物；发现元素遗漏、坐标/卡片边界、业务归属或事实字段冲突时，必须回到 Phase2 修正 manifest，重新验证并重跑受影响 Phase3/4，禁止在报告数据或 HTML 中补丁掩盖。
- `repair_*` 不是报告生成的默认前置步骤，仅可执行其 docstring 明示的结构/兼容修复；不得改写评级、问题数量、事实证据或业务归属。校验未通过时停止渲染。
- 所有批量生成必须显式传入当前 `--project-dir`、隔离的 `--artifact-dir`、`--batch-name`、`--output`、`--dataset-output` 与 `--expected-business-tabs`；路径从项目级 `screenshots-out/`、`.artifacts/`、`reports/` 推导。禁止扫描全局历史目录、使用固定搜索词、机器专属绝对路径、`/tmp` 或 skill 内部 `out/` 作为通用入口。
- **业务 Tab 预期校验纪律（阻断）**：生成前必须根据当前批次已通过验收的 Phase2 清单，确定实际存在的已确认业务 `businessCode` 集合，并完整传入 `--expected-business-tabs`。生成器必须校验实际输出的业务 Tab 与该集合完全一致，且业务代码和标准名称均在允许口径内。若出现缺失、多出、未知、已废弃或名称不符的业务 Tab，必须停止生成；先追溯 Phase2 manifest 的 `ownershipScope/businessCode/businessName/classificationEvidence` 或受影响的上游评测产物，定位归类错误并修正，重新执行受影响的 Phase2 校验、Phase3/4 和报告校验后，才可重新生成。禁止在 HTML、数据集或报告聚合逻辑中临时隐藏、重命名或绕过不一致的业务 Tab。

## 固定输出契约（优先级最高）

报告样式不允许根据 Agent 偏好临时变化。先依据输入范围选择**唯一**模板，再按模板的 DOM 区块顺序、标题和交互输出；不得混用两套模板，也不得新增未定义的首页板块。

| 输入范围 | 唯一模板 | 生成方式 | 允许的输出文件名 |
|---|---|---|---|
| 一个搜索词及其截图/评测结果 | `DETAIL_V1` 单词明细模板 | 按本 Skill 的「HTML 报告版式」渲染 | `meituan_eval_report_<搜索词>[_<tag>]_<dimSlug>.html`；`dimSlug` 为各维度目录名去掉 `phase3-` 前缀和 `-eval` 后缀后以下划线连接 |
| 两个及以上搜索词，且可访问项目 `screenshots-out/` 与 `.artifacts/过程文件-评测结果与审计/` | `GOVERNANCE_DASHBOARD_V1` 跨词治理看板 | **只运行** `python3 scripts/build_experience_dashboard.py --project-dir <项目绝对路径> --artifact-dir <本轮隔离产物目录> --batch-name <批次> --expected-business-tabs <当前批次确认业务代码的逗号列表> --output <reportPath> --dataset-output <datasetPath>`；Tab 校验失败时必须先修上游归属再重跑 | `meituan_search_experience_dashboard_<批次>.html` 或用户指定的汇总报告名；同时输出 `.governance_dataset_<批次>.json` |
| 已有通过验收的 V1 治理数据集，需要对比测试新版式 | `GOVERNANCE_DASHBOARD_V2_PREVIEW` | **仅测试预览**：`python3 scripts/build_experience_dashboard_v2.py --dataset <V1数据集> --output <reportPath> --period <评测周期>` | `meituan_search_experience_dashboard_<批次>_v2-preview.html`；不生成、不改写数据集，也不替换 V1 |
| 已有通过验收的 V1 治理数据集，用户明确选择 Acme editorial 风格 | `GOVERNANCE_DASHBOARD_V3_ACME_PREVIEW` | **仅测试预览**：`python3 scripts/build_experience_dashboard_v3.py --dataset <V1数据集> --output <reportPath> --period <评测周期>` | `meituan_search_experience_dashboard_<批次>_v3-acme-preview.html`；不生成、不改写数据集，也不替换 V1/V2 |

### `GOVERNANCE_DASHBOARD_V2_PREVIEW`（新版式测试）

- V2 是用户验收中的**独立预览出口**：只读一个已通过验收的 V1 `.governance_dataset_<批次>.json`，不得扫描全局历史目录、不得重算分数/问题、不得改变 V1 HTML、数据集、工作流入口或 NoCode 契约。
- V2 固定结构：黑色顶栏（搜索 / 白皮书 / 体验标准 / 体验评测）→ 标题区（报告标题、日期/范围、详情链接、周期选择器）→ 文字业务 Tab（概览 + 当前数据集业务线）→ 概览分数/问题发现卡 + 四列业务卡 → 单业务分数/问题发现卡 + 两列问题明细卡。
- 分数卡左侧展示总分与三维度得分，右侧展示问题总数、三维度问题数及 P0/P1 分布，中间仅使用细竖线分隔；业务卡点击必须切换到对应业务 Tab；问题卡必须使用现有 `evidenceImage` 或原图，禁止虚构证据。
- V2 问题卡为两列网格；单卡左证据、右文案，标题固定为“问题N：指标名”，并展示黑底白字的维度与优先级标签、按“事实 → 结论依据 → 用户影响”固定顺序展开且不显示字段标签的问题描述，以及该问题独立的个性化优化建议。没有图片时显示“暂无截图证据”。
- V2 不得显示“待人工确认”或“待人工定位”作为重复性占位文案。确认新版式后，必须由用户明确要求，才能将其提升或合并为正式 V1；在此之前 V1 仍是唯一生产与 NoCode 输出。

### `GOVERNANCE_DASHBOARD_V3_ACME_PREVIEW`（Acme editorial 风格可选预览）

- V3 是可由用户**显式选择**的独立本地预览出口，唯一实现为 `scripts/build_experience_dashboard_v3.py`；只读已通过验收的 V1 `.governance_dataset_<批次>.json`，沿用 V2 的事实聚合、业务分组、评分、问题与证据图，不得扫描历史目录、重算或改写数据集。
- 仅当用户明确要求 `V3`、`Acme editorial`、`编辑感/档案感` 风格，或指定 `build_experience_dashboard_v3.py` 时才可选用；未指定风格时仍按输入范围选择 V1，不能自行以 V3 替代正式生产模板。
- V3 固定结构：顶部通栏导航（搜索标识；白皮书、体验标准、体验评测入口）→ 标题区（报告标题、日期/范围、详情链接、周期选择器）→ 胶囊式业务 Tab → 概览/单业务的左右双栏分数与问题发现区 → 四列业务卡 → 左证据、右问题文案的明细卡。不得改变该结构、数据口径或业务 Tab 切换行为。
- 顶部链接契约：白皮书链接为 `https://km.sankuai.com/collabpage/2771507978`；体验标准链接为 `https://km.sankuai.com/collabpage/2770196684`；标题摘要的「详情」链接为 `https://km.sankuai.com/collabpage/2772784557`；外部链接须使用 `target="_blank"` 与 `rel="noopener"`，体验评测入口为页面内 `#details`。
- V3 视觉令牌固定为暖白 `#FAF9F5`、石墨 `#141413`、陶土强调色 `#D97757`；使用 serif 标题、mono 元信息、细描边与低阴影。不得混入 V1 的紫蓝渐变玻璃态或 V2 的黑色顶栏/大圆角视觉。V3 不输出报告底部数据集/生成日期脚注。
- 问题发现区的每个维度容器必须显示该维度的真实 `P0/P1/P2` 证据计数，分别由当前作用域的 `groups[].evidence[].priority`（缺失时取组 priority，仍缺失时视为 P2）确定性汇总；不得把总数重复展示在各维度容器。
- V3 问题明细沿用本 Skill 的问题级输入契约：每条问题必须按“事实 → 结论依据 → 用户影响”的无标签连续文案展示，并附该条独立建议；不得因为复用 V2 聚合器而退化为只显示 `verdictReason` 或组级 `recommendation`。
- V3 是预览样式，不得作为工作流默认生成器、NoCode 数据源或正式 V1 替代品。用户要求提升为生产版时，必须先明确更新 `GOVERNANCE_DASHBOARD_V1` 契约并修改唯一生产入口 `scripts/build_experience_dashboard.py`。

### `GOVERNANCE_DASHBOARD_V1` 的硬性约束

- **视觉和交互基准**：`phase5-report/dashboard_renderer.py` 是 `GOVERNANCE_DASHBOARD_V1` 的已验收渲染实现；其信息架构、两级 Tab、紫蓝令牌与组件样式整合自 `meituan-eval-dashboard-style`。后续生成必须保持一致，不能因 Agent 偏好改变字体、色号、间距、圆角、动效或交互时序。
- 唯一实现来源是 `scripts/build_experience_dashboard.py` 的 `collect()`、`validate_dataset()` 与**唯一生产渲染入口** `render()`；`render()` 只委派给 `phase5-report/dashboard_renderer.py:render_dashboard()`。前者负责采集和阻断校验，后者只负责读取通过校验的数据集并渲染，二者均不得二次计算评分或补造问题/证据。生成器并行产出 HTML 看板与 `.governance_dataset_<批次>.json`。
- **渲染入口纪律（阻断）**：`main()` 只能执行 `output.write_text(render(data), ...)`。脚本内如因历史审计保留 `_render_legacy_*`、实验性渲染函数或辅助片段，它们均不得被 `main()`、工作流或手工命令调用；不得以 `render_v2`、`render_new` 等并行入口绕过 `render()`。正式版式调整只能修改 `phase5-report/dashboard_renderer.py` 及本 Skill 的对应视觉/结构条款，禁止新建第二套生产 HTML 模板。
- **版式变更流程（阻断）**：用户提出“最新版式”后，先将已确认的信息架构、文案、DOM 区块、视觉令牌和交互时序更新到本 Skill 的 `GOVERNANCE_DASHBOARD_V1` 条款，再修改 `phase5-report/dashboard_renderer.py`；生成前须静态确认 `main()` 仍调用 `render(data)`，生成后须按本 Skill 的文本验收，并额外核对首页业务 Tab、概览摘要和两类问题明细与最新条款一致。任何一个环节不一致即停止交付，修正唯一生产渲染器后重新生成。
- **变更范围纪律**：数据采集/评分/证据口径只改 `collect()`、`validate_dataset()` 或上游阶段；仅版式、文案、交互调整只改 `phase5-report/dashboard_renderer.py`。不得为解决样式问题改动 `collect()`、`validate_dataset()` 或结构化数据字段，更不得在 HTML 中重新计算或补造数据。
- **批次隔离强制要求**：批量报告必须传入只含本轮 `.eval_results_*` 的 `--artifact-dir`，并显式指定 `--batch-name` 和基于本批已确认 Phase2 清单得出的 `--expected-business-tabs`；禁止扫描全局历史产物目录后再靠关键词过滤。生成器必须校验 `queryCount == queryDetails` 数量、每个已评测词均有原图、每个**带坐标的待优化问题（达标或不达标）**均有 Phase4 整页红框证据图、治理卡证据词属于当前 `queryDetails`、实际业务 Tab 与预期业务集合及标准名称完全一致，任一失败即停止生成。业务 Tab 失败不得靠报告端过滤处理，必须回溯修正上游分类并重新校验后再生成。
- 页面固定为**两级 Tab 看板**：顶部毛玻璃导航（搜索、白皮书、体验标准、体验评测）→ 标题区（标题、副行、批次选择器）→ 第一级业务 Tab（概览 + 本批确认业务）→ 概览或单业务 Panel。第一级 Tab 是靛蓝实心胶囊激活态，同一时刻仅一个 Panel 可见。
- 概览 Panel 固定只含一个「评测总分｜问题发现」双栏摘要面板和四列业务卡网格；不得在概览展示逐条问题或第二级 Tab。摘要面板只展示数据集已给出的总体分、维度得分、问题数及 P0/P1 分布；未执行维度显示灰色「—」，不得以 0 填充或参与平均。
- 每个业务 Panel 固定顺序：同结构双栏摘要 →「问题明细」。第二级 Tab（按搜索词 / 按指标）与「问题明细」标题同一行右侧对齐；默认激活「按指标」。第二级 Tab 仅作用于所属 `.business-panel`，使用靛紫色 `#6366f1` 下划线激活态，不得影响其他业务 Panel。
- 「按搜索词」视图：以搜索词和业务 Tab 分组；左侧仅展示一张覆盖问题数最多的 Phase4 整页红框 `evidenceImage`，右侧按维度（组件/卡片 → 页面框架 → 单一元素）分块展示全部问题。相同问题图不可重复渲染。
- 「按指标」视图：按维度 + 指标分组；组头展示指标、维度标签和问题数，每条问题独立显示自己的 Phase4 整页红框 `evidenceImage`。两个视图均由同一 `groups[].evidence[]` 派生，问题数与证据必须一致。
- 业务 Tab、业务卡与业务 Panel 只能展示本批目标截图中存在至少一张 `ownershipScope=business` 且业务归属已确认的可见卡片的业务线；不得展示未知、平台、混合、零可见或历史业务。自然触底截断且仅露出标题的卡不得驱动业务展示。
- 证据图使用 `file://` 绝对路径、`loading="lazy"`、点击新标签打开大图；没有 Phase4 证据时显示“暂无截图证据”，禁止 base64、原图替代或伪造图片。**同一截图的截图级红框证据图可被该截图内所有待优化问题复用**：当 Phase4 因页面级结论无坐标（`page_region_boundary_missing`）跳过某问题时，渲染层必须从同一 `screenshot` 的其他问题中复用已有的 `evidenceImage`，确保每条待优化问题都有可视化证据，不出现空占位符。
- **问题明细回收与简洁呈现（阻断）**：Phase5 必须消费每个 `issues[]` 的 `finding.observableFact`、`finding.ruleOrThreshold`、`finding.verdictReason`、`finding.userImpact` 以及问题级 `recommendation`，并在输入校验时保证它们完整；但问题卡正文固定按“事实（含评级）→用户影响”拼接：`{observableFact}，评级为{issue.rating}。{userImpact}。`。`ruleOrThreshold` 与 `verdictReason` 作为可追溯的结构化审计事实保留在数据集内，不在问题卡重复展示，以避免阈值、计数和评级结论的复述。不呈现字段标签；不得只取 `description`、只展示评级或用笼统的指标说明代替。渲染前必须去除正文各字段末尾已有的句号、逗号、分号、问叹号，统一由拼接器补充分隔标点。若任一待优化问题缺少上述结构化事实、影响或问题级建议，必须停止 Phase5，回收给对应 Phase3/4 子代理补齐后重新验收；不得由报告端臆测截图外事实。
- **问题级个性化优化建议（阻断）**：每个待优化 `issue` 必须携带独立的 `recommendation`，以该问题的元素/卡片 ID、可见字段、坐标范围、测量值或阈值为约束，明确“调整哪个对象 + 采用何种具体动作 + 保留/收敛到何种结果”。同一指标的多条问题不得直接复用同一句建议；只有当其问题对象、可见事实、触发规则和修改动作均完全相同，才允许文本相同，并须在结果中声明可复用原因。`infer_advice()` 仅可提供按指标的建议骨架，必须与 issue 的事实字段合成后才可渲染，不能把模板原文重复输出为多条问题建议。计数、得分、待优化率、证据内容必须来自结构化输入，禁止补造。
- **文案对象引用与禁用词校验（阻断）**：`observableFact`/`description`/`recommendation` 中引用具体对象须使用 Phase3 已按「商卡N」（标准商卡独立计数）与描述性类型名称（异构模块，重复出现时独立加序号）表达的人类可读形式，不得出现内部 ID、字段名或脚本文件名；完整规则见各 Phase3 eval skill 的“问题解释统一契约”，黑名单定义见 `scripts/forbidden_copy_terms.json`，由 `validate_eval_results.py` 强制校验，Phase5 不重复维护该词表。

### 治理优先级算法（本地与 NoCode 共用，阻断）

优先级不得使用 issue 原始主观值，也不得由报告端按问题率推断。生成器须以“同一 **业务线 + 维度 + 指标**”为一个统计单元（卡型不拆票池），统计 `F=不达标票数` 与 `P=达标票数`；优秀不计票，并依序计算：

```text
F >= 2 或 P >= 4  → P0
否则，F >= 1 或 P >= 2 → P1
否则，P >= 1      → P2
否则               → 不产生问题
```

- 计算结果同时回写该组 `priority`、`priorityReason`，并覆盖组内每条 `evidence.priority` 与 `evidence.priorityReason`；所有问题级证据继承所在统计单元的优先级。
- 报告与 NoCode 按 **P0 → P1 → P2** 排序。NoCode 映射固定为 P0/high/0、P1/medium/1、P2/low/2。
- 这属于数据聚合口径，只能在 `scripts/build_experience_dashboard.py:collect()` 计算；`dashboard_renderer.py`、HTML、NoCode 前端都只能消费结果，禁止重新统计或重判。

### 像素级渲染规范（`GOVERNANCE_DASHBOARD_V1`）

本节是 `reports/meituan_eval_report_首评-单一元素_32张_最终.html` 的确定性视觉/交互规格。HTML 必须内联 CSS 与 JavaScript，不依赖外部字体、UI 框架或在线资源；证据图片允许且仅允许 `file://` 绝对路径、`loading="lazy"`、`target="_blank"` 与 `rel="noopener"`。

#### A. 全局设计令牌与画布

| 项目 | 固定值/规则 |
|---|---|
| 字体栈 | `-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif` |
| 基础字号/字色 | `14px`；主文字 `#172033` |
| 辅助文字 | `#64748b`，行高 `1.6` |
| 主色变量 | 靛蓝 `--indigo: #6366f1`；绿 `--green: #10b981`；蓝 `--blue: #60a5fa` |
| 背景 | `linear-gradient(135deg, #e8eaf6 0%, #ede9fe 35%, #dbeafe 68%, #e0f2fe 100%)`，最小高 `100vh` |
| 背景氛围球 | `::before`：`360×360px`、`#c4b5fd`、右 `-100px`、上 `80px`；`::after`：`330×330px`、`#7dd3fc`、左 `-120px`、下 `40px`；两者均为圆形、`blur(18px)`、不透明度 `.32`、`position: fixed`、不可点击 |
| 内容容器 | 最大宽 `1440px`、水平居中、内边距 `30px 24px 56px`、相对定位 |
| 统一卡片 | Hero、Panel、治理卡/详情卡使用白色 `rgba(255,255,255,.9)`、边框 `1px solid rgba(255,255,255,.8)`、圆角 `24px`、阴影 `0 18px 40px rgba(71,85,105,.12)` |

#### B. 字级、间距与结构布局

- Hero：内边距 `28px 30px`，背景 `linear-gradient(135deg, #f5f3ff, #eff6ff)`；标题/导航使用弹性布局，`justify-content: space-between`、间距 `20px`、顶部对齐。
- `h1`：`30px`、无外边距、字距 `-.8px`；`h2`：`20px`、无外边距；`h3`：`16px`、外边距 `13px 0 8px`。
- 顶层 Tab 与业务筛选器均是可折行 flex，元素间距 `8px`；每个内容视图顶部留 `20px`，非激活视图必须 `display:none`。
- Panel：内边距 `22px`、底部外边距 `18px`；标题行水平两端对齐，底部外边距 `16px`。卡片栅格：`repeat(auto-fit, minmax(320px, 1fr))`，间距 `16px`；治理卡/详情卡内边距 `18px`。
- 角标统一胶囊形：`border-radius:999px`。信息 Badge 为 `5px 9px`、`12px`、粗体，背景 `#eef2ff`、文字 `#4f46e5`。层级 Badge 同为 `5px 9px`、`12px`、白字，单一元素/组件/页面框架分别使用 `#6366f1/#10b981/#60a5fa`。

#### C. 按钮、表格和语义色

- 通用按钮/Tab：白底、文字 `#334155`、`1px solid #dbe4ff`、内边距 `10px 14px`、圆角 `14px`、`font-weight:700`、鼠标手势；`transition:.2s`。悬浮时上移 `2px`，阴影 `0 8px 18px rgba(99,102,241,.18)`。
- 顶层激活 Tab：背景/边框 `#6366f1`、白字；业务筛选激活态：背景/边框 `#f59e0b`、白字。问题明细二级 Tab 使用靛紫色 `#6366f1` 下划线与文字激活态。
- 表格为全宽、`border-collapse:separate`、`border-spacing:0`、`border-radius:16px`、裁切溢出。表头使用 `linear-gradient(135deg,#4338ca,#6366f1)`、白字、左对齐、`13px` 内边距；单元格背景 `rgba(255,255,255,.74)`、`12px` 内边距、底边 `#e8edf8`，最后一行无底线。
- 分数胶囊：最小宽 `50px`、`4px 9px`、粗体、居中；维度分 `#eef2ff/#4338ca`，总体分 `#fff1f2/#be123c`，缺失分 `#f1f5f9/#94a3b8`。待优化率 `#dc2626`、`font-weight:800`。
- 优先级：`P0=#ef4444`、`P1=#f59e0b`、`观察=#10b981`，均白字、`12px`、`4px 8px` 胶囊。卡头文字为 `#64748b`、粗体，项目间距 `9px`。卡内分数右浮、红色 `#ef4444`、`21px`。
- 根因告警块：外边距 `10px 0`、内边距 `11px 12px`、圆角 `14px`、行高 `1.55`，使用 `#fffbeb` 背景、`#fde68a` 边框、`#92400e` 文字；建议块采用 `#eff6ff/#bfdbfe/#1e40af`。不得以红色大面积背景替代。

#### D. 证据、规则与可读性细节

- `summary` 为粗体、鼠标手势、上外边距 `13px`；列表左内边距 `20px`、行高 `1.55`，每项底部间距 `8px`。
- 典型证据采用两列 Grid：`130px 1fr`、间距 `12px`、顶部对齐、顶部外边距 `12px`。缩略图固定宽 `130px`、圆角 `12px`、边框 `1px solid #dbeafe`；链接鼠标为放大镜，悬浮图像放大 `1.03` 并投影 `0 8px 18px rgba(30,64,175,.24)`，过渡 `.2s`。点击必须在新标签打开同一张原尺寸图。
- 路径/代码展示块：上外边距 `5px`、内边距 `5px`、背景 `#f8fafc`、圆角 `7px`、文字 `#475569`、`12px`，并 `word-break:break-all`。
- 体验标准链接是块级卡片：内边距 `16px`、圆角 `16px`、背景 `linear-gradient(135deg,#ede9fe,#dbeafe)`、文字 `#312e81`、粗体且无下划线。

#### E. 顶层与治理区交互（时序不可变）

1. 顶层 Tab 点击后，先移除所有 `.tab` 与 `.view` 的 `active`，再为当前按钮及其 `data-target` 对应视图添加 `active`；仅保留一个可见视图。
2. `activateBusiness(code)` 必须同时更新 `.business-tab.active` 与对应 `.business-pane.active`；`code === 'all'` 时展示业务汇总表，其他业务码时展示该业务的归因建议和证据。
3. 汇总表「查看问题」调用 `activateBusiness(code)`，激活对应业务 Tab，并以 `behavior:'smooth'`、`block:'start'` 平滑滚动到 `#governance-panel`。
4. 业务问题详情卡保持悬浮上移 `2px`；业务 Tab 的激活态为琥珀背景/边框 `#f59e0b` 与白字。

#### F. 渲染验收

- 生成结果应与基准报告在上述令牌、结构、交互和时序上保持一致；允许变化的只有结构化数据文本、数字、业务数、卡片数和证据图路径。生成前必须核验业务线集合完全由本批已确认的可见业务卡确定；任何未知、平台、混合或未涉及业务出现在汇总、筛选或治理卡中均视为验收失败。
- 不得添加外部 CDN、远端字体、第三方图表库、base64 证据图、模态图库或未定义的额外首页板块。所有动画须遵守上述 `.2s`、`.32s`、`1.45s`、`1.6s`、`420ms`、`1700ms`、`2000ms` 时序。

### 线上看板出口

本 Skill 只生成本地 HTML 与同源的 `.governance_dataset_<批次>.json`；不创建 NoCode 项目、不导入数据库、不部署。

- 若用户要求本地文件：完成本 Skill 的生成与验收后交付 `reports/` 下的 HTML 和数据集。
- 若用户要求 NoCode、线上看板或部署：本 Skill 生成数据集后，切换并交由 `phase5-report/nocode-dashboard/SKILL.md` 执行导入、展示和部署。
- 两个出口必须遵守同一份 `GOVERNANCE_DASHBOARD_V1` 的业务 Tab、双栏摘要、问题级文案、分数、计数、优先级与证据口径；NoCode 的像素级 React 布局、受控图片发布和批次选择器以 `nocode-dashboard/SKILL.md` 为唯一线上模板，不得回退为旧版汇总表/桑基图/逐词审计首页。

生成后进行以下文本验收；任一失败即不可交付：

```text
必须包含：待优化项（业务维度）、评测详情、评测规则、① 各业务线问题项汇总与待优化项归因建议、activateBusiness、business-pane、query-group、问题明细
必须不包含：业务 × 指标待优化关联、桑基图、sankey-link、sankey-tooltip、④ 高频问题跨词覆盖、⑤ 典型问题证据库、<title>
```

## `DETAIL_V1`：HTML 报告版式

生成单文件 HTML（内联 CSS，浏览器直接打开美观）。结构：

### 1. 标题与开头摘要（固定顺序）

标题必须为：`<截图词汇>｜<评测维度>｜<第X屏>`。

- 从 `images[].original` 文件名解析截图词和屏次（遵守项目截图命名）。若只有 1 个不同截图词，标题使用该词；若有多个不同词，使用 `n词`。
- 若 `dimensions[]` 只有 1 个维度，标题使用其可读中文维度名（例如 `组件/卡片维度`）；若有多个维度，使用 `n维度`。
- 屏次去重并按数值排序，展示为 `第1、2、3屏`；若无法解析，展示 `n张截图`。
- 标题下方必须依次展示：**整体得分**（各 Tab 综合分卡）、**评测项概览**、以及 **问题概要**。评分、加权分、原始计数等次要信息必须放在概览后的 `<details>` 折叠区中。
- 待优化概要按不达标、达标的顺序显示问题数、涉及评测项、涉及截图屏次和一句话结论；无待优化项时明确写“未发现待优化项”。

### 2. 维度切换与评测结论

- 当 `dimensions.length > 1`，必须渲染可切换的维度 Tab；每个 Tab 只展示该维度的评测结论。不得把多个维度的长内容连续堆叠。
- 当 `dimensions.length = 1`，不显示冗余的维度 Tab，但仍展示该维度的结论。
- 每个评测项显示评级、`reason` 和 `details.summary`；主表或卡片均可，但必须让优秀/达标/不达标一眼可辨。
- **问题配图强制要求**：任一评测结论为达标或不达标时，均作为待优化结论展示；有 `issues[]` 时逐条展示。每条带合法坐标的问题必须引用对应的 **Phase4 整页红框证据图**（`issues[].evidenceImage`）；同一截图的多个问题允许且应当复用同一张汇总红框图，渲染层需对连续相同路径去重展示。若问题涉及多个相邻对象，红框范围以 `evidenceCoord` 为准。评测项级待优化结论无 `issues[]` 或无坐标时，必须显示完整 `reason/summary` 与“无元素级证据，待人工定位”，不得伪造图片。图片可点击打开，并标注对应屏次、元素 ID、坐标、问题类型、评级、问题描述与判定依据。
- `issues[]` 为空的优秀结论不强制配图，仅显示“无问题项”。

### 3. 组件/卡片评测结论分组与切换

- **不得按截图是否有问题分组。**报告应按组件/卡片维度的评测结论分组：将达标或不达标的评测项归为“待优化结论（n）”；将优秀评测项归为“无待优化结论（n）”。
- 当同一维度下存在多个评测项时，使用 Tab 切换“有问题结论（n）”与“无问题结论（n）”；每个结论卡片保留评级、reason、summary 和问题明细。不得将结论按其命中的截图拆分。
- 有问题结论的每个 `issues[]` 仍需配对应的 Phase4 整页红框证据图；无问题结论只展示“无问题项”，不强制展示图片。
- 若有多个维度，先用维度 Tab 切换维度，再在每个维度内展示上述结论分组 Tab。整页红框证据图只使用 `file://` + `issues[].evidenceImage` 路径；证据图不可用时显示明确空态。不得使用 base64。

### 4. 全局底部
- 跨维度综合分计算明细表、每项加权分和原始计数均放在折叠区。
- 对所有 `extra` 非空的评测项统一列出「⚠️ AI 初步建议，待人工确认」提示条。
- 若某维度 `skills` 为空（该维度未发现 eval skill），该维度区块显示「未发现评测项」占位，不影响其他维度。

---

## `GOVERNANCE_DASHBOARD_V1` 结构说明（批量搜索词汇总）

当输入覆盖多个搜索词、且目标是推动业务共性治理时，除保留逐词详情外，输出一份独立的「大搜结果页体验评测看板」。看板服务于结论和治理，搜索词、截图、卡片与元素 ID 仅作为可追溯证据。具体 HTML 由固定生成器产出，本节仅解释信息口径，不是让 Agent 自行实现页面的说明。

### 固定信息架构

1. **顶部导航与标题区**：固定展示搜索标识、白皮书/体验标准/体验评测入口、标题「大搜结果页体验评测看板」、评测日期和范围、详情链接及当前批次选择器。
2. **第一级业务 Tab**：顺序为概览 → 各业务线，使用靛蓝实心胶囊激活态。概览仅提供双栏摘要和业务卡入口；业务卡与 Tab 通过同一 `activateBusiness(code)` 切换并平滑定位。
3. **单业务问题明细**：单业务 Panel 先复用双栏摘要，再由第二级 Tab 在「按搜索词」与「按指标」两种组织方式间切换。前者每词仅展示一张代表性 Phase4 红框图，后者每条问题展示各自证据图；两种视图由同一问题列表派生。
4. **问题文案和证据**：每条问题按“事实 → 结论依据 → 用户影响”渲染，并保留独立的可执行建议。证据只能引用 `evidenceImage`；不存在时明确提示暂无截图证据。

不再设置「高频问题跨词覆盖」「典型问题证据库」、桑基图或独立业务×指标关联板块，避免和两种问题分组视图重复。

### 看板交互与视觉

- 第一级 Tab 和业务卡共用 `activateBusiness(code)`：只激活对应 Panel，并以 `behavior:'smooth'` 定位到业务 Tab 栏。
- 第二级 Tab 必须通过 `tab.closest('.business-panel')` 限定作用域，只切换当前业务的 `.detail-pane`，不滚动、不影响其他业务。
- 保持紫蓝渐变、半透明白卡片、靛蓝一级 Tab、靛紫二级 Tab 的统一语言；二级 Tab 默认展示「按指标」；交互过渡统一 `.2s`。所有数量和分数仅消费上游已计算的结构化数据，禁止报告端重算或补造。

---

## 渲染约束

- 评级色块用纯色背景 + 白字评级文字（优秀=#2e7d32 绿 / 达标=#f9a825 黄 / 不达标=#c62828 红）。
- 数字保留 1 位小数。
- 表格响应式，深色标题行、斑马纹。
- 标题严格遵循 `截图词汇｜评测维度｜第X屏`，不得再使用泛化的“美团搜索结果页评测报告”标题。
- 用 Write 工具写入工作流指定的 `reportPath`。
- 不自行修改、计算或补造任何数字、问题或元素；JSON 里是什么就渲染什么。
- `details.overview`、`issues`、`distribution` 必须逐字逐数渲染输入值；禁止根据 HTML 上下文重新汇总。
- 若渲染 issues，报告面向用户展示由 Phase2 原文和类型生成的可读对象描述（例如“履约标签：「闪购」”“资质标签：「医疗资质」”），不得展示 `elementId`、`coord`、`evidenceTargetElementId`、`evidenceTargetCoord` 等内部定位字段；这些字段仅保留在 JSON 结果/治理数据集用于审计回查。`evidenceImage` 仅作为图片来源，不以路径文本展示。

---

## 返回

按工作流 REPORT_SCHEMA 返回 `reportPath` 与 `summary`（=输入 `overall` 数组，每条 tab/normalizedScore/verdict）。
