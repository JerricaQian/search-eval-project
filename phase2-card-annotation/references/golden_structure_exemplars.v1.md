# 黄金样本结构范例 v1

本文件提供可迁移的元素结构参照。它回答“当前可见内容应如何分区、分项和归属”，不提供可复制到新截图的字段值或坐标模板。

文中路径均相对于 `phase2-card-annotation/`。

## 目录

1. 卡片标题
2. 文字下挂
3. 常规图文下挂
4. 异构下挂与常规下挂共存
5. 图片内部文字与独立 UI 文字
6. 基础信息、标签与元素粒度
7. 失败处理

## 使用方法

1. 先在当前截图中确认卡片、区域和可见下挂项边界。
2. 对每个下挂项分别选择最接近的范例结构；同一区域可以使用不同范例。
3. 只复用字段关系和可选性。文字、坐标、项数、排列、尺寸及裁切状态全部以当前截图为准。
4. 范例的适用范围以各节说明为准；不要把样本中未被本节引用的其他区域标注当作规则。
5. 当前结构与所有范例都不同，才新增异构类型。新增时必须同时补充一份人工确认的黄金 JSON 范例和回归用例。

## 1. 卡片标题

参照：

- `golden-sample-results/merchant-graphic-hang/盒马.elements.json` 中“盒马鲜生代购（望京广顺北大街）”的 `标题区`。
- `golden-sample-results/merchant-graphic-hang/蜜雪冰城.elements.json` 中“蜜雪冰城（东辛店）”和“茶山季（合生汇店）”的 `标题区`。

结构含义：主标题是卡片身份文本；同一区域内的“外卖”“到店”等履约标是独立元素，不能替代或并入标题。标题通过卡片身份、视觉层级及相邻元素关系确认，不以“第一条长 OCR 文本”“包含店字”或固定坐标确认。

```json
{
  "标题区": {
    "elements": [
      {"elementType": "履约标签", "visibleText": "<当前可见履约文字>"},
      {"elementType": "商家标题", "visibleText": "<当前可见完整标题>"}
    ]
  }
}
```

标题区没有履约标签时只保留标题；卡片可见但标题证据不足时标记 `uncertain`，不从搜索词或其他卡片补写。

## 2. 文字下挂

参照：`golden-sample-results/merchant-text-hang/商家卡片-文下挂-搜索词为按摩.elements.json` 的 `文字下挂区`。

一个文字下挂项代表一个可购买的服务/商品供给。名称、价格、折扣和销量都归属于该项，但它们是独立语义元素；是否出现、出现几行以及彼此位置由当前画面决定，不存在固定的“文字槽”“价格槽”或“折扣槽”。没有渲染图片时 `imageElements=[]`。

```json
{
  "itemIndex": 1,
  "imageElements": [],
  "textElements": [
    {"elementType": "下挂商品名", "visibleText": "【按摩养生】冲击波/超声按摩仪"}
  ],
  "priceElements": [
    {"elementType": "下挂商品价格", "visibleText": "¥160"}
  ],
  "auxiliaryElements": [
    {"elementType": "下挂价格折扣标签", "visibleText": "<若可见>"},
    {"elementType": "下挂商品销量", "visibleText": "年售60+"}
  ]
}
```

这里的示例文字只帮助理解角色，不是新截图的候选答案。折扣或销量不可见时省略对应元素；名称发生真实换行时可以有多个文字元素，但不能按单字拆分，也不能把相邻下挂项的字段合并进来。

## 3. 常规图文下挂

参照：`golden-sample-results/merchant-graphic-hang/盒马.elements.json` 第一张商家卡的 `下挂商品区`。

每个下挂项是一个完整归属单元：下挂图片、下挂文字和下挂价格属于同一个 `item`，再按语义放入对应数组。不能先收集整排图片、整排文字和整排价格，再靠序号猜配。

```json
{
  "itemIndex": 1,
  "imageElements": [
    {"elementType": "下挂商品图片", "visibleText": ""}
  ],
  "textElements": [
    {"elementType": "下挂商品名", "visibleText": "盒马 左旋肉碱水 960ml"}
  ],
  "priceElements": [
    {"elementType": "下挂商品价格", "visibleText": "¥10 限1件"}
  ],
  "auxiliaryElements": [],
  "visibleStatus": "confirmed"
}
```

