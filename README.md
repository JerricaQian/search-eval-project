# 美团搜索结果页标准化评测 Agent

这是一个面向美团搜索结果页的、可复用的评测系统。1.0 把用户任务拆成两个独立职责：**Screenshot Agent** 负责获取或发现截图，**Evaluation Agent** 负责将已确认截图依次完成识别、评测、证据与报告。Workflow 只做按需询问和调度，不承载评分逻辑。

它既支持“一次完成截图和评测”，也支持“今天截图、数天后再选图评测”。底层仍保留严格且可追溯的事实链：**截图 → Phase2 轻量识别 → 多维度评测 → 问题证据 → HTML 报告**。

## 如何提出评测请求

项目使用一个 Workflow 入口处理所有请求，而不是根据图片直接给出人工评分。收到请求后，系统会先确认任务类型、输入范围、缺失参数和预计产物，再开始执行。

| 你的目标 | 可以这样说 | 系统将交付 |
|---|---|---|
| 评测一张已有图 | “评测这张截图：`<绝对路径>`” | 单图 manifest、三维度评测结果、问题证据和本地 HTML 报告 |
| 评测多张图或一个目录 | “评测这个目录中的截图：`<绝对路径>`” | 先返回自动发现的截图组，确认后按组评测并生成汇总交付物 |
| 自动截图再评测 | “搜索 `<词>`，截图 `<Tab>` 的第 `<屏>` 屏后评测” | 先交付并校验截图；确认维度和报告出口后生成评测报告 |
| 只截图 | “只截图，不评测：搜索 `<词>`，`<Tab>`，第 `<屏>` 屏” | 项目级 `screenshots/` 中可复用的截图 |
| 复核已有报告 | “复核报告 `<路径>` 的 OCR/证据/评分” | 对输入、manifest、阶段结果和证据的可追溯复核；必要时生成新批次重跑结果 |
| 了解能力 | “这个项目能评什么？” | 支持的输入、评测维度、报告与限制说明；不会运行评测 |

外部图片会保留原件，并以可追溯副本纳入项目级 `screenshots/` 后再进入评测。能力咨询和缺少必要输入的请求都会得到明确回复，但不会被静默改成主观截图点评。

项目外目录可用跨宿主前置入口接入。它会保留源文件，并按原文件名直接复制到
`screenshots/`；它只负责复制与发现，不伪装为能替代宿主 LLM 的评测器：

```bash
python3 workflow/eval_cli.py prepare-evaluate \
  --project-dir "$(pwd)" \
  --source-dir "/path/to/external/screenshots"
```

不带 `--query` 时会返回可选分组；加入 `--query 库迪` 后会返回
`MEITUAN_EVAL_HANDOFF_V1.workflowArgs`，可交给支持 `workflow/meituan_eval_workflow.js`
的宿主继续执行。外部文件 `库迪_全部_1_副本.png` 会在项目中保留为
`screenshots/库迪_全部_1_副本.png`；若同名目标已存在但字节不同，复制会追加递增的副本序号而不覆盖，并将其作为独立截图处理。

## 1.0 架构与优势

```text
用户
  └─ Workflow（只询问必要参数、编排、批次控制）
       ├─ Screenshot Agent（Phase1：截图 / 已有截图发现）
       └─ Evaluation Agent（Phase2 → Phase3 → Phase4 → Phase5）
```

| 优势 | 具体表现 |
|---|---|
| 截图与评测解耦 | 已有截图可单独发现、选择和评测；不需要重新连接设备或重复输入搜索词。 |
| 参数按需收集 | 仅截图不询问维度和报告；仅评测不询问搜索词、Tab、屏数或设备。 |
| 职责可维护 | Screenshot Agent 不碰评测事实；Evaluation Agent 不负责设备和截图操作；Workflow 不参与业务判断。 |
| 结果可追溯 | 每张图独立 manifest，逐阶段校验，过程文件按批次与搜索词隔离保留。 |
| 评测可扩展 | 19 个 Skill 按目录自动发现；增加评测项无需修改 Workflow。 |

