# 项目工作流声明（search-eval-project）

本仓库是美团搜索结果页标准化评测工作流：**截图 → phase2 轻量识别/可选全量标注 → phase3 多维度评测 → phase4 问题证据标注 → phase5 合并报告**。完整参数与用法见 `README.md`，本文件只声明阶段、目录与数据流向，供每个 Claude Code 会话快速对齐。

## 阶段与目录

| 阶段 | 目录 | 作用 |
|---|---|---|
| phase1 截图 | `phase1-screenshot/` | ADB 现场截图或复用已有图，产物写入项目根 `screenshots/` |
| phase2 轻量识别/全量标注 | `phase2-card-annotation/` | 默认只输出统一元素清单 JSON；可选产出整页标注 PNG |
| phase3 评测 | `phase3-card_or_component-eval/`、`phase3-single_element-eval/`、`phase3-page_framework-eval/` | 基于截图 + 清单按维度评测，记录问题定位与判定依据 |
| phase4 问题证据 | `phase4-issue-evidence/` | 只为 phase3 已判为问题的位置产出整页截图红框证据图 |
| phase5 报告 | `phase5-report/` + `workflow/meituan_eval_workflow.js` | 生成消费局部问题证据的本地 HTML 与批量治理数据集；可选同步到 NoCode 线上看板 |

> **phase2 重命名说明**：phase2 原名 `imd-card-annotation`，目录已重命名为 `phase2-card-annotation`。若历史脚本/文档仍出现旧名 `imd-card-annotation`，一律以 `phase2-card-annotation` 为准。

## phase2 输入 / 输出（关键）

- **输入**：截图取自项目根 `screenshots/`（phase1 产物或手动放入）。
- **输出**：默认仅输出统一元素清单（JSON）到项目根 `screenshots-out/`；`phase2Mode=full-annotation` 时额外输出整页标注 PNG。
- phase2 不再以 skill 内部的 `screenshots/`、`out/` 子目录作为输入输出根；统一以项目级 `screenshots/` → `screenshots-out/` 为准。

## phase3 与 phase2 的衔接

- phase3 评测读取原始截图 + phase2 元素清单 JSON；全量标注 PNG 仅为可选复核素材，不是默认依赖。
- 统一元素清单是 phase3 各评测 skill 的单一事实源：`overview.total` 必须由清单确定性计算，禁止各 skill 自行拆分或按截图重新数。

## 数据流向一览