同一范例中的第四项展示页面边缘裁切：仍保留下挂图片、可见文字“国产富士...粒装 约6...”和可见价格“¥13.44 限...”，并设置 `visibleStatus: "naturally_cropped"`。省略号和截断内容只能来自当前可见像素，不能推测屏外原文。

## 4. 异构下挂与常规下挂共存

参照：`golden-sample-results/merchant-graphic-hang/蜜雪冰城.elements.json` 中“茶山季（合生汇店）”的 `下挂商品区`。

该卡的第一个可见项是异构横幅：图片和横幅文字构成一个项，横幅文字本身包含价格，因此不再虚构独立价格元素。后续可见项是常规图文下挂，各自拥有图片、商品名、现价及可见原价。这个范例说明的是“逐项选择结构”，不是“异构项后面固定有两个普通项”。

```json
[
  {
    "itemIndex": 1,
    "itemType": "异构下挂",
    "imageElements": [
      {"elementType": "异构下挂图片", "visibleText": ""}
    ],
    "textElements": [
      {"elementType": "下挂文字横幅", "visibleText": "【茶山季必喝】四 ¥16"}
    ],
    "priceElements": [],
    "auxiliaryElements": [],
    "visibleStatus": "naturally_cropped"
  },
  {
    "itemIndex": 2,
    "itemType": "常规图文下挂",
    "imageElements": [
      {"elementType": "下挂商品图片", "visibleText": ""}
    ],
    "textElements": [
      {"elementType": "下挂商品名", "visibleText": "【手作冰淇..."}
    ],
    "priceElements": [
      {"elementType": "下挂商品价格", "visibleText": "¥10.8"}
    ],
    "auxiliaryElements": [
      {"elementType": "下挂商品原价", "visibleText": "¥18"}
    ],
    "visibleStatus": "confirmed"
  }
]
```

识别时应遍历整个可见下挂区域，为每个兄弟项独立选型。若最右侧只露出图片边缘，也建立该可见项并标记自然裁切；不可见的文字和价格数组保持为空。

## 5. 图片内部文字与独立 UI 文字

参照：烧烤类黄金样本中曾出现的商品图片印刷字。

图片作为一个图片元素占位。包装、招牌、品牌或装饰画面里的文字属于图片内容，不自动转成标签、标题或下挂文字。只有与图片视觉容器分离，并承担价格、商品名、按钮、标签等界面角色的文字，才建立独立元素。

## 6. 基础信息、标签与元素粒度

基础信息和标签按独立语义字段或独立视觉 chip 拆分。例如面积、人数、床型是三个元素；起送价、配送费、距离也是各自的字段。规则的粒度是“用户可以独立理解和比较的字段”，不是整行，也不是单个字符。符号和后缀（如 `¥`、`起`、`折`）必须跟随其所属字段。

标签区参照：`golden-sample-results/merchant-text-hang/商家卡片-文下挂-搜索词为面部清洁.elements.json` 中“美丽荟西子医疗美容”。同一行有三个独立视觉实体：

```json
[
  {"elementType": "商家标签", "visibleText": "医疗资质", "visual": {"colorRole": "green"}},
  {"elementType": "商家标签", "visibleText": "放心美验真", "visual": {"colorRole": "orange"}},
  {"elementType": "商家标签", "visibleText": "神券最高膨至300", "visual": {"colorRole": "red"}}
]
```

这个范例说明：OCR 即使把“医疗资质放心美验真”返回为一行，绿色与橙色的独立文字段仍是两个元素；红色神券是第三个元素。分元素依据是当前截图中的独立颜色、间隔、容器或功能语义，不能把 OCR 行框直接当元素框。

## 7. 失败处理

- 能确定区域和元素角色、但原文不完整：重新读取覆盖完整可见字形的当前元素范围。
- 当前可见范围天然被屏幕裁切：只写可见原文并标记 `naturally_cropped`。
- 角色或归属无法确认：标记 `uncertain` 并阻断发布，不用最相似黄金样本补值。
- 出现未覆盖的新结构：保留当前证据，新增经人工确认的结构范例后再发布；不要用坐标特判把它伪装成已有结构。