> 1.0 暂不包含自动反思或经验库。所有宿主共享的输入运行前检查由
> `workflow/eval_cli.py` 完成；现有确定性校验器仍由 Evaluation Agent 在 Phase2～4 内严格执行。

---

## 三个评测维度

| 维度目录 | 含义 | 状态 |
|---|---|---|
| `phase3-card_or_component-eval/` | 卡片/组件级评测（8 项：供给/视觉秩序/色彩/元素复杂度/信息层级/分区/真实性/冗余） | ✅ 已就绪 |
| `phase3-single_element-eval/` | 单元素级评测（4 项：供给质量/色彩逻辑/元素规范/信息真实性） | ✅ 已就绪 |
| `phase3-page_framework-eval/` | 页面框架级评测（7 项：供给模块完整性/视觉秩序/页面色彩/静态组件复杂度/浏览流畅度/信息可比性/信息冗余） | ✅ 已就绪 |

每个维度目录下放 `eval-skills/eval-X-<name>/SKILL.md`，工作流会自动扫描并读取其 frontmatter（见下文）。新增维度或评测项**无需改工作流**。

---

## 快速开始

### 第 1 步：准备项目与环境

整个 `search-eval-project/` 可放在任意目录下（不再要求固定为 `~/Desktop/search-eval-project/`）。工作流不再提供 `projectDir` 兜底默认值，**运行时必须显式传入 `projectDir` 为项目实际所在的绝对路径**，否则会直接报错阻断。

每台机器首次运行：

```bash
# 评已有截图：检查 Python、Node、图像依赖和项目结构
bash ~/Desktop/search-eval-project/setup.sh

# 现场截图：额外检查 Android 真机、ADBKeyboard 与美团 App
bash ~/Desktop/search-eval-project/setup.sh --with-device

# 要求 Phase2 PaddleOCR 运行时和本地模型就绪
bash ~/Desktop/search-eval-project/setup.sh --with-ocr
```
默认模式不要求连接手机，适合复用已有截图；现场截图时才需要 Android 真机。若缺 Python 图像依赖，在项目根目录执行 `python3 -m pip install -r requirements.txt`。

### 第 2 步：选择任务模式

先让用户选择一项；不要提前询问其他模式才需要的参数。

| 用户选择 | 系统执行 | 此时才询问 |
|---|---|---|
| **仅自动化截图** | Workflow → Screenshot Agent | 搜索词、Tab、屏数 |
| **仅评测已有截图** | Workflow → Screenshot Agent（只读发现）→ Evaluation Agent | 截图范围、评测维度、报告出口 |
| **自动化截图 + 评测** | Workflow → Screenshot Agent → Evaluation Agent | 先问搜索词、Tab、屏数；截图成功后才问维度、报告出口 |

**仅评测已有截图**时，系统先扫描 `screenshots/` 并返回截图组；用户选择文件后，搜索词、Tab、屏号从命名规则 `<搜索词>_<Tab>_<屏>.png` 自动推导。用户不必重复填写这些信息。

### 第 3 步：按模式调用 Workflow

Workflow 是依赖宿主 API 的 DSL，不能直接通过 `node` 执行。`workflow/eval_cli.py`
提供可执行的复制、发现和宿主交接层，但完整的 Phase3 多模态判断仍需要一个
支持 `agent/parallel/phase/log` 注入的宿主。完整调用方式见 [`.claude/skills/run-eval.md`](.claude/skills/run-eval.md)。常用参数如下：

```json
// 仅截图
{
  "mode": "capture_only",
  "projectDir": "<项目绝对路径>",
  "query": "库迪",
  "tabs": ["全部", "外卖"],
  "screens": ["1", "2"]
}
```

```json
// 仅评测：第一轮发现截图
{
  "mode": "evaluate_only",
  "projectDir": "<项目绝对路径>",
  "discoveryOnly": true
}
```

