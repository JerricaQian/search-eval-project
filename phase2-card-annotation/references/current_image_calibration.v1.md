# 当前图片校准契约 v1

本契约把黄金 JSON 的校准方法迁移到每一张用户输入图片。黄金样本只提供结构范例；当前图片的文字、坐标、元素数量、顺序、样式和裁切状态必须全部重新取证。

## 校准链路

1. 读取当前完整截图一次，先确认页面模块、结果卡、卡内区域、每个可见下挂项和独立视觉实体。
2. 读取本次运行产生的 CV/OCR、卡型语义和门控产物。PaddleOCR 用于读取已经定位的范围，不负责创造页面结构。
3. 参考 `golden_structure_exemplars.v1.md` 选择最接近的结构，只复用区域、元素和所有权关系。
4. 对 OCR 分歧、碎片、标签边界、异构下挂和完整字形覆盖不足之处生成局部裁图，再用当前像素复核。整图固定读一次，局部复核最多十一张，总读图次数不超过十二次。
5. 逐一复核主 JSON 中全部非排除元素，同时检查当前截图中是否还有漏掉的可见模块、卡片、下挂项或原子元素。不能只处理门控已报告的 OCR 失败项。
6. 将修正同步写入唯一主 manifest，并同步维护 region、itemGroups、relations、factInventory 与 recognition 状态。主 JSON 之外的审计不是 Phase3 第二事实源。
7. 使用枚举文件、元素契约和当前图片校准审计共同校验。任何当前像素事实仍不能确认时，保持 `blocked`，不得发布为 Phase3-ready。

## 模型视觉能力的边界

模型可以依据当前整图或当前局部裁图确认：完整可见字面、独立视觉边界、元素类型、语义角色、卡片/区域/下挂归属和自然裁切状态。

模型不得：

- 从黄金 JSON、搜索词、常识或相邻卡片复制、补全当前图的文字、坐标、数量或顺序；
- 把语言上更通顺的猜测写成原文，或把 OCR 候选直接做语言纠错；
- 将图片内部包装字、招牌字或装饰字拆成独立 UI 元素；
- 因为结构和 schema 完整就把未逐像素确认的字段标为 `confirmed`；
- 在 Phase3 中回看截图并补写 Phase2 事实。

Paddle、CV 与模型视觉复核是互补证据。Paddle 可跨机器安装并稳定重跑，但遇到合并文字、异色标签、复杂卡型和图文归属时，单靠 OCR 不足以证明视觉原子边界；模型视觉复核也不能替代 OCR 过程证据和确定性校验。

`search_card_taxonomy.v1.json` 中“不让视觉模型补读”的识别规则约束本地候选器：枚举/规则代码自身不得悄悄调用模型或把模型猜测伪装成 OCR 事实。它不取消候选阶段之后、由本契约明确记录证据的当前图片校准步骤。

## 复核审计

先运行：

```bash
.venv/bin/python phase2-card-annotation/scripts/build_current_image_calibration_audit.py \
  <elements.json> --output <elements.recognition-audit.json>
```

模板默认 `reviewedAgainstCurrentPixels=false`，所有元素为 `uncertain`。完成当前图片复核后，逐项填写真实 `source`、`evidencePath`、`status` 和 `reason`；只有确实完成全量复核时才能设置：

```json
{
  "reviewedAgainstCurrentPixels": true,
  "goldenValueInjection": false
}
```

最后运行：

```bash
.venv/bin/python scripts/validate_element_manifest.py <elements.json> \
  --audit <elements.audit.json> \
  --recognition-audit <elements.recognition-audit.json> \
  --require-current-image-calibration
```

校验器要求每个非排除元素在审计中恰好出现一次，并交叉核对卡片、坐标、字段类型和可见原文。缺项、重复、审计与 manifest 不一致、黄金字段注入、未完成当前像素复核或超过读图上限都会阻断。
