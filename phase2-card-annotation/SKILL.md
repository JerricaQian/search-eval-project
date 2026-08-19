---
name: phase2-card-annotation
description: "对搜索结果页截图执行 Phase2 轻量识别：仅以本地 CV/OCR、卡型契约、拓扑和确定性语义门控，为每张截图分别生成一个包含该页全部事实及整页门控状态的 JSON；不合并多图、不让视觉模型补读 OCR、不生成整页标注图、不执行 IMD 操作，也不输出评测结论。"
---

# Phase2 轻量识别

## 1. 目标、边界与产物

Phase2 只采集事实：当前截图中的页面模块、结果卡、最小元素、坐标、可见原文与视觉规格。它为 Phase3 提供唯一事实源。

## 两条流程、一个元素契约（硬约束）

必须明确区分两条流程：

1. **黄金样本校准流（离线）**：允许在已经确认的截图/卡片边界内使用 PaddleOCR，并允许模型视觉能力逐像素复核标题、元素语义归属和分组。所有改写都必须保留 bounded evidence 与校准来源。该流程只更新 `golden-sample-results/` 和离线回归引用，绝不能被生产入口导入。
2. **用户截图 Phase2 生产流**：只使用当前截图的本地 CV/OCR、卡型契约与门控；视觉模型和黄金字段值不得补读、猜测或注入。失败时有界重跑 Paddle/Tesseract，仍不满足契约就阻断，不发布伪完整 JSON。

两条流程允许的证据不同，但输出必须遵循同一个元素级契约：

- 完整且已知卡型的卡片必须有位于 `标题区` 的主标题元素。履约标签、配送时长、影院属性等不能代替标题。商家卡、商品卡、酒店卡、演出/电影卡都适用。
- 下挂按可见供给逐项分组：`items[0]` 只拥有下挂1的 `imageElements`、`textElements`、`priceElements`、`auxiliaryElements`，`items[1]` 只拥有下挂2；禁止把多项图片、文字、价格平铺到一个 region 后丢失归属。文字下挂未渲染图片时 `imageElements=[]`，不得伪造图片。
- `基础信息区`、`商家信息区`、`标签区` 必须按独立语义字段/独立视觉 chip 拆分；例如 `15-25m²｜2人｜双床` 是面积、人数、床型三个元素。不得按整行合并，也不得按单字切分。
- 元素边界以独立视觉实体为准，不以 OCR 返回的一行文字为准。同行但颜色、间距、容器、图形辅助或交互含义不同的标签必须分别建元素；参照“面部清洁”黄金样本中“美丽荟西子医疗美容”的三个标签。
- 文字/标签不得成为单字符元素；`起`、`¥` 等后缀或符号必须与所属价格合并。图片元素可使用空 `visibleText`。
- 任何一条不满足，黄金校准不得标记完成，生产识别不得设置 `phase3Ready=true`。
- **结构完整不等于文字正确。** 每个 `status=confirmed` 的标题和下挂文字/价格必须有同一原图范围内的完整可见像素证据。仅通过 schema、字段非空或卡片数量检查，不得宣称黄金样本正确。
- 标题、文字下挂、常规图文下挂、异构下挂的长期识别规则采用“已校准黄金样本的结构范例 + 当前截图像素证据”，不用某张图的坐标、槽位宽高、列数或字段值充当规则。具体范例与 JSON 骨架见 `references/golden_structure_exemplars.v1.md`。
- 黄金样本只在文档明确标注的结构范围内作为范例。例如引用“茶山季（合生汇店）”是为了说明异构下挂和常规图文下挂的表达方式，不代表复制该卡的文字、位置、数量、顺序或其他区域标注。
- 黄金校准明确要求 PaddleOCR 时，实际后端不是 `paddleocr` 必须立即失败；禁止静默回退 Tesseract 后仍把产物标成 Paddle 证据。
- 黄金发布 JSON 的文字事实只保留元素级 `visibleText`；`boundedEvidence` 仅保留像素坐标溯源，不重复发布 observation `text`，也不发布 `ocrConfidence`。OCR 原文与置信度只允许存在于离线过程证据目录，不能成为黄金或 Phase2 最终 JSON 的消费字段。
- 图片内部的包装字、品牌字和装饰字属于图片像素，不另建 UI 文本或标签元素；只有与图片分离、承担界面语义的可见文字才拆成元素。

