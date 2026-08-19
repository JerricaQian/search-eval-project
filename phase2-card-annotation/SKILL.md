---
name: phase2-card-annotation
description: "对搜索结果页截图执行 Phase2 轻量识别：仅以本地 CV/OCR、卡型契约、拓扑和确定性语义门控，为每张截图分别生成一个包含该页全部事实及整页门控状态的 JSON；不合并多图、不让视觉模型补读 OCR、不生成整页标注图、不执行 IMD 操作，也不输出评测结论。"
---

# Phase2 轻量识别

## 1. 目标、边界与产物

Phase2 只采集事实：当前截图中的页面模块、结果卡、最小元素、坐标、可见原文与视觉规格。它为 Phase3 提供唯一事实源。

只做：**每张截图 → 本地 CV/OCR 候选 → 卡型/元素识别 → 整页门控 → 该图独立元素清单 JSON → schema 校验**。

不做：整页画框 PNG、IMD/设计稿操作、体验评级、问题结论、人工复核任务、跨截图坐标复用，以及用黄金样本补造当前截图事实。

每张截图必须独立生成且只生成一个主 JSON；不同截图不得合并进同一个识别 JSON。该截图的唯一 Phase3 输入是：

- `screenshots-out/elements_<截图文件名>[_<tag>].json`：只包含对应截图的页面模块、卡片、最小元素、视觉事实、关系及 `recognition` 整页门控状态。

同名 `.audit.json`、可选 `.recognition-audit.json` 和 `.artifacts/.../phase2/` 只用于调试、回归与追踪来源，不是 Phase3 的第二事实源。门控失败仍必须写出主 JSON，但其中 `recognition.phase3Ready=false`，Phase3 必须拒绝消费。

批量黄金回归产生的 `index.json` 只索引每张截图自己的 `canonicalManifest` 并汇总指标；它不包含、替代或合并各截图的完整识别事实，永远不是 Phase3 输入。

`uncertain` 只表示当前证据不足；绝不表示缺失、错误、不达标、优秀或待创建的人工任务。

## 2. 当前规则与数据源

| 用途 | 唯一来源 |
| --- | --- |
| 页面模块与结果流顺序 | `references/search_result_page_taxonomy.v1.json` |
| 卡型、分区与元素候选 | `references/search_card_taxonomy.v1.json` |
| 卡型边界与最小证据 | `references/card_recognition_contracts.v1.json` |
| 黄金样本聚合几何经验 | `references/learned_card_geometry_profiles.v1.json`；只作软证据 |
| OCR 文本角色候选 | `references/search_page_semantic_rules.v1.json` |
| 清单及审计 schema | `scripts/validate_element_manifest.py` |
| 黄金样本回归 | `golden-samples/` 与 `golden-sample-results/`；不得外推到新截图 |

`extract_product_card_elements.py` 仅用于已登记文件名的黄金回归，不能用于新截图。新截图只能消费本次 CV/OCR、卡型候选和本地像素/拓扑证据。

## 3. 执行流程

对每张截图串行运行；所有路径由 `projectDir`、`batch`、`query`、`tag` 推导，禁止写死搜索词或历史目录。

生产入口是一条命令；它直接产出 Phase3 manifest、识别审计和校验审计：

```bash
python3 phase2-card-annotation/scripts/run_phase2_recognition.py \
  --query <query> --screenshot <screenshot> --output <elements.json> \
  --artifacts-dir <this-batch-artifacts-dir>
```

需要排查来源时才追加 `--recognition-audit <elements.recognition-audit.json>`；不加也不影响主 JSON 的完整性。

以下是该入口内部的可审计展开流程；只用于诊断或替换某一识别步骤：

