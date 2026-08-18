---
name: phase2-card-annotation
description: "在 IMD 设计文件（imd.sankuai.com）中，对搜索结果页/信息页的整页截图做「宏观组件 + 商卡内部分区」两级颗粒度的可视化标注——通过 window.mg 插件 API 直接新增半透明矩形图层 + 红色文字标签，非破坏性地标出状态栏/导航/Tab/图筛/快筛/营销横幅/商卡边界/头图区/标题区/基础信息区/标签区/价格区/图文下挂/文字下挂等区域。当用户提供 imd.sankuai.com 设计稿链接并要求「标注商卡」「标注页面组件」「识别商卡分区」「标注设计稿」「IMD 在线标注」「页面组件识别」「商卡信息布局」「下挂区/标签区判定」，或要求把某个/某些场景（如某搜索词的结果页）按识别规则画出区域框时使用。即使用户只说「帮我标一下这个设计稿里的商卡」也应触发。也支持对本地整页截图（PNG/JPG）直接标注——即用户只给出本地截图文件/文件夹并要求「标注商卡/页面组件」时同样触发（走 annotate_image.py，无需 IMD）。不适用于：普通网页自动化、非搜索页/信息页的图片，以及只读取/提取设计稿文字内容或据此生成测试用例/需求文档而不画标注框的场景（那属于 imd-reader）。"
---

# Phase2 商卡轻量识别与全量标注

## 运行模式

- **`lightweight`（默认）**：识别页面组件、商卡边界、元素类型、坐标、可见性与确定性计数，只输出统一元素清单 JSON；**不得**生成整页标注 PNG。
- **`full-annotation`（按需）**：在同一份元素清单 JSON 的基础上，按本 Skill 既有流程生成整页可视化标注 PNG，供需要整页人工复核的用户使用。

无论模式如何，统一元素清单都是 Phase3 的单一事实源。Phase3 的问题位置由 Phase4 再按需生成整页截图红框证据图，不由 Phase2 预先批量生成。

### 本地 CV JSON 的归属树（强制）

`extract_merchant_graphic_hang_elements.py` 的输出以 `pageStructure.components` 为唯一页面树：搜索框、Tab、图筛、异构卡、快筛和结果列表都是页面组件；**结果卡只能放在 `results_list.components[]` 内**，不得再在根节点输出平铺 `cards`；每张结果卡的 `regions`（头图区、标题区、商家信息区、标签区、下挂商品区、特殊下挂）只能放在该卡组件内。图筛的 Tab 和图筛项只能放在图筛组件的 `elements[]` 内；每个图筛项必须将图片与文字作为同一项的 `image` / `text` 子对象。快筛仅登记组件存在性，不提取其内部元素。

商品卡使用 `extract_product_card_elements.py`，同样遵守该树；其卡内 `regions` 固定以可见事实拆为 `头图区 / 标题区 / 副标题区 / 价格区 / 商家区`。商品主图及其角标归头图区，履约标签与商品名归标题区，属性/推荐文案归副标题区，商品价格/价格说明/销量/券归价格区，商家名、起送配送、配送时长和距离归商家区。

商家**文字下挂**使用 `extract_merchant_text_hang_elements.py`，不得调用图文下挂的商品图片格语义。卡内增加 `AI推荐理由区（可选）` 和 `文字下挂区`；后者必须以 `items[]` 表达每条服务，并将价格、折扣、服务名、销量拆为同一 `itemIndex` 的独立字段。完整规则见 `references/merchant_text_hang_algorithm.v1.md`。

演出电影卡与主点卡为独立卡型：演出/电影规则见 `references/performance_movie_card_algorithm.v1.md`；主点卡须先判为非商、商场、景点或医院，再按 `references/primary_point_card_algorithm.v1.md` 输出。主点卡是结果列表前的页面组件，不能嵌入结果商卡。

## 事实源、校验与参数化纪律（阻断）

1. **先事实、后评测：**元素遗漏、卡片/模块边界、业务归属、可见原文、渲染状态或视觉属性存在错误时，必须先修正本 Phase2 manifest；不得在 Phase3/4 结果 JSON 中以补丁替代事实源修正。
2. **Phase2 出口必须校验：**每份 manifest 生成或修订后，必须运行 `python3 scripts/validate_element_manifest.py <manifest绝对路径> --audit <audit绝对路径>`；存在 `recognition-audit` 时还必须传入 `--recognition-audit`。校验未通过不得交给 Phase3。
3. **回退复核闭环：**收到 Phase3 的 `待回退Phase2复核` 或 `phase2ReviewRequired=true` 时，读取复核请求、保留旧清单/审计与中间图，修正 manifest 后重新生成 audit；受影响的 Phase3 必须重建或复跑，不能仅修改下游结论。
4. **参数化运行：**可复用命令必须通过 `projectDir / batch / query / manifest / outputDir` 等显式参数或由项目根推导路径；统一使用项目级 `screenshots/`、`screenshots-out/` 与 `.artifacts/`。禁止把固定搜索词、机器专属绝对路径、`/tmp` 历史目录或 skill 内部 `out/` 作为通用入口。一次性 `annotate_*` / `rebuild_*` 仅作历史审计材料，不得被默认工作流自动发现或执行。

## 标签 / icon 视觉属性契约（Phase3 静态元素复杂度的唯一输入）

Phase2 不输出“优秀/达标/不达标”评级，也不按页面或卡片预先聚合数量。它必须先完成逐卡、逐区域、逐个最小视觉实体的事实清单，再让 Phase3 确定性计数。**不得先以“普通文字”“同样式去重”或“截图未确认”反驳任何候选标签；必须先留下找到/未找到、计入/不计入及视觉依据。**

- 扫描范围是每张商卡和图筛的完整可见边界：头图品牌/活动角标、标题前 badge（如“自营”“直播中”）、基础信息/履约标（如“闪购”及闪电）、标签区、价格旁促销标（如“冰爽价”“神券”“已减”“折扣”）、文字下挂、每个图文下挂商品图的角标/腰封、保障标（如“安心闪购 坏必赔”）都必须扫描；`标签区` 不是唯一来源。
- 每个独立标签、角标、徽标、履约标、券标、腰封和 icon 都必须拆成一个元素；不同底色、描边、图形辅助、留白分隔或语义作用不同的实体不得合并。图片本体不计标签，但叠在图片上的系统 UI 角标必须单列。
- 普通标题、评分数字、价格数字和黑/灰/白纯文本不能写成标签；无法确认时也要保留候选记录，写 `visualStatus: "uncertain"`、`countedInComplexity: false` 和不确定原因，Phase3 不得将它按 0 或按已计入处理。
- 对标签 / icon 元素，在原有字段外必须写入下列 `visual` 对象；非标签的普通元素可省略该对象：

```json
{
  "id": "C2-badge-hot",
  "元素类型": "标签",
  "内容简述": "原文:人气热销",
  "坐标": [635, 1380, 150, 65],
  "visual": {
    "entityKind": "tag",
    "visualStatus": "confirmed",
    "isColored": true,
    "isShaped": true,
    "colorRole": "red",
    "semanticRole": "榜单标",
    "containerShape": "实底圆角胶囊",
    "backgroundColor": "#D93838",
    "textColor": "#FFFFFF",
    "borderColor": "",
    "hasGraphicAssist": false,
    "graphicType": "无",
    "graphicAssistRole": "无",
    "countedInComplexity": true,
    "countDecision": "红色实底圆角榜单标，属于独立异色标签",
    "dedupDecision": "不得与券标、履约标或商品卖点标去重",
    "dedupWithElementIds": [],
    "styleKey": "标签|红色|榜单标|实底圆角胶囊|无",
    "sourceRegion": "标签区"
  }
}
```

- `entityKind` 只能是 `tag | icon | text | image`；`colorRole` 使用 `neutral | red | orange | yellow | green | blue | purple | multicolor | unknown`；`sourceRegion` 必须是当前卡实际分区。`semanticRole` 使用中文角色：`品牌身份标、履约标、保障标、券标、优惠金额标、折扣标、商品属性标、商品卖点标、品质标、榜单标、营销腰封、活动角标、直播状态标、其他标签`；icon 也必须写其中文语义角色，例如“闪电履约图标”“奖杯榜单图标”。
- `containerShape` 必填，使用可复核的中文外观描述，例如“实底圆角胶囊”“描边圆角胶囊”“矩形角标”“图片角贴”“无容器图标”。`graphicType` 和 `graphicAssistRole` 必须明确写“闪电/奖杯/品牌图形/无”及其作用；带闪电的“闪购”同时登记一个 `tag` 和一个 `icon`，两者各有独立 `styleKey`。
- `styleKey` 固定为 **实体类别｜颜色角色｜语义角色｜容器形态｜图形辅助**。同卡仅当这五个维度均一致，且 `dedupDecision` 写明可去重的具体对象和理由时，才允许去重；颜色相近或轮廓相似不能去重。故即使都是橙色圆角容器，“神券”（券标）、“鲜打”（商品卖点标）、“酒水热卖榜第1名”（榜单标）、“秒提 到店取”（履约标）、“直播特惠”（营销腰封）、“满85减15”（优惠金额标）也必须分别保留。
- `isColored || isShaped || hasGraphicAssist` 为真且 `countedInComplexity=true` 的 `tag` 是标签候选；独立可识别、`countedInComplexity=true` 的 `icon` 是 icon 候选。每个不计入候选也必须填写 `countDecision` 的可见视觉依据，不能只写“普通文字”。
- 每个完整可评组件额外写 `visualInventory`：按六分区列出已确认元素 ID、`styleKey`、`countedInComplexity` 与未确认项；另写 `tagScanChecklist`，每项固定含 `candidate`、`status: found|not_found|uncertain`、`checkedRegions`、`elementIds`、`visualBasis`。检查表仅提醒扫描，不能凭搜索词补造截图中不存在的标签，也不得写死标签数量或评级。

Phase2 交付校验：完整组件必须提供 `visualInventory`；其列出的元素 ID 必须存在于该卡、坐标在卡边界内、`sourceRegion` 与元素所在分区一致；`confirmed` 的 tag/icon 必须具有完整五段式 `styleKey` 和全部语义/去重字段，并且每个已确认 tag/icon 都必须在所属分区库存中出现。缺任一可见分区扫描记录或缺少标签扫描检查表时，`visualInventory.complete=false`，Phase3 静态元素复杂度不得输出该卡“优秀”。