```json
// 仅评测：用户选图后执行
{
  "mode": "evaluate_only",
  "projectDir": "<项目绝对路径>",
  "selectedScreenshots": ["<截图绝对路径>"],
  "dimensions": ["phase3-card_or_component-eval"],
  "reportOutlet": "local_html"
}
```

显式 `capture_and_evaluate` 会在截图成功后返回 `awaiting_evaluation_config`，然后再由用户确认评测维度与报告出口，避免无效截图进入评测。

### Phase2 本地 OCR（按需安装）

Phase2 对每张截图独立运行 `phase2-card-annotation/scripts/run_phase2_recognition.py`，先以本地 OCR、OpenCV、卡型契约和确定性 hooks 产出候选，再按黄金样本的结构范例对当前图片执行全量视觉校准，生成该图自己的 `elements.json`。它不读取 OCR 置信度决定字段，也不复制黄金文字或坐标。初次整页使用 Tesseract；门控失败时主入口自动执行一次卡内有界 Paddle 重识别（默认 2 线程），不会运行整页 Paddle：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/setup_phase2_ocr.py --all
bash setup.sh --with-ocr
```

`setup_phase2_ocr.py --all` 使用执行该命令的同一个 Python 安装 PaddlePaddle/PaddleOCR，
从 Paddle 官方 BOS 模型源下载固定的 PP-OCRv5 server 检测与识别模型，校验 SHA-256，
随后初始化模型并完成一次本地推理冒烟测试。模型保存在 gitignored 的
`phase2-card-annotation/models/paddleocr/`，因此 `git clone` 本身不会携带模型。
只检查、不安装时执行 `.venv/bin/python scripts/setup_phase2_ocr.py --check`。

生产识别允许 Paddle 不可用时回退 Tesseract，但每个裁剪都会记录
`requestedBackend`、`actualBackend` 和 `fallbackReason`。需要确认本轮确实由 Paddle
执行时，为 `run_phase2_recognition.py` 追加 `--require-bounded-paddleocr`；任何裁剪
发生回退都会阻断该轮。

没有本地 OCR 时，提取器会把能力缺口记录为 `missingCapabilities`，不得据此认定文本或图片缺失。`uncertain` 不创建人工复核任务，也不能作为“不达标”、缺失或“优秀”的依据。

**手机端（仅现场截图）**：USB 连电脑 + 「传输文件」模式 + 开启 USB 调试 + 安装并登录美团 App。
**macOS 权限（关键）**：系统设置 → 隐私与安全性 → 完全磁盘访问权限 → 添加 CatPaw → **完全退出并重启应用**。不做这步评测子进程可能读不到桌面截图，报告会全空。

选择 `reportOutlet=nocode` 时，也必须先完成本地 HTML 和治理数据集；线上导入与证据上传仍按 `phase5-report/nocode-dashboard/SKILL.md` 在获得授权后执行。

---

## 目录结构

```
search-eval-project/
├── README.md                       # 本文件
├── CLAUDE.md                       # 工作流声明（阶段/目录/数据流向，每次会话加载）
├── setup.sh                        # 跨机器环境检查（可选 --with-device 检查真机）
├── requirements.txt                # Python 图像/YAML 依赖
├── requirements-ocr.txt            # 可选 PaddlePaddle/PaddleOCR 运行时范围
├── scripts/setup_phase2_ocr.py      # 官方模型下载、哈希校验和本地推理健康检查
├── .gitignore                      # 代码与运行产物隔离规则
├── ADBKeyboard.apk                 # 中文输入法（现场截图时使用）
├── .claude/
│   ├── agents/screenshot-agent.md   # 只负责截图或发现已有截图
│   ├── agents/evaluation-agent.md   # 对外评测入口，内部执行 Phase2～5
│   ├── agents/phase2345-query-pipeline.md # Evaluation Agent 的既有内部流水线
│   ├── contracts/                   # Workflow 与 Agent 的输入/输出契约
│   └── skills/run-eval.md           # 1.0 三模式调用说明
├── phase1-screenshot/               # phase1 共享截图能力
│   ├── SKILL.md                    # 截图流程+坐标+陷阱表
│   └── scripts/{run_scroll.sh, loop_screenshot.sh}
├── phase2-card-annotation/         # phase2 本地 CV/OCR、卡型契约、整页门控与一图一 JSON
│   ├── SKILL.md / scripts/ / references/ / scenes/
├── phase3-card_or_component-eval/         # 维度1：卡片/组件（8 项 eval skill）
│   └── eval-skills/eval-1~8/SKILL.md
├── phase3-single_element-eval/            # 维度2：单元素（4 项 eval skill）
│   └── eval-skills/eval-1~4/SKILL.md
├── phase3-page_framework-eval/            # 维度3：页面框架（7 项 eval skill）
│   └── eval-skills/eval-1~7/SKILL.md
├── phase4-issue-evidence/                 # Phase4：为问题生成整页红框证据图
│   └── SKILL.md
├── phase5-report/                         # Phase5：本地报告、治理数据集与线上看板出口
│   ├── SKILL.md                            # 本地 HTML / GOVERNANCE_DASHBOARD_V1
│   └── nocode-dashboard/SKILL.md           # NoCode 导入、证据图发布与部署
├── scripts/
│   ├── discover_screenshot_groups.py # 只读聚合可复用截图
│   ├── build_experience_dashboard.py       # 批量本地治理看板 + 数据集生成器
│   └── import_to_nocode.py                 # 治理数据集导入 NoCode
├── workflow/
│   └── meituan_eval_workflow.js    # 1.0 模式路由与 Agent 编排
├── screenshots/                    # phase1 截图输出 / phase2 输入
├── screenshots-out/                # phase2 每图元素清单；phase4 问题证据图
├── .artifacts/过程文件-评测结果与审计/ # 按批次、搜索词、阶段隔离的评测结果与审计
└── reports/                        # phase5 HTML 与批量治理数据集输出
```

> **对外与对内数据流**：Screenshot Agent 可把新截图写入 `screenshots/`，或只读发现该目录中的历史截图；Evaluation Agent 消费用户已选中的截图，按 `screenshots/` ──Phase2──▶ `screenshots-out/` ──Phase3──▶ `.artifacts/过程文件-评测结果与审计/` ──Phase4──▶ `screenshots-out/evidence/` ──Phase5──▶ `reports/` 输出结果。Phase3 只消费与当前截图对应且 `recognition.phase3Ready=true` 的清单；批量 `index.json` 不是事实源。详见 `CLAUDE.md`。

---

## Workflow 参数（1.0）

### 模式路由参数

| 参数 | 适用模式 | 说明 |
|---|---|---|
| `mode` | 全部 | 必填语义：`capture_only`、`evaluate_only`、`capture_and_evaluate`。未传时兼容旧的 `skipScreenshot` 调用。 |
| `projectDir` | 全部 | 必填，项目根绝对路径。 |
| `discoveryOnly` | 仅评测已有截图 | `true` 时只读扫描 `screenshots/` 并返回截图组，不进入评测。 |
| `selectedScreenshots` | 仅评测已有截图 | 用户从截图组中选择的一组绝对路径。系统从名称推导搜索词。 |
| `query` | 仅截图、截图+评测 | 搜索词；仅评测已有截图时由截图名称推导，除非名称无法解析。 |
| `tabs` / `screens` | 仅截图、截图+评测 | 要截图的 Tab 与屏号。 |
| `dimensions` | 需要评测时 | 要执行的维度目录数组；默认组件/卡片维度。 |
| `reportOutlet` | 需要评测时 | `local_html` 或 `nocode`；NoCode 仍需后续授权。 |

### Evaluation Agent 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `phase2Mode` | `lightweight` | 生产路径只允许本地轻量识别。 |
| `annotate` | `true` | 默认执行 Phase2；仅在已有单图 manifest 已验证时才可显式跳过。 |
| `granularity` | `element` | 固定元素级统一事实源，组件与页面维度再按 Skill 聚合。 |
| `screenshotDir` | `projectDir/screenshots` | Screenshot Agent 的输出与发现目录，也是 Phase2 输入。 |
| `annotatedDir` | `projectDir/screenshots-out` | 单图 manifest 和 Phase4 证据目录。 |
| `reportDir` | `projectDir/reports` | 最终报告目录。 |
| `batchId` / `tag` | `单词运行` / 空 | 隔离批次和同词复跑产物。 |

`skipScreenshot` 是兼容旧调用的参数；新任务应使用 `mode` 表达意图。批量截图仍可直接运行 `phase1-screenshot/scripts/loop_screenshot.sh`。

---

## eval skill frontmatter 约定（新增评测项/新维度必读）

每个 `eval-skills/eval-X-<name>/SKILL.md` 的 frontmatter 必须声明评测元数据，工作流靠它自动发现与计分：

```yaml
---
name: eval-X-xxx
title: 中文名
weight: { "优秀": 1, "达标": 0, "不达标": -1 }
aggregate: "聚合到 Tab 级的规则文本"
extra: ""
description: ...
metadata: ...
---
```

- `weight`：三级评级加权分，**一律**按 优秀/达标/不达标 键值。原始评级若为其他分档（如高线/中线/低线、按问题数 N），在 skill 正文 / `aggregate` 里说明映射，输出 schema 仍是三级。
- `aggregate`：把细颗粒度评级聚合到 Tab 级的规则（评测 agent 直接读）。
- `extra`：可空。非空内容会作为该项的额外说明注入评测 prompt，并在报告里标「AI 初步建议，待人工确认」徽标。

新增 `phase3-single_element-eval` / `phase3-page_framework-eval` 的评测项时，在对应维度 `eval-skills/` 下建 `eval-X-<name>/SKILL.md` 即可，工作流下次运行自动识别。

---

## Evaluation Agent 内部的五阶段事实链

Workflow 的三模式只决定是否调用 Screenshot Agent，以及何时调用 Evaluation Agent；一旦进入 Evaluation Agent，以下五阶段顺序、事实来源和校验规则不变：

1. **① 截图**：ADB 现场截图或复用已有图（9 张/词）。设备离线守卫，避免 0 字节覆盖。
2. **② Phase2 轻量识别（默认）**：默认 `annotate=true`、`phase2Mode=lightweight`，对 `screenshots/` 中每张图分别产出一个元素清单及审计到 `screenshots-out/`。每个清单都必须通过整页门控和 `validate_element_manifest.py`，才可进入评测。
3. **③ 评测**：先自动发现所选维度的全部 eval skill（读 frontmatter），再按清单及其结构化事实评测，每项按 `aggregate` 聚合到 Tab 级评级 + 加权分，并将原始结果和审计写入当前批次 `.artifacts/过程文件-评测结果与审计/<batch>/<query>/results/`。
4. **④ 问题证据**：只消费已通过 Phase3 校验的待优化问题。`phase3-single_element-eval` 保留元素级判定与精确定位，但红框展示所属完整组件/商卡上下文，并回写 `evidenceTargetElementId`、`evidenceTargetCoord`；组件/卡片维度同样框选完整聚合区块。生成原尺寸整页红框图并回写 `evidenceImage` 后，以 `validate_eval_results.py --require-evidence` 再次验收。
5. **⑤ 报告**：仅消费已通过 Phase2、Phase3 与 Phase4 验收的结果；工作流 JS 侧按每维度 weight 的 min/max 做归一化（确定性，不靠 LLM 算术），`phase5-report` 渲染本地合并 HTML。两个及以上搜索词的跨词治理场景必须运行 `scripts/build_experience_dashboard.py`，并显式传入当前 `--artifact-dir`、`--batch-name`，确定性输出 `GOVERNANCE_DASHBOARD_V1` 本地看板与同批 `.governance_dataset_<批次>.json`；该看板固定为顶部导航 → 标题区 → 概览/业务两级 Tab，其中概览展示双栏摘要与业务入口，单业务按搜索词或按指标浏览问题明细与证据。

> **1.0 的确认规则**：仅截图只确认搜索词、Tab 和屏数；仅评测只确认截图范围、评测维度和报告出口；截图+评测在截图成功后才确认评测维度和报告出口。Phase2 默认 lightweight，不作为每次任务的额外选择。

---

## 批量治理看板与 NoCode 部署（可选）

当需要跨两个及以上搜索词汇总治理时，先用 `scripts/build_experience_dashboard.py` 生成本地 `GOVERNANCE_DASHBOARD_V1` HTML 与同批 `.governance_dataset_<批次>.json`；HTML 与数据集必须同批次，且前端不重新计算分数或问题率。

若需上线，改用 `phase5-report/nocode-dashboard/SKILL.md`：导入脚本以新建批次返回的真实 `batch_id` 关联六张看板表；上线前需验证浏览器匿名角色能读取当前批次。典型证据来自项目根 `screenshots-out/evidence/` 的 Phase4 整页红框图；线上页面不能读取本机 `file://` 路径，必须在取得用户授权后上传实际引用图片到 NoCode 工程的 `public/evidence/`，以 `/evidence/<原文件名>` 展示缩略图并点击打开大图。