```bash
bash phase2-card-annotation/scripts/run_cv_facts.sh <screenshot> --output <facts.json>
python3 phase2-card-annotation/scripts/build_search_page_structure.py <facts.json> --output <structure.json>
python3 phase2-card-annotation/scripts/build_search_result_candidates.py <facts.json> <structure.json> --output <candidates.json>
python3 phase2-card-annotation/scripts/map_result_card_semantics.py <facts.json> <candidates.json> --output <card-semantics.json>
python3 phase2-card-annotation/scripts/map_search_page_semantics.py <facts.json> <structure.json> --output <text-semantics.json>
python3 phase2-card-annotation/scripts/validate_phase2_recognition.py \
  --facts <facts.json> --result-candidates <candidates.json> \
  --card-semantics <card-semantics.json> --text-semantics <text-semantics.json> \
  --output <recognition-gate.json>
# 仅当上一步阻断：主入口自动执行一次以下卡内定向重识别，随后重建全部下游候选并再次整页门控
python3 phase2-card-annotation/scripts/reprocess_bounded_cards.py \
  --screenshot <screenshot> --facts <facts.json> \
  --result-candidates <candidates.json> --card-semantics <card-semantics.json> \
  --recognition-gate <recognition-gate.json> --output <facts.retry.json> \
  --report <bounded-card-reprocess.json>
python3 phase2-card-annotation/scripts/build_phase2_manifest.py \
  --query <query> --facts <facts.json> --result-candidates <candidates.json> \
  --card-semantics <card-semantics.json> --text-semantics <text-semantics.json> \
  --recognition-gate <recognition-gate.json> --output <elements.json>
python3 scripts/validate_element_manifest.py <elements.json> \
  --audit <elements.audit.json>
```

前五个文件是**过程候选 JSON**：保留 OCR/CV 原始坐标、双版面 OCR 一致性、颜色像素提示和未决项，便于重新识别；不使用或发布 OCR 置信度。其中每个文字/图片候选直接携带可转写为 Phase3 的 `render`、`textFacts`/`visual` 像素事实。`build_phase2_manifest.py` 只把同一次识别结果写入统一 JSON，不制造新事实。已确认元素进入 `cards[].regions[].elements[]`；未确认项进入主 JSON 的 `recognition.semanticHookFindings/reprocessTargets` 与 `pageFactInventory.uncertainElementIds`，绝不被误当作“页面没有”。

固定顺序：**初次 CV/OCR → 局部页面模块 → 结果卡候选 → 卡型最小契约 → 卡内分区/文本角色 → 初次整页门控 →（失败时）一次有界卡内重识别 → 全量重建结构/卡型/文本角色 → 最终整页门控 → 最小元素 → 统一 JSON → schema 校验**。任一卡失败即整页阻断；重识别最多一轮、每张失败卡最多三个裁剪，禁止部分页面进入 Phase3。不会因 OCR 字段失败而把截图送给模型读图。已确认字段不得重复裁读。

Tesseract 默认用 `PSM 6` 与 `PSM 11` 两种独立布局识别。主输出不得按置信度切换；核心语义须通过 `ocr_consensus` hook：结构化数字要求数值锚一致，自然文本只允许确定性的包含或高相似关系。价格行可在相同数值锚下选择脚本连贯性更好的独立布局文本；疑似价格可做少量有界遮罩复读，但都必须保留原文、独立布局和接受理由，禁止无锚纠错。行内相邻的汉字碎片先按空间合并，明显分隔的标签、价格和标题保持独立。

照片检测除多色轮廓外，允许以“大面积 + 高像素方差 + 足够彩色像素 + 非细长几何”补充低色相商品/商家照片；该规则不检测圆角容器，不按业务词推断图片。

PaddleOCR 只允许作为门控失败后的本地重跑后端：先用 CV 得到 `reprocessTargets` 的失败卡边界，再一次加载模型、顺序识别这些卡的标题/价格/信息列裁剪；禁止整页长图 OCR、禁止每个字段单独初始化模型。主入口会在初次门控失败时自动尝试这一轮；本地模型不存在或初始化失败时退回有界 Tesseract，设置 `PHASE2_DISABLE_BOUNDED_PADDLEOCR=1` 可完全关闭 Paddle。线程默认由 `PHASE2_OCR_THREADS=2` 限制。

## 4. 事实源、校验与参数化纪律（阻断）