### 业务/搜索意图标签扫描检查表

建立以下“提醒而非补造”的基础库，按当前卡片可见业态、页面区域和截图原文选择适用项。每个适用项必须在 `tagScanChecklist` 留下 `found/not_found/uncertain` 结果；发现后按最小实体登记，未发现则写清检查区域，`uncertain` 必须触发复核。

| 场景 | 优先检查的可见候选 |
|---|---|
| 闪购/商品零售/水果/酒水 | 闪购与闪电、时令、赠品、冰爽价、神券/神价、已减/折扣、安心闪购保障、商品图角标、品牌角标 |
| 餐饮外卖 | 品牌/自营、到店取/配送履约、招牌/鲜打卖点、券标、满减/折扣、榜单、保障、直播状态 |
| 医药健康 | 品牌、医保/个账、原研/品质、口碑/加购、健康卡券、买药履约、保障/服务、商品图角标 |
| 酒店旅行/景点 | 品牌、星级/榜单、套餐/权益、限时优惠、直播中/直播特惠、旅行社/旅游角标、保障/履约 |
| 服务/维修/娱乐 | 品牌、上门/到店履约、直播状态、团购/券标、保障、榜单、折扣、活动角标 |


## 结构化事实契约（供 Phase3 确定性消费）

标签 / icon 之外，Phase2 还必须把截图中**可观察、可定位、可重复计算**的事实写入统一元素清单。它只登记事实、状态与置信度，**不得**提前输出“信息冗余、布局合理、信息真实、规范合规”等主观结论；这些结论仍由对应的 Phase3 Skill 依据本契约和自身规则生成。

### 本地 CV/OCR 语义候选（Phase2 前置）

本地路径先依次运行 `scripts/run_cv_facts.sh`、`scripts/build_search_page_structure.py` 和 `scripts/map_search_page_semantics.py`。最后一个脚本消费 `references/search_page_semantic_rules.v1.json`，把 OCR 文本按可见文案、颜色提示、相对位置和布局候选映射为**标签/价格/标题/基础信息的候选**。该 JSON 是从本文与 `references/页面与商卡识别规则.md` 提炼的可执行补充：它只能给出 `confirmed|uncertain`、证据和建议分区，不能替代当前截图的可见性核对，也不能直接输出体验结论。

示例：独立 OCR 候选“直播中”命中 `live-status`，且文字颜色提示为红/橙时可成为 `tag → 标签区` 的 confirmed 候选；若没有独立视觉证据或 OCR/布局置信度不足，必须保留 `uncertain`，不得把它并入标题、补造成标签或推断为缺失。

### PaddleOCR 局部识别纪律（强制）

- 对长搜索结果截图，先用轻量 CV 建立页面组件、卡片及区域坐标，再对**单个语义区域**执行本地 PaddleOCR；禁止把整页长截图直接送入 PaddleOCR。局部模型目录为 `models/paddleocr/`，运行时由 `scripts/extract_cv_facts.py` 复用一次模型实例；不得联网下载模型。
- `PaddleOCR 3.x` 的 `predict()` 为惰性迭代器，必须消费其结果并读取每个文本框的坐标、原文与置信度；不得因未消费迭代器而静默回退到 Tesseract。
- OCR 裁剪必须与字段一一对应：履约标签、标题、配送时长、评分/销量/起送费/配送费/距离、每个标签、每个下挂商品名和价格分别裁剪。不得把整行或整个商家区拼成一个 `visibleText`，再以正则猜字段。
- 履约标签必须使用独立左侧裁剪并命中明确枚举（到店/外卖/上门/景点等）后才输出；标题必须从履约标签右侧独立裁剪。不得因为预期存在履约标签而删去标题开头字符，也不得把 OCR 误读的前两字当作履约标签。
- OCR 出现乱码、过长拉丁字母串、异常标点序列或跨字段拼接时，不得发布为 `confirmed.visibleText`；保留空值 `uncertain` 或不发布候选。此规则适用于商品卡、图文下挂和文字下挂。
- 结果列表卡片数应由连续的左侧大头图候选和 y 轴锚点共同确定；检测阈值不足时可降低图片尺寸阈值或使用已确认组件锚点补齐，但不得因某个头图漏检而截断后续结果卡。
- 商品卡标题允许一行或两行。标题裁剪中出现规格/属性/卖点的第二行时，必须拆为 `标题区.商品标题` 与 `副标题区` 的独立元素；例如 `≥… / 保质期… / 麦香浓郁 / 口感…` 不得并入商品标题。无法可靠切分时，保留 `uncertain`，不可把整块文本确认为标题。
- 价格区裁剪不得越过商家区；券、销量、价格说明均须使用有边界的表达式匹配。错误地包含商家名、距离、配送信息的价格/神券候选必须丢弃，不能发布为可见事实。
- CV 未检出商品头图、但黄金组件样本已确认卡片位置时，可用黄金位置锚点恢复标题/副标题/价格/商家区域的**候选裁剪**；头图元素必须标为 `uncertain`，不得伪称 CV 已检测成功。
- 用户确认的元素级文本必须写入对应黄金结构的 `cardElementOverrides`，并优先于 OCR；它们既是回归测试真值，也用于后续规则校准。黄金真值只能修正该已确认样本，不能凭相似搜索词外推到未标注截图。

### 1. 页面与组件事实

清单根对象必须有 `pageFacts`，每个宏观组件及 `cards[]` 均必须有 `structure`。字段可扩展，但以下字段不可省略：

```json
{
  "pageFacts": {
    "screen": 1,
    "isContinuation": false,
    "viewport": { "width": 1224, "height": 2700 },
    "modules": [
      {
        "id": "M3",
        "moduleType": "tab | image_filter | business_filter | quick_filter | marketing_banner | primary_card | result_list | recommendation | sidebar | other",
        "coord": [0, 310, 1224, 180],
        "visibleStatus": "confirmed | partial | uncertain",
        "contentRole": "频道切换/意图细分/排序筛选/营销/结果供给/推荐等可见功能",
        "isListPrefix": false,
        "isListItem": false
      }
    ]
  },
  "cards": [{
    "id": "C2",
    "structure": {
      "visibleStatus": "complete | naturally_cropped | uncertain",
      "cardTypeCode": "稳定卡型编码",
      "layoutMode": "left_image_right_text | top_image_bottom_text | text_only | grid | heterogeneous | other",
        "layoutSignature": "left_image_right_text|title>meta>price|text_append",
        "comparisonGroupKey": "food_delivery|merchant_left_image_right_text|text_append",
        "isResultListItem": true,

      "isHeterogeneous": false,
      "listPosition": 2,
      "regions": [
        { "region": "头图区", "coord": [32, 1182, 328, 353], "visibleStatus": "confirmed", "hasPhysicalBoundary": false, "hasBackgroundSeparation": true },
        { "region": "标题区", "coord": [385, 1182, 760, 52], "visibleStatus": "confirmed", "hasPhysicalBoundary": false, "hasBackgroundSeparation": false }
      ]
    }
  }]
}
```

- `modules` 以**视觉/功能独立区域**登记，`primary_card` / `heterogeneous` 按实例登记，普通连续结果统一登记 `result_list`；不得把 Tab、快筛内部每个子项误写成独立模块。
- `isListPrefix=true` 只用于 Tab/快筛之后、首张结果前的营销腰封或提示条；它不占 `listPosition`。真实插入结果流的异构模块应写 `isListItem=true`、有连续 `listPosition`。
- `layoutSignature` 仅描述可见的几何与分区序列，不推断新旧设计版本或优劣；同类卡是否应一致由 Phase3 判定。
- `comparisonGroupKey` 是视觉秩序横向比较的唯一分组事实：对 `isResultListItem=true` 且 `visibleStatus=complete` 的卡必须填写，由稳定业态/卡型、`layoutMode` 与可见下挂结构组成（例如 `food_delivery|merchant_left_image_right_text|text_append`）。仅相同 key 的卡可做跨卡一致性比较；单例 key 只检查本卡阅读顺序，不得借“单例默认一致”输出跨卡优秀。
- **布局锚点（强制事实）**：同一个 `comparisonGroupKey` 内有两张及以上完整结果卡时，每张卡的 `structure` 必须额外填写 `layoutAnchors`（`image`、`title`、`primaryInfo` 三个真实元素坐标 `[x,y,w,h]`）与 `layoutAnchorRelation`（仅写该卡内关系，例如 `image_left_of_text; title_above_primaryInfo`）。`layoutAnchors` 只记录事实，禁止写“错层”“右移异常”“混用”等结论；图片尺寸、文字列绝对 x 坐标或卡片高度不同本身不能改变 `comparisonGroupKey`，也不能作为布局异常事实。关键锚点看不清时必须将卡标记为 `visibleStatus=uncertain` 或在 `factInventory.uncertainElementIds` 留痕，禁止伪精确填写。
- `visibleStatus=uncertain`、自然触底截断或跨屏续接必须原样登记；下游不得把它们改写成缺失或异常。

### 2. 最小元素渲染、文本与视觉规格事实

每个可见最小元素（图片、文字、标签、icon、按钮、价格、评分等）除原有字段外，必须补充 `render`；文字元素再补 `textFacts`，视觉可判元素补 `visual`。图片的存在性、加载状态、自然裁切和疑似照片性质是事实字段，不得以“清单漏标”替代读图事实。

```json
{
  "id": "C2-title",
  "元素类型": "文字",
  "内容简述": "原文:某某商家",
  "坐标": [385, 1182, 520, 52],
  "render": {
    "visibleStatus": "confirmed | partial | uncertain",
    "renderState": "normal | placeholder | blank | load_failed | naturally_cropped | abnormal_clipped | garbled | uncertain",
    "sourceRegion": "标题区",
    "isPhoto": false,
    "isSystemUi": true
  },
  "textFacts": {
    "rawText": "某某商家",
    "textStatus": "complete | naturally_ellipsized | abnormal_clipped | garbled | uncertain",
    "semanticRole": "title | subtitle | price | rating | sales | location | fulfillment | promotion | filter | recommendation | other",
    "emphasisLevel": "primary | secondary | tertiary | unknown",
    "fontSizeBucket": "large | medium | small | unknown",
    "fontWeightBucket": "bold | regular | unknown",
    "textColorRole": "neutral | emphasis | red | orange | yellow | green | blue | purple | multicolor | unknown"
  },
  "visual": {
    "visualStatus": "confirmed",
    "entityKind": "text",
    "colorRole": "neutral",
    "backgroundColor": "",
    "textColor": "#222222",
    "borderColor": "",
    "hasPhysicalBoundary": false,
    "hasBackgroundSeparation": false,
    "styleKey": "text|primary|large|neutral"
  }
}
```