> NoCode 页面是本地治理看板的数据库驱动复刻，必须使用相同的 Hero、三个顶层 Tab、七列汇总、三种维度色、筛选/定位交互和统计口径；不得新增或恢复“高频问题跨词覆盖”“典型问题证据库”等独立首页区块。

---

## 统一元素口径（识别 → 评测 的关键机制）

同一张截图，不同评测 skill 若各自拆分元素，元素总数会不一致。本工作流通过“每张截图一个 Phase2 元素清单”解决：

1. **Phase2 轻量识别（默认）**对每张截图产出独立页面元素清单：`<annotatedDir>/elements_<截图文件名>.json`。结构包含 `cards[].regions[].elements[]`、`recognition`、`pageFacts`、`pageFactInventory`、`relations`；多图不得合并进一个 JSON。
2. 每个清单每次新建、复用或修订后都必须通过 `validate_element_manifest.py` 与对应 audit；任一截图未通过即按整页阻断，不能把该截图送入 Phase3。
3. **评测 phase** 把清单路径 + 确定性计数脚本注入每个评测 agent prompt。单元素项的 `overview.total` 必须等于脚本输出；组件/页面项按各 Skill 的 `aggregate` 聚合，并保留 `evidence.sourceManifestTotal` 追溯，禁止人工重拆事实对象。
4. `isExcluded=true` 的元素（商家头图/营销大图/金刚 icon 等）不计入元素总数也不评测；`uncertain` 事实不能被当作 UI 缺失、错字或违规依据。