### 结构参照法（优先于坐标模板和 OCR 行形状）

识别顺序必须是：**判断卡型 → 判断区域 → 按可见边界枚举每个下挂项 → 为每项选择最接近的黄金结构范例 → 在当前截图中定位该项的实际语义元素 → 使用当前流程允许的 OCR/模型证据复核可见原文**。OCR 是读取已经定位的元素，不负责凭文字行形状创造卡片结构。

使用黄金范例时遵守四条原则：

1. **学习结构，不复制答案。** 范例规定字段怎样归属、哪些元素可选、异构如何表达；当前截图独立决定文字、坐标、数量、顺序和裁切状态。
2. **按项判断，不按区域套一种模板。** 同一下挂区域中的每个可见项分别选择结构；一个项与范例匹配，不构成停止识别其余可见项的条件。
3. **语义角色不是固定槽位。** 商品/服务文字、现价、价格折扣、原价、销量等由视觉关系和语义决定，可换行、移位或缺省；它们没有跨截图固定的像素宽高或相对偏移。
4. **只记录可见事实。** 页面边缘项按当前可见内容建立同样的元素结构并标记裁切，不补造屏外文字；证据不足则 `uncertain`，不得用范例字段值填空。
5. **先分视觉实体，再读实体文字。** OCR 合并框只是候选；当前截图中独立的颜色段、容器、间隔或功能单元具有更高的分元素优先级。多个 OCR 后端冲突时，选择与独立视觉实体边界一致且覆盖完整字形的证据，不选择“文本更长”的合并框。

遇到新布局时，先在 `references/golden_structure_exemplars.v1.md` 中寻找同层级结构；只有视觉结构确实不同才新增异构结构及对应黄金范例。实现层的坐标扩框、卡片底边裁剪和遍历控制只是保障上述原则的手段，不能反过来定义业务规则。

### 规则沉淀层级

从错误案例更新规则时，按 **根因 → 可迁移的结构原则 → 具名黄金样本及 JSON 正例 → 适用边界 → 实现防回归** 记录。主 Skill 和结构范例描述前四层；像素阈值、裁剪扩框、循环退出条件等只进入算法实现或测试。除非数值本身属于输出协议，不把单张截图的像素经验提升为长期业务规则。

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
| 酒店单列/双列/民宿与混排细则 | `references/hotel_card_algorithm.v1.md` 与 `references/hotel_card_element_contract.v1.json` |
| 标题、文字下挂、图文下挂与异构下挂结构范例 | `references/golden_structure_exemplars.v1.md`；只学习结构，当前截图独立取证 |
| UI/图标检测、OCR 与颜色事实融合 | `references/screen_parser_backend.v1.md`；处理非文本 UI、图标漏检或评估 OmniParser 时读取 |
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

非文本 UI/图标候选与 OCR 分工按 `references/screen_parser_backend.v1.md` 执行。OmniParser 只可作为可选的本地候选检测后端：它提供图标/交互区域框及可选语义描述，不能替代 PaddleOCR、卡型契约、逐元素颜色测量或最终语义归属。依赖、权重或许可条件未满足时不得宣称已启用，也不得让其缺失阻断现有确定性 CV/OCR 流程。

## 4. 事实源、校验与参数化纪律（阻断）

