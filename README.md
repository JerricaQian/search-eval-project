# 美团搜索结果页标准化评测 Agent

三维度、可组合、开箱即跑的端到端评测工作流：**截图 → Phase2 轻量识别（可选全量标注）→ 多维度评测 → 问题证据 → 合并 HTML 报告**。
共享资源在顶层，每个维度只放自己的 eval-skills，工作流自动发现。换电脑/换人只需跑一次 `setup.sh`。

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

### 第1步：放桌面
整个 `search-eval-project/` 可放在任意目录下（不再要求固定为 `~/Desktop/search-eval-project/`）。工作流不再提供 `projectDir` 兜底默认值，**运行时必须显式传入 `projectDir` 为项目实际所在的绝对路径**，否则会直接报错阻断。

### 第2步：配置环境（每台机器一次）
```bash
# 评已有截图：检查 Python、Node、图像依赖和项目结构
bash ~/Desktop/search-eval-project/setup.sh

# 现场截图：额外检查 Android 真机、ADBKeyboard 与美团 App
bash ~/Desktop/search-eval-project/setup.sh --with-device
```
默认模式不要求连接手机，适合复用已有截图；现场截图时才需要 Android 真机。若缺 Python 图像依赖，在项目根目录执行 `python3 -m pip install -r requirements.txt`。

### Phase2 本地 OCR（推荐）