> **复用已有清单**：Phase2 按截图逐一审核对应 `elements_<截图文件名>.json`；仅确定性校验通过才复用。批量 `index.json` 只能帮助定位文件，不能替代任何单图清单。

---

## 确定性校验闸门与修复边界

以下校验器是工作流阻断闸门，不是可选检查：

| 阶段 | 必经校验 | 未通过时的处理 |
|---|---|---|
| Phase2 | `scripts/validate_element_manifest.py` | 修正统一清单及识别审计后重新验收；禁止把事实补丁写入下游结果。 |
| Phase3 | `scripts/validate_eval_results.py` | 修正评测证据、计数或回退 Phase2 复核；不得直接进入 Phase4/5。 |
| Phase4 | `scripts/validate_eval_results.py --require-evidence` | 补齐由合法 Phase2 坐标解析出的证据，或回退上游事实源；禁止伪造红框。 |
| Phase5 | 消费最终 `evalAudit.valid=true` 且 `phase2ReviewRequired=false` 的结果 | 只渲染验收产物，不重算分数、评级、计数或问题。 |

`repair_*` 脚本不是默认步骤，仅可做其 docstring 明示的结构/兼容修复；任何评级、问题数量、坐标边界、可见原文、业务归属或视觉事实变化，必须回到 Phase2/Phase3 正式流程。涉及色彩、样式复杂度、分区边界与页面排除统计的评测项，必须优先运行对应确定性测量脚本，并在 `assessmentRows.measurement` 保留工具、产物和输入参数；LLM 只解释脚本未覆盖的语义，不能目视改写脚本阈值结论。

