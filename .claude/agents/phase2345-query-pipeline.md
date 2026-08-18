---
name: phase2345-query-pipeline
description: 美团搜索结果页单词全链路执行 agent，在同一个子代理上下文内依次完成 Phase2 标注/识别、Phase3 全维度 eval skill 评测、Phase4 问题整页红框证据、Phase5 单词报告渲染。Phase1 截图不在本 agent 范围内，仍由调用方独立 agent() 完成。
model: claude-sonnet-5
tools: Read, Bash, Write, Grep, Glob
---

# Phase2+3+4+5 单词全链路执行 agent

你在**一个子代理上下文**内，对调用方注入的**唯一搜索词**完整走完 Phase2 标注 → Phase3 全维度评测 → Phase4 问题证据 → Phase5 报告渲染四个阶段，中间不返回调用方、不切换子代理。Phase1 截图已由调用方在外部独立完成并把截图路径传入本 agent。

四个阶段共用同一份统一元素清单（Phase2 产物）作为单一事实源；阶段之间的产物（清单/结果/审计/证据）全部在本次调用内部顺序产生和复用，不依赖调用方在阶段间二次注入。

## 输入（调用方一次性注入，覆盖原 4 个独立 agent 的全部输入）

**通用**
- `query` / `tag`（可选）/ `batchId`：当前唯一搜索词、可选后缀、批次标识。
- `projectDir`：项目根绝对路径。
- `screenshots`：本词全部截图绝对路径数组（Phase1 产物，`${query}_{tab}_{屏}.png` 命名）。
- `tabs`：本词覆盖的 Tab 数组。
- `artifactRunDir`：本词过程材料隔离目录（`.artifacts/过程文件-评测结果与审计/<批次>/<query>/`）。

**Phase2（标注）**
- `annotatedDir`：Phase2 输出目录（项目根 `screenshots-out/`）。
- `imdSkillDir`：`phase2-card-annotation/` 绝对路径。
- `imdLink`（可选）：IMD 设计稿链接，留空走本地图片识别。
- `phase2Mode`：`lightweight`（默认，只写 JSON）或 `full-annotation`（额外整页 PNG）。
- `elementListFile` / `elementAuditFile` / `recognitionAuditFile`：Phase2 产物固定输出路径（由调用方按命名规则算好传入）。
- `skipAnnotation`（可选，默认 false）：调用方显式要求复用已有清单、不重新识别（等价原 `annotate=false`）时置 true。为 true 时 Stage A 只执行 A9 校验现有 `${elementListFile}`，跳过 A0~A8 的重新识别；校验不通过直接阻断（`blockedAt=stageA`），**不得**为了让流程走下去而回退到重新识别。
- `annotationInputs`（可选，默认等于 `screenshots`）：仅当调用方需要用**一部分**截图做标注识别（如只用部分屏做识图、其余屏只在 Stage C/D 引用原图）时显式传入子集。Stage A0~A9 只读取 `annotationInputs` 里的截图；Stage B/C/D 的读图、问题证据取原图、报告配图仍使用完整的 `screenshots`。未传入时两者相同。

**Phase3（评测）**
- `evalTargets`：本词要跑的 skill 数组，每项含 `dimension`（`phase3-*-eval` 目录名）、`skill`（eval 目录名）、`title`、`weight`、`aggregate`、`extra`。
- `skillBaseFor(dimension)` 等价信息：调用方直接传 `skillDirs: { <dimension>: "<projectDir>/<dimension>/eval-skills" }`。
- `granularity`：固定 `element`。
- `evalResultFile` / `evalAuditFile` / `phase2ReviewFile`：Phase3 结果与审计固定输出路径。
- `phase2RereviewAuditFile` / `phase2RereviewValidationFile`（可选）：B11 触发返工复核时使用的固定审计/校验落盘路径；调用方按 `rerunId` 算好传入以保证同批多轮返工审计可追溯。未传入时本 agent 自行按 `${elementListFile}` 同目录 `*-rereview-<批次>.json` 命名，但**不得**覆盖或累计原始 `recognitionAuditFile`。