Phase2 会先运行 `phase2-card-annotation/scripts/run_cv_facts.sh`，以本地 OCR 和既有 OpenCV 产出文本、坐标、图片候选和行间留白事实；视觉模型只处理低置信候选的局部裁剪。系统已安装 Tesseract 时可直接作为后端；如需更好的中文 OCR，可在项目虚拟环境中安装 PaddleOCR：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-ocr.txt
```

没有本地 OCR 时，提取器会把能力缺口记录为 `missingCapabilities`，不得据此认定文本或图片缺失。`uncertain` 不创建人工复核任务，也不能作为“不达标”、缺失或“优秀”的依据。

**手机端（仅现场截图）**：USB 连电脑 + 「传输文件」模式 + 开启 USB 调试 + 安装并登录美团 App。
**macOS 权限（关键）**：系统设置 → 隐私与安全性 → 完全磁盘访问权限 → 添加 CatPaw → **完全退出并重启应用**。不做这步评测子进程可能读不到桌面截图，报告会全空。

### 第3步：选择执行模式并运行

本项目支持两种**等价**执行模式：

1. **显式 Workflow（优先）**：当前 CatPaw / Claude Code 会话提供 Workflow 工具时，调用 `workflow/meituan_eval_workflow.js`；
2. **Agent 任务编排（回退）**：Workflow 工具不可用或用户要求逐阶段运行时，Agent 仍按 phase1 → phase2 → phase3 → phase4 → phase5 执行对应 skill、确定性审计和报告渲染。该模式不得跳过清单、审计或固定输出路径，结果口径与显式 Workflow 相同。编排前 Agent 必须确认：是否执行 phase2 标注、评测哪些维度（单一元素/组件或卡片/页面框架，可多选）、仅交付本地 HTML 或继续生成 NoCode 报告。

> `workflow/meituan_eval_workflow.js` 是依赖 Workflow 宿主 API 的 DSL，不能直接通过 `node` 执行。它不可用不代表评测不可执行，应切换为 Agent 任务编排。选择 NoCode 时仍须先完成本地 HTML 或批量治理数据集，再按 NoCode 流程处理线上发布。

在 Claude Code 里说：
> 帮我跑美团评测工作流，搜「库迪」，跑 card_or_component 维度，3个tab×3屏

或用 Workflow 工具：
```
scriptPath: ~/Desktop/search-eval-project/workflow/meituan_eval_workflow.js
args: { "query": "库迪", "dimensions": ["phase3-card_or_component-eval"], "tabs": ["全部","外卖","团购"], "screens": ["1","2","3"], "skipScreenshot": false }
```

跑完后 HTML 报告在 `reports/`，截图在 `screenshots/`，标注图与元素清单（若开启标注）在 `screenshots-out/`。

---

## 目录结构

```
search-eval-project/
├── README.md                       # 本文件
├── CLAUDE.md                       # 工作流声明（阶段/目录/数据流向，每次会话加载）
├── setup.sh                        # 跨机器环境检查（可选 --with-device 检查真机）
├── requirements.txt                # Python 图像/YAML 依赖
├── .gitignore                      # 代码与运行产物隔离规则
├── ADBKeyboard.apk                 # 中文输入法（现场截图时使用）
├── phase1-screenshot/               # phase1 共享截图能力
│   ├── SKILL.md                    # 截图流程+坐标+陷阱表
│   └── scripts/{run_scroll.sh, loop_screenshot.sh}
├── phase2-card-annotation/         # phase2 按需标注（组件+商卡分区可视化）[原 imd-card-annotation，已更名]
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
│   ├── build_experience_dashboard.py       # 批量本地治理看板 + 数据集生成器
│   └── import_to_nocode.py                 # 治理数据集导入 NoCode
├── workflow/
│   └── meituan_eval_workflow.js    # 标准化工作流（截图→识别→评测→证据→报告）
├── screenshots/                    # phase1 截图输出 / phase2 输入
├── screenshots-out/                # phase2 元素清单；可选全量标注图；phase4 证据图
├── .artifacts/过程文件-评测结果与审计/ # 按批次、搜索词、阶段隔离的评测结果与审计
└── reports/                        # phase5 HTML 与批量治理数据集输出
```

> **数据流向**：`screenshots/` ──Phase2 轻量识别──▶ `screenshots-out/`（统一元素清单；可选全量标注图）──Phase3 评测──▶ `.artifacts/过程文件-评测结果与审计/` ──Phase4 证据──▶ `screenshots-out/evidence/` ──Phase5──▶ `reports/`（HTML；批量治理看板还会输出 `.governance_dataset_<批次>.json`）──▶ NoCode 线上看板（可选）。Phase3 以元素清单为唯一事实源；全量标注 PNG 仅作可选人工复核素材。详见 `CLAUDE.md`。

---

## 工作流参数（args）

| 参数 | 默认 | 说明 |
|------|------|------|
| query | 库迪 | 搜索词 |
| dimensions | ["phase3-card_or_component-eval"] | 要跑的维度文件夹名数组，可多选组合 |
| tabs | ["全部","外卖","团购"] | 要评测的 tab |
| screens | ["1","2","3"] | 要评测的屏 |
| skipScreenshot | true | true=用已有图评测；false=现场 ADB 截图 |
| annotate | true | 默认先跑 Phase2；仅 `false` 显式跳过（标准工作流的元素级评测通常不应跳过） |
| phase2Mode | lightweight | `lightweight` 仅输出统一元素清单 JSON；`full-annotation` 额外输出整页标注 PNG |
| granularity | element | 标准工作流固定 `element`，确保三维度共用统一事实源 |
| imdLink | "" | 标注 IMD 设计稿链接（留空则对本地截图识别） |
| annotateScenes | [] | 指定参与 Phase2 的截图绝对路径数组，空=使用本轮截图 |
| projectDir | 必填，无默认值 | 项目根绝对路径；调用方必须显式传入 |
| screenshotDir | projectDir/screenshots | phase1 截图目录 / phase2 输入目录 |
| annotatedDir | projectDir/screenshots-out | phase2 标注产物（标注图 + 元素清单）输出目录，供 phase3 参考图文 |
| reportDir | projectDir/reports | 报告目录 |
| shotSkillDir | projectDir/phase1-screenshot | 截图 skill 目录 |
| imdSkillDir | projectDir/phase2-card-annotation | phase2 标注 skill 目录（原 imd-card-annotation，已更名） |
| issueEvidenceSkillDir | projectDir/phase4-issue-evidence | Phase4 问题证据 skill 目录 |
| reportSkillDir | projectDir/phase5-report | Phase5 汇总 skill 目录 |
| batchId | 单词运行 | 当前批次标识；批量治理报告必须显式传入 |
| tag | "" | 区分同一搜索词的多份截图与产物后缀 |

**典型用法**：
- 现场截图 + 单维度评测：`{ "query": "库迪", "dimensions": ["phase3-card_or_component-eval"], "skipScreenshot": false }`
- 只评测已有截图：`{ "query": "库迪", "skipScreenshot": true }`
- 多维度组合：`{ "query": "库迪", "dimensions": ["phase3-card_or_component-eval","phase3-single_element-eval"] }`
- 带标注：`{ "query": "库迪", "annotate": true }`
- 批量截图（不经工作流）：`bash phase1-screenshot/scripts/loop_screenshot.sh`

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

## 工作流各 phase（5 步）

1. **① 截图**：ADB 现场截图或复用已有图（9 张/词）。设备离线守卫，避免 0 字节覆盖。
2. **② Phase2 轻量识别（默认）**：默认 `annotate=true`、`phase2Mode=lightweight`，从 `screenshots/` 产出统一元素清单及识别审计到 `screenshots-out/`；只有 `phase2Mode=full-annotation` 才额外生成整页标注 PNG。清单必须先通过 `validate_element_manifest.py`，才可进入评测。
3. **③ 评测**：先自动发现所选维度的全部 eval skill（读 frontmatter），再按清单及其结构化事实评测，每项按 `aggregate` 聚合到 Tab 级评级 + 加权分，并将原始结果和审计写入当前批次 `.artifacts/过程文件-评测结果与审计/<batch>/<query>/results/`。
4. **④ 问题证据**：只消费已通过 Phase3 校验的待优化问题。`phase3-single_element-eval` 保留元素级判定与精确定位，但红框展示所属完整组件/商卡上下文，并回写 `evidenceTargetElementId`、`evidenceTargetCoord`；组件/卡片维度同样框选完整聚合区块。生成原尺寸整页红框图并回写 `evidenceImage` 后，以 `validate_eval_results.py --require-evidence` 再次验收。
5. **⑤ 报告**：仅消费已通过 Phase2、Phase3 与 Phase4 验收的结果；工作流 JS 侧按每维度 weight 的 min/max 做归一化（确定性，不靠 LLM 算术），`phase5-report` 渲染本地合并 HTML。两个及以上搜索词的跨词治理场景必须运行 `scripts/build_experience_dashboard.py`，并显式传入当前 `--artifact-dir`、`--batch-name`，确定性输出 `GOVERNANCE_DASHBOARD_V1` 本地看板与同批 `.governance_dataset_<批次>.json`；该看板固定为顶部导航 → 标题区 → 概览/业务两级 Tab，其中概览展示双栏摘要与业务入口，单业务按搜索词或按指标浏览问题明细与证据。

> **启动 Agent 任务编排前的确认**：Claude 会确认三项——① 是否执行 Phase2（默认 lightweight）；② 要跑哪些维度（卡片/组件、单一元素、页面框架，可多选）；③ 仅生成本地 HTML，还是继续生成 NoCode 报告。显式 Workflow 由调用参数决定。

---

## 批量治理看板与 NoCode 部署（可选）

当需要跨两个及以上搜索词汇总治理时，先用 `scripts/build_experience_dashboard.py` 生成本地 `GOVERNANCE_DASHBOARD_V1` HTML 与同批 `.governance_dataset_<批次>.json`；HTML 与数据集必须同批次，且前端不重新计算分数或问题率。

若需上线，改用 `phase5-report/nocode-dashboard/SKILL.md`：导入脚本以新建批次返回的真实 `batch_id` 关联六张看板表；上线前需验证浏览器匿名角色能读取当前批次。典型证据来自项目根 `screenshots-out/evidence/` 的 Phase4 整页红框图；线上页面不能读取本机 `file://` 路径，必须在取得用户授权后上传实际引用图片到 NoCode 工程的 `public/evidence/`，以 `/evidence/<原文件名>` 展示缩略图并点击打开大图。

