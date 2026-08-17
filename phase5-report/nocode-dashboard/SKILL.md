---
name: report-nocode-dashboard
description: >-
  美团搜索结果页治理看板的 NoCode 数据导入、页面同步、Phase4 证据发布与线上部署 Skill。
  用于发布或更新 phase5 跨词治理看板；必须以本地 .governance_dataset_<批次>.json
  和 phase5-report/SKILL.md 的 GOVERNANCE_DASHBOARD_V1 为事实源，复刻既有 NoCode 看板的
  顶部通栏、双层 Tab、摘要、证据卡、优先级和批次切换布局。
metadata:
  author: qianjing16
  version: "2.0"
  domain: 美团搜索结果页综合质量评估
---

# NoCode 治理看板部署

## 1. 定位与边界

本 Skill 是 phase5 的线上展示层，只将已验收的本地治理数据集导入 NoCode 并以固定模板展示；不执行 phase3 评测、phase4 标注，不从 HTML 反向取数，不创建第二套评分或优先级算法。

| 范围 | 唯一入口 | 产物 |
|---|---|---|
| 本地 HTML 与治理数据集 | `../SKILL.md` + `scripts/build_experience_dashboard.py` | `reports/*.html`、`.governance_dataset_<批次>.json` |
| NoCode 数据、页面、证据资源、部署 | 本 Skill | 数据库记录、`public/evidence/`、线上看板 |

- 待优化问题唯一口径为 `rating ∈ {达标, 不达标, 🟡, 🔴}`；优秀不进入问题列表。
- 本地数据集是唯一事实源。线上只能改变读取介质与 React 实现，问题文案、建议、优先级、分数、业务归属和证据图必须与同批本地报告一致。
- 不得修改受保护的 NoCode 工程文件：`vite.config.js`、`src/main.jsx/tsx`、NoCodeProvider、`tsconfig/jsonconfig` 或目录结构；只能改 `src/pages/**`、业务组件和 `public/evidence/**`。
- 后续批次必须复用当前应用 `cli-ztdzbi6vu4dmnxrf`，不得因更新数据新建风格不同的页面或项目。

## 2. 优先级数据契约（阻断）

优先级由本地生成器在“同一 **业务线 + 维度 + 指标**”统计单元内确定性计算；卡型不拆分独立票池。令 `F=不达标票数`，`P=达标票数`，优秀不计票，按以下顺序判定：

```text
F >= 2 或 P >= 4  → P0
否则，F >= 1 或 P >= 2 → P1
否则，P >= 1      → P2
否则               → 不产生问题
```

- P0、P1、P2 的展示顺序固定为 **P0 → P1 → P2**。
- 一个统计单元下的所有 `groups[].evidence[]` 必须继承该单元同一个 `priority` 和 `priorityReason`；NoCode 不得按单条问题主观重判。
- 导入映射固定为：`P0 → severity=high, priority=0`；`P1 → medium, 1`；`P2 → low, 2`。
- 概览、业务卡、业务摘要和问题列表的 P0/P1/P2 数量均统计当前 batch 的问题级 `issue_attribution` 记录；不能用指标组数量、问题率或前端猜测替代。

## 3. 固定页面模板：GOVERNANCE_DASHBOARD_V1

线上页必须复刻当前已部署的治理看板，而非旧版“汇总表 + 桑基图 + 逐词详情”的管理台。页面顺序固定为：

```text
固定顶部通栏
→ 标题/范围/批次选择区
→ 一级业务 Tab（概览 + 本批业务）
→ 概览 Panel 或单业务 Panel
→ 单业务内的“问题明细”二级 Tab（按搜索词 / 按指标）
```

不得额外展示：业务汇总表、桑基图、典型证据折叠开关、逐词审计首页、评测规则首页、数据来源页脚、高频问题跨词覆盖或第二套首页模块。

### 3.1 固定顶部通栏