---

## 模型选择

Evaluation Agent 将 Phase2 与后续阶段严格隔离：Phase2 使用本地 CV/OCR 加当前图片全量视觉复核来校准 manifest，视觉模型只依据当前像素，禁止注入黄金字段或语言猜写；Phase3/4 只能消费通过校准的 manifest。默认使用 `claude-sonnet-5`，可通过 `args.model` 显式切换到白名单内其他模型：

| agent | 模型（默认/可选） | 原因 |
|------|------|------|
| 截图、Phase3/4 核图、报告与检查 | 默认 `claude-sonnet-5`；可选 `vertex.claude-opus-4.6`、`kimi-k3`、`gpt-5.6-terra` | 合并 agent 的后续阶段需要多模态；Phase2 在同一 agent 内仍只能调用本地脚本。确定性校验由项目内 Python/JS 脚本执行。`glm-5.2`/DeepSeek 系列等非多模态模型不在白名单内。 |

> 若需调整模型，只修改 `workflow/meituan_eval_workflow.js` 的 `SUBAGENT_MODEL`（或传入 `args.model`），并同步更新本节；新模型必须先加入 `MULTIMODAL_MODEL_WHITELIST` 才能生效。不要按历史 Sonnet/Opus 分配表单独指定某个阶段。

---