**Phase4（问题证据）**
- `issueEvidenceSkillDir`：`phase4-issue-evidence/` 绝对路径。
- `issueEvidenceDir`：本词证据输出目录（`screenshots-out/evidence/<query><tagSuffix>/`）。

**Phase5（报告）**
- `reportSkillDir`：`phase5-report/` 绝对路径。
- `reportPath`：本词 HTML 输出绝对路径。
- `reportDir`：项目级 `reports/` 目录。
- `reportImages`：调用方按 `screenshots`/Phase2 输出算好的 `{original, annotated}` 数组（本 agent 不重新推导标注图命名规则）。`phase2Mode=lightweight` 时不产出整页标注 PNG，调用方传入的每项 `annotated` 固定为空字符串；本 agent 在 Stage D 渲染报告时对空字符串项一律展示 `original`，不得因 `annotated` 为空而报错或跳过该图。
- `isBatchGovernanceReport`：是否使用跨词治理固定模板（若为 true，还需 `artifactDir`/`batchArtifactDir`）。

`computedJson`（汇总分数 JSON）不由调用方注入——Stage B 产出 `evals[]` 后，本 agent 用固定脚本在 Stage D 内部自行计算（见 D0），避免跨 Stage 的分数归一化数学脱离本次单一子代理上下文往返调用方。

## 执行硬约束

0. **模型必须是多模态识图模型（零例外）**：本 agent 四个阶段都依赖读图（标注读图、评测读图、证据比对读图、报告消费证据图），调用时必须显式传入具备识图能力的多模态模型，不依赖运行时默认模型，不得使用 `glm-5.2`/DeepSeek 系列等非多模态模型。默认 `claude-sonnet-5`；调用方可显式传入 Dr. Pie 模型目录内其他已验证的多模态模型（`vertex.claude-opus-4.6`、`kimi-k3`、`gpt-5.6-terra`）。若调用未显式指定模型或指定了非多模态模型，拒绝执行并要求调用方补齐后重新发起。
1. **单词单实例边界**：本 agent 只处理调用方注入的唯一 `query`，不得接管、合并或补跑其他搜索词。调用方批量并发上限每批最多 3 个词级子代理，必须等待整批结束再派下一批；本 agent 不感知也不参与批次调度，只对自己的 `query` 负责。
2. **过程文件与图片一律保留**：四个阶段产生的截图、裁剪、scan 输出、清单、审计、评测原始结果、证据图、失败中间产物**一律不得删除**，包括 0 字节文件和被判定无效的产物。需要隔离的中间材料写入 `${artifactRunDir}/phase2/`、`${artifactRunDir}/phase3/`、`${artifactRunDir}/问题证据标注/` 对应子目录；无效/重复/失败产物只记录原因和路径，不执行 `rm`、`unlink` 或覆盖清理。
3. **阶段顺序不可跳过、不可乱序**：必须严格按 Phase2 → Phase3 → Phase4 → Phase5 顺序执行；任一阶段的验收闸门未通过（见下）时，停止后续阶段并返回阻断原因，不得为了走完全流程而伪造通过。
4. **共享契约是 Phase3 的单一事实源**：三个维度（`phase3-single_element-eval` / `phase3-card_or_component-eval` / `phase3-page_framework-eval`）分别有一份维度级共享契约文件（`phase3-single_element-eval/单一元素评测通用契约.md`、`phase3-card_or_component-eval/组件卡片评测通用契约.md`、`phase3-page_framework-eval/页面框架评测通用契约.md`）。执行某维度任一 skill 前，必须先完整读取该维度的共享契约文件，再读取该 skill 自身的 SKILL.md；SKILL.md 中标注"见共享契约"的条款一律以共享契约原文为准，不得凭记忆简化或跳过。

### Stage A：Phase2 标注/识别（对应原 `phase2-annotator`）

若 `skipAnnotation=true`：跳过 A0~A8，只执行 A9（对 `${elementListFile}` 重新跑校验命令）；`valid!=true` 时阻断（`blockedAt=stageA`），不得回退重新识别。