1. 元素、模块/卡片边界、业务归属、原文、渲染或视觉事实有误，必须修正 Phase2 manifest；不得在 Phase3/4 结果中打补丁。
2. 每次新建、复用或修订 manifest 后都必须校验；`valid != true` 时不得进入 Phase3。
3. 收到 Phase3 回退请求时，保留旧 manifest/audit/过程候选，按新证据重建 Phase2，再重跑受影响的 Phase3；不得只改下游结论。
4. 禁止固定搜索词、机器路径、历史 `/tmp` 或场景脚本输出作为生产入口。
5. `validate_phase2_recognition.py` 是整页发布门控：OCR 碎片比例超限、异常文字、无结果卡、卡内可用事实不足、卡型未确认或未通过卡型最小契约时，必须写出 blocked JSON 并重跑本地 CV/OCR。它不读取 OCR 置信度，也不触发模型读图。
6. 门控 hooks 按顺序执行：字段文法、字符/脚本连贯性、双布局 OCR 一致性、卡型语义契约。hook 只报告异常和阻断，不按语言模型/词典改写 `rawText`。有界重识别只允许两种可追踪更新：保留被第二裁剪证明的原 OCR 字面子串，或以卡内 Paddle 直接识别替换明显混合脚本失败行；两者都必须保留原文、裁剪和接受理由。
7. 结果流最后一张重复卡自然触底时，若上一张卡已确认具体已知卡型且本卡无明确广告证据，可继承上一张卡型；只豁免因截断不可见的必需字段与语义锚点。当前屏幕已显示文字的乱码、OCR 分歧和字段文法错误仍阻断整页。
8. 中文语言纠错器只能作为可选异常检测 hook：检测到疑似形近字/不通顺时返回失败行和候选原因，随后重跑原图裁剪；不得把纠错器生成的句子直接写入 manifest。未安装本地模型时不得伪装成已完成语义校验。
9. 黄金 JSON 的人工卡型/坐标不能成为当前截图答案。`references/golden_page_truth.v2.json` 是允许模型辅助校准的离线回归真值，只能在推理结束后比较卡数、卡型、模块与 IoU，禁止传入生产命令。允许离线聚合经过清洗的归一化几何分布；缺坐标、整页误框和页尾残片必须排除。该分布只给已通过最小契约的卡型增加少量辅助分，不能补齐缺失证据或单独否决新布局。每次更新黄金样本后运行：

```bash
python3 phase2-card-annotation/scripts/learn_card_geometry_profiles.py \
  --output phase2-card-annotation/references/learned_card_geometry_profiles.v1.json
```

10. 黄金回归只在整条推理完成后做 `expectedCardTypes`/`predictedCards` 对照，绝不能向生产识别传入期望卡型：

```bash
python3 phase2-card-annotation/scripts/rerun_golden_cv.py \
  --output-dir .artifacts/golden-cv-rerun
```

```bash
python3 scripts/validate_element_manifest.py \
  <manifest.json> --audit <manifest.audit.json>
```

同一 `comparisonGroupKey` 有两张以上完整结果卡时，追加 `--require-alignment-anchors`。Phase3 的视觉层级、静态复杂度和真实性门槛分别由其 skill 追加对应校验参数；Phase2 不输出评级。

## 5. 页面与组件事实

根对象必须且只能含八个键：

```json
{
  "query": "布洛芬",
  "screenshot": "/abs/path/布洛芬_全部_1.png",
  "annotatedImage": "",
  "cards": [],
  "recognition": {},
  "pageFacts": {},
  "pageFactInventory": {},
  "relations": []
}
```

轻量模式下 `annotatedImage` 固定为空字符串。

`pageFacts` 至少记录 `screen`、`isContinuation`、`viewport` 和 `modules[]`。每个 module 含 `id`、`moduleType`、`coord`、`visibleStatus`、`contentRole`、`isListPrefix`、`isListItem`。

- 模块按视觉/功能独立区域登记：搜索栏、Tab、图筛、业务图筛、快筛、营销条、主点卡、异构卡、结果列表等。
- 普通连续结果只登记一个 `result_list`；Tab 或快筛内部项目不得误写为页面模块。
- 插入结果流的异构卡使用 `isListItem=true` 和连续 `listPosition`；首张结果前的提示/营销条使用 `isListPrefix=true`，不占结果位置。
- `pageFactInventory` 含 `complete`、`scanned`、`uncertainElementIds`、`notes`。看不清、自然触底和跨屏续接必须如实记录，不能写成“缺失”。

## 6. 卡片、分区与最小元素

每张卡必须含 `cardId`、`卡片类型`、`coord`、`regions`、`structure`、`factInventory`。坐标一律为 `[x, y, width, height]`。