---

## 机型不同怎么办

坐标按**华为 ABR-AL80（1224×2700）**校准。换机型必须重新校准，否则点错位置：

1. 读 `phase1-screenshot/SKILL.md` 的「关键坐标」表（搜索框、搜索按钮、3个tab、返回按钮）。
2. 手机连电脑，美团打开搜索页，跑：
   ```bash
   adb shell uiautomator dump /sdcard/ui.xml
   adb shell cat /sdcard/ui.xml > /tmp/ui.xml
   ```
3. 在 /tmp/ui.xml 搜对应元素的 text 或 resource-id，取 bounds 中心点坐标。
4. 改 `phase1-screenshot/scripts/run_scroll.sh` 里的坐标。

---

## 常见问题

**Q: 我几天前截的图，怎样只评测而不重新截图？**
A: 使用 `mode=evaluate_only, discoveryOnly=true` 先发现 `screenshots/` 中的截图组；选择同一组 `files` 后，用它们作为 `selectedScreenshots` 发起评测。系统会从文件名推导搜索词、Tab 和屏号。

**Q: 为什么“截图 + 评测”截图完成后会停下来？**
A: 这是 1.0 的刻意设计。截图通过完整性检查后，Workflow 返回 `awaiting_evaluation_config`，此时才确认评测维度与报告出口；失败或不需要的截图不会进入 Evaluation Agent。

**Q: 仅自动化截图为什么不生成报告？**
A: `capture_only` 的职责是稳定采集可复用截图，结果只写入 `screenshots/`。需要评测时再选择“仅评测已有截图”。

**Q: 评测报告全是空数据 / 评测 agent 报错**
A: 99% 是 macOS 权限没给。完全磁盘访问权限里加终端 App，**重启终端**再跑。

**Q: 截图 0 字节 / 文件没生成**
A: 设备卡顿或掉线。批量用 `loop_screenshot.sh`（自动重连+删 0 字节+逐词重跑），不要用全量 `run_scroll.sh`。