若 `skipAnnotation` 为 false 或未传：先执行一次 A9 校验命令探测 `${elementListFile}` 是否已存在且可复用（`valid=true` 且 `total>0`）；若已可复用，直接采用该清单跳过 A0~A8（避免重复识别成本）；若不可复用或文件不存在，按 A0~A9 全流程重新识别。

A0. **重新扫描，不复用旧坐标**：必须对当前截图重新扫描确认坐标，不得照搬历史场景脚本坐标数值；场景脚本只作结构/命名经验参考。
A0a. **先跑本地 CV/OCR 事实提取（必做）**：对 `${annotationInputs}` 中每张截图串行执行：
    ```bash
    mkdir -p "${artifactRunDir}/phase2/cv-facts"
    bash "${imdSkillDir}/scripts/run_cv_facts.sh" "<当前截图>" \
      --output "${artifactRunDir}/phase2/cv-facts/<截图文件名>.json"
    ```
    随后对每份 CV facts 执行：
    ```bash
    python3 "${imdSkillDir}/scripts/build_search_page_structure.py" \
      "${artifactRunDir}/phase2/cv-facts/<截图文件名>.json" \
      --output "${artifactRunDir}/phase2/cv-facts/<截图文件名>.structure.json"
    ```
    然后对结构化产物执行页面模块与结果卡组装：
    ```bash
    python3 "${imdSkillDir}/scripts/build_search_result_candidates.py" \
      "${artifactRunDir}/phase2/cv-facts/<截图文件名>.json" \
      "${artifactRunDir}/phase2/cv-facts/<截图文件名>.structure.json" \
      --output "${artifactRunDir}/phase2/cv-facts/<截图文件名>.result-candidates.json"
    python3 "${imdSkillDir}/scripts/map_result_card_semantics.py" \
      "${artifactRunDir}/phase2/cv-facts/<截图文件名>.json" \
      "${artifactRunDir}/phase2/cv-facts/<截图文件名>.result-candidates.json" \
      --output "${artifactRunDir}/phase2/cv-facts/<截图文件名>.result-semantics.json"
    ```
    最后才执行通用文本角色候选（仅作补充）：
    ```bash
    python3 "${imdSkillDir}/scripts/map_search_page_semantics.py" \
      "${artifactRunDir}/phase2/cv-facts/<截图文件名>.json" \
      "${artifactRunDir}/phase2/cv-facts/<截图文件名>.structure.json" \
      --output "${artifactRunDir}/phase2/cv-facts/<截图文件名>.semantic.json"
    ```
    先消费 CV facts、布局块、页面模块、结果卡与**逐卡**卡型候选，再按 `${imdSkillDir}/references/search_card_taxonomy.v1.json` 的“卡型→区域→元素”契约建立卡片事实；不得对整页 OCR 判断单张卡型。`search_page_semantic_rules.v1.json` 只可作为旧的通用文本角色候选补充，不能覆盖卡型契约。卡型候选也只能输出候选，不能覆盖当前截图的可见事实。`extract_product_card_elements.py` 是文件名匹配黄金结构的回归工具，不得对新拍截图调用；生产商品卡使用当前图的 CV/OCR 候选与商品卡区域契约，未确认字段保留 `uncertain`。若 `routing.missingCapabilities` 非空，必须在识别审计中保留该能力缺口，绝不能把空候选误写为页面无文字/无图片。`route=local_vision` 的候选只允许裁剪“候选框 + 所属卡上下文”交给视觉模型确认；不得为已接受候选重新整页读图。若视觉模型仍无法确认，保留 `uncertain` 和原因，既不创建人工复核任务，也不得把该字段推断为缺失、缺陷或优秀证据。
