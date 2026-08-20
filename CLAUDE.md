# 项目工作流声明（search-eval-project）

本仓库是美团搜索结果页标准化评测系统。1.0 对外由 **Workflow → Screenshot Agent / Evaluation Agent** 编排：Screenshot Agent 负责 Phase1 的现场截图或已有截图发现；Evaluation Agent 在同一上下文内执行 **Phase2 轻量识别 → Phase3 多维度评测 → Phase4 问题证据 → Phase5 报告**。完整参数与用法见 `README.md`，本文件只声明阶段、目录与数据流向，供每个 Claude Code 会话快速对齐。

## 1.0 任务模式与职责边界

- `capture_only`：只调用 Screenshot Agent；只向用户确认搜索词、Tab、屏数。
- `evaluate_only`：Screenshot Agent 只读发现 `screenshots/`；用户选择截图后才调用 Evaluation Agent，只确认评测维度和报告出口，不要求用户重复搜索词、Tab、屏数或设备参数。
- `capture_and_evaluate`：先调用 Screenshot Agent；截图通过基本完整性检查后，返回 `awaiting_evaluation_config`，再确认评测维度和报告出口后调用 Evaluation Agent。
- Workflow 只做条件询问、模式路由、单词隔离、批次屏障和状态汇总；不得运行 OCR、评测、评分、证据或报告业务逻辑。
- 1.0 不存在 Runtime Guard、自动反思或经验库。Phase2～4 的既有确定性校验器仍在 Evaluation Agent 内执行。

## 评测请求预检与路由门禁（铁律）

任何涉及本项目的截图、评测、已有报告复核、批量治理或能力咨询的用户请求，都必须先进入唯一入口 `workflow/meituan_eval_workflow.js` 的任务路由语义；不得把用户提供的图片直接当作人工点评对象。

### 执行前的必经预检

在识别截图内容、给出评级或运行任何阶段脚本前，当前会话必须：

1. 确认项目根目录，并完整读取根 `CLAUDE.md`、存在时的 `AGENTS.md`、根 `README.md`；
2. 识别用户意图与输入类型（单图、多图/目录、现场截图、已有结果复核或能力咨询）；
3. 定位并读取该意图所需的入口与阶段契约：评测任务读取 `.claude/skills/run-eval.md`、`workflow/meituan_eval_workflow.js` 及所选阶段的 `SKILL.md`；能力咨询仅读取这些说明文件，不运行评测；
4. 在执行前先向用户回告：识别出的任务模式、输入范围、下一步将调用的阶段、仍缺的最小输入，以及预期交付物。

未完成上述预检，不得开始目视判图、OCR、评级或输出“已完成评测”。人工视觉判断仅可作为已完成流水线后的复核意见，并必须标为“人工复核”，不能替代 Phase2～5 结果。

### 用户请求路由

| 用户意图 | 路由与后续动作 | 首次回复要求 |
|---|---|---|
| 单张已有截图评测 | `evaluate_only`：先只读发现/校验截图，再由用户确认范围、维度与报告出口后执行 Phase2～5 | 确认文件、任务模式和将产出的 manifest、证据、HTML；不得先给人工分数 |
| 多张图片或目录评测 | `evaluate_only`：发现并按搜索词/Tab/屏号分组；同词图片作为一组进入流水线 | 返回发现的组、无法解析/无效文件及待用户选择的组 |
| 现场截图后评测 | `capture_and_evaluate`：先 Phase1，截图合格后再收集评测维度和报告出口 | 明确截图词、Tab、屏数，以及截图完成后会暂停确认评测配置 |
| 仅自动化截图 | `capture_only`：只执行 Phase1 | 明确只交付截图，不生成评测结论或报告 |
| 复核已有报告 | 读取其输入、单图 manifest、阶段结果、证据与校验记录；必要时回退并重跑受影响阶段 | 标明复核范围及是否会产生新批次产物；不得用新的人工评分覆盖旧结果 |
| 询问系统能力 | 只读取项目说明和已注册技能，回答支持的输入、维度、产物与限制 | 明确这是能力说明，未对任何截图运行评测 |

用户直接给出项目外图片路径时，先以不修改原文件的方式将图片直接复制到 `screenshots/`。复制保留原文件名，不生成 Intake manifest，也不做名称规范化；发现阶段负责报告无效或无法解析的文件。目标同名但字节不同则追加递增的副本序号保留两份，绝不覆盖，并作为独立截图而非同一屏，不能直接判图。