```json
{
  "cardId": "C1",
  "卡片类型": "商品卡片",
  "coord": [16, 980, 1192, 480],
  "regions": [{"name": "头图区", "coord": [32, 996, 300, 300], "elements": []}],
  "structure": {
    "visibleStatus": "complete",
    "cardTypeCode": "product",
    "layoutMode": "left_image_right_text",
    "layoutSignature": "image|title>subtitle>price>merchant",
    "comparisonGroupKey": "flash_delivery|product|left_image_right_text",
    "isResultListItem": true,
    "isHeterogeneous": false,
    "listPosition": 1,
    "regions": []
  },
  "factInventory": {"complete": true, "scanned": ["card_boundary", "regions", "images", "text", "render_state", "visual_spec", "layout", "relations"], "uncertainElementIds": [], "notes": []}
}
```

卡型和分区以 `search_card_taxonomy.v1.json` 为准，不能把商品卡、商家图文下挂、文字下挂、酒店、套餐、演出/电影和主点卡套入同一模板。只登记当前截图可见的分区。

卡型决策只有三步：

1. 在已知卡型中，仅保留满足 `card_recognition_contracts.v1.json` 全部 `minimumEvidenceGroups` 且未命中 `forbiddenFeatures` 的类型；多个通过时才选择最接近者。
2. 没有已知卡型通过且存在明确广告标时归 `广告卡`。
3. 否则，只要是稳定独立渲染单元且有可见内容，归 `异构卡`；禁止输出 `unknown`。

不同卡型必须使用各自边界策略：商品卡以单商品主图、标题和价格重复为界；商家图文下挂必须吸附下一商家头图前的商品图组；商家文字下挂必须吸附下一商家头图前的服务文字块；酒店按酒店头图纵向重复或双列网格切分；演出按竖版海报、电影按影院标题和场次块切分；套餐保持主图、概要和价格在同一卡内；主点卡位于普通结果列表前且不占 `listPosition`。完整细则只以卡型契约文件为准。

同一 `comparisonGroupKey` 中有两张以上 `visibleStatus=complete` 的结果卡时，每卡必须提供 `layoutAnchors.image/title/primaryInfo` 与 `layoutAnchorRelation`。它们只描述卡内相对位置，不能写评测结论。

每个最小元素必须含 `id`、`所属组件`、`元素类型`（`文本`、`图片`、`标签`）、`内容简述`（可读文本以 `原文:` 开头）、`坐标`、`isExcluded`；排除项另写非空 `excludeReason`。真实头图、商品图、图筛配图均单列为图片；叠在图片上的系统标签/icon 仍单列。

## 7. 最小元素渲染、文本与视觉规格事实

所有元素写 `render`；文字再写 `textFacts`；标签/icon 与可判视觉实体写 `visual`。

```json
{
  "id": "C1-title",
  "所属组件": "C1",
  "元素类型": "文本",
  "内容简述": "原文:布洛芬咀嚼片",
  "坐标": [360, 996, 620, 52],
  "isExcluded": false,
  "excludeReason": "",
  "render": {"visibleStatus": "confirmed", "renderState": "normal", "sourceRegion": "标题区", "isPhoto": false, "isSystemUi": true},
  "textFacts": {"rawText": "布洛芬咀嚼片", "textStatus": "complete", "semanticRole": "title", "emphasisLevel": "primary", "fontSizeBucket": "medium", "fontWeightBucket": "bold", "textColorRole": "neutral"}
}
```

`visual.textColor` 可记录 CV 的前景像素中位色（例如 `#D93838`），同时保留 `colorRole` 与 `colorEvidence`；未测得背景/边框色必须保留空字符串，不能从业务词推断。图片不在 Phase2 预计算综合色数，必须写 `render.isPhoto=true` 和准确坐标，Phase3 再据此建立排除 mask 并运行其确定性像素统计。

- `renderState`：`normal | placeholder | blank | load_failed | naturally_cropped | abnormal_clipped | garbled | uncertain`；它是事实，不是结论。
- `textStatus`：`complete | naturally_ellipsized | abnormal_clipped | garbled | uncertain`。看不清就留空/`uncertain`，不得猜测。
- `semanticRole`：`title | subtitle | price | rating | sales | location | fulfillment | promotion | filter | recommendation | other`。
- 完整结果卡的文字若存在 `unknown`/`uncertain` 规格，必须记入 `factInventory.uncertainElementIds`；该卡不能作为视觉层级“优秀”证据。