- `renderState` 是 Phase3 供给完整性、单元素质量的唯一初始事实源；`uncertain` 只能触发复核，禁止下游计入问题或作为“优秀”证据。
- `rawText` 记录可见原文；文字看不清写 `textStatus=uncertain`，绝不脑补。`semanticRole` 是可见字段角色，不是“真实业务含义”判断。
- `fontSizeBucket`、`fontWeightBucket`、`textColorRole` 只记录可见相对规格；设计稿可取到精确值时可额外写 `fontSizePt`、`fontWeight`、`fontFamily`。截图无法可靠读取时写 `unknown`，不允许伪精确。
- **视觉层级事实门槛：**对 `structure.isResultListItem=true` 且 `structure.visibleStatus=complete` 的结果卡，所有可见文字元素必须登记 `semanticRole`、`emphasisLevel`、`fontSizeBucket`、`fontWeightBucket`、`textColorRole`，所有图片元素必须有 `render.visibleStatus=confirmed` 与有效 `renderState`，所有标签必须有 `visual.visualStatus=confirmed` 与非 `unknown` 的颜色角色。任一字段缺失、`unknown` 或 `uncertain` 时，必须在 `factInventory.uncertainElementIds` 与 notes 留痕；该卡不得作为视觉层级 Skill 的优秀证据，等待 Phase2 回退复核补齐事实。
- 每张真实头图、商品图、图筛配图均必须以一个图片元素登记，写 `isPhoto`、`renderState` 和坐标；图片上独立的系统标签/角标仍单列为 tag/icon，不随图片排除。

### 3. 关系与可比事实（只登记，不下结论）

清单根对象追加 `relations[]`，仅记录可由位置、文本和卡片归属确定的候选关系，供 Phase3 做语义与规则终判：

```json
{
  "relations": [
    {
      "relationType": "same_card | same_field_across_cards | title_to_image | title_to_append | overlapping_annotation | same_supply_candidate",
      "from": "C2-title",
      "to": "C2-image",
      "status": "confirmed | uncertain",
      "evidence": "同属 C2；标题右侧文字列与头图相邻",
      "normalizedValue": "可选：用于同字段/同标题候选的保守归一值"
    }
  ]
}
```

- `same_field_across_cards` 只在同 `cardTypeCode` 且字段角色相同的可见元素之间登记；`same_supply_candidate` 只可作为标题/门店/地址一致的保守候选，不能直接等同重复供给。
- **真实性关系门槛：**对 `isResultListItem=true` 且 `visibleStatus=complete` 的结果卡，存在主标题和图片时，主标题必须与每个可见图片建立 `title_to_image` 关系；存在主标题和下挂区实体时，主标题必须与每个下挂实体建立 `title_to_append` 关系。关系只记录可见对应事实，无法确认则写 `status=uncertain` 并记入 `factInventory.uncertainElementIds`；此时信息真实无歧义 Skill 不得以该卡支撑优秀。
- 不得在 Phase2 写“图文不符”“语义重复”“功能重复”“不合规”“颜色过多”“视觉权重倒置”等结论；Phase2 仅提供元素、位置、文本、样式桶、模块/卡型、状态及候选关系。

### 4. `factInventory` 与复核门槛

每张卡补充 `factInventory`，页面根对象补充 `pageFactInventory`，逐项列出模块、图片、文字、分区、布局和关系的扫描状态。`complete=false` 或任一关键项 `uncertain` 时，相关 Phase3 维度不得把该项作为“优秀”证据；未确认项既不计入缺陷分子，也不得按 0 处理、不得创建人工复核任务。视觉层级维度还要求上述“视觉层级事实门槛”全部满足，不能只因其他事实项已完成而放行。对存在同组完整卡的视觉秩序评测，还必须通过 `--require-alignment-anchors`：任一卡缺少 `image/title/primaryInfo` 布局锚点或卡内关系事实，必须阻断该项 Phase3 评测。

```json
{
  "factInventory": {
    "complete": true,
    "scanned": ["card_boundary", "regions", "images", "text", "render_state", "visual_spec", "layout", "relations"],
    "uncertainElementIds": [],
    "notes": []
  }
}
```

## 读图优先级与强制停止（Phase2 必守）

- **主读取路径是整图视觉阅读**：每张截图先读 1 次 `sm_` 整图，按“顶部组件 → 商卡 → 头图 → 标题 → 基础信息 → 标签/价格 → 下挂”的视觉顺序登记可见实体、语义和文字；不得把局部裁图变成逐行 OCR 流水线。
- **局部裁图只作低置信复核**：仅当标题、价格、评分/履约文案或“是否存在真实图片”在整图中无法可靠确认时，才用窄条裁图复核对应字段；已确认字段不得重复裁读。
- **保留 12 次强制停止**：一次 Phase2 识别会话内，整图与局部 PNG 的全部 Read 合计最多 12 次。整图占 1 次，故局部复核最多 11 次；达到 12 次或关键字段已覆盖时立即停止读图。未确认字段写入旁路 `recognition-audit` 的 `uncertain`，不得继续裁图，也不得被下游当成 UI 截断、错字、缺失或无头图的证据。
- **Phase3 回退复核是独立会话**：若收到 `待回退Phase2复核_*.json`，原 `recognition-audit.json` 必须只读保留，绝不得覆盖或把新读图次数累加到原文件；新建 `elements_<query>.recognition-audit-rereview-<timestamp>.json`，记录 `reviewOf` 与 `reviewRequest`。该复核文件独立执行“整图 1 次 + 局部最多 11 次”的 12 次上限，并须通过 `validate_element_manifest.py --recognition-audit <复核审计>`；所有旧/新审计及裁图均保留。

## 全量标注模式：IMD 商卡标注（插件 API 版）

在 IMD 设计文件中，把搜索结果页/信息页的整页截图按《页面与商卡识别规则》
拆成宏观组件与商卡内部分区，并**直接在设计文件里新增半透明矩形 + 文字标签**完成可视化标注。

已在万达广场、蜜雪冰城、电竞房、迪士尼、相声、给阿嬷的情书、剧本杀 7 个场景验证，
覆盖单列/双列瀑布流/演出票务/电影场次/异构聚合等多种布局。

## 为什么用插件 API，而不是模拟鼠标或截图

IMD 编辑器在 `window.mg` 上暴露了**类 Figma 插件 API**，可编程创建/读取/导出图层。
早期尝试过「模拟鼠标拖矩形 + 改属性面板」的方案，极易错位、慢、且事件常被画布吞掉；
截图（`screenshot` action）在画布密集页面还会超时。所以本 skill 一律走插件 API——
精确、可靠、可批量，且天然非破坏性（只 `createRectangle`/`createText`，不碰原图层）。

三条必须记住的事实：

1. 当前已验证的场景画板常命名为 `{场景名}_全部_{1|2|3}`，且为 `scale=1` 导出的整页截图矩形
   （`type=RECTANGLE`，`fills[0].type=IMAGE`）。开始标注前必须读取当前画板的 `name/x/y/width/height` 和导出 PNG 尺寸；仅当两者尺寸相同且 `scale=1` 时，像素坐标才等于画板局部坐标。绝对设计坐标由画板偏移 `(FX,FY)` 加局部坐标得到。
2. 标注全部加图层名前缀 `[ANNO]`（矩形）/ `[ANNO-TXT]`（文字），便于筛选、验证、一键回滚。
3. 视觉验证靠「克隆底图 + 克隆本场景标注 → 编组 → 导出 group PNG → 删除临时组」，不改动任何原件。

## 核心原则：内容优先，像素扫描仅限卡间/卡内留白（务必先读）

区域「是什么」靠**读图内容**判定。像素扫描阈值会随抗锯齿 / 压缩 / 阴影 / 渐变波动，
且只看墨迹密度、读不出文字——判不了区域类型。但像素扫描能给出**客观的行间留白边界**，
这是读图肉眼难以精确量化的。故采用**混合方法**：

1. **内容优先**：对照 `references` 的「总原则」「宏观组件」「标准商卡与异构卡」「卡内分区规则」和「官方设计线索」（角标位 / 颜色语义 / 字数 / 固定位置 / 枚举值），读出每个区域的文字与元素，据此定区域类型。像素扫描不能当语义判官。
2. **卡间留白**：`scan_rows.py`（无 y 参数）一次性找「卡片之间 / 宏观组件之间」的稳定留白带，
   定位卡与卡的纵向切割线和宏观组件外接矩形。
3. **卡内分区（混合方法）**：`scan_rows.py <img> <x0> <x1> <y0> <y1>` 限定到单卡文本区域
   （如 `385 1188 710 1188`），一次性扫描出**客观内容行边界**（行间留白带 + 内容行）。
   再**读图内容**给每行贴语义标签（标题/基础信息/价格/标签/商家）。详见下方「商卡内分区：混合方法」。
4. **扫描不循环**：同一张图片的同一扫描目的与同一参数组合最多执行一次。允许一次整图扫描；必要时，对每张当前卡已确认的文本列各执行一次限区扫描。禁止调阈值 / 调区间重扫去「凑」与读图一致的结果；冲突时以读图内容为准。
5. **逐卡独立**：不同卡的头图宽 / 标题起点 / 行高 / 下挂类型不同，禁止把第一张卡坐标平移套到后续卡。其他卡的结构仅可作为读图或扫描的候选范围，写入任务表前必须逐边确认当前卡。

> 一句话：读图定语义，scan_rows 定行边界（卡间 + 卡内），两者结合；绝不调参重扫。

### 绘制前的强制语义-几何核对（本地图片与 IMD 均适用）

以下核对必须在写 `tasks` 前逐项完成；不能因为一行的位置、颜色或扫描行高“看起来像”就赋予语义：