## 阶段与目录

| 阶段 | 目录 | 作用 |
|---|---|---|
| phase1 截图 | `phase1-screenshot/` | ADB 现场截图或复用已有图，产物写入项目根 `screenshots/` |
| phase2 轻量识别 | `phase2-card-annotation/` | 本地 CV/OCR、卡型契约、整页门控；每张截图输出一个独立元素清单 JSON |
| phase3 评测 | `phase3-card_or_component-eval/`、`phase3-single_element-eval/`、`phase3-page_framework-eval/` | 基于截图 + 清单按维度评测，记录问题定位与判定依据 |
| phase4 问题证据 | `phase4-issue-evidence/` | 只为 phase3 已判为问题的位置产出整页截图红框证据图 |
| phase5 报告 | `phase5-report/` + `workflow/meituan_eval_workflow.js` | 生成消费局部问题证据的本地 HTML 与批量治理数据集；可选同步到 NoCode 线上看板 |

> **phase2 重命名说明**：phase2 原名 `imd-card-annotation`，目录已重命名为 `phase2-card-annotation`。若历史脚本/文档仍出现旧名 `imd-card-annotation`，一律以 `phase2-card-annotation` 为准。

## phase2 输入 / 输出（关键）

- **输入**：截图取自项目根 `screenshots/`（phase1 产物或手动放入）。
- **输出**：每张输入截图分别输出一个元素清单 JSON 到项目根 `screenshots-out/`；文件之间不合并页面事实。
- phase2 不再以 skill 内部的 `screenshots/`、`out/` 子目录作为输入输出根；统一以项目级 `screenshots/` → `screenshots-out/` 为准。

## phase3 与 phase2 的衔接

- phase3 评测读取原始截图 + 与该截图一一对应的 Phase2 元素清单 JSON。
- 单图元素清单是 phase3 各评测 skill 的唯一事实源：只有 `recognition.phase3Ready=true` 才可消费。批量 `index.json` 仅是索引，不能作为事实源。

## 数据流向一览

```
screenshots/ ──phase2 轻量识别──▶ screenshots-out/ ──phase3 评测──▶ .artifacts/
   (截图)                         (每张截图一个元素清单)              (问题定位)
                                                                         │
                                      screenshots-out/evidence/ ◀──phase4 问题证据标注
                                                                         │
                                                                         ▼
                                                                     reports/
                                                              (phase5 HTML + 治理数据集)
                                                                         │
                                                                         └──NoCode 线上看板（可选）
```

## phase5 本地与线上出口

- `phase5-report/SKILL.md` 负责本地 HTML；当输入覆盖两个及以上搜索词时，必须由 `scripts/build_experience_dashboard.py` 确定性生成 `GOVERNANCE_DASHBOARD_V1` 本地看板与同批 `.governance_dataset_<批次>.json`，不得手写另一套批量 HTML。
- `phase5-report/nocode-dashboard/SKILL.md` 负责将上述数据集导入 NoCode、发布 Phase4 局部问题证据图并部署线上看板。线上页必须沿用本地看板的信息架构、分数/计数口径、视觉令牌与交互语义；它不能读取开发机 `file://` 图片，证据图需经 `public/evidence/` 受控资源发布。
- NoCode 数据库的每张批次明细表都以真实 `batch_id` 关联；浏览器匿名角色对看板表的只读权限是上线验收项。CLI 能读取记录不代表线上页面可读。

## 执行模式：显式 Workflow 与 Agent 任务编排

本项目的“工作流”指固定的 `phase1 → phase2 → phase3 → phase4 → phase5` 数据契约，而不是必须依赖某一种宿主工具。两种执行模式产物与验收口径必须完全一致：

| 模式 | 适用场景 | 执行入口 | 约束 |
|---|---|---|---|
| **显式 Workflow（优先）** | 当前会话提供 Workflow 工具时 | `workflow/meituan_eval_workflow.js` + args | 由宿主注入 `args/agent/parallel/phase/log`，脚本内部按同一子代理分派结构编排各 phase（见下）。 |
| **Agent 任务编排（等价回退）** | Workflow 工具未注入、宿主运行时不可用，或用户明确要求逐阶段执行时 | Agent 以 TODO 依次派发子代理调用 | 不得跳过任何 phase 的事实源、确定性校验或报告契约；不得因为显式 Workflow 不可用而停止评测；子代理分派结构必须与显式 Workflow 一致（见下）。 |