- 固定在顶部：高 `56px`，`z-index:10`，半透明白 `rgba(255,255,255,.82)`，`blur(12px)` 毛玻璃，底边 `1px solid rgba(230,230,240,.8)`。
- 内层最大宽 `1180px`，左右 `32px`；左侧为深色加粗的“搜索”。
- 右侧按顺序固定为“白皮书”“体验标准”“体验评测”，间隔 `28px`。
- “白皮书”链接 `https://km.sankuai.com/collabpage/2771507978`；“体验标准”链接 `https://km.sankuai.com/collabpage/2770196684`；均新窗口打开并使用 `rel="noopener noreferrer"`。
- “体验评测”为当前页深色加粗文本，不跳离看板。

### 3.2 画布、标题与批次选择

- 页面背景为 135° 紫蓝渐变：`#e8eaf6 → #ede9fe → #dbeafe → #e0f2fe`，并保留右上蓝色、左下紫色柔和氛围光斑。
- 主内容区最大宽 `1180px`，页面顶部内边距 `104px`，左右 `32px`，底部 `48px`；字体为 `-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif`。
- 标题固定为“**大搜结果页体验评测看板**”，`32px`、`800`、深色 `#1e1b3a`。
- 标题副行固定顺序：`评测日期：{batch_date} | 评测范围：{scope} 个搜索词、组件/卡片 / 页面框架 | 详情`；“详情”链接 `https://km.sankuai.com/collabpage/2772784557`，靛蓝色。
- 当前生产口径的范围为 **32 个搜索词**。后续正式批次应从 `evaluation_batches.description` 的 `查询数=<n>` 读取；只有数据契约明确指定固定范围时才可显示固定值，禁止使用数据库行数或 `queryDetails` 行数替代。
- 标题区右上固定保留 `280px` 可搜索、不可清空的批次选择器。选项标签为：`{batch_name}（{batch_date}·{查询数}词）`；用真实 `id` 作为 value，以处理同名历史批次。
- `fetchBatches()` 固定按 `batch_date DESC, id DESC` 排序，初始选择最新批次；批次变更后必须重新加载该 `batch_id` 的全部页面数据并回到概览。

### 3.3 一级业务 Tab

- 一级导航位于标题区下方，顺序为“概览”后接当前批次确认的业务线；同一时刻仅激活一个。
- 容器为半透明白色圆角胶囊，内边距 `4px`；按钮内边距 `8px 20px`、`14px`、粗体、圆角 `999px`。
- 默认透明背景和深灰文字；激活态为实心靛蓝 `#6366f1`、白字、`0 4px 12px rgba(99,102,241,.35)` 阴影。
- 业务线集合只从当前 batch 的 `business_summary` 聚合行（`description.dimensionScores` 存在）读取；不得混入平台、未知、零可见、历史业务线。
- 概览业务卡与对应业务 Tab 调用同一个选择逻辑；进入业务页后默认激活“按指标”。

### 3.4 概览 Panel

概览只包含以下两部分，禁止插入逐条问题：

1. **左右双栏摘要**：两张半透明白卡、`24px` 圆角、柔和靛蓝阴影，左右等宽。
   - 左卡标题“评测总分”，展示大号总体分以及单一元素、组件/卡片、页面框架三个维度分；缺失维度为灰色 `—`，不得以 0 补齐。
   - 右卡标题“问题发现数”，展示当前 batch 问题级记录总数及 P0/P1/P2 标签计数。
2. **四列业务卡网格**：`repeat(4, 1fr)`、间距 `16px`。每卡依次展示业务名、总体分（`30px`）和“问题发现 N 项”及存在的 P0/P1/P2 标签。点击进入对应业务 Panel。

业务总体分和三维度分来自 `business_summary.description` 的 `overallScore/dimensionScores`；全局摘要只对当前业务汇总行已存在的数值做展示层平均，不能从问题记录倒推分数。

### 3.5 单业务 Panel

固定顺序：

