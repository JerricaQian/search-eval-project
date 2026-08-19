# Phase2 轻量截图识别

本目录负责把搜索结果页截图转换成 Phase3 可消费的结构化事实。生产路径只使用本地 CV/OCR、卡型契约和确定性门控，不让视觉模型补读 OCR，不生成整页标注图，也不执行 IMD 操作。

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
python3 phase2-card-annotation/scripts/run_phase2_recognition.py \
  --query <query> \
  --screenshot <absolute-screenshot-path> \
  --output <one-screenshot-elements.json> \
  --artifacts-dir <one-screenshot-artifact-dir>

python3 scripts/validate_element_manifest.py \
  <one-screenshot-elements.json> \
  --audit <one-screenshot-elements.audit.json>
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
9. `validate_element_manifest.py`：校验 Phase3 所需事实与整页状态。

主流程不读取 OCR 置信度。疑似价格只允许在数值锚一致时做有界遮罩复读或选择更连贯的独立布局文本，并保留原始文本和接受理由。PaddleOCR 只在初次门控失败后自动加载一次，顺序处理门控给出的失败卡裁剪，不能处理整页长图；设置 `PHASE2_DISABLE_BOUNDED_PADDLEOCR=1` 可关闭，`PHASE2_OCR_THREADS` 默认是 `2`。

## 卡型与页尾规则

卡型决策顺序固定为：满足最小契约的已知卡型 → 有明确广告证据的广告卡 → 稳定独立的异构卡。禁止输出 `unknown`。

结果流最后一张重复卡自然触底时，可在无广告证据的前提下继承上一张已确认已知卡型。只豁免因截断不可见的必需字段；已显示文字的乱码、OCR 分歧和字段文法错误仍阻断整页。

不同卡型的边界策略不得混用：商品卡按单商品主图/标题/价格重复切分；商家图文下挂吸附商品图组；商家文字下挂吸附服务文字块；酒店、演出/电影、套餐和主点卡分别使用自己的拓扑契约。

## Phase3 事实

每个最小元素携带坐标、归属、原文、`render`，文字携带 `textFacts`，标签/icon 携带 `visual`。Phase2 记录颜色、颜色角色、字重/字号桶、渲染状态、关系和标签扫描库存；不输出评级。

当前阶段不做通用圆角容器检测。无法由像素确认的 `containerShape` 写 `unknown`。图片在 Phase2 只记录准确坐标与 `render.isPhoto=true`，Phase3 再做确定性像素统计。

## 回归与经验沉淀

黄金样本只用于推理后的回归和清洗后的归一化几何学习，不能向当前截图注入人工卡型、坐标或字段值：

```bash
python3 phase2-card-annotation/scripts/learn_card_geometry_profiles.py \
  --output phase2-card-annotation/references/learned_card_geometry_profiles.v1.json

python3 phase2-card-annotation/scripts/rerun_golden_cv.py \
  --output-dir .artifacts/golden-cv-rerun
```

模型辅助校准只允许写入 `references/golden_page_truth.v2.json`，且只在整条推理完成后比较模块、卡数、卡型和边界 IoU。回归目录中每个截图子目录各有一个 `elements.json`；顶层 `index.json` 仅做索引和指标汇总。

## 历史兼容文件

`scenes/`、旧 `annotation_scene.py`、`annotate_image.py` 和 IMD 脚本仅保留历史标注复现能力，不属于 Phase2 生产识别流程，不得作为新截图的坐标、卡型或元素事实来源。