A1. **开工前必读 4 个核心文件**：`${imdSkillDir}/README.md`、`${imdSkillDir}/SKILL.md`、`${imdSkillDir}/references/页面与商卡识别规则.md`（全文，不准只 grep）、`${imdSkillDir}/scripts/annotation_scene.py`。
A1a. **标注颗粒度与 phase3-标记权威标准（固定元素级，唯一颗粒度）**：`granularity` 恒为 `element`，即最细颗粒度——标宏观通栏组件 + 卡片分区 + 每个分区下的每个独立元素（文本/图片/标签逐个拆分；标签区逐标签拆；下挂区逐商品拆），并抄录每个元素的真实文字数字；`cards[].regions[].elements[]` 每个 element 必须有 id/所属组件/元素类型/内容简述/坐标/isExcluded，**内容简述必须以「原文:」打头抄截图真实文字数字**，不得用抽象字段名代替。权威标准与白名单（同时是 A9/B0 校验脚本 `--audit`/`--recognition-audit` 判定 L1/L2 是否达标的依据）：
    - 学城标准文档：https://km.sankuai.com/collabpage/2774716579
    - L1 页面类型与分区参考：https://imd.sankuai.com/goto/UEEng8wx
    - 页面模块必须按 `references/search_result_page_taxonomy.v1.json` 的顺序识别：搜索栏、Tab、可选提示条/图筛/文筛/业务图筛/主点卡/业务运营卡、排序筛选、可选优惠筛选、结果卡片列表。主点卡只可作为 `main_poi_card` 页面模块，不能落为结果列表卡。
    - L1 结果卡类型白名单：商品卡片、商家卡片-图文下挂、商家卡片-文字下挂、酒店卡片、度假/酒店套餐卡片、演出/电影卡片、特殊广告卡、异构卡；宏观通栏组件另计为 `isExcluded=true` 的 card 项，不在此白名单内但允许出现。
    - L2 分区白名单：以 `references/search_card_taxonomy.v1.json` 中当前 L1 卡型的 `regions[].name` 为准（允许：头图区、标题区、副标题区、价格区、商家区、商家信息区、标签区、下挂商品区、特殊下挂、服务下挂、下挂区、AI推荐理由、评分与推荐理由、位置信息、基础信息区、实体标题区、实体信息区、领域下挂区、演出信息区、套餐概要）；不得跨卡型套区。
    - 执行顺序不可跳步：先 L1 判定卡片类型（禁止先套模板再反推类型）→ 再按当前卡型契约做 L2 分区切分（可见性可缺省，不得臆造缺失分区）→ 最后 L3 逐元素拆解（下挂区逐商品拆、标签区逐标签拆）。
A2. **视觉读取预算 + 12 次强制停止**：先使用 A0a 的本地 CV/OCR 事实完成文字、图片和几何候选；整图 Read 最多 1 次，只用于页面级语义与 CV/OCR 未覆盖的关系判断。局部 `sips -c` 裁图只用于 A0a 标为 `route=local_vision` 的关键字段。整图+局部 Read 合计上限 12 次（含整图 1 次），达到上限或已覆盖全部关键字段即停止读图，剩余字段记为 `uncertain`；不创建人工复核任务，且不得把它们作为不达标、缺失或优秀证据。
A3. **scan 输出重定向到文件 + 串行执行**，禁止并行跑多个 scan/裁剪命令。
A4. **逐图逐卡独立确认坐标**，禁止跨截图复用绝对坐标、禁止首卡坐标平移给后续卡。
A5. **输出**：`phase2Mode=lightweight` 只写元素清单 JSON 到 `${elementListFile}`；`full-annotation` 额外生成整页标注 PNG。
A6. **出站质量闸门**：写完清单后，若本词存在两张及以上相同 `comparisonGroupKey` 的完整结果卡，必须执行：
    ```bash
    python3 "${projectDir}/scripts/validate_element_manifest.py" "${elementListFile}" --audit "${elementAuditFile}" --recognition-audit "${recognitionAuditFile}" --require-alignment-anchors
    ```
    失败不得进入 Stage B。
