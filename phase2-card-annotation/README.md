# Phase2 轻量截图识别

本目录负责把搜索结果页截图转换成 Phase3 可消费的结构化事实。生产路径采用“本地 CV/OCR 候选 + 黄金结构范例 + 当前图片像素复核 + 卡型/枚举/元素契约门控”；模型只复核当前图片，不复制黄金字段，不生成整页标注图，也不执行 IMD 操作。

`phase2.atomic-manifest.v3` 每次写出前必须使用 `references/search_card_taxonomy.v1.json` 校验，并记录枚举契约版本与文件 SHA-256。所有标签元素统一使用 `kind: "tag"`，槽位名统一以 `_tag` 结尾，例如 `product_attribute_tag` 与 `scenic_rating_tag`。

生产 Phase2 与离线黄金校准共享同一证据策略和元素契约：完整已知卡必须有主标题；每个下挂项分别拥有自己的图片/文字/价格；基础信息和标签按语义原子拆分；禁止单字符文字元素。生产流同样使用 Paddle 与模型视觉复核，但所有事实必须来自当前截图，黄金只提供结构，契约不满足即阻断。

详细执行纪律见 `SKILL.md`；卡型边界与最小证据以 `references/card_recognition_contracts.v1.json` 为准。

## 输入与输出

输入是一张 PNG/JPG 截图。每张截图独立生成一个主 JSON：

```text
截图 A ──▶ elements_A.json
截图 B ──▶ elements_B.json
截图 C ──▶ elements_C.json
```

禁止把多张截图的页面、卡片或元素合并进一个识别 JSON。批量回归的 `index.json` 只记录每张图自己的 `canonicalManifest` 和统计指标，永远不是 Phase3 事实源。

主 JSON 固定包含 `query`、`screenshot`、`annotatedImage`、`cards[]`、`recognition`、`pageFacts`、`pageFactInventory` 和 `relations`。门控失败仍写主 JSON，但必须设置 `recognition.phase3Ready=false`，Phase3 不得消费。

## 生产入口

```bash
.venv/bin/python phase2-card-annotation/scripts/run_phase2_recognition.py \
  --query <query> \
  --screenshot <absolute-screenshot-path> \
  --output <one-screenshot-elements.json> \
  --artifacts-dir <one-screenshot-artifact-dir> \
  --recognition-audit <one-screenshot-elements.recognition-audit.json> \
  --visual-review <current-screenshot-main-session-review.json> \
  --require-bounded-paddleocr

.venv/bin/python phase2-card-annotation/scripts/build_current_image_calibration_audit.py \
  <one-screenshot-elements.json> \
  --output <one-screenshot-elements.recognition-audit.json>

.venv/bin/python scripts/validate_element_manifest.py \
  <one-screenshot-elements.json> \
  --audit <one-screenshot-elements.audit.json> \
  --recognition-audit <one-screenshot-elements.recognition-audit.json> \
  --require-current-image-calibration
```

## 当前执行链

1. `extract_cv_facts.py`：Tesseract 双版面 OCR、文本行、颜色提示和照片候选。
2. `build_search_page_structure.py`：页面内容块。
3. `build_search_result_candidates.py`：页面模块和按卡型区分的结果卡边界。
4. `map_result_card_semantics.py`：按最小证据契约确认已知卡型、广告卡或异构卡。
5. `map_search_page_semantics.py`：补充文本角色候选。
6. `validate_phase2_recognition.py`：字段文法、文本连贯性、双版面一致性和卡型语义的初次整页门控。
7. 初次门控失败时，`reprocess_bounded_cards.py` 自动执行一次失败卡定向重识别（每卡最多三个裁剪），随后重新生成结构、卡型、文本角色并再次整页门控。
8. `build_phase2_manifest.py`：把最终同一次识别事实写入该截图自己的主 JSON。
9. 模型读取当前整图一次，结合本次 Paddle/CV 产物全量复核卡片、区域、下挂项、标签边界、字面和漏标；冲突处才读局部裁图。
10. `build_current_image_calibration_audit.py` 与 `validate_element_manifest.py`：逐元素交叉核对当前像素证据，并校验 Phase3 所需事实与整页状态。

第 3 步之后先做结构门禁；第 7 步使用同一个 Paddle 实例，按每张卡“主信息区 / 下挂区”顺序读取（通常每卡 2 裁剪，最多 3），输出行框及可用的词/字符框和绝对坐标，不按失败字段逐个重启 OCR。第 9 步是必须提供的主会话局部复核，不是可选人工备注。最后任一 `itemGroups`、枚举、schema 或审计校验失败都会回写主 JSON 的 `recognition.phase3Ready=false`。