> NoCode 页面是本地治理看板的数据库驱动复刻，必须使用相同的 Hero、三个顶层 Tab、七列汇总、三种维度色、筛选/定位交互和统计口径；不得新增或恢复“高频问题跨词覆盖”“典型问题证据库”等独立首页区块。

---

## 统一元素口径（标注 → 评测 的关键机制）

同一张截图，不同评测 skill 若各自拆分元素，元素总数会不一致（曾出现 49/50/51/51 偏差），无法横向对比。本工作流通过「标注产出统一元素清单」解决：

1. **Phase2 轻量识别（默认）**产出一份页面元素清单 JSON（单一事实源）：`<annotatedDir>/elements_<query>[_<tag>].json`（默认 `screenshots-out/`），结构包含 `cards[].regions[].elements[]`、`pageFacts`、`pageFactInventory`、`relations`。每元素含 id/所属组件/元素类型/内容/坐标/`isExcluded`；全量标注 PNG 仅在 `phase2Mode=full-annotation` 时额外生成。
2. 每次新产出、复用或修订清单都必须通过 `validate_element_manifest.py` 与对应 audit/recognition-audit；未通过即阻断 Phase3。
3. **评测 phase** 把清单路径 + 确定性计数脚本注入每个评测 agent prompt。单元素项的 `overview.total` 必须等于脚本输出；组件/页面项按各 Skill 的 `aggregate` 聚合，并保留 `evidence.sourceManifestTotal` 追溯，禁止人工重拆事实对象。
4. `isExcluded=true` 的元素（商家头图/营销大图/金刚 icon 等）不计入元素总数也不评测；`uncertain` 事实不能被当作 UI 缺失、错字或违规依据。