1. 元素、模块/卡片边界、业务归属、原文、渲染或视觉事实有误，必须修正 Phase2 manifest；不得在 Phase3/4 结果中打补丁。
2. 每次新建、复用或修订 manifest 后都必须校验；`valid != true` 时不得进入 Phase3。
3. 收到 Phase3 回退请求时，保留旧 manifest/audit/过程候选，按新证据重建 Phase2，再重跑受影响的 Phase3；不得只改下游结论。
4. 禁止固定搜索词、机器路径、历史 `/tmp` 或场景脚本输出作为生产入口。
5. `validate_phase2_recognition.py` 是整页发布门控：OCR 碎片比例超限、异常文字、无结果卡、卡内可用事实不足、卡型未确认或未通过卡型最小契约时，必须写出 blocked JSON 并重跑本地 CV/OCR。它不读取 OCR 置信度，也不触发模型读图。
6. 门控 hooks 按顺序执行：字段文法、字符/脚本连贯性、双布局 OCR 一致性、同行碎片、语义原子性、卡型语义契约。hook 只报告异常和阻断，不按语言模型/词典改写 `rawText`。有界重识别只允许两种可追踪更新：保留被第二裁剪证明的原 OCR 字面子串，或以卡内 Paddle 直接识别替换明显混合脚本失败行；两者都必须保留原文、裁剪和接受理由。
7. 结果流最后一张重复卡自然触底时，若上一张卡已确认具体已知卡型且本卡无明确广告证据，可继承上一张卡型；只豁免因截断不可见的必需字段与语义锚点。当前屏幕已显示文字的乱码、OCR 分歧和字段文法错误仍阻断整页。
8. 中文语言纠错器只能作为可选异常检测 hook：检测到疑似形近字/不通顺时返回失败行和候选原因，随后重跑原图裁剪；不得把纠错器生成的句子直接写入 manifest。未安装本地模型时不得伪装成已完成语义校验。
9. 黄金 JSON 的人工卡型/坐标不能成为当前截图答案。`references/golden_page_truth.v2.json` 是允许模型辅助校准的离线回归真值，只能在推理结束后比较卡数、卡型、模块与 IoU，禁止传入生产命令。黄金元素校准可使用 `scripts/extract_golden_contract_evidence.py` 的有界 Paddle 证据与模型视觉复核，再由 `scripts/calibrate_golden_element_contract.py` 写回；这两个脚本禁止由生产入口调用。允许离线聚合经过清洗的归一化几何分布；缺坐标、整页误框和页尾残片必须排除。该分布只给已通过最小契约的卡型增加少量辅助分，不能补齐缺失证据或单独否决新布局。每次更新黄金样本后运行：

   黄金文本发布以结构范例和当前卡片的完整像素证据共同门控：标题与下挂不能由预设槽位生成；文字元素非空并不代表正确，必须能追溯到同卡、同元素且覆盖完整可见字形的 bounded observation；校准命令指定 `--require-backend paddleocr` 时任何后端降级均阻断。已有非空标题也必须按标题结构重新核验。

```bash
python3 phase2-card-annotation/scripts/learn_card_geometry_profiles.py \
  --output phase2-card-annotation/references/learned_card_geometry_profiles.v1.json
python3 phase2-card-annotation/scripts/enrich_golden_visual_facts.py
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

不同卡型必须使用各自边界策略：商品卡以单商品主图、标题和价格重复为界；商家图文下挂必须吸附下一商家头图前的商品图组；商家文字下挂必须吸附下一商家头图前的服务文字块；酒店单列按逐卡头图/标题锚切分，双列按独立网格单元逐格切分，头图高度逐卡量取；演出按竖版海报、电影按影院标题和场次块切分；套餐保持主图、概要和价格在同一卡内；主点卡位于普通结果列表前且不占 `listPosition`。完整细则只以卡型契约文件为准。

query 只写入输出上下文，不是卡型或页面结构主键。同一 query 的不同截图必须独立识别；混排页必须逐卡应用契约。酒店页尾截断格只可从同列上一张已确认酒店卡继承，不能从行内相邻异构卡继承。处理酒店样本或酒店识别失败时，读取 `references/hotel_card_algorithm.v1.md`；需要双列房型元素分区时再读取 `references/hotel_card_element_contract.v1.json`。

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

每个非图片元素必须记录当前元素框实测的 `visual.textColor`、`backgroundColor`、`colorRole` 与 `colorEvidence`；测量失败时保留空字符串、`unknown` 和失败证据，并阻断依赖该字段的 Phase3，不得省略字段或从业务词推断。标签/icon 还必须记录 `containerShape`、图形辅助和是否计入复杂度。图片不在 Phase2 预计算综合色数，必须写 `render.isPhoto=true`、准确坐标及 `photo_excluded_phase3_pixel_measurement_required`，Phase3 再据此建立排除 mask 并运行确定性像素统计。

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