## 8. 标签 / icon 视觉属性契约

这是 Phase3 静态元素复杂度的唯一输入。Phase2 只记录事实，不计分、不评级、不预聚合数量。

扫描范围：头图角标/腰封、标题前 badge、履约标与闪电 icon、基础信息、标签区、价格旁促销标、文字下挂、每个图文下挂商品的角标/腰封、保障标与图筛项。每个独立标签、角标、券标、腰封和 icon 都拆为一个元素；不能因颜色或轮廓相近而合并。

标签/icon 的 `visual` 必填。当前阶段不做通用圆角容器检测；未由像素事实确认时，`containerShape` 写 `unknown`，不得按业务词猜形状：

```json
{
  "entityKind": "tag",
  "visualStatus": "confirmed",
  "isColored": true,
  "isShaped": false,
  "colorRole": "red",
  "semanticRole": "券标",
  "containerShape": "unknown",
  "backgroundColor": "#D93838",
  "textColor": "#FFFFFF",
  "borderColor": "",
  "hasGraphicAssist": false,
  "graphicType": "无",
  "graphicAssistRole": "无",
  "countedInComplexity": true,
  "countDecision": "独立红色券标",
  "dedupDecision": "不与履约标或榜单标去重",
  "dedupWithElementIds": [],
  "styleKey": "标签|red|券标|unknown|无",
  "sourceRegion": "标签区"
}
```

`entityKind` 只能是 `tag | icon | text | image`；`colorRole` 只能是 `neutral | red | orange | yellow | green | blue | purple | multicolor | unknown`。`styleKey` 固定为“实体类别｜颜色角色｜语义角色｜容器形态｜图形辅助”；只有五段都相同并写明理由时才可去重。

每张完整卡还必须有 `visualInventory`（各可见分区的已确认元素、styleKey、是否计入与未确认项）和 `tagScanChecklist`。每项包含 `candidate`、`status: found|not_found|uncertain`、`checkedRegions`、`elementIds`、`visualBasis`。检查表提醒扫描，不能按搜索词补造标签。

### 业务/搜索意图标签扫描检查表

| 场景 | 优先扫描的可见候选 |
| --- | --- |
| 闪购/商品零售/水果/酒水 | 闪购与闪电、时令、赠品、冰爽价、神券/神价、已减/折扣、保障、商品图角标、品牌角标 |
| 餐饮外卖 | 品牌/自营、到店取/配送履约、招牌/鲜打、券标、满减/折扣、榜单、保障、直播状态 |
| 医药健康 | 品牌、医保/个账、原研/品质、口碑/加购、健康卡券、买药履约、保障/服务、商品图角标 |
| 酒店旅行/景点 | 品牌、星级/榜单、套餐/权益、限时优惠、直播状态、旅行角标、保障/履约 |
| 服务/维修/娱乐 | 品牌、上门/到店履约、直播状态、团购/券标、保障、榜单、折扣、活动角标 |

## 9. 关系、整页门控与不确定性

`relations` 只允许记录 `same_card`、`same_field_across_cards`、`title_to_image`、`title_to_append`、`overlapping_annotation`、`same_supply_candidate`。每条含 `from`、`to`、`status`、`evidence` 和可选 `normalizedValue`。

完整结果卡中，主标题与可见图片、下挂实体的关系必须分别写为 `title_to_image`、`title_to_append`；无法确认则写 `uncertain` 并登记关联元素。不得写“图文不符”“重复供给”“颜色过多”等评测结论。

主 JSON 的 `recognition` 至少包含 `contractVersion`、`status`、`phase3Ready`、`wholePageGate`、`blockingCardIds`、`backends`、`errors`、`semanticHookFindings`、`reprocessTargets`、`reprocess`。

- 只有 `status=confirmed`、`phase3Ready=true`、`wholePageGate=true` 且 manifest validator 通过时，Phase3 才能消费。
- 任一卡、任一阻断 hook 或页面级事实失败时，`status=blocked`、`phase3Ready=false`；`blockingCardIds` 给出重跑范围，但不代表其他卡可以先发布。
- `reprocessTargets` 只记录原图上的有界裁剪重跑目标和原因，不写模型补读任务，不写纠错器生成的替代文本。
- 可选的独立 recognition audit 只保留调试字段来源，不改变主 JSON 的状态或事实。