1. 当前业务的同结构双栏摘要；
2. “问题明细”标题行，底部 `1px` 细分隔线；
3. 标题右侧二级 Tab：“按搜索词”“按指标”。

二级 Tab 为透明底文字，默认“按指标”激活；激活文字 `#4338ca`、粗体，底部 `2px #6366f1` 指示线。切换只影响当前业务，不影响批次或其他业务。

#### 按搜索词

- 按 `搜索词 + Tab` 分组；每组为大圆角半透明白卡。
- 卡头左侧为搜索词，右侧为 `{Tab} Tab · N 个问题`。
- 内容为左 `300px` Phase4 红框证据、右侧问题列表，间距 `22px`。
- 同一搜索词组仅展示覆盖问题最多的一张 `evidenceImage`；右侧按维度顺序“组件/卡片 → 页面框架 → 单一元素”分区展示问题。

#### 按指标

- 按“维度 + 指标”分组，并整体按 P0 → P1 → P2、再按维度和指标名排序。
- 组头展示指标名、靛蓝维度标签和问题数量。
- 组内每条问题为左 `220px` 证据、右文案的横向行；相邻行以细线分隔。
- 每条问题必须展示其自身 `evidenceImage`；没有图片时显示“暂无截图证据”，不得用原图、全量标注图或其它搜索词图片替代。

#### 问题文案

- 标题格式：按搜索词视图使用“问题N：指标名”；按指标视图使用“问题N：搜索词”。
- 旁边展示 P0/P1/P2 优先级胶囊；颜色固定：`P0 #ef4444`、`P1 #f59e0b`、`P2 #10b981`。
- 描述固定消费问题级 `finding`，按“可见事实 → 规则阈值 → 结论原因 → 用户影响”拼成无字段标签连续文案；不得退化为 group rootCause 或只显示 description。
- 紧随其后展示“优化建议”，只消费当前问题的 `recommendation`；建议块采用浅琥珀背景、左侧琥珀强调线。不同问题不能被组级建议覆盖。

## 4. 数据模型与导入

### 4.1 表职责

| 表 | 数据集来源 | 用途 |
|---|---|---|
| `evaluation_batches` | `batch/generatedAt/queryCount` | 批次选择、日期和评测范围 |
| `business_summary` | `businesses[]` | 每业务一行的分数、问题率与维度分 |
| `issue_attribution` | `groups[].evidence[]` | **每条问题证据一行**，支撑概览计数和两种问题视图 |
| `business_metric_relations` | `groups[]` | 保留可追溯关联数据；当前模板不展示桑基图 |
| `word_evaluation_details` | `queryDetails[]` | 保留完整逐词审计数据；当前首页不展示 |
| `evaluation_rules` | 指标去重 | 保留方法追溯数据；当前首页不展示 |

### 4.2 导入规则

执行：

```bash
python3 scripts/import_to_nocode.py <dataset-json> <chat-id>
```

- 每次导入必须新建 `evaluation_batches` 并使用数据库返回的真实 `batch_id` 写入所有明细表；不得复用或硬编码历史 batch_id。
- `issue_attribution` 必须是问题级写入：一个 `groups[].evidence[]` 对应一行，`issue_desc` 为完整 finding 文案，`suggestion` 为问题级 recommendation，`severity/priority` 由数据集已算好的聚合 priority 映射。
- 重复同名批次可存在，选择器必须以 id 和词数后缀区分。不得删除历史批次或过程产物。
- 导入前必须验证：`queryCount == queryDetails` 数量；每个已评测词有原图；证据所属搜索词属于本批；业务 Tab 与 Phase2 已确认集合完全一致。
- 导入后必须核验新 batch 的业务汇总、67 等实际问题行数、关系、逐词详情和规则行均使用同一个 batch_id；CLI 可读不代表浏览器 anon 可读，必须验证 RLS 只读权限。

## 5. Phase4 证据资源发布