1. **目标文件核对**：批量任务先列出 `screenshots/` 实际文件名，逐个确认用户指定的场景名与输出文件一一对应；禁止沿用近期打开图片、上一轮任务表或未被点名的场景。
2. **顶部组件按完整模块取框（强制声明，零例外）**：图筛若由「图片/图标行 + 与每项对应的文字行」组成，必须用**同一个图筛外接矩形**完整覆盖两行；图筛的文字行是图筛不可分割的组成部分，**严禁单独标为快筛，严禁同时创建重叠的快筛框**。快筛必须是图筛之外、能从当前图独立读出的纯文字筛选项（如“品牌”“类型”“综合排序”）才可取框；找不到独立文字筛选行则不得创建快筛。不得把图筛的文字行当快筛，也不得把“快筛下方有空白/细条”自动判为营销横幅。
3. **头图区按图片像素边缘取框**：分别确认左、上、右、下四条边是否是实际图片内容；卡片 padding、圆角外白边、右侧文字列和图片下的留白均不得计入头图区。`scan_rows` 的内容带只能辅助 y，不可替代视觉确认 x/y 四边。
4. **先锁列再分行**：左图右文卡先记录 `image_x0..image_x1` 与 `text_x0..text_x1`。标题、标签、价格、文字下挂等右侧文字分区默认只能落在 `text_x0..text_x1`；只有实际横跨全卡的内容才可越过头图，且必须在任务表注释说明。
5. **逐行按文字含义贴标签 + 最小独立元素拆分（强制）**：先逐行写下读到的关键文案，再决定区域。元素清单的单位是可独立理解、可独立着色或有独立视觉边界的**最小元素**，不是一整行文字或一个分区：相邻的独立标签/徽标/权益（即使同在一行）必须逐个建立元素及各自坐标，例如“一类医疗器械”“药监认证”必须是两个元素，“酒水热卖榜第1名”“不冰必赔”必须是两个元素；以`｜`、分隔点、标签间留白、独立底色/边框、icon 或语义切换为线索逐个拆分。不得把多个独立标签、价格与商品名、评分与评论/人均/距离、多个横滑商品拼为一个元素。只有无可见分隔、共同构成一句不可拆语义的连续文本才保留为一个元素。资质、验真、神券、榜单等徽标/权益文案仍属`标签区`；标签之后连续的商品/促销文字才属`文字下挂区`。价格不是天然的`价格区`：若它属于一条「券后价/神券/商品促销」下挂文案，则随该整行/多行标为`文字下挂区`；没有真实副标题或商家信息时，禁止为了凑模板新增对应分区。**左图右文或图文下挂商卡的图片完整性核对：只要当前卡可见真实头图/商品缩略图，元素清单必须写入对应的 `元素类型: 图片`、坐标和内容简述；图片区漏识别时必须记录 `photoRecognitionPending` 审计告警，绝不可把“清单中无图片元素”解释为“页面无头图”。** 最小元素拆分只写入元素清单/任务数据，绝不增加标注图上的元素级框或 `[E:…]` 编号；可视化标注一律保持“宏观组件 + 商卡边界 + 卡内分区”的原有聚合样式。**
6. **交付前反向审图**：读取输出 PNG 后，逐项对照原图检查：①每个宏观框是否覆盖完整语义模块；②头图框是否只贴图片；③右侧文字分区有没有压到头图；④标签行与下挂首行的切割是否正确；⑤不存在的营销横幅、图筛、副标题、价格区、商家区是否被凭空标出；⑥**图筛与首张商卡之间必须存在可见边界**：图筛框的下边缘不得越过其最后一行分类文字，首张商卡边框必须从实际商品/商户内容开始，二者不能重叠。任一项不通过，改任务表后重新生成再交付。

## 商卡内分区：混合方法（像素留白检测 + 内容定位）

当用户反馈「商卡内分区不到位」（分区有大段留白未覆盖 / 边界不准），用此混合方法精修：

### 步骤
1. **确定卡文本区域 x 范围**：头图在左（如 x=32-362），文本在右（如 x=385-1188）。只扫文本列。
2. **scan_rows 限区扫描（仅当前卡文字列已确认且边界仍不清晰时）**：`python3 scripts/scan_rows.py <img> 385 1188 <卡顶y> <卡底y>`
   → 输出该卡内所有**内容行**（绝对 y + 高度）和**留白带**。
3. **识别大留白带**：卡内常有一条 h≥50 的留白带，将卡分为**上区**（标题+基础信息）和
   **下区**（价格+标签+商家）。这条带是天然的分区切割线。
4. **读图贴标签**：对每条内容行，读图确认其语义（标题/基础信息/价格/标签/商家）。
   颜色线索：红色文字=价格；异形异色小标签=标签区；底部行=商家。
5. **覆盖全部内容行**：每条内容行都要落到某个分区里，**不留大段未标注留白**
   （这是「不到位」的主要病因——原来只在卡顶标了标题/价格，卡中下部大段空白未标）。

### 喜力啤酒整箱场景的分区纵向顺序
头图(左) → 标题 → 基础信息 → **大留白带** → 价格 → 标签 → 商家
（价格在大留白带**下方**，靠下不靠上。不同场景顺序可能不同，以读图为准。）

### 阈值限制
`scan_rows.py` 阈值 `row_std<6 & row_mean>240` 适配色背景。若卡背景非纯白（浅灰/渐变），
卡间留白带检测不到（整段被当成一个内容行）。此时：
- 对能扫出行的卡用实测边界；
- 对扫不出的卡，可用同页同类型卡的行结构作为**候选范围**，但不得直接平移坐标；必须以当前卡可见文案和边缘逐边确认，且在任务表标明 `source: estimated` 与原因。

> ⚠️ **营销横幅 vs 商卡（最易错，导致编号整体错位）**：搜索结果页快筛下方常有一张通栏促销条
> （金色/彩色背景、纯图或图文、高度~110-120px），它**不是商卡**，应标为 `营销横幅`（DAA520 macro）。
> 若误标为商卡 border，会导致后续所有商卡编号 +1 错位、且「首张矮商卡」视觉异常。判定法：
> ① 高度明显小于正常商卡（~450px）的通栏元素；② `scan_rows` 中它上下都是留白带、且自身占位
> 矮（h<120）；③ 读图内容为促销/活动通栏而非商品信息。三者满足即判营销横幅。

## 前置

- 目标是 `imd.sankuai.com` 链接，需先按 `catdesk-browser` skill 的内网页面流程完成登录态准备。
- 依赖 `catdesk`（浏览器自动化）、Python3 + Pillow + numpy（像素扫描）。
- 识别标准见 `references/页面与商卡识别规则.md`；标注前按需阅读「总原则」「宏观组件」「标准商卡与异构卡」「卡内分区规则」「官方设计线索」与「统一执行流程」。当前截图可见语义与 `SKILL.md` 硬约束优先于模板、颜色、位置和历史案例。

## 工作流

以下命令均从 Skill 根目录执行，并使用 `scripts/<脚本名>.py` 路径。`imd_eval.py` 负责规避 shell/JSON 转义，评估 JS 表达式。

### 1. 打开设计文件 + 放大视口

```bash
catdesk browser-action '{"action":"navigate","url":"https://imd.sankuai.com/file/<fileId>?page_id=<pageId>","waitUntil":"networkidle"}'; sleep 6
catdesk browser-action '{"action":"viewport","width":1600,"height":1000}'; sleep 4
```

视口过小会让画布以约 2% 极低缩放渲染，务必先放大到 1600×1000。`window.mg` 需编辑器完全加载后才可用，导航后多等几秒更稳。

### 2. 定位场景画板（拿 id + 偏移坐标）

```bash
python3 scripts/imd_eval.py eval '(() => { const doc=window.mg.document; const page=doc.currentPage||doc.children[0]; return JSON.stringify(page.children.filter(n=>/关键词/.test(n.name||"")).map(n=>({id:n.id,name:n.name,x:Math.round(n.x),y:Math.round(n.y),w:Math.round(n.width),h:Math.round(n.height)}))); })()'
```

- `{场景名}_全部_{1|2|3}`、画板左右顺序和尺寸仅是当前已验证文件的常见约定。必须依据本次列出的 `name/x/y/width/height` 确认；用户未要求只标首屏时，不得据命名假设排除其他画板。
- 注意用 `mg.document.currentPage || mg.document.children[0]`（`mg.currentPage` 可能为 undefined）。
- 记下该画板的 `id` 和偏移 `(x, y)` —— 后者就是任务表里的 `FX, FY`。

### 3. 导出画板底图 PNG（用于识别，不要截图）

```bash
python3 scripts/imd_export_node.py "<画板id>" /tmp/scene_1.png 1
```

内部调用 `node.exportAsync({format:'PNG', constraint:{type:'SCALE', value:1}})`，导出尺寸 1224×2700。用它读图识别，别用 `screenshot`（会超时）。

### 4. 识别（读图内容）+ 卡间留白定位

> 💡 **多图/省 context 必看**：本步「读图」会把整页 PNG 作为视觉 token 注入主线程，一张图就占一大块。
> 同时标 ≥2 张图、或想给主线程留余量时，把本步整步外包给 subagent（见下方「避免 context 爆满」章节）：
> subagent 读图+出任务表+画标注+自检，主线程只收坐标 JSON。本节下面是主线程自己做时的流程。

**先读图**：用 `Read` / `image_read` 打开导出的整页 PNG，对照 references 规则，逐卡读出每张
商卡的类型与卡内各分区（头图 / 标题 / 基础信息 / 标签 / 价格 / 下挂…）的类型及起止边界——靠
读到的文字、颜色语义、字数、固定位置判定，不靠像素扫描。

> 💡 **必须用眼睛读图，不准套模板**：每填一个坐标前，都要再读一下图——这块区域实际是
> 什么？是不是标到了文字上？位置是否遮住了实际内容？顶部组件（状态栏/导航/Tab/图筛/快筛）
> 位置**绝对不能套上一张图的数值**，每次都要从本图 `scan_rows` + 读图实际取。

> 💡 **逐卡独立量取，不能跨卡平移**：每张卡的标题起点 y、价格 y、下挂类型都可能不同，
> 头图高度不同（药店页头图高度：商卡1=540、商卡2=260、商卡3-5=190、商卡6=200 都不一样）。
> 同一搜索词结果页的分区顺序可作为当前卡读图时的候选，但不得把第一张卡的偏移或高度直接用于后续卡；写入任务表前，当前卡的每条边都必须独立确认。