**Q: 搜的词和截图对不上 / 新旧词叠加**
A: ADBKeyBoard 输入法被切回百度了。重跑 `setup.sh` 或手动 `adb shell ime set com.android.adbkeyboard/.AdbIME`。

**Q: USB 频繁掉线**
A: 换数据线、换 USB 口。`loop_screenshot.sh` 有自动重连（最多 20 次）。

**Q: macOS 提示 `timeout: command not found`**
A: macOS 没有 timeout 命令。本项目脚本不依赖它，别在循环里用。

**Q: 跑了某维度但报告里该维度空白**
A: 该维度 `eval-skills/` 下没有 `eval-*` 子目录，或 SKILL.md frontmatter 缺 `title/weight/aggregate`。按上文约定补齐。

**Q: 不同评测 skill 报的元素总数对不上（如色彩 14、规范 12）**
A: 各 skill 自行拆元素导致口径漂移。解决：执行 Phase2（`annotate=true`），为每张截图产出独立清单；评测 phase 按截图注入对应清单并用确定性脚本计数，禁止人工重拆。

**Q: 某个评测 skill 只有「优秀/不达标」两档，工作流报「缺达标键」**
A: 二档制 skill 合法，frontmatter `weight` 写 `{ "优秀": 1, "不达标": -1 }` 即可，「达标」键可省略；工作流发现脚本用 `.get("达标",0)` 兜底，schema 已把「达标」设为可选。不要硬凑三档。

**Q: Phase2 识别一直很慢 / 根本没动 / 卡死**
A: 先检查本地 Tesseract、长图双版面 OCR 和一次性的卡内有界重识别是否仍在运行。Phase2 不依赖视觉模型读图；PaddleOCR 只会在初次门控失败后加载一次，线程数默认限制为 2，可设置 `PHASE2_DISABLE_BOUNDED_PADDLEOCR=1` 关闭。已有单图清单若 `phase3Ready=false` 或 manifest 校验失败会被阻断，必须按 `reprocessTargets` 对失败卡/失败行重跑。

**Q: 评测 agent 计数还是不对（49/50/51）**
A: 评测 agent 读清单后仍自己数。工作流已注入确定性 python 计数脚本，要求 `overview.total` 必须等于脚本输出，禁止人工推导。若仍错，检查 agent 是否真跑了脚本而非自行计数。

**Q: 检查脚本输出 `EXISTS=0`，但文件明明存在**
A: python 的 `os.path.expanduser("$HOME/...")` **不展开 shell 变量**，只展开 `~`。工作流传入的 `phase2Outputs[].manifest` 必须已经是绝对路径；自己写脚本时应传绝对路径，或使用 `~/` 让 `expanduser` 处理。

**Q: 报告里出现「AI 初步建议，待人工确认」徽标**
A: 该评测项 frontmatter `extra` 字段非空。用户已排除需人工审查的评测，若不想要此徽标，把 `extra` 留空。

**Q: NoCode 页面只有组件/卡片维度，或最新批次整页为空？**
A: 先确认 `.governance_dataset_<批次>.json` 已包含 `element/component/page` 三类 `dimensionScores`，再核对导入后的六张表是否均使用同一真实 `batch_id`。若 CLI 可查询但浏览器页面为空，优先检查匿名角色的 `SELECT`/RLS 权限和 `VITE_SUPABASE_URL`、`VITE_SUPABASE_ANON_KEY`，不要靠前端重新计算或复制伪造数据解决。

**Q: NoCode 的「查看典型证据」没有图片？**
A: 线上页面不能访问本机 `file://`。从数据集的 Phase4 `evidenceImage` 去重找出实际引用的 `screenshots-out/evidence/` 整页红框图，在取得上传授权后写入 NoCode 工程 `public/evidence/`，保留原文件名，并检查标题映射和 `/evidence/<文件名>` 请求。无映射时应显示明确空态，不应显示损坏图片。