线上浏览器不能读取本地 `file://`。必须将当前数据集使用的图片上传到 `public/evidence/`。

1. 只提取当前数据集实际引用的 `groups[].evidence[].evidenceImage` 和逐词审计需要的 `queryDetails[].screenshot`；不得混入历史批次资源。
2. 上传前说明图片数量、绝对路径范围和用途，取得用户同意；每次 `nocode send --images` 最多 5 张。
3. Phase4 同名文件必须以 `{搜索词}__{原文件名}` 重命名后发布，例如 `西瓜__1_all_issues.png`，防止多个词的 `1_all_issues.png` 覆盖。
4. 页面通过 `import.meta.env.BASE_URL + 'evidence/' + filename` 引用，不得使用 `file://`、base64、开发机绝对路径或外部不受控 URL。
5. 图片缺失只能显示明确空态；不得回退到旧批次同名图、原图或自造图片。缩略图与大图均指向同一 Phase4 红框资源，点击新标签打开。

## 6. 后续批次标准流程

1. 以当前批次隔离 artifact 运行 `scripts/build_experience_dashboard.py`，同时生成本地 HTML 和 `.governance_dataset_<批次>.json`。
2. 由生成器按第 2 节优先级算法写入 group/evidence 的 `priority` 与 `priorityReason`；禁止手改 HTML 或 NoCode 数字来改优先级。
3. 对新数据集校验业务集合、三维度分、问题级 finding/recommendation、Phase4 evidenceImage 和 P0/P1/P2 票数。
4. 若新增或变化证据图，先取得授权，上传到 `public/evidence/` 并核验文件存在。
5. 用 `scripts/import_to_nocode.py` 新建批次并导入；核验返回的真实 batch_id 贯穿所有明细。
6. 页面默认加载按 `batch_date DESC, id DESC` 排在第一的完整批次；截图核验顶部通栏、32词范围/当前批次范围、一级 Tab、概览双栏、四列业务卡、单业务二级 Tab、两种证据布局、P0/P1/P2 计数。
7. 截图通过后执行 `nocode deploy <chatId> --skillId 2981`。部署成功后只能交付 NoCode 对话页或部署 URL，不得给 sandbox render URL。

## 7. 验收清单

### 数据

- [ ] 当前 batch 的 6 张表 batch_id 一致，anon 只读可用。
- [ ] 每条 NoCode 问题记录与本地 `groups[].evidence[]` 一一对应：描述、建议、优先级、搜索词和证据文件一致。
- [ ] P0/P1/P2 遵循第 2 节固定阈值，页面按 P0→P1→P2 排序。
- [ ] 业务线仅为当前 Phase2 已确认业务，且分数不由问题数据反推。

### 布局与视觉

- [ ] 存在“搜索 / 白皮书 / 体验标准 / 体验评测”固定顶部通栏。
- [ ] 标题、副行、详情链接和右上批次选择器存在；不得出现“数据来源”脚注。
- [ ] 一级 Tab 为靛蓝胶囊，概览只含双栏摘要和四列业务卡。
- [ ] 单业务默认“按指标”；按搜索词为 300px 左图右文，按指标为 220px 左图右文。
- [ ] 页面保持紫蓝渐变、白色半透明卡片、24px 圆角和靛蓝交互语言。

### 资源与部署

- [ ] `public/evidence/` 中的图片使用 `{query}__` 前缀且与数据集映射一致。
- [ ] 缩略图可显示、可点击打开同一张大图；缺图显示明确空态。
- [ ] 已通过 `nocode screenshot <chatId>` 核验；若渲染或部署报平台异常，停止自动重试并联系 NoCode 研发。

## 当前应用

- chatId：`cli-ztdzbi6vu4dmnxrf`
- 对话页：`https://nocode.sankuai.com/#/chat?pageId=cli-ztdzbi6vu4dmnxrf`
- 部署地址：`https://cx8ehm.mynocode.host`