两种模式共用同一套**子代理分派结构**，不是各自随意拆分：

- **Screenshot Agent 独立**：`capture_only` 时执行现场 ADB 截图；`evaluate_only` 时只读运行 `scripts/discover_screenshot_groups.py` 发现、聚合和校验已有截图；不与其它 phase 混入同一上下文。
- **Evaluation Agent 独立**：对用户已确认的截图，内部把本地轻量识别（phase2）→ 全维度评测（phase3）→ 问题证据（phase4）→ 报告（phase5）按序完成。Phase2 在该上下文中仍只运行本地脚本，并为每张截图分别生成清单；多模态能力只能用于后续阶段。
- **回退模式的具体派发机制**：Agent 任务编排没有 `agentType:` 参数机制，因此对 phase2+3+4+5 发起的这**唯一一次** `Agent` 工具调用，其 prompt 必须完整拼入 `.claude/agents/phase2345-query-pipeline.md` 的正文全部内容（Stage A~D 的输入契约、执行硬约束、输出 schema 逐条原文，不得摘要、简化或用自己的话复述替代），再附加当次 query/screenshots/路径等具体参数。禁止只截取该文件的部分小节、禁止凭记忆转述其中的校验命令或字段名。
- **FACT_GATES 与 Phase2 返工复核内嵌在这一次调用内部**：`--require-hierarchy-facts` 等 4 项前置事实校验命令，以及校验失败触发的 Phase2 本地返工（按 `reprocessTargets` 重跑失败卡/失败行、更新对应单图清单、重跑受影响 skill），都必须在这同一个子代理的同一次执行内部完成闭环。Phase3 不得回看原图补写 Phase2 事实；主 Agent 只根据这一次调用最终返回的 `ok`/`blockedAt`/`error` 决定是否继续 phase5 之后的 NoCode 出口或整体重跑。
- 跨维度共享契约：phase3 评测前必须先读对应维度的共享契约文件（单一元素维度读 `phase3-single_element-eval/单一元素评测通用契约.md`，组件/卡片维度读 `phase3-card_or_component-eval/组件卡片评测通用契约.md`，页面框架维度读 `phase3-page_framework-eval/页面框架评测通用契约.md`；契约文件与各维度 `eval-skills/` 同级共存），再读该 skill 自身 SKILL.md；SKILL.md 中标注"见共享契约"的条款以共享契约原文为准。

Agent 任务编排先要求用户选择 `capture_only`、`evaluate_only` 或 `capture_and_evaluate`，再按模式询问必要参数。仅评测已有截图时先发现截图组，不询问搜索词、Tab、屏数；截图+评测时必须在截图成功后才询问评测维度与报告出口。Phase2 默认 lightweight，不作为额外确认项。

Agent 任务编排的固定顺序：① Screenshot Agent 截图或发现/校验已有截图；② 对需要评测的已选截图，单个 Evaluation Agent 调用（内部复用 `phase2345-query-pipeline`）依次完成：phase2 默认轻量识别并为每张截图分别将一个元素清单及其审计写入项目级 `screenshots-out/`，不生成整页标注 PNG → phase3 逐维度先读共享契约再读所有目标 `eval-*/SKILL.md`，按截图消费对应清单、确定性计数并将原始结果和审计写入 `.artifacts/过程文件-评测结果与审计/` → phase4 只为不达标区域在 `screenshots-out/evidence/` 生成整页红框证据图并回写结果 → phase5 按 `phase5-report/SKILL.md` 渲染 `reports/` 本地 HTML；用户选择 NoCode 时，再按 `phase5-report/nocode-dashboard/SKILL.md` 处理线上出口。除显式 Workflow 的宿主调度方式外，两种模式不得产生不同的数据流、评分口径、输出路径或子代理分派结构。

### 批量子代理调度纪律（铁律）