> **复用已有清单**：Phase2 启动前会先用 `validate_element_manifest.py` 审核 `elements_<query>[_<tag>].json` 及识别审计；仅确定性校验通过才复用。首次、文件失效或事实契约缺失时必须重新识别，旧产物保留供审计。

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

工作流各子 agent 的模型分配以 `workflow/meituan_eval_workflow.js` 中的 `SUBAGENT_MODEL` 为唯一事实源。全流程依赖读图（截图识别、标注、证据比对），因此必须是具备识图能力的**多模态模型**；`SUBAGENT_MODEL` 内置白名单校验，非多模态模型会直接报错拒绝执行。默认使用 `claude-sonnet-5`，可通过 `args.model` 显式切换到白名单内其他模型：

| agent | 模型（默认/可选） | 原因 |
|------|------|------|
| 截图、标注、发现、评测、报告、检查 | 默认 `claude-sonnet-5`；可选 `vertex.claude-opus-4.6`、`kimi-k3`、`gpt-5.6-terra` | 全流程统一多模态模型，避免不同阶段因模型差异产生口径漂移；确定性校验仍由项目内 Python/JS 脚本执行。`glm-5.2`/DeepSeek 系列等非多模态模型不在白名单内，禁止用于本工作流。 |

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
A: 各 skill 自行拆元素导致的口径漂移。解决：先开标注（`annotate=true`）产出统一元素清单，评测 phase 会把清单路径 + 确定性计数脚本注入每个 agent，要求 `overview.total` 必须等于脚本输出。详见上文「统一元素口径」。

**Q: 某个评测 skill 只有「优秀/不达标」两档，工作流报「缺达标键」**
A: 二档制 skill 合法，frontmatter `weight` 写 `{ "优秀": 1, "不达标": -1 }` 即可，「达标」键可省略；工作流发现脚本用 `.get("达标",0)` 兜底，schema 已把「达标」设为可选。不要硬凑三档。

**Q: Phase2 识别一直很慢 / 根本没动 / 卡死**
A: 几个可能：① 识别输出长或读图范围过大导致上下文/流式响应异常；当前工作流统一使用多模态模型（默认 `claude-sonnet-5`），模型设置以 `workflow/meituan_eval_workflow.js` 的 `SUBAGENT_MODEL` 为准。② 上次已产出 `elements_<query>[_<tag>].json`，但其 manifest 或 recognition-audit 未通过确定性校验，因而不能复用；③ 识别 agent 读了原图（2MB）+ scan 全量输出导致上下文爆炸 → scan 输出重定向到过程文件、只读 `sm_` 缩放图、规则分段读。

**Q: 评测 agent 计数还是不对（49/50/51）**
A: 评测 agent 读清单后仍自己数。工作流已注入确定性 python 计数脚本，要求 `overview.total` 必须等于脚本输出，禁止人工推导。若仍错，检查 agent 是否真跑了脚本而非自行计数。

**Q: 检查脚本输出 `EXISTS=0`，但文件明明存在**
A: python 的 `os.path.expanduser("$HOME/...")` **不展开 shell 变量**，只展开 `~`。工作流已改为 shell 侧 `P=$(echo "${elementListFile}")` 先展开 `$HOME` 再传给 python argv。自己写脚本时同理：要么传 `~/` 让 expanduser 处理，要么在 shell 侧展开后传绝对路径。

**Q: 报告里出现「AI 初步建议，待人工确认」徽标**
A: 该评测项 frontmatter `extra` 字段非空。用户已排除需人工审查的评测，若不想要此徽标，把 `extra` 留空。

**Q: NoCode 页面只有组件/卡片维度，或最新批次整页为空？**
A: 先确认 `.governance_dataset_<批次>.json` 已包含 `element/component/page` 三类 `dimensionScores`，再核对导入后的六张表是否均使用同一真实 `batch_id`。若 CLI 可查询但浏览器页面为空，优先检查匿名角色的 `SELECT`/RLS 权限和 `VITE_SUPABASE_URL`、`VITE_SUPABASE_ANON_KEY`，不要靠前端重新计算或复制伪造数据解决。

**Q: NoCode 的「查看典型证据」没有图片？**
A: 线上页面不能访问本机 `file://`。从数据集的 Phase4 `evidenceImage` 去重找出实际引用的 `screenshots-out/evidence/` 整页红框图，在取得上传授权后写入 NoCode 工程 `public/evidence/`，保留原文件名，并检查标题映射和 `/evidence/<文件名>` 请求。无映射时应显示明确空态，不应显示损坏图片。