```
screenshots/ ──phase2 轻量识别──▶ screenshots-out/ ──phase3 评测──▶ .artifacts/
   (截图)                         (元素清单；可选整页标注图)          (问题定位)
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

- **phase1 独立**：截图（现场 ADB 或复用已有图）单独一次 Agent 调用，不与其它 phase 混入同一上下文。
- **phase2+3+4+5 合并进同一个子代理**：标注/识别（phase2）→ 全维度 eval skill 评测（phase3）→ 问题整页红框证据（phase4）→ 单词报告渲染（phase5），在**同一个子代理上下文**内按序完成，中间不切换子代理、不返回调用方再重新派发。显式 Workflow 模式下用 `agentType: 'phase2345-query-pipeline'`（见 `.claude/agents/phase2345-query-pipeline.md`）承载这四个阶段；Agent 任务编排回退模式下，同样必须以单个 Agent 调用（同一 agent 实例的同一次执行）依次完成这四个阶段，不得为图方便按旧的四个独立 agent（`phase2-annotator`/`phase3-evaluator`/`phase4-issue-evidence`/`phase5-report-renderer`）逐个单独派发再拼接结果——那四份定义现由 `phase2345-query-pipeline.md` 统一承载并保留原有各阶段硬约束，仅用于历史参照。
- **回退模式的具体派发机制**：Agent 任务编排没有 `agentType:` 参数机制，因此对 phase2+3+4+5 发起的这**唯一一次** `Agent` 工具调用，其 prompt 必须完整拼入 `.claude/agents/phase2345-query-pipeline.md` 的正文全部内容（Stage A~D 的输入契约、执行硬约束、输出 schema 逐条原文，不得摘要、简化或用自己的话复述替代），再附加当次 query/screenshots/路径等具体参数。禁止只截取该文件的部分小节、禁止凭记忆转述其中的校验命令或字段名。
- **FACT_GATES 与 Phase2 返工复核内嵌在这一次调用内部**：`--require-hierarchy-facts` 等 4 项前置事实校验命令，以及校验失败触发的 Phase2 返工复核（重新读图、更新清单、重跑受影响 skill），都必须在这同一个子代理的同一次执行内部完成闭环，不得由外层主 Agent 再单独发起校验或复核的子调用；主 Agent 只根据这一次调用最终返回的 `ok`/`blockedAt`/`error` 决定是否继续 phase5 之后的 NoCode 出口或整体重跑。
- 跨维度共享契约：phase3 评测前必须先读对应维度的共享契约文件（单一元素维度读 `phase3-single_element-eval/单一元素评测通用契约.md`，组件/卡片维度读 `phase3-card_or_component-eval/组件卡片评测通用契约.md`，页面框架维度读 `phase3-page_framework-eval/页面框架评测通用契约.md`；契约文件与各维度 `eval-skills/` 同级共存），再读该 skill 自身 SKILL.md；SKILL.md 中标注"见共享契约"的条款以共享契约原文为准。

Agent 任务编排**启动前必须先向用户确认**以下三项，确认后才创建 TODO 并进入 phase1：

1. 是否在评测前执行 phase2 标注（是 / 否）；
2. 评测维度（可多选）：单一元素（`phase3-single_element-eval`）、组件/卡片（`phase3-card_or_component-eval`）、页面框架（`phase3-page_framework-eval`）；
3. 交付出口：仅生成本地 HTML 报告，或生成本地 HTML 后继续按 `phase5-report/nocode-dashboard/SKILL.md` 导入、发布证据并部署 NoCode 报告。

Agent 任务编排的固定顺序：① phase1 校验/复用或现场截图（独立 Agent 调用）；② 单个 Agent 调用（`phase2345-query-pipeline` 或等价的单实例连续执行）依次完成：phase2 默认轻量识别并将元素清单和审计写入项目级 `screenshots-out/`（用户指定全量模式时才额外生成 PNG）→ phase3 逐维度先读共享契约再读所有目标 `eval-*/SKILL.md`，以统一清单确定性计数并将原始结果和审计写入 `.artifacts/过程文件-评测结果与审计/` → phase4 只为不达标区域在 `screenshots-out/evidence/` 生成整页红框证据图并回写结果 → phase5 按 `phase5-report/SKILL.md` 渲染 `reports/` 本地 HTML；用户选择 NoCode 时，再按 `phase5-report/nocode-dashboard/SKILL.md` 处理线上出口。除显式 Workflow 的宿主调度方式外，两种模式不得产生不同的数据流、评分口径、输出路径或子代理分派结构。

### 批量子代理调度纪律（铁律）

- **模型必须是多模态识图模型（零例外）**：本项目每一次子代理调用（包括 Phase1/2/3/4/5、复核、重试、报告渲染及任何临时探索任务）都涉及读图（截图识别、标注、证据比对），必须显式指定具备识图能力的多模态模型，不得依赖运行时默认模型，也不得使用 `glm-5.2`/DeepSeek 系列等非多模态模型。默认使用 `claude-sonnet-5`；用户可显式要求切换到 Dr. Pie 模型目录内其他已验证的多模态模型（当前收录 `claude-sonnet-5`、`vertex.claude-opus-4.6`、`kimi-k3`、`gpt-5.6-terra`；目录当前未收录 Gemini 系列）。工作流层通过 `args.model` 传入并统一注入所有子代理调用，且会校验其在多模态白名单内；若某次调用的模型参数缺失、非多模态或未成功生效，必须停止该子代理任务并记录原因，待补齐合规模型参数后才能继续。
- 批量搜索词执行时，**一个子代理只处理一个搜索词**（该词所需的 Phase2/Phase3/Phase4 连续工作）；不得把多个词、多个截图词或“剩余若干词”合并下发给同一子代理。
- 每批并发最多 **3 个子代理 / 3 个搜索词**；必须等待本批全部成功、失败或明确介入完成后，才可启动下一批。不得为了追吞吐提前投放下一批。
- 子代理要处理的当前搜索词、批次序号、输入截图和输出目录必须在派发 prompt 中显式声明；失败只重试该词，不影响同批其他词和已完成批次。
- 维度内的 skill 可在该词子代理上下文中顺序执行；禁止以“每个 skill 一个子代理”的方式突破上述 3 个词并发上限。

### 过程文件与图片保留纪律（铁律）

- 评测、标注、截图、裁剪、扫描、审计、失败重试等过程中产生的文件和图片**一律不得删除**，包括 0 字节截图、临时裁剪图、scan 输出、旧证据图和失败中间产物。
- 需要从工作目录隔离的中间产物，必须写入 `.artifacts/过程文件-评测结果与审计/` 下按 `query/批次/阶段` 分组的目录；不得通过 `rm`、`unlink`、覆盖删除或清理脚本回收。
- 子代理 prompt 必须同样声明本纪律：只新增或保留文件；发现无效、重复或失败产物时记录原因与路径供审计，不得删除。

phase2 默认开启轻量识别；仅 `annotate=false` 显式跳过。`phase2Mode=lightweight|full-annotation`，默认 `lightweight`；phase2 skill 目录由 `imdSkillDir` 指定（默认 `projectDir/phase2-card-annotation`）。

---

## 控制体系（让任何人得到一致、准确输出）

本项目用 7 类控制手段叠加，覆盖「全局→按需→隔离→确定性→临时」全链路：

| 手段 | 位置 | 作用 | 生效时机 |
|---|---|---|---|
| CLAUDE.md（本文件） | 项目根 | 声明阶段/数据流/规范/契约，每次会话自动加载 | 全局、每会话 |
| Rules | `.claude/rules/*.md` | 按文件类型约束（SKILL.md 契约、命名/路径规范） | 按需：碰对应文件才加载，不碰不占 token |
| Subagents | `.claude/agents/*.md` | phase2 标注、phase3 评测、phase4 证据和 phase5 报告渲染的独立上下文分身 | 按阶段执行、并行评测或交互式单跑 |
| Hooks | `.claude/settings.json` | SKILL.md 编辑后自动校验 frontmatter（确定性） | 每次 Edit/Write SKILL.md 后 |
| Output Styles | `.claude/output-styles/eval-strict.md` | 评测模式人设，强制评级/计数/输出一致性 | 切到 eval-strict 模式时 |
| Skills | 项目 `phase*/SKILL.md` | 每个截图、标注、评测、报告与 NoCode 部署步骤的口径手册 | 工作流按路径读，或交互调用 |
| System Prompt Append | CLI `--append-system-prompt` | 一次性临时指令 | 单次调用 |

### 已落地
- **Rules**：`.claude/rules/skill-frontmatter.md`（SKILL.md frontmatter 契约）、`.claude/rules/project-conventions.md`（命名+路径+评级规范）。
- **Subagents**：`.claude/agents/phase2345-query-pipeline.md`（phase2 标注+phase3 全维度评测+phase4 问题证据+phase5 报告渲染，单词单实例、单一子代理上下文顺序完成四阶段）。历史独立定义 `phase2-annotator.md`/`phase3-evaluator.md`/`phase4-issue-evidence.md`/`phase5-report-renderer.md` 已并入其内容，仅作参照保留。该 agent 必须先完整读取各阶段对应 `SKILL.md`（含 phase3 的维度共享契约），仅处理调用方注入的唯一搜索词，并由工作流显式以多模态识图模型（默认 `claude-sonnet-5`）调用。
- **Hooks**：`.claude/settings.json` + `scripts/validate_skill_frontmatter.py`（编辑 SKILL.md 后自动校验四键，非阻断）。
- **Output Style**：`.claude/output-styles/eval-strict.md`。
- **运行入口**：`.claude/skills/run-eval.md`，以保守默认参数调用工作流。

### 可按需补齐
- `PreToolUse` 钩子：跑评测前自动校验 `screenshots/` 有非空截图 + macOS 完全磁盘访问权限，避免报告全空。

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

1. 统一元素清单是单一事实源：`overview.total` = 清单确定性计数，禁止各 skill 自行拆分/重数。
2. 评级只认 skill 的 weight 分档，不自创中间档。
3. 只评可见内容，截图外信息（落地页真实性、提示条准确性）不计入评级。
4. 逐组件给独立评级，不整屏笼统打分。

## 新增评测项 checklist

1. 在对应维度 `eval-skills/eval-X-<name>/` 建 `SKILL.md`，frontmatter 四键齐全（参考 `.claude/rules/skill-frontmatter.md`）。
2. 评级口径写在正文 + `aggregate`；两档制 `weight={ "优秀":n, "不达标":n }`。
3. 保存后看钩子输出 `[skill-frontmatter] OK`；若 FAIL 补齐再继续。
4. 工作流下次运行自动发现，无需改 JS。