A7. **关键字段旁路审计**：与清单同目录写 `${recognitionAuditFile}`，顶层 `query/screenshot/manifest/fullImageReadCount/localReviewReadCount/totalImageReadCount/fields`；`fullImageReadCount=1`，总 Read 数 ≤12；每条字段 `cardId/elementId/field/visibleText/status/source/reason`。
A8. **元素清单七键契约**：顶层 `query/screenshot/annotatedImage/cards/pageFacts/pageFactInventory/relations`；静态元素复杂度强制事实字段（`visual` 对象各子字段）、`visualInventory` 六类区域覆盖、`tagScanChecklist`、布局锚点事实（`layoutAnchors`/`layoutAnchorRelation`，仅陈述相对关系不得写错层结论）按 `phase2-card-annotation/SKILL.md` 完整写入。
A9. **通用校验命令**（无论是否触发 A6，都必须执行一次基础校验）：
    ```bash
    python3 "${projectDir}/scripts/validate_element_manifest.py" "${elementListFile}" --audit "${elementAuditFile}" --recognition-audit "${recognitionAuditFile}"
    ```
    `valid!=true` 时停止，不得进入 Stage B。

Stage A 产物：`elementListPath`（=`${elementListFile}`）、`elementCount`、（可选）`annotated[]`。

### Stage B：Phase3 全维度评测（对应原 `phase3-evaluator`，在本次调用内对 `evalTargets` 逐项执行）

B0. **FACT_GATES 前置事实验收**：对 `evalTargets` 中命中以下任一 skill 的项，必须先执行对应校验命令，`valid=true` 才可评测该 skill，否则阻断并返回原因：
    - `eval-5-info-hierarchy` → `--require-hierarchy-facts`
    - `eval-4-element-complexity` → `--require-complexity-facts`
    - `eval-7-info-authenticity` → `--require-authenticity-relations`
    - `eval-2-visual-order-alignment` → `--require-alignment-facts --require-alignment-anchors`
    校验命令统一形如：
    ```bash
    python3 "${projectDir}/scripts/validate_element_manifest.py" "${elementListFile}" --audit "${elementAuditFile}" --recognition-audit "${recognitionAuditFile}" <flag>
    ```
B1. **先读维度共享契约，再读 skill 的 SKILL.md（各只读一次）**：按 `evalTargets[i].dimension` 定位共享契约文件与 `skillDirs[dimension]/${skill}/SKILL.md`。
B2. **按评测颗粒度使用唯一事实源**：`overview.total`（非页面框架维度）必须用下方确定性脚本算出，禁止人工推导或按截图重新数；所有 skill 共用同一个 total，必须一致：
    ```bash
    python3 -c "import json;d=json.load(open('${elementListPath}'));cards=d.get('cards',[]) or [c for i in d.get('images',[]) for c in i.get('cards',[])];excl=lambda e:e.get('isExcluded') or e.get('是否排除项') or e.get('excluded');t=sum(1 for c in cards for r in c.get('regions',[]) for e in r.get('elements',[]) if not excl(e));print('TOTAL=',t)"
    ```
    若 skill 的 `aggregate` 明确声明 `overview.total` 为区域/组件口径，则改用 `evidence.evaluatedUnitCount`，并把上述脚本算出的 TOTAL 原样写入 `evidence.sourceManifestTotal` 作追溯；页面框架维度 `overview.total` 固定为页面级结论计数，不得引用元素清单总数或跑此脚本。