> 💡 **必须读图取真实商家名，不准赋套**：商卡1 必须读图内容定位，取实际商家名作为
> 标题区标签。药店商卡1 = **111医药馆**；游乐场商卡1 = **奈尔宝**。错位检验错用真名。

**再找留白候选**：可对整图运行一次 `scan_rows.py`，辅助定位卡间和宏观组件的留白带；不调参重扫，与读图冲突时以读图为准。仅当当前卡的文字列已确认且卡内边界仍不清晰时，才对该文字列运行一次限区扫描：

```bash
python3 scripts/scan_rows.py /tmp/scene_1.png                       # 可选：一次整图扫描
python3 scripts/scan_rows.py /tmp/scene_1.png 365 1190 <y0> <y1>    # 可选：当前卡已确认文字列的一次限区扫描
```

整图和限区结果都是几何候选，不是强制双路校验；不得用扫描替代组件语义、也不得为追求一致而重复扫描。

**图文下挂区可能含两行横滑商品卡**：`scan_rows` 会把两张横滑卡中间的小间隔误判为留白带。
此时按读图覆盖：下挂区作为一个外接矩形跨多行，同一 label。

产出一张「任务表」：每个区域一条 `{label, x, y, w, h, kind}`（像素坐标，来源 = 读图内容 + 卡间
留白）。`kind` 取值：`macro`（宏观通栏组件）| `border`（商卡整体边界，只描边）| `part`（商卡
内部分区）。

### 4.1 业务治理字段（元素清单必填，标注图不展示）

每个 `cards[]` 对象都必须补充业务治理元数据；**按当前卡片可见内容、履约方式和结构判断，严禁按搜索词推断业务**。宏观组件、平台运营、混合业务与无法判断的卡必须如实标记，不能为凑业务统计硬归类。

```json
{
  "ownershipScope": "business | platform | mixed | unknown",
  "businessCode": "dine_in | food_delivery | flash_delivery | service_retail | healthcare | hotel_travel | xiaoxiang | maoyan | bike | youxuan | errand | finance | power_bank | ride_hailing | xiaoxiang_supermarket | dianping_overseas | topup_game_ecommerce | platform | mixed | unknown",
  "businessName": "到餐等中文业务名；非业务卡为平台公共组件/混合业务/未知待确认",
  "businessConfidence": "high | medium | low | unknown",
  "cardTypeCode": "稳定英文卡型编码，如 merchant_text_append_card / product_card / platform_component",
  "cardTypeName": "与可见卡型一致的中文名称",
  "resultType": "merchant | product | package | hotel | ticket | platform_component 等",
  "classificationEvidence": ["当前卡片可见的业务/履约/内容判断依据"]
}
```

判定优先级：① 明确**业务线**标识；② 可确认业务线的卡片结构与可见内容；③ 可见标题与标签。履约方式只可作为辅助事实，不得单独推导业务线。**“团购”“团购套餐”“可随时退”等是履约/权益或卡型事实，绝不等同于业务线；`tuangou_goods` 不是合法 `businessCode`，不得写入清单，也不得映射为“团好货”。**仅存在团购履约标、但没有其他可见业务线证据时，标为 `ownershipScope: "unknown"`、`businessCode: "unknown"`，同时把团购信息写入 `resultType`、`cardTypeCode` 或 `classificationEvidence`；不得进入业务治理统计。`businessCode` 必须使用上述稳定业务线枚举；`businessName` 可保留当前可见商户名供审计，但**不得被下游当作业务线聚合键**（例如“熊本便利店”应以 `food_delivery` 聚合为“餐饮外卖”）。`high`/`medium` 的业务卡可进入业务治理统计。**自然触底截断且仅露出商品标题、缺少门店、履约方式或足以判定业务的完整卡片结构时，直接忽略：不得创建该卡的 `cards[]`、不得写入 `unknown` / “未知待确认”业务，也不得进入元素计数、评测分母、治理统计或报告。**其他 `low`、`unknown`、`mixed` 和 `platform` 卡保留在清单中仅供审计，但不得计入业务得分分母或生成业务治理 Tab。

### 4.2 关键字段识别旁路审计（必做，不污染元素清单 schema）

在元素清单同目录新增 `elements_<query><tagSuffix>.recognition-audit.json`。该文件必须记录 `query`、`screenshot`、`manifest`、`fullImageReadCount`、`localReviewReadCount`、`totalImageReadCount` 及 `fields`；每条 `fields[]` 至少含 `cardId`、`elementId`（图片存在性可为空）、`field`、`visibleText`、`status`（`confirmed|uncertain`）、`source`（`full_image|local_review`）、`reason`。总图片读取数不得超过 12。标题、价格、基础信息、履约和可见图片存在性均须按实际情况记录；低置信字段标为 `uncertain`，而不是猜测、补全或写成 UI 缺失。下游 Phase3 看到 `uncertain` 时只跳过该未确认事实的正向/负向推断，不创建人工复核任务；不得据此判定截断、错字、元素缺失或头图缺失。

> ⚠️ **禁止跨卡复用坐标——必须逐卡读图独立标定**。同类卡片之间头图高度、标题起始 y、
> 各信息行行高、下挂区类型都可能不同（例：迪士尼商卡1头图高约352、有5行信息含文字下挂；
> 商卡2头图高度/行数不同，且下挂是「文字下挂」而非「图文下挂」）。
> 每张卡都要单独**读图**定出**它自己**的头图区 y/x、各信息行 y/x、下挂类型与边界，据此填
> 该卡 tasks；不能把第一张卡的分区尺寸整体平移套到后续卡上。下挂区类型也要逐卡读图判断
> （有商品缩略图横滑=图文下挂/绿色；纯文字促销行=文字下挂/鹅黄）。
>
> 实测差异示例（迪士尼首屏）：商卡1头图宽326、标题起点 y1185、基础信息宽220；
> 商卡2头图宽338(更宽)、标题起点 y2078、基础信息宽806(含右侧距离)、下挂为2行文字下挂。
> 若不逐卡读图，商卡2的头图宽度、标题位置、下挂区范围都会框错。
>
> 卡内分区边界靠读图内容定，**不要**对卡内跑 `scan_card_regions.py` / `scan_textrows.py`
> 去凑精确 Y——它们阈值波动且读不出内容，只会引发调参重扫死循环（见顶部「核心原则」）。

### 5. 绘制标注

`SceneSpec` 与 `annotation_scene.py` 是**本地 PNG/JPG** 的统一渲染与审计入口；当前仓库尚无通用的“SceneSpec → IMD”在线适配器。在线新任务须先根据当前画板确认同一份局部 `image_pixel` 任务数据，再新建当前场景专用的 `scripts/imd_run_<scene>.py`，由该脚本将局部坐标加到当前画板偏移后传给 `run_scene`。历史 `imd_run_<scene>1.py` 只可参考任务字段、绘制顺序和交付格式，不可作为新图坐标或语义模板。

```bash
python3 scripts/imd_run_<scene>.py
```

底层调用 `imd_annotate_api.run_scene(FX, FY, tasks, "场景前缀")`，会为每条任务创建一个矩形 + 一个文字标签。
**绘制顺序即 z-order**：先画大的（border / 宏观组件），再画内部分区，文字标签自动叠在最上层。
配色由 `color_for(label)` 按 label 子串自动匹配（配色表见下方与 `imd_annotate_api.py` 的 `COLORS`）。

> 💡 **宏观组件按视觉边界划分，不是 scan_rows 内容行边界**：例，状态栏视觉边界 = y=0-120
> （含顶部padding+状态栏文字+底部padding），但 `scan_rows` 仅会检测出状态栏「文字内容行」
> = y=38-79。状态栏作为一个整体区域标注时，应该用 y=0-120 而不是 y=38-79——要的是肉眼
> 看到的整块视觉区域，不只是文字墨迹本身。

### 6. 验证（数值 + 视觉）

```bash
python3 scripts/imd_verify_export.py "<画板id>" "<场景前缀>_1" /tmp/verify.png
```

克隆底图 + 该场景全部 `[ANNO]`/`[ANNO-TXT]` 图层 → 编组 → 导出 → 删除临时组，得到叠加效果图。
再统计自查：`[ANNO]` 矩形数应与 `[ANNO-TXT]` 文字数相等。读回若干图层 `x/y/w/h/fills` 核对坐标与配色落地。

## 避免 context 爆满：读图外包给 subagent（多图并行必读）

工作流第 4 步「读图识别」会把整页 PNG（1224×2700）作为**视觉 token** 注入主线程上下文——
一张图就是一大块 token，读 2~3 张、或裁成多条分别读，主线程 context 会很快爆满，后续连
写脚本+验证的余量都没有。**根本解法：把「读图 + 出任务表」整步外包给 subagent（Agent 工具），
主线程只收坐标文本**。

### 怎么做

一张图起一个 `general-purpose` subagent，prompt 里交代：
1. 读 `SKILL.md`（核心原则 / 混合方法 / 配色表 / 踩坑速查）+ 模板脚本（如 `annotate_药店_1.py`）
2. 跑一次 `scan_rows.py` 找卡间留白（只跑一次，不调参重扫）
3. `Read` 图片，按规则识别宏观组件 + 每卡 border + 内部分区（逐卡独立，营销横幅≠商卡）
4. 写 `annotate_<场景>_1.py` 任务表脚本并执行，产出标注 PNG
5. `Read` 输出图自检，有错改 tasks 重跑
6. **最终回复只返回任务表 JSON + 确认 + 关键判断，禁止返回图片字节/base64**

多张图并行起多个 subagent（同一条消息里多个 Agent 调用），互不阻塞。base64 全留在
subagent 上下文里，主线程只拿回几行坐标——context 几乎不涨。

### 通用执行器下发给子代理：提效但不替代识别

将 `scripts/annotation_scene.py` 与 `scenes/scene_spec.template.json` 一并下发给子代理，能提高**确定性环节**的速度与准确性：子代理只需为当前截图完成语义判断和坐标确认，随后由统一执行器自动完成任务协议转换、越界/重复 ID/画布尺寸校验、PNG 绘制和审计报告生成。它避免每个子代理重复编写渲染、路径处理和基础校验代码，也让主 agent 能用统一报告汇总结果。