- **模型能力按阶段隔离**：Phase2 只允许运行本地 CV/OCR、卡型契约和确定性 hooks；即使它处于多模态子代理上下文，也禁止模型读取截图后补写 OCR、卡型、坐标或视觉事实。Phase1、Phase3/4 核图和问题证据任务需要多模态能力，因此合并的 phase2345 子代理必须显式使用白名单模型（当前为 `claude-sonnet-5`、`vertex.claude-opus-4.6`、`kimi-k3`、`gpt-5.6-terra`）。模型能力不得回流改写 Phase2 manifest。
- 批量搜索词执行时，**一个子代理只处理一个搜索词**（该词所需的 Phase2/Phase3/Phase4 连续工作）；不得把多个词、多个截图词或“剩余若干词”合并下发给同一子代理。
- 每批并发最多 **3 个子代理 / 3 个搜索词**；必须等待本批全部成功、失败或明确介入完成后，才可启动下一批。不得为了追吞吐提前投放下一批。
- 子代理要处理的当前搜索词、批次序号、输入截图和输出目录必须在派发 prompt 中显式声明；失败只重试该词，不影响同批其他词和已完成批次。
- 维度内的 skill 可在该词子代理上下文中顺序执行；禁止以“每个 skill 一个子代理”的方式突破上述 3 个词并发上限。

### 过程文件与图片保留纪律（铁律）

- 评测、标注、截图、裁剪、扫描、审计、失败重试等过程中产生的文件和图片**一律不得删除**，包括 0 字节截图、临时裁剪图、scan 输出、旧证据图和失败中间产物。
- 需要从工作目录隔离的中间产物，必须写入 `.artifacts/过程文件-评测结果与审计/` 下按 `query/批次/阶段` 分组的目录；不得通过 `rm`、`unlink`、覆盖删除或清理脚本回收。
- 子代理 prompt 必须同样声明本纪律：只新增或保留文件；发现无效、重复或失败产物时记录原因与路径供审计，不得删除。

phase2 默认开启轻量识别；仅 `annotate=false` 显式跳过。`phase2Mode` 作为兼容参数固定为 `lightweight`；phase2 skill 目录由 `imdSkillDir` 指定（默认 `projectDir/phase2-card-annotation`）。

---

## 控制体系（让任何人得到一致、准确输出）

本项目用 7 类控制手段叠加，覆盖「全局→按需→隔离→确定性→临时」全链路：

| 手段 | 位置 | 作用 | 生效时机 |
|---|---|---|---|
| CLAUDE.md（本文件） | 项目根 | 声明阶段/数据流/规范/契约 | Claude Code 全局、每会话 |
| AGENTS.md | 项目根 | 为 Codex 等通用 Agent 声明同一入口门禁与可移植前置入口 | 支持 AGENTS.md 的宿主、每会话 |
| Rules | `.claude/rules/*.md` | 按文件类型约束（SKILL.md 契约、命名/路径规范） | 按需：碰对应文件才加载，不碰不占 token |
| Subagents | `.claude/agents/*.md` | Screenshot Agent 负责截图/发现；Evaluation Agent 负责 Phase2～5，内部保留阶段职责定义 | 按任务模式和单词边界执行 |
| Hooks | `.claude/settings.json` | SKILL.md 编辑后自动校验 frontmatter（确定性） | 每次 Edit/Write SKILL.md 后 |
| Output Styles | `.claude/output-styles/eval-strict.md` | 评测模式人设，强制评级/计数/输出一致性 | 切到 eval-strict 模式时 |
| Skills | 项目 `phase*/SKILL.md` | 每个截图、识别、评测、报告与 NoCode 部署步骤的口径手册 | 工作流按路径读，或交互调用 |
| System Prompt Append | CLI `--append-system-prompt` | 一次性临时指令 | 单次调用 |

### 已落地
- **Rules**：`.claude/rules/skill-frontmatter.md`（SKILL.md frontmatter 契约）、`.claude/rules/project-conventions.md`（命名+路径+评级规范）。
- **Subagents**：`.claude/agents/screenshot-agent.md`（截图/外部图片复制/已有截图发现）与 `.claude/agents/evaluation-agent.md`（对外评测入口）；后者复用 `.claude/agents/phase2345-query-pipeline.md`（单词单实例、Phase2～5 顺序完成）。Phase2 的候选提取只运行本地 CV/OCR；其受审计的当前像素校准可由多模态模型核对整图或有界裁图，但只能确认可见边界、类型、归属和原文，不能补写 OCR、注入黄金字段或做任何评测判断。
- **Hooks**：`.claude/settings.json` + `scripts/validate_skill_frontmatter.py`（编辑 SKILL.md 后自动校验四键，非阻断）。
- **Output Style**：`.claude/output-styles/eval-strict.md`。
- **运行入口**：`.claude/skills/run-eval.md`，以保守默认参数调用工作流。