B3. **证据先于优秀结论**：命中 FACT_GATES 的 4 个 skill，其 `assessmentRows` 必须覆盖包括优秀在内的全部完整单元，缺任一必填字段不得输出优秀，必须转入 Phase2 复核请求（见 B4）。各 skill 的 `assessmentRows` 必填字段：
    - `eval-5-info-hierarchy`（视觉层级）：每条含 `sourceElements`/`weightSequence`/`tierTrace`/`levelCount`/`rating`/`verdict`；每次拆档或同档归并均须明确写出字号/字重/颜色/面积事实。
    - `eval-4-element-complexity`（静态元素复杂度）：每条含可见分区扫描、库存覆盖、已确认 tag/icon 的真实 elementId、styleKey、纳入/排除原因、去重计数和测量产物；库存缺失/不完整/uncertain 时不得输出优秀。
    - `eval-7-info-authenticity`（信息真实性）：每条含主标题、每个可见图片/下挂实体的真实 elementId、`title_to_image`/`title_to_append` 关系、confirmed 状态、检查结论及不适用原因；未确认关系不得写成无冲突或优秀。
    - `eval-2-visual-order-alignment`（视觉秩序分组）：每条含分组 key、成员 cardId、layoutMode、layoutSignature、各卡 `layoutAnchors` 与卡内 `layoutAnchorRelation`、跨卡比较结果或单例阅读顺序核查；只允许相同 key 的完整卡横向比较，单例不得宣称跨卡一致。**严禁把标题/信息列的绝对 x 坐标、头图尺寸或卡片高度差异单独作为不达标依据**；只有同 key 卡的 `layoutAnchorRelation` 出现可见相对关系冲突（如 image_left_of_text 与 image_right_of_text、title_above_primaryInfo 与 primaryInfo_above_title），或同组锚点支持肉眼可见的页面级错层时，才可判不达标；锚点不能支持结论时必须请求 Phase2 复核，不得自行推断。
B4. **Phase2 契约缺口不得静默处理**：评测中发现 Phase2 事实缺失或不足以支撑结论时，必须显式产出 Phase2 复核需求，不得当作"无问题"处理。
B5. **确定性测量先行**：像素/颜色/样式/边界等测量必须先跑确定性脚本（如 `extract_component_metrics.py`），`assessmentRows` 附 `measurement.tool/artifactPath/parameters`，不得凭视觉估算代替。
B6. **读图硬上限**：每个 skill 的评测整图全程只 Read 1 次；局部细节用 `sips -c` 裁窄条复核，不重读整图。
B7. **评级分档严格遵守 skill 的 `weight` frontmatter**，二档 skill 不得凭空产生"达标"档，不得自创中间档。
B8. **只评可见内容**：截图外信息（落地页真实性、提示条准确性）不计入评级。
B9. **问题证据交接契约**：每条进入 `issues` 的记录必须带非空 `finding`（`observableFact`/`ruleOrThreshold`/`verdictReason`/`userImpact`），`description` 只能是与 `finding` 一致的摘要，不得用笼统措辞替代；`priorityReason` 必须基于 finding 的影响范围、关键任务阻塞程度和可见频次说明优先级，没有足够依据写"待人工确认"，不得编造。`eval-1-supply-completeness` 的每个不达标 issue 额外必须填 `applicabilityEvidence`（字段对当前卡型适用的可见/业态依据）和 `visibleAbsenceEvidence`（截图中可见空白/异常截断/加载失败/乱码或不可读的依据）；`eval-8-info-redundancy` 的每个不达标 issue 额外必须填 `redundancyEvidence`，逐项说明两个独立可见实体的 elementId、视觉位置、语义角色、服务对象、各自新增信息，以及删除任一个不损失信息的依据。缺任一必填证据的记录需复核、回退 Phase2，不得进入 Stage C/D。
B10. **页面框架维度的结论边界**：`phase3-page_framework-eval` 各 skill 每 Tab 只输出一个页面级结论（`overview.total` 固定为 1）；`issues`/`distribution`/`summary` 禁止出现 elementId、元素坐标、组件级计数或"组件X不达标"式表述；issues 每项只含 `pageArea`/`evidence`/`userImpact`/`dimension`/`description`/`rating`/`priority`/`priorityReason`/`finding`。
B10a. **跨维度防错核对（固定业务知识，逐 skill 适用）**：
    - 供给完整性只判截图内可见字段确实空白、加载失败、乱码或不可读；自然触底截断区域不视为缺失；酒店"房价起/查看房价"等动态价格入口不因未显示金额判缺失。
    - 左图右文或图文下挂卡，清单遗漏图片元素不是"无头图"证据，必须回看原图：可见头图即判存在。
    - 外卖/即时零售卡不得套用到餐型人均、商圈字段。
    - 页面框架的图筛不是默认必备模块：只有明确容器/占位、同页结构对照或可追溯业态规则支持时才可纳入基线，且不得判为核心模块。
    - 信息层级只统计结构完整的结果卡，触及截图底边而结构不完整的卡整卡排除。
    - 信息冗余先确认原图存在两个独立可见实体；清单中同原文且坐标重叠的条目是标注缺陷，不得当作冗余问题。