但执行器不是识别模型，不能把工作缩减为“只量坐标”：子代理仍必须先读当前原图，判断模块与卡型、逐卡确认头图四边/文本列/真实字段，再将这些**当前图的语义与坐标**写入 SceneSpec。`scan_rows` 只提供候选边界；历史 `annotate_<场景>.py` 只能参考任务结构和交付格式，绝不能作为新图坐标或语义的来源。

**推荐派发流程**：
1. 子代理读 `SKILL.md` 的核心原则、强制语义-几何核对、踩坑速查和本节；读取 `references` 的相关卡型规则。
2. 对当前图片最多执行一次整图 `scan_rows`（必要时一次当前卡文本列扫描），读取原图后填写 `scenes/<scene>.json`。
3. 运行 `python3 scripts/annotation_scene.py scenes/<scene>.json`，读取生成的 PNG 与 `.report.json` 做反向审图；修正 SceneSpec 后重跑。
4. 子代理最终返回输出路径、报告路径、任务数、告警、关键语义判断与 `elapsed_per_image`；主 agent 用报告核验，不接收图片字节。

### 子代理耗时基线与超时介入（强制）

一次「单图完整标注」的计时范围是：主 agent 派发任务时刻起，到子代理完成
`scan_rows → 原图识别 → 写任务表 → 生成 PNG → 输出反向审图`并返回时止。**禁止把只写脚本、未审图的中间状态计为完成。**

1. **固定超时阈值：11 分钟**：历史完整交付样本的耗时观察仅用于制定该阈值；统一以**子代理派发后 11 分钟未完成**作为介入节点，耗时记录不改变该阈值。
2. **11 分钟介入动作**：超过 11 分钟，主 agent 必须立即介入，不能只等待：①恢复该 agent 读取已完成步骤和卡点；②检查 SceneSpec、脚本、输出、审计报告与终端任务是否存在；③若卡在重复读图、重复扫描、模板化补全或过度细分，要求停止循环并按已读原图的真实语义收敛；④必要时接管未完成图片或拆分为单图新任务。介入、原因和处置结果必须记录在最终汇总中。
3. **仍需记录耗时**：每次完整交付仍记录 `dispatch_at / complete_at / image_count / elapsed_per_image`，用于观察异常和评估通用执行器效果，但不再改变 11 分钟的介入阈值。

### subagent prompt 必含的内容（派发模板）

派发 prompt 时，**先让 subagent 读 SKILL.md 的指定章节**——经验都在 skill 里，她读章节就能
用上，主线程不必每次重抄。再把下面禁令清单作为**额外强调**贴进去（这些是「安睡裤」场景
subagent 真实犯过的错，skill 别处没集中说，需明示）。

**prompt 要让她读的 SKILL.md 章节**（这些章节本身就是全部经验，subagent 读后能用上）：
- 「核心原则：内容优先，像素扫描仅限卡间/卡内留白」
- 「商卡内分区：混合方法」
- 「配色表（务必与 imd_annotate_api.py 的 COLORS 保持一致）」
- 「踩坑速查」
- 「本地图片标注」
- 模板脚本 `scripts/annotate_药店_1.py`（仅看 tasks/annotate_image 调用格式，坐标禁抄）

**额外强调禁令**（subagent 最易踩，需在 prompt 里明示才避）：

- ❌ **禁止套用别的场景的模板坐标**：顶部宏观组件（状态栏/搜索框/Tab/图筛/快筛/营销横幅）
  的**每个 y 边界**必须从本图实际读出，不准抄药店/烧烤/任何模板的数值。例如药店模板里
  搜索框 38-120、Tab 120-215、快筛 299-355 是**那个场景**的，安睡裤/烧烤的值完全不同，
  直接套用 → 宏观组件位置全错。
- ❌ **图筛、快筛与营销横幅按内容语义分，不按位置猜**：图筛必须有多个品类图片/图标及其分类文字，且外接框覆盖图标/图片行与文字行；快筛是独立的纯文字或文字+功能 icon 胶囊；营销横幅是优惠券/促销/满减/活动通栏（如“领券立减”“限时秒杀”“满99减20”）。不能因颜色、位置或图筛文字行误判。
- ❌ **头图宽度逐卡读实际值，禁用固定 w**：头图有多种尺寸类型，同一页里不同卡头图宽度
  可能不同（药店页就有 242/162 两种；安睡裤误用统一 w=286 导致框偏小）。逐卡 `Read`
  确认每张卡头图的**实际** x/w/h，不准把第一张卡的尺寸套到后续卡。
- ❌ **跨卡平移坐标**：每张卡的标题起点 y、价格 y、下挂类型都可能不同，逐卡读图，
  不准把第一张卡的分区 y 整体平移到后续卡。
- ❌ **禁止在过渡句停下**：必须一口气做完「scan_rows → Read → 写脚本 → 执行 → Read 自检
  → 返回」。不在"Now let me run the script..."这类过渡句处停手返回。中途出错自己改了继续，
  不返回中间状态。
- ❌ **第二/三屏禁止沿用首屏顶部组件**：`_2`、`_3` 默认从列表续页/滚动位置开始；只有原图实际存在完整的选中态文字导航时才标 `Tab`，只有实际存在“图片/图标 + 分类文字”整体时才标 `图筛`。普通内容、留白或列表续页不能补造顶部组件。
- ❌ **屏序必须先判定再写 SceneSpec**：首屏仅在原图可见首屏结构时写 `screen: 1, is_continuation: false`；第二、三屏必须写 `screen: 2|3, is_continuation: true`。续屏可以真实存在状态栏、搜索导航和纯文字快筛，但这些不构成 Tab 或图筛；出现商品图片也不等于图筛，必须同时满足“分类用途 + 图片/图标行 + 分类文字行”。
- ❌ **续屏结构先切模块、再切商卡**：屏顶若只露出上一张卡的商品/文字下挂，只标“续页可见尾部”的截断商卡部分，禁止补标题、头图或整卡字段；“大家还在搜 + 关键词胶囊”必须整体标 `相似推荐提示`；多商品拼贴/运营内容必须整体标 `运营聚合卡`，禁止套标准商卡模板。每张新起的标准左图右文卡都必须标出紧贴真实图片四边的 `头图区`，再从右侧文字列拆标题、基础信息、标签与下挂。
- ❌ **异构卡禁止套商卡模板**：看到「大家还在搜」、费力度/满意度评分、调研解释、品牌/运营聚合等非重复模块，应整体标为 `相似推荐提示` 或 `运营聚合卡`；不得创建其 `商卡_border`、头图区、标题区、价格区、下挂区。
- ❌ **续页不得模板化补全字段**：第二/三屏的每张标准卡也可能只剩标题+标签、图文下挂或其他局部结构。不要因为卡被识别为商家卡就固定补齐“商家信息→标签→AI推荐→文字下挂”；逐行读出当前可见文案，缺失字段不创建，图文/文字下挂按真实横跨范围处理。
- ❌ **图筛文字行不得另标快筛**：图筛的分类文字是图筛模块的一部分。先框完“图片/图标行+全部分类文字行”，再寻找真正独立、纯文字胶囊的快筛；找不到则不添加快筛。
- ❌ **最终只回 JSON + 关键判断**：禁止返回 base64/图片字节（否则主线程 context 仍会爆）。
  返回 tasks JSON + 一句确认 + 关键判断（图筛/营销横幅各是什么、每卡头图宽度）即可。

> 这几条本质是把「核心原则」「踩坑速查」里已有但分散的点，集中成 subagent 可照做的禁令。
> subagent 不会主动综合全文，集中派发比让她自己读 SKILL.md 全文更可靠。

### 何时用

- 同时标 ≥2 张图：**强烈建议**，否则主线程必爆。
- 单张图但想省 context：也建议，主线程只做最后 `ls` 确认输出存在。
- 已装 `explore-design-tree-remote` 且能拿 IMD 图层树 JSON：优先走图层树（纯文本坐标，
  根本不读图，见下节），subagent 是本地截图/无图层树时的首选。

### 反面（不要再这么做）

- ❌ 主线程 `Read` 整页 1224×2700 PNG 多张 → 一张就是一大块视觉 token
- ❌ 把图裁成 4 条、主线程逐条 `Read` → 开销 ×4 且视觉 token 不去重
- ❌ 同一会话反复 `Read` 同一张大图 → 不去重，重复计费
- ❌ 主线程读大段参考文档（如 59KB 规则.md 整篇）→ 按需读章节，别整篇塞

> 本节方法已在「烧烤 / 安睡裤」双图场景验证：两个 subagent 并行，主线程 context 基本不涨，
> 标注 PNG 正常产出。核心是把「读图」这个 token 大户隔离出主线程。

## 精确坐标提取：利用 explore-design-tree-remote 图层树（替代步骤 3-4 的手工像素扫描）

步骤 4 的卡内分区靠读图内容判定、卡间留白用 `scan_rows.py` 一次性定位（见顶部「核心原则」）。**若本机已装 `explore-design-tree-remote` skill**（mtflexbox-agent 工作区自带，或从 FRIDAY Skillhub 装），可直接从 IMD 设计稿提取完整图层树 JSON，拿到每个节点的精确 `absBox`（像素坐标）+ CSS + 语义角色，据此自动填任务表——这是精确坐标的**首选**：无阈值波动、含语义角色辅助判卡片类型，远胜像素扫描。

**前提**：catdesk-browser 可用 + 本机已登录美团 SSO（imd 复用登录态）。不装浏览器插件、不上传 Supabase、不受席位限制。

**提取命令**（在 `explore-design-tree-remote` skill 目录下）：

```bash
python3 scripts/pipeline/fetch_imd_direct.py <documentId> --frame-id "<layerId>" \
  --url "https://imd.sankuai.com/file/<documentId>?layer_id=<layerId>" --outdir /tmp/d2c
```

> `documentId`/`layerId` 从 IMD 编辑模式 URL `https://imd.sankuai.com/file/{documentId}?...&layer_id={layerId}` 取。只给 `/goto/<短码>` 短链时，需用户先在浏览器打开解析到 `/file/` 长链再提供 documentId/layerId（短链是 JS 客户端跳转，citadel fetchImage 只拿到 SPA 壳）。

**产物**（落 `/tmp/d2c/{documentId}/`）：

| 文件 | 用途 |
|---|---|
| `<帧名>.json` | 单一权威设计树（cleaned，含全节点 `_abs` 绝对坐标 + semantic 语义角色 + CSS） |
| `<帧名>.png` | Frame 预览截图 = **可直接当标注底图**（替代步骤 3 的 `imd_export_node.py` 导出） |
| `_ready.json` | 帧索引：`modules`（带 bbox 的模块候选）+ 节点/切图/文本数量 |
| `_exports.json` | 切图清单（nodeId→文件路径） |