### 已落地的运行前入口
- `workflow/eval_cli.py`：在没有 Workflow DSL 宿主的环境中完成外部截图直接复制、发现与 `MEITUAN_EVAL_HANDOFF_V1` 交接参数生成；它不伪装为可执行 LLM 评测器。
- `scripts/ingest_external_screenshots.py`：外部截图直接复制工具；保留原文件名，冲突不覆盖。

### 职责边界（不可由 LLM 替代）
- `scripts/validate_element_manifest.py` 是 Phase2 清单的确定性验收入口；Phase2 agent 只负责识别和产出清单，校验失败必须阻断 Phase3。
- `scripts/validate_eval_results.py` 是 Phase3 结果及 Phase4 证据的确定性验收入口；Phase3/Phase4 agent 不得以主观判断豁免缺失字段、计数冲突或证据缺失。
- 批次并发上限、单词隔离、同批屏障和失败重试由 Workflow/宿主编排强制保证；不得新增或依赖“批量调度 agent”自行协调。

---

## 命名与路径规范（铁律，详见 `.claude/rules/project-conventions.md`）

- 阶段目录一律 `phaseN-<role>`，不带 `-skill` 后缀：`phase1-screenshot`、`phase2-card-annotation`、`phase3-*-eval`、`phase4-issue-evidence`、`phase5-report`。
- 数据流：`screenshots/`（phase1 出/phase2 入）→ `screenshots-out/`（phase2 清单；可选全量 PNG）→ `.artifacts/`（phase3 结果）→ `screenshots-out/evidence/`（phase4 整页红框证据）→ `reports/`（phase5 HTML；批量看板同时输出 `.governance_dataset_<批次>.json`）→ NoCode 线上看板（可选）。**不得**用 `screenshots/annotated/` 或 skill 内部 `out/`。
- 场景脚本输入/输出必须用项目级绝对路径，不得写独立的 `Desktop/<旧名>/` 或 `meituan_search_screenshots_v2/`。
- 旧名 `imd-card-annotation` / `screenshot-skill` / `report-skill` / 非前缀维度名已废弃，见到即视为待替换（重命名声明行例外）。

## SKILL.md frontmatter 契约（铁律，详见 `.claude/rules/skill-frontmatter.md`）

每个 `eval-*/SKILL.md` 必须含 `name/title/weight/aggregate` 四键（缺一则工作流发现/计分失败）：
- `weight` 键只能是 `优秀/达标/不达标`；两档制写 `{ "优秀": n, "不达标": n }`（省 `达标`），三档制三键齐全。**不得**用高线/中线/低线等别名。
- `aggregate` 必须写清：原始颗粒度如何评级 + 如何聚合到 Tab 级（取最差/求和/阈值）。
- `name` 用 kebab-case 且与目录名一致。
- 编辑 SKILL.md 后，`scripts/validate_skill_frontmatter.py` 钩子会自动校验四键。

## 评级分档

- 多数 eval skill 已两档（优秀/不达标，任一问题即不达标）；少数三档。两种都合法，由 `weight` 声明，工作流 schema 兼容（`达标` 可选）。
- 新增评测项默认两档，除非确需中间档。

## 一致性铁律（评测 phase 必守）

1. 每张截图对应的 Phase2 清单是该图唯一事实源：`overview.total` 由各单图清单确定性计数后汇总，禁止各 skill 自行拆分、重数或跨图合并事实。
2. 评级只认 skill 的 weight 分档，不自创中间档。
3. 只评可见内容，截图外信息（落地页真实性、提示条准确性）不计入评级。
4. 逐组件给独立评级，不整屏笼统打分。

## 新增评测项 checklist

1. 在对应维度 `eval-skills/eval-X-<name>/` 建 `SKILL.md`，frontmatter 四键齐全（参考 `.claude/rules/skill-frontmatter.md`）。
2. 评级口径写在正文 + `aggregate`；两档制 `weight={ "优秀":n, "不达标":n }`。
3. 保存后看钩子输出 `[skill-frontmatter] OK`；若 FAIL 补齐再继续。
4. 工作流下次运行自动发现，无需改 JS。