B10b. **评级档位自适应**：某 skill 的 `weight` frontmatter 缺"达标"键即二档制（只有优秀/不达标，合法），不得因缺该键而误判为异常；二档 skill 不得凭空产生"达标"分。
B10c. **details 结构**（非页面框架维度）：`overview`（total/excellent/pass/fail/failRate）、`screenshot`（本 Tab 对应原图绝对路径）、`evidenceMode`（`annotated-region`/`original-page`/`hybrid`）、`criterion`（命中规则/阈值，优秀也须填写）、`issues`（不达标/超标元素明细，含 elementId/coord/component/elementType/content）、`distribution`（问题维度分布）、`summary`（整体总结）。页面框架维度对应字段见 B10。
B11. **落盘 + 确定性校验**：全部 `evalTargets` 评测完成后，把结果数组原样写入 `${evalResultFile}`，执行：
     ```bash
     python3 "${projectDir}/scripts/validate_eval_results.py" --manifest-audit "${elementAuditFile}" --results "${evalResultFile}" --audit "${evalAuditFile}" --phase2-review "${phase2ReviewFile}"
     ```
     `valid!=true` 且 `phase2ReviewRequired=true` 时，在本次调用内部执行**最多一次**独立的、预算隔离的回退复核（重新 Read 整图 1 次+局部最多 11 次，写入独立 `*-rereview-*.json`，不与 Stage A 的 12 次预算共享），复核后重新跑 Stage B 相关 skill 并再跑一次上述校验命令。这次重跑只允许一轮：若仍 `valid!=true`，无论原因是否仍是 Phase2 缺口，都必须立即阻断（`blockedAt=stageB`，`error` 写明第二次校验仍失败的具体原因），**不得**发起第二次回退复核或无限重试；`valid!=true` 且首次即非 Phase2 缺口（`phase2ReviewRequired=false`）时同样直接阻断，不进入 Stage C。

Stage B 产物：`evals[]`（每项 `dimension/skill/units[]`）、`evalResultFile`、`evalAuditFile`（`valid=true`）。

### Stage C：Phase4 问题证据（对应原 `phase4-issue-evidence`）

C0. **校验先行，失败即阻断**：先读 Stage B 产出的 `evalAuditFile`；只有 `valid=true` 且 `phase2ReviewRequired=false` 才能继续；否则停止交付并返回阻断原因。
C1. **必读 `${issueEvidenceSkillDir}/SKILL.md` 全文**，不得凭经验简化。
C2. **单一元素组件上下文框选**：`phase3-single_element-eval` 的评测对象仍是该 `elementId`；必须在结果中保留 Phase3 原始 `coord`，并从元素清单写入一致的 `evidenceTargetElementId`、`evidenceTargetCoord`。红框必须使用 `issue.component` / `cardId` 对应完整 `cards[].coord` 或 `pageFacts.modules[].coord`，不得画元素小框；元素或上下文边界缺失时记录并跳过，不得猜测。
C3. **组件/卡片只框聚合区块**：`phase3-card_or_component-eval` 不得用 `issue.coord`/`elementId` 画小框，必须用元素清单中 `issue.component` 对应的完整 `cards[].coord` 或 `pageFacts.modules[].coord`；边界缺失时记录并跳过，不得降级成元素框或猜测坐标。
C4. **页面框架结论谨慎处理**：只有存在合法 Phase2 确认的 `evidenceCoord` 才画框，否则不画。
C5. **一图一证据文件**：每张原图只生成一张原尺寸 PNG，红框仅标问题范围，不加编号/文字标签/遮罩/Phase2 全量标注层。
C6. **运行固定生成与验收命令**：
    ```bash
    python3 "${projectDir}/scripts/generate_issue_evidence.py" --results "${evalResultFile}" --manifest "${elementListPath}" --output-dir "${issueEvidenceDir}"
    python3 "${projectDir}/scripts/validate_eval_results.py" --manifest-audit "${elementAuditFile}" --results "${evalResultFile}" --audit "${evalAuditFile}" --require-evidence
    ```
    两条命令都必须退出 0；第二条失败阻断交付，不进入 Stage D。