**如何据此填任务表**：用 skill 自带工具从 JSON 提取坐标——

```bash
# 列出所有模块候选（带 bbox），对应宏观组件/商卡边界
python3 scripts/search_nodes.py /tmp/d2c/<帧名>.json --exportable --compact
# 看某模块内部布局尺寸（absBox 即像素坐标，直接填 tasks 的 x/y/w/h）
python3 scripts/inspect_node.py /tmp/d2c/<帧名>.json "<引用>" --with-parent --neighbors
# 裁某块小图做 Diff 验证
python3 scripts/crop_node.py /tmp/d2c/<帧名>.json "<引用>"
```

> `<引用>` = 节点寻址语法（`id` / `text:子串` / `name:子串`）。先读取目标 frame 的 `absBox`：若子节点坐标接近 frame 左上角的 `(0,0)`，按局部坐标使用；否则按绝对坐标处理并减去 `frame.x/frame.y`。适配层只接收转换后的局部 `image_pixel` 坐标，最终仍须用导出图核验。

**与读图 / 扫描的关系**：图层树只提供精确几何候选与节点语义线索；读图内容是区域类型与可见边界的**权威**。`scan_rows.py` 只作留白和内容行边界辅助。仅当图层树不可用、整图与当前卡文本列的单次 `scan_rows` 都无法提供可用候选、且人工读图仍不能确定边界时，才可二选一单次使用 `scan_textrows.py` 或 `scan_card_regions.py`；必须在 SceneSpec 的 `source` 和审计告警中记录工具、参数与原因，禁止循环重扫。

**备选方案（更简单，仅截图无图层树）**：若只需底图不需坐标，用 `imd-reader` skill（`~/.catpaw/skills/skills-market/imd-reader`）走原型预览模式截图——URL 改 `/file/`→`/prototype/`，100% 缩放清晰可读，catdesk 截图即可，无需图层树解析。

## 配色表（务必与 imd_annotate_api.py 的 COLORS 保持一致）

| 组件 / 分区 | HEX | 透明度 | 说明 |
|---|---|---|---|
| 状态栏 | C8D2DC | 20% | |
| 顶部导航/搜索框 | 6495ED | 22% | |
| Tab | 7B68EE | 22% | |
| 场次日期Tab / 日期区 | 40E0D0 | 22% | 演出/影院场次专用；须在 Tab 前（含子串） |
| 图筛 | DAA520 | 20% | 金色系，区别于纯文字筛选器 |
| 快筛/排序/筛选器 | 9370DB | 22% | |
| 营销横幅 / 品牌秀异构卡 / 运营聚合卡 | DAA520 | 18-22% | 列中异构卡整体一个矩形 |
| 商卡整体边界 | 787878 描边 | strokeWeight=4 | 只描边不填充 |
| 头图区 | ADD8E6 | 25% | |
| 副标题区 | B0C4DE | 22% | 商品卡片 region③；须在「标题区」前（含子串） |
| 标题区 | 87CEFA | 24% | |
| 评分区 / 评分与推荐理由 | F08080 | 22% | 评分/想看/已售；酒店商家卡 region③ 顶部、房型卡底部同色 |
| 基础信息区 / 商家信息区 / 套餐概要 / 演出信息区 | DDA0DD | 24% | 各卡类型 region③ 信息行等价（商家卡称"商家信息区"、度假卡称"套餐概要"、演出卡称"演出信息区"） |
| 标签区 | FFDAB9 | 25% | 异形/异色标签、榜单标签 |
| AI推荐理由 | D8BFD8 | 22% | 商家卡-文字下挂 region⑤ |
| 价格区 / 价格标签 | FF8C69 | 24% | 价格/销量；酒店卡 region⑥"价格标签"同色 |
| 坑位（左上/右上/底部/标题后） | CD5C5C | 28% | 头图角标/标题后坑位，可选子区（详见规则 3.4.2） |
| 图文下挂区 | 98FB98 | 22% | 带商品缩略图的横滑卡 |
| 文字下挂区 | FFEC8B | 25% | 纯文字型下挂（神券/满减券后价等） |
| 相似推荐提示 | FFDAB9 | 20% | |

**标签区 vs 文字下挂区（最易错，重点区分）**：
「标签区」是挂在标题/基础信息旁的异形/异色标签、榜单/推荐语；
「文字下挂区」是卡片下半部的**纯文字型促销下挂**，如「神券 券后¥x」「满xx减xx」「6.5折 商品名」等成行文字（无商品大图时）；
有商品缩略图横滑的下挂则是「图文下挂区」（绿色）。曾在万达地标卡把文字下挂误判为标签区，务必按这条区分。

## 踩坑速查

| 现象 | 解决 |
|---|---|
| `screenshot` 报 `Page.captureScreenshot timed out` | 改用 `imd_export_node.py`（`exportAsync`）取底图 |
| `catdesk browser-action` 里写复杂 JS 报 Invalid JSON | 用 `imd_eval.py` 封装（Python `json.dumps` 序列化后再传） |
| 超长 evaluate 返回混入「Full output saved to...」 | 脚本已自动检测并回读落盘文件；base64 分块 CHUNK=60000 且校验无空格/换行 |
| 颜色/透明度不生效、读回是默认灰 alpha=1 | fills 传完整对象，`color.a` 与 `alpha` 双写（见 `create_rect`） |
| `resize is not a function` | 用 `node.width` / `node.height` 直接赋值 |
| `mg.currentPage` 为 undefined | 用 `mg.document.currentPage \|\| mg.document.children[0]` |
| 图层面板点击无效 | 全程走插件 API，不碰面板；必须点面板时用 catdesk 原生 click 而非 JS `.click()` |
| 像素扫描结果与读图判断不一致、想调参重扫 | 停。卡内边界以读图内容为准；`scan_rows` 只跑一次找卡间留白，禁止重扫（见「核心原则」） |
| **营销横幅误判为商卡**（通栏促销条高度~117px，比正常商卡~450px 矮很多，被当成「首张小商卡」）导致后续商卡编号整体错位+1 | 读图看内容：金色/彩色通栏促销条 = 营销横幅（DAA520 macro），**不是**商卡 border。`scan_rows` 留白带能区分：矮留白带（h<120）夹在快筛与正常卡之间的是营销条占位 |
| **scan_rows 稀疏组件留白陷阱**：Tab/图筛/快筛之间常有「内容→留白→内容→留白」交替，留白带高度不均（如 84px/68px/57px），不能把每个留白带都当卡间切割线 | 顶部宏观组件（Tab/快筛/营销条）的边界**必须读图确认**，不能只靠 `scan_rows` 留白带推断。`scan_rows` 仅用于卡列表区域（留白带均匀、h>60）的卡间切割 |
| 商卡内分区顺序套错（价格紧跟标题，实际价格在卡中下部） | 读图确认分区纵向顺序：通常 头图(左)→标题→基础信息→标签→价格→商家，价格靠下不靠上。逐卡读图，不套用第一张卡的分区尺寸 |
| **商卡内分区不到位**（卡顶标了标题/价格，卡中下部大段空白未标；分区不贴合内容行） | 混合方法：`scan_rows.py <img> 385 1188 <卡顶> <卡底>` 限区扫出客观内容行边界 → 读图贴语义标签 → **覆盖全部内容行不留空白**。卡内大留白带(h≥50)是上下区天然切割线，价格通常在下区（见「商卡内分区：混合方法」）|
| **scan_rows 卡内扫描整段被当成一个内容行**（卡背景非纯白，留白带 mean<240 检测不到） | 不调阈值重扫。可参考同页同类型卡结构缩小当前卡的人工核验范围，但不得平移旧坐标；按当前卡可见文案和边缘逐边确认，并在任务表标记 `source: estimated`。 |
| **subagent 套用别的场景模板坐标**（状态栏/搜索框/Tab/图筛/快筛 y 全错，直接抄了药店 38-120/120-215/299-355） | 派发 prompt 必须贴「subagent prompt 必含的禁令」清单（见上节），明示"禁抄模板坐标，每个 y 边界逐图读出"。光让她读 SKILL.md 全文不够，她不会主动避开 |
| **subagent 在过渡句停下不完成**（返回"Now let me run the script..."就停了，未产出标注 PNG） | 同上禁令清单：明示"一口气做完 scan_rows→Read→写脚本→执行→自检→返回，不在过渡句停" |
| **subagent 把头图统一标成 w=286**（头图实有多种尺寸，同页 242/286/326/338 都可能） | 禁令清单：头图宽度逐卡 Read 实际值，禁用固定 w，禁跨卡平移 |
| **顶部组件位置“凭印象”定位（Tab 标在 Tab 与 图筛之间的空白带、图筛和快筛错位）** | 宏观组件先按可见内容和视觉边缘取框；整图 `scan_rows.py` 仅可单次辅助核验留白候选。特别是图筛含「图片/图标行 + 文字行」时，任务框必须覆盖完整两行；快筛必须以实际纯文字筛选项所在行取框，不能把图筛的文字行错当快筛。 |
| **错认不存在组件（如未核实就给生理盐水页加了“图筛”，或把普通内容细条加成营销横幅）** | 是否存在图筛/营销横幅必须读图内容判断：图筛应有圆形/圆角图标或图片及相应分类文字；营销横幅必须有明确促销/活动文案与通栏视觉。Tab 与快筛之间若是留白或普通页面内容，任务表不得凭空添加任何组件。 |
| **头图区范围偏大/偏小**（框进卡片白边、文字列，或缩小后仍未贴真实图片） | 不能用“内容行”或固定宽度代替图片边界。读原图逐边确认 `x0/x1/y0/y1`，以实际图片颜色/照片边缘为准；输出图复核时专门放大头图，确认框不触碰 padding、右侧文字与图片下方留白。 |
| **文字下挂区压到左侧头图，或把标签行并入下挂** | 先锁定右侧文本列起点，右侧文字下挂的 `x` 必须从文本列开始；只有横跨全卡的真实内容才能从卡左侧开始。按文案语义切分：资质、验真、神券权益、榜单等是标签区；其后的连续商品/促销文字（可含券后价）才是文字下挂区，按实际两行/多行整体覆盖。 |
| **为凑模板虚构副标题/价格/商家分区** | 任务表不要求每种 label 都出现。先读取每行实际文案：价格若是促销下挂的一部分，标为文字下挂；无副标题/商家信息就不要创建副标题区/商家区。输出前逐项检查是否存在“画面中找不到的语义标签”。 |
| **商卡1识别为错误商家（如药店标了“美罗家大药房”为第一张，实际是“111医药馆”；游乐场标了“武汉欢乐谷”实际是“奈尔宝”）** | 商卡1 必须读图内容定位，取实际商家名作为错位检验错。不准模板套、不准其他场景的第一个商卡名拿过来。每次画任务表前必读图识别每一张卡的标题区商家名，错位检验错使用。 |
| **图文下挂区有时含两行内容（scan_rows 会误判中间为留白带）** | 图文下挂区是横滑商品卡列表，可能分多行。例：游乐场商卡1 下挂区 = y=1054-1172（h=118），含 ¥190 4.2折 ... 一年售1.4万+ 与 ¥53 5.3折 成人陪同票 ... 一年售3.9万+ 两行横滑。`scan_rows` 会将中间部分（h=44）判为留白带，此时按读图覆盖：下挂区作为一个外接矩形覆盖到下一张卡的上边界，同一 label 跨多行。 |
| **卡内分区需要限区扫描辅助** | 商卡头图会干扰整宽扫描。仅当当前卡文字列已确认、且读图仍无法确定卡内行边界时，才可用 `scripts/scan_rows.py <img> 365 1190 <y0> <y1>` 对该文字列单次扫描。结果只是文字行间隔候选，不代表头图或区域语义；不强制与整图扫描组成双路校验。 |
| **同类页的商卡结构相似** | 可参考第一张卡的字段命名和分区顺序来组织当前卡的核验，但不能把其位置、偏移或字段存在性带入当前卡。当前卡坐标和字段必须由可见内容逐项确认；扫描结果只作几何候选。 |
| **第二/三屏仍标了 Tab 或图筛** | `_2`/`_3` 默认视为列表续页：先读顶部是否真的存在完整组件。只有可见一排带选中态的文字导航才标 `Tab`；只有每项同时具备图片/图标和分类文字才标 `图筛`。内容续页、留白和商卡列表均不得继承首屏任务。 |
| **把大家还在搜、费力度评分卡当成常规商卡** | 先看模块是否重复且具备标准卡字段。`大家还在搜`（标题+关键词胶囊网格）标为 `相似推荐提示`；费力度/满意度评分（问题、分值/选项、解释）标为 `运营聚合卡`。两者均整体取外接矩形，不创建商卡边界或任何常规卡内分区。 |
| **子代理长时间未结束或疑似卡住** | 主 agent 记录每图派发/完成时间。派发后超过 **11 分钟**仍未完成，必须立即检查已完成步骤、SceneSpec、脚本、输出、审计报告和终端状态；排除重复扫描、反复读图、模板化补全或过度拆分后，要求收敛、接管或拆为单图，并记录原因和处置结果。 |