主流程不读取 OCR 置信度。疑似价格只允许在数值锚一致时做有界遮罩复读或选择更连贯的独立布局文本，并保留原始文本和接受理由。PaddleOCR 只在初次门控失败后自动加载一次，顺序处理门控给出的失败卡裁剪，不能处理整页长图；设置 `PHASE2_DISABLE_BOUNDED_PADDLEOCR=1` 可关闭，`PHASE2_OCR_THREADS` 默认是 `2`。

## 卡型与页尾规则

卡型决策顺序固定为：满足最小契约的已知卡型 → 有明确广告证据的广告卡 → 稳定独立的异构卡。禁止输出 `unknown`。

结果流最后一张重复卡自然触底时，可在无广告证据的前提下继承上一张已确认已知卡型。只豁免因截断不可见的必需字段；已显示文字的乱码、OCR 分歧和字段文法错误仍阻断整页。

不同卡型的边界策略不得混用：商品卡按单商品主图/标题/价格重复切分；商家图文下挂吸附商品图组；商家文字下挂吸附服务文字块；酒店单列按逐卡头图/标题锚切分、双列按独立网格单元逐格切分，头图高度逐卡测量；演出/电影、套餐和主点卡分别使用自己的拓扑契约。酒店细则见 `references/hotel_card_algorithm.v1.md`。

### 已知失败模式与回归口径（2026-08-20）

“隆江猪脚饭”样本验证了以下必须同时满足的发布条件：顶部状态/调试层不参与 OCR；图片内来源不生成正文列退化裁剪；重复商家头图之间的摘要和横滑商品区是一张 `商家卡片_图文下挂`，不能退回异构卡；确认该卡型后商品图归“下挂商品区”而非“特殊下挂”；横滑商品必须逐项拥有图片/文字/价格所有权，没有确认价格的项为 `uncertain`；底部卡仅对屏幕外部分标 `naturally_cropped`。主会话局部复核的字段必须进入 recognition audit，并且 OCR 门控、manifest schema、itemGroups 所有权与枚举校验全通过后才可进入 Phase3。

搜索词不是页面模板主键。同一搜索词的多次截图分别生成 JSON，允许结果模块和卡片不同；同页混排时逐卡判型，不能用页面多数卡型覆盖单卡。双列酒店页尾截断格只从同列上一张已确认酒店卡继承。

## Phase3 事实

每个最小元素携带坐标、归属、原文、`render`，文字携带 `textFacts`，标签/icon 携带 `visual`。Phase2 记录颜色、颜色角色、字重/字号桶、渲染状态、关系和标签扫描库存；不输出评级。

当前阶段不做通用圆角容器检测。无法由像素确认的 `containerShape` 写 `unknown`。图片在 Phase2 只记录准确坐标与 `render.isPhoto=true`，Phase3 再做确定性像素统计。

## 回归与经验沉淀

黄金样本只用于推理后的回归和清洗后的归一化几何学习，不能向当前截图注入人工卡型、坐标或字段值。酒店样本位于 `golden-samples/hotel-card/`；相同 query 的不同 `searchInstance` 不得合并：

```bash
python3 phase2-card-annotation/scripts/learn_card_geometry_profiles.py \
  --output phase2-card-annotation/references/learned_card_geometry_profiles.v1.json

python3 phase2-card-annotation/scripts/rerun_golden_cv.py \
  --output-dir .artifacts/golden-cv-rerun
```

仓库只保留 `golden-atomic-2.0/` 下最新的 34 份页面可重建黄金 JSON 和一个汇总 `index.json`，这 34 份 atomic v3 同时也是后续重建的原始输入。`scripts/build_atomic_manifest_v3_goldens.py` 默认重新校验并规范化写出它们、重建索引，不依赖旧格式。旧 `golden-sample-results/**/*.elements.json` 已外部归档；只有一次性追溯迁移时才显式传入 `--legacy-source-root`。逐 manifest audit sidecar 已删除，审计摘要集中保存在索引中。

## 历史兼容文件

`scenes/`、旧 `annotation_scene.py`、`annotate_image.py` 和 IMD 脚本仅保留历史标注复现能力，不属于 Phase2 生产识别流程，不得作为新截图的坐标、卡型或元素事实来源。