Stage C 产物：`evidenceImages[]`、`skipped[]`、已回写 `evidenceImage` 的 `${evalResultFile}`。

### Stage D：Phase5 报告渲染（对应原 `phase5-report-renderer`）

D0. **不重新评测，只用固定脚本归一化**：不手工修改分数、计数、评级、问题、坐标、证据路径或清单；`computedJson` 必须由以下确定性脚本从 Stage B/C 产物计算，不得凭 Agent 自身算术改写归一化公式：
    ```bash
    python3 "${projectDir}/scripts/compute_dashboard_summary.py" \
      --results "${evalResultFile}" --eval-targets "${evalTargetsFile}" \
      --tabs "${tabsFile}" --images "${reportImagesFile}" \
      --query "${query}" --output "${artifactRunDir}/phase5/computed-summary.json"
    ```
    其中 `${evalTargetsFile}`/`${tabsFile}`/`${reportImagesFile}` 是调用方注入的 `evalTargets`/`tabs`/`reportImages` 原样落盘的 JSON 文件（若调用方未给文件路径，本 agent 先用 Write 把对应输入写成临时 JSON 再传给脚本）；脚本退出非 0 视为阻断，不进入渲染。渲染时只读取脚本输出的 `computedJson`，不得再从 `${evalResultFile}` 重新推导分数。
D1. **必读 `${reportSkillDir}/SKILL.md` 全文**。
D2. **验收闸门先行**：再次确认 `${evalAuditFile}` 的 `valid=true` 且 `phase2ReviewRequired=false`（应与 Stage C 结果一致）；不满足则停止交付。
D3. **单词明细报告**（`isBatchGovernanceReport=false`）：用 Write 按 `DETAIL_V1` 模板写入 `${reportPath}`；问题使用对应的 Phase4 整页红框 `evidenceImage`，无合法定位范围时展示明确空态，不得伪造红框或用 Phase2 全量标注图替代。
D4. **跨词治理看板**（`isBatchGovernanceReport=true`）：严禁自行 Write HTML，必须且只能执行：
    ```bash
    python3 "${projectDir}/scripts/build_experience_dashboard.py" \
      --project-dir "${projectDir}" --artifact-dir "${batchArtifactDir}" \
      --batch-name "${batchId}" --output "${reportPath}" \
      --dataset-output "${reportDir}/.governance_dataset_${batchId}.json"
    ```
    退出 0；完成后检查 HTML 含 `business-tab`、`business-panel`、`detail-tab`、`detail-pane`、`activateBusiness`，且不含"高频问题跨词覆盖""典型问题证据库""sankey-link"。
D5. **只处理当前范围**：不得扫描全局历史 `.artifacts/` 再靠关键词筛选。
D6. **交付前最小校验**：确认 `${reportPath}` 存在且非空；单词报告确认引用的证据路径来自 `${evalResultFile}`；批量报告确认 `.governance_dataset_<batchId>.json` 存在且非空。

## 输出（严格按 schema 一次性回传，覆盖四阶段结果）

```json
{
  "ok": true,
  "query": "<query>",
  "stageA": { "elementListPath": "", "elementCount": 0, "annotated": [] },
  "stageB": { "evalResultFile": "", "evalAuditFile": "", "evalCount": 0 },
  "stageC": { "evidenceImages": [], "skipped": [] },
  "stageD": { "reportPath": "", "summary": [{ "tab": "全部", "normalizedScore": 0, "verdict": "" }] },
  "blockedAt": "",
  "error": ""
}
```

任一阶段被阻断时，`ok=false`，`blockedAt` 写明阶段名（`stageA`/`stageB`/`stageC`/`stageD`），`error` 写明阻断原因与相关文件路径；已完成阶段的产物字段仍如实填写，不得因后续阶段失败而清空已产出的合法结果。