## 脚本清单

核心库与辅助工具（复用固定资产）：

- `imd_eval.py` — `catdesk browser-action` 封装。`eval '<js>'` / `action '<json>'` 两种模式。
- `imd_export_node.py` — `<nodeId> <out.png> [scale]`：导出画板底图 PNG。
- `imd_annotate_api.py` — **核心库**：`create_rect` / `create_label` / `run_scene` + 配色表 `COLORS`。
- `imd_verify_export.py` — `<baseId> <场景前缀> <out.png>`：非破坏性验证导出。
- `imd_read_frames.py` — 按图层名批量读画板坐标（属性面板方式，备用）。
- `scan_rows.py` — 找卡间/组件间留白带（无 y 参数）+ 商卡内内容行边界（给 y 范围：`<img> <x0> <x1> <y0> <y1>`）。混合方法用：scan_rows 出客观行边界，读图贴语义标签（**一次性，不调参重扫**）。
- `detect_photo_region.py` — **纯像素照片区检测（头图/商品图），不读图**。OpenCV port 自 eval-3-color-logic 策略A：白底→内容mask→`findContours`→逐轮廓按 面积/hue active bins/RGB std/宽高比 分类 photo/ui→合并邻近。`python3 scripts/detect_photo_region.py <img> [--min-area N] [--h-gap 20] [--v-gap 15] [--json]`。双页验证：头图可靠检出（烧烤 4/4、安睡裤 3/4，第4卡图底截断漏检非脚本缺陷）；**min-area 非通用筛子**（两页头图 area 差 4 倍），选头图需配 scan_rows 卡 Y 归卡；**营销横幅不靠它**（检横幅内零碎照片，通栏 macro 靠 scan_rows+内容判定）。
- `scan_textrows.py` / `scan_card_regions.py` — **已降级，不用于卡内边界判定**（阈值波动且读不出内容，易引发重扫死循环）。保留脚本仅供极端 fallback 单次使用。
- `annotation_scene.py` — **通用本地执行器**：读取 `scenes/*.json` 的声明式 SceneSpec，执行几何/结构校验、调用 `annotate_image.py` 并输出 `<图片>_annotated.report.json` 审计报告。它不推断区域语义、不卡片自动分类、也不复用其他截图坐标。
- `scenes/scene_spec.template.json` — SceneSpec 数据模板。场景坐标和语义必须基于当前原图独立确认；可复制结构填写，不可复制另一张图的数值。

> **通用能力与场景经验的边界**：可复用的是任务协议、渲染、配色、几何校验、审计报告、`scan_rows` 的候选边界发现和同一页面内“独立锚点驱动”的布局生成；不可复用的是跨图绝对坐标、卡片顺序、字段是否存在、营销/异构模块归类。`annotate_<场景>.py` 仅是已验证场景的真值记录，不能作为新截图坐标来源。

历史场景真值索引（仅供同图复核与任务格式参考）：

- `imd_run_wanda1.py` — 单列：地标卡 + 图筛 + 快筛 + 商家卡片（含被截断卡）。
- `imd_run_dianjing1.py` — 双列瀑布流酒店卡（左右列 x 偏移 + 行 y 偏移）。
- `imd_run_xiangsheng1.py` — 单列演出票务卡（海报头图/评分/日期/价格/场馆），等距循环。
- `imd_run_qingshu1.py` — 电影影院场次页（影片信息卡 + 日期Tab + 多张纯文字场次卡）。
- `imd_run_jubensha1.py` — 单列剧本卡 + 顶部双并排运营聚合卡。

## 本地图片标注（另一条产出路径，无需 IMD）

当用户给的是本地整页截图（PNG/JPG，如 `xxx_全部_1.png`）而非 IMD 链接时，用 `annotate_image.py` 直接在图片像素上绘制标注，产出一张标注 PNG。它与 IMD 版**共用同一套配色表 COLORS 和任务表结构** `{label,x,y,w,h,kind}`，坐标就是像素坐标（本地图片即画板本身，无偏移）。

```python
import sys; sys.path.insert(0, "<skill>/scripts")
from annotate_image import annotate_image
tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 112, "kind": "macro"},
    {"label": "商卡1_border", "x": 18, "y": 1150, "w": 1188, "h": 540, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 1182, "w": 328, "h": 353, "kind": "part"},
    # ... 其余区域
]
annotate_image("迪士尼_全部_1.png", "out/迪士尼_全部_1_annotated.png", tasks)
```

流程与在线版一致：先列出并核对用户指定的目标文件名；再用 `image_read` 读图识别卡内分区类型与边界 + `scan_rows.py` 一次性找卡间留白补宏观边界；按「绘制前的强制语义-几何核对」逐项确认后写任务表调用 `annotate_image` 或 `annotation_scene.py`；最后同时对照原图与输出图做反向审图。推荐将当前截图的已确认任务保存为 `scenes/<scene>.json`。SceneSpec 必须填写 `page_context.screen` 与 `page_context.is_continuation`；首屏还必须填写 `below_tab_component`（`运营聚合卡` / `图筛` / `无`）。再运行：

```bash
python3 scripts/annotation_scene.py scenes/<scene>.json
```

执行器会阻断续屏继承 Tab/图筛/营销横幅、续屏首卡未声明 `cropped:true`、以及首屏“运营聚合卡”与图筛同时存在等结构错误。除审计报告外，交付前还须确认 `elements_<搜索词>.json` 中 `screenshot`、`annotatedImage` 均指向项目级绝对路径，且每张可见商卡已填稳定 `businessCode`；不得用 `--skip-semantic-validation` 绕过新场景校验。

该命令会在导出前阻断越界/尺寸不符/重复 id 等几何结构错误，并生成审计报告；它不会替代读图语义判定。审计输出的 `duplicateSupplyCandidates` 是**保守候选**：仅同一截图内主标题完全一致时产生，必须继续核对门店、地址、业态和套餐/商品；它只提示 Phase3 复核，绝不直接等同于重复供给或冗余问题。若某场景已在 IMD 版做过任务表（`imd_run_<scene>1.py`），只能复用**已经针对同一张底图验证过**的坐标（去掉 `FX/FY` 偏移即为像素坐标）；不同截图禁止直接复用。

## 一键回滚（删除本次全部标注）

```bash
python3 scripts/imd_eval.py eval '(() => { const doc=window.mg.document; const page=doc.currentPage||doc.children[0]; let c=0; for(const n of [...page.children]){ if(n.name && (n.name.indexOf("[ANNO] ")===0 || n.name.indexOf("[ANNO-TXT] ")===0)){ n.remove(); c++; } } return "removed "+c; })()'
```

## 约束

- 只新增 `[ANNO]` 图层，绝不修改/移动/删除原设计稿图层（非破坏性）。执行前告知用户会在源文件留下新图层。
- 若用户尚未明确标注范围（场景/画板/屏数）或颗粒度（两级 / 仅宏观），先询问；用户已明确时直接执行，无需重复确认。
- 每个场景绘制后必做 group 导出视觉验证。
- 识别环节（读图判定卡内分区，尤其标签区 / 文字下挂区、异构卡边界）应保留来源、置信度和 `uncertain` 原因；不创建人工复核任务。
- 若新场景图层名不符合 `{场景名}_全部_{N}` 规律，先用关键词试搜或请用户提供准确画板名，禁止凭猜测的 id 执行。
