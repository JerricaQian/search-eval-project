#!/usr/bin/env python3
"""Build complete eval_results for 安睡裤 query."""
import json
from pathlib import Path

PROJECT = Path("/Users/qianjing/Desktop/workproject_2/search-eval-project")

results = [
  {
    "skill": "eval-1-supply-completeness",
    "dimension": "phase3-card_or_component-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "不达标",
        "reason": "三张商品卡中第二张存在空白元素（下挂区补充说明行），取最差值为不达标",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "original-page",
          "criterion": "逐组件识别页面截图中是否存在元素缺失（标题、下挂、价格、评分、人均、商圈、商家头图、标签等），判断缺失元素的重要程度并按标准评级",
          "summary": "页面含三张商品卡，均为闪购业态左图右文布局。第一张含七个元素全部正常渲染。第二张含八个元素，其中下挂区第二行文本渲染失败（像素扫描inkRatio为零）。第三张含八个元素全部正常渲染。",
          "overview": {"total": 3, "excellent": 2, "pass": 0, "fail": 1, "failRate": "33.3%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png",
            "evaluatedUnitCount": 3,
            "assessmentRows": [
              {
                "componentId": "C1", "visibleBounds": [18,952,1188,417],
                "applicableFields": ["头图","标题","基础信息","标签","价格","商家","下挂"],
                "checkResults": [
                  {"field":"头图元素","inkRatio":0.8418,"blank":False,"status":"ok"},
                  {"field":"标题元素","inkRatio":0.4262,"blank":False,"status":"ok"},
                  {"field":"基础信息元素","inkRatio":0.1072,"blank":False,"status":"ok"},
                  {"field":"标签元素","inkRatio":0.2722,"blank":False,"status":"ok"},
                  {"field":"价格元素","inkRatio":0.1037,"blank":False,"status":"ok"},
                  {"field":"商家元素","inkRatio":0.2166,"blank":False,"status":"ok"},
                  {"field":"下挂文字元素","inkRatio":0.085,"blank":False,"status":"ok"}
                ],
                "rating": "优秀"
              },
              {
                "componentId": "C2", "visibleBounds": [18,1454,1188,478],
                "applicableFields": ["头图","标题","基础信息","标签","价格","商家","下挂行一","下挂行二"],
                "checkResults": [
                  {"field":"头图元素","inkRatio":0.9454,"blank":False,"status":"ok"},
                  {"field":"标题元素","inkRatio":0.4302,"blank":False,"status":"ok"},
                  {"field":"基础信息元素","inkRatio":0.0542,"blank":False,"status":"ok"},
                  {"field":"标签元素","inkRatio":0.073,"blank":False,"status":"ok"},
                  {"field":"价格元素","inkRatio":0.1512,"blank":False,"status":"ok"},
                  {"field":"商家元素","inkRatio":0.14,"blank":False,"status":"ok"},
                  {"field":"下挂行一文字元素","inkRatio":0.2508,"blank":False,"status":"ok"},
                  {"field":"下挂行二文字元素","inkRatio":0.0,"blank":True,"status":"fail"}
                ],
                "rating": "不达标"
              },
              {
                "componentId": "C3", "visibleBounds": [18,2017,1188,478],
                "applicableFields": ["头图","标题","基础信息","标签","价格","商家","下挂行一","下挂行二"],
                "checkResults": [
                  {"field":"头图元素","inkRatio":0.4014,"blank":False,"status":"ok"},
                  {"field":"标题元素","inkRatio":0.4291,"blank":False,"status":"ok"},
                  {"field":"基础信息元素","inkRatio":0.0348,"blank":False,"status":"ok"},
                  {"field":"标签元素","inkRatio":0.0392,"blank":False,"status":"ok"},
                  {"field":"价格元素","inkRatio":0.1417,"blank":False,"status":"ok"},
                  {"field":"商家元素","inkRatio":0.1369,"blank":False,"status":"ok"},
                  {"field":"下挂行一文字元素","inkRatio":0.1828,"blank":False,"status":"ok"},
                  {"field":"下挂行二文字元素","inkRatio":0.1045,"blank":False,"status":"ok"}
                ],
                "rating": "优秀"
              }
            ]
          },
          "issues": [
            {
              "elementId": "C2-text-append-2",
              "coord": [18, 1868, 1188, 28],
              "component": "C2",
              "elementType": "文本",
              "content": "原文:下挂补充说明信息",
              "dimension": "供给完整性",
              "description": "第二张商品卡下挂区第二行文本像素扫描确认为空白，元素未正常加载",
              "rating": "不达标",
              "priority": "中",
              "priorityReason": "下挂区第二行是辅助信息，空白渲染不影响核心购买决策，但供给不完整影响信息完整度",
              "applicabilityEvidence": "下挂区第二行文本字段在第二张商品卡中已被标注为有效元素，坐标区域内字段本应携带补充说明内容",
              "visibleAbsenceEvidence": "像素扫描inkRatio为零，该坐标区域（18,1868,1188,28）内全部像素均为白色背景色，无任何文字墨迹，确认文本字段未渲染任何内容",
              "finding": {
                "observableFact": "下挂区第二行文本 inkRatio 为零，坐标区域（18,1868,1188,28）像素扫描全白，文字未渲染",
                "ruleOrThreshold": "元素 inkRatio 为零判定为空白渲染失败，供给缺失评级不达标",
                "verdictReason": "下挂区第二行文本空白，供给元素缺失，评级不达标",
                "userImpact": "用户无法获取第二张商品卡下挂区的补充说明信息，信息完整度受损"
              },
              "recommendation": "排查第二张商品卡下挂区第二行数据供给链路，确保补充说明信息正常渲染",
              "evidenceImage": "screenshots-out/evidence/evidence_eval-1-supply-completeness_C2-text-append-2_安睡裤_全部.png"
            }
          ]
        }
      }
    ]
  },
  {
    "skill": "eval-1-supply-module-completeness",
    "dimension": "phase3-page_framework-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "优秀",
        "reason": "六个模块（搜索框导航、频道标签栏、图筛、排序筛选条、营销横幅、结果列表）全部完整加载，核心模块无缺失，评级为优秀",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "original-page",
          "criterion": "核查页面框架必要模块是否完整加载，任一核心模块缺失为不达标，仅辅助模块缺失为达标",
          "summary": "页面含六个模块：搜索框返回导航、频道切换标签栏（全部/外卖/团购）、图筛（品类筛选）、排序筛选条、营销横幅（优惠信息）、商品搜索结果列表。核心模块均完整可见，辅助模块均正常渲染",
          "overview": {"total": 1, "excellent": 1, "pass": 0, "fail": 0, "failRate": "0%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png",
            "assessmentRows": [
              {
                "modules": [
                  {"id":"M1","moduleType":"搜索框返回导航","expected":True,"present":True},
                  {"id":"M2","moduleType":"频道切换标签栏","expected":True,"present":True},
                  {"id":"M3","moduleType":"图筛","expected":True,"present":True},
                  {"id":"M4","moduleType":"排序筛选条","expected":True,"present":True},
                  {"id":"M5","moduleType":"营销横幅","expected":True,"present":True},
                  {"id":"M6","moduleType":"商品搜索结果列表","expected":True,"present":True}
                ],
                "expectedModules": ["搜索框返回导航","频道切换标签栏","图筛","排序筛选条","营销横幅","商品搜索结果列表"],
                "layoutChecks": [
                  {"module":"搜索框返回导航","status":"complete"},
                  {"module":"频道切换标签栏","status":"complete"},
                  {"module":"图筛","status":"complete"},
                  {"module":"商品搜索结果列表","status":"complete"}
                ],
                "rating": "优秀"
              }
            ]
          },
          "issues": []
        }
      }
    ]
  },
  {
    "skill": "eval-1-supply-quality-scanner",
    "dimension": "phase3-single_element-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "不达标",
        "reason": "二十三个独立元素中下挂区第二行文本为空白渲染，存在供给质量问题，评级为不达标",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "original-page",
          "criterion": "图片五维度（合规/完整/画质/比例/相关）+ 文字四维度（完整/准确/用户视角/相关），任一维度不达标即不达标",
          "summary": "页面含三张商品卡共二十三个独立元素。三张头图均为安睡裤商品实物图，像素扫描 inkRatio 分别为0.84/0.95/0.40，均非空白。二十二个元素供给质量正常。第二张商品卡下挂区第二行文本 inkRatio 为零，完全空白，文字完整性检查失败",
          "overview": {"total": 23, "excellent": 22, "pass": 0, "fail": 1, "failRate": "4.3%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png"
          },
          "issues": [
            {
              "elementId": "C2-text-append-2",
              "coord": [18, 1868, 1188, 28],
              "component": "C2",
              "elementType": "文本",
              "content": "原文:下挂补充说明信息",
              "dimension": "供给质量",
              "description": "第二张商品卡下挂区第二行文本像素扫描 inkRatio 为零，坐标区域内无任何文字墨迹，文字元素完整性检查失败",
              "rating": "不达标",
              "priority": "中",
              "priorityReason": "下挂区辅助信息空白，影响信息完整度但不影响核心购买决策",
              "applicabilityEvidence": "下挂区第二行文本字段在该商品卡中已被标注为有效元素，字段本应携带补充说明内容",
              "visibleAbsenceEvidence": "像素扫描 inkRatio 为零，坐标区域（18,1868,1188,28）内全部像素均为白色，无文字墨迹",
              "finding": {
                "observableFact": "下挂区第二行文本 inkRatio 为零，坐标区域（18,1868,1188,28）全白无文字",
                "ruleOrThreshold": "文字元素 inkRatio 为零判定为完整性失败，评级不达标",
                "verdictReason": "文字元素完全空白，不满足供给质量要求，评级不达标",
                "userImpact": "用户无法读取第二张商品卡下挂区第二行辅助信息"
              },
              "recommendation": "排查第二张商品卡下挂区第二行文本的数据供给和渲染链路，确保文字正常渲染",
              "evidenceImage": "screenshots-out/evidence/evidence_eval-1-supply-quality-scanner_C2-text-append-2_安睡裤_全部.png"
            }
          ]
        }
      }
    ]
  },
  {
    "skill": "eval-2-color-logic-single-element",
    "dimension": "phase3-single_element-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "优秀",
        "reason": "排除三张商品头图后二十个纳入评估元素，单元素颜色数均不超过两种，评级为优秀",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "annotated-region",
          "criterion": "单一元素内总颜色数（36色标准，含无彩色）：不超过2优秀、等于3达标、大于3不达标。排除项：商家头图、营销图片、金刚图标、通栏白底；元素内面积占比小于1%的颜色不计",
          "summary": "纳入评估的元素共二十个（排除三张商品主图）。所有文本元素单元素内颜色均不超过两种：标题为深色系单色，基础信息为中性灰单色，第一张卡标签区为有彩色底加白色文字（两色），价格为有彩色加白底（两色），商家为有彩色单色，下挂文字为中性色单色。空白元素计零色。无超过两色的元素",
          "overview": {"total": 23, "excellent": 23, "pass": 0, "fail": 0, "failRate": "0%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png"
          },
          "issues": []
        }
      }
    ]
  },
  {
    "skill": "eval-2-visual-order-alignment",
    "dimension": "phase3-page_framework-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "优秀",
        "reason": "三张商品卡同为闪购左图右文布局，视觉结构一致，无新旧卡混排或大小头图混排，评级为优秀",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "original-page",
          "criterion": "分析页面布局对齐情况和同类卡片视觉结构一致性，识别新旧卡混排、大小头图混排等对齐错乱问题",
          "summary": "页面布局从上至下：搜索框导航、频道标签栏、图筛、排序筛选条、营销横幅、结果列表。结果列表含三张卡片，均为闪购业态左图右文布局，头图尺寸一致（332×332像素），文字区对齐一致。未发现新旧卡混排或大小头图混排",
          "overview": {"total": 1, "excellent": 1, "pass": 0, "fail": 0, "failRate": "0%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png",
            "assessmentRows": [
              {
                "pageRegions": ["搜索框导航","频道标签栏","图筛","排序筛选条","营销横幅","结果列表"],
                "sameTypeComparisons": [
                  {"cardType":"闪购左图右文商品卡","cards":["C1","C2","C3"],"consistent":True}
                ],
                "rating": "优秀"
              }
            ]
          },
          "issues": []
        }
      }
    ]
  },
  {
    "skill": "eval-3-color-logic",
    "dimension": "phase3-card_or_component-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "达标",
        "reason": "三张商品卡色系数均为4（红色/黄色/橙色/品红色），均达到达标线，取最差值为达标",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "annotated-region",
          "criterion": "逐组件统计有彩色系数量（36色标准），排除照片/营销素材/金刚图标等非界面色彩干扰，不超过3优秀、4至5达标、大于5不达标",
          "summary": "三张商品卡排除商品主图后有效界面色彩：第一张色系4个（红色54.4%/黄色30.5%/橙色12.0%/品红色3.1%），第二张色系4个（红色64.3%/黄色23.9%/橙色9.4%/品红色2.4%），第三张色系4个（红色50.5%/橙色24.4%/黄色22.7%/品红色2.3%）。三卡色系数均为4，达到达标线",
          "overview": {"total": 3, "excellent": 0, "pass": 3, "fail": 0, "failRate": "0%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png",
            "evaluatedUnitCount": 3,
            "assessmentRows": [
              {
                "componentId": "C1",
                "validUiPixelCount": 39550,
                "excludedPhotoPixelCount": 110224,
                "colorFamilies": [
                  {"family":"红","pixelCount":5890,"ratio":0.5441},
                  {"family":"黄","pixelCount":3298,"ratio":0.3047},
                  {"family":"橙","pixelCount":1295,"ratio":0.1196},
                  {"family":"品红","pixelCount":336,"ratio":0.031}
                ],
                "colorFamilyCount": 4,
                "debugImage": ".artifacts/过程文件-指标测量/debug_C1_安睡裤.png",
                "rating": "达标",
                "measurement": {
                  "tool": "scripts/extract_component_metrics.py",
                  "artifactPath": ".artifacts/过程文件-指标测量/metrics_安睡裤_eval-3-color-logic.json",
                  "parameters": {
                    "manifest": "screenshots-out/elements_安睡裤.json",
                    "screenshot": "screenshots/安睡裤_全部_1.png"
                  }
                }
              },
              {
                "componentId": "C2",
                "validUiPixelCount": 42818,
                "excludedPhotoPixelCount": 110224,
                "colorFamilies": [
                  {"family":"红","pixelCount":8880,"ratio":0.6427},
                  {"family":"黄","pixelCount":3298,"ratio":0.2387},
                  {"family":"橙","pixelCount":1296,"ratio":0.0938},
                  {"family":"品红","pixelCount":336,"ratio":0.0243}
                ],
                "colorFamilyCount": 4,
                "debugImage": ".artifacts/过程文件-指标测量/debug_C2_安睡裤.png",
                "rating": "达标",
                "measurement": {
                  "tool": "scripts/extract_component_metrics.py",
                  "artifactPath": ".artifacts/过程文件-指标测量/metrics_安睡裤_eval-3-color-logic.json",
                  "parameters": {
                    "manifest": "screenshots-out/elements_安睡裤.json",
                    "screenshot": "screenshots/安睡裤_全部_1.png"
                  }
                }
              },
              {
                "componentId": "C3",
                "validUiPixelCount": 42222,
                "excludedPhotoPixelCount": 110224,
                "colorFamilies": [
                  {"family":"红","pixelCount":7320,"ratio":0.5047},
                  {"family":"橙","pixelCount":3543,"ratio":0.2443},
                  {"family":"黄","pixelCount":3298,"ratio":0.2274},
                  {"family":"品红","pixelCount":336,"ratio":0.0232}
                ],
                "colorFamilyCount": 4,
                "debugImage": ".artifacts/过程文件-指标测量/debug_C3_安睡裤.png",
                "rating": "达标",
                "measurement": {
                  "tool": "scripts/extract_component_metrics.py",
                  "artifactPath": ".artifacts/过程文件-指标测量/metrics_安睡裤_eval-3-color-logic.json",
                  "parameters": {
                    "manifest": "screenshots-out/elements_安睡裤.json",
                    "screenshot": "screenshots/安睡裤_全部_1.png"
                  }
                }
              }
            ]
          },
          "issues": [
            {
              "elementId": "C1-price",
              "coord": [380, 1202, 810, 66],
              "component": "C1",
              "elementType": "文本",
              "content": "原文:商品价格",
              "dimension": "色彩逻辑",
              "description": "第一张商品卡色系数为4，达到达标线。有效界面像素含红色5890像素（54%）、黄色3298像素（30%）、橙色1295像素（12%）、品红色336像素（3%），共4色系",
              "rating": "达标",
              "priority": "低",
              "priorityReason": "色系4个均为功能性色彩，对核心信息扫读影响较小",
              "finding": {
                "observableFact": "第一张商品卡排除主图后有效界面像素含4个色系：红色5890、黄色3298、橙色1295、品红色336",
                "ruleOrThreshold": "色系数不超过3优秀、4至5达标、大于5不达标，此卡色系数为4",
                "verdictReason": "色系数4达到达标线，由价格区红色、图筛高亮标签黄色、促销标签橙色底色贡献",
                "userImpact": "多色系对页面视觉统一性有一定影响，但均为功能性色彩"
              },
              "recommendation": "第一张商品卡可统一图筛标签和促销区的色彩语义，将4个色系整合为3个以内，消除多余的黄色和品红色",
              "evidenceImage": "screenshots-out/evidence/evidence_eval-3-color-logic_C1-price_安睡裤_全部.png"
            },
            {
              "elementId": "C2-price",
              "coord": [380, 1693, 810, 72],
              "component": "C2",
              "elementType": "文本",
              "content": "原文:商品价格",
              "dimension": "色彩逻辑",
              "description": "第二张商品卡色系数为4，达到达标线。有效界面像素含红色8880像素（64%）、黄色3298像素（24%）、橙色1296像素（9%）、品红色336像素（2%），共4色系",
              "rating": "达标",
              "priority": "低",
              "priorityReason": "色系4个均为功能性色彩，对核心信息扫读影响较小",
              "finding": {
                "observableFact": "第二张商品卡排除主图后有效界面像素含4个色系：红色8880、黄色3298、橙色1296、品红色336",
                "ruleOrThreshold": "色系数不超过3优秀、4至5达标、大于5不达标，此卡色系数为4",
                "verdictReason": "色系数4达到达标线，由价格区红色、图筛黄色、橙色促销贡献",
                "userImpact": "多色系对页面视觉统一性有一定影响，但均为功能性色彩"
              },
              "recommendation": "第二张商品卡可将4个色系中的黄色图筛标签背景与橙色促销标签统一为同一色系，将色系数降至3个以内",
              "evidenceImage": "screenshots-out/evidence/evidence_eval-3-color-logic_C2-price_安睡裤_全部.png"
            },
            {
              "elementId": "C3-price",
              "coord": [380, 2256, 810, 72],
              "component": "C3",
              "elementType": "文本",
              "content": "原文:商品价格",
              "dimension": "色彩逻辑",
              "description": "第三张商品卡色系数为4，达到达标线。有效界面像素含红色7320像素（50%）、橙色3543像素（24%）、黄色3298像素（23%）、品红色336像素（2%），共4色系",
              "rating": "达标",
              "priority": "低",
              "priorityReason": "色系4个均为功能性色彩，对核心信息扫读影响较小",
              "finding": {
                "observableFact": "第三张商品卡排除主图后有效界面像素含4个色系：红色7320、橙色3543、黄色3298、品红色336",
                "ruleOrThreshold": "色系数不超过3优秀、4至5达标、大于5不达标，此卡色系数为4",
                "verdictReason": "色系数4达到达标线，由价格区橙红色、图筛黄色标签背景贡献",
                "userImpact": "多色系对页面视觉统一性有一定影响，但均为功能性色彩"
              },
              "recommendation": "第三张商品卡可将4个色系中的品红色标签细节色合并至橙色系，将价格区和促销区统一为最多3个色系",
              "evidenceImage": "screenshots-out/evidence/evidence_eval-3-color-logic_C3-price_安睡裤_全部.png"
            }
          ]
        }
      }
    ]
  },
  {
    "skill": "eval-3-element-compliance-scanner",
    "dimension": "phase3-single_element-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "优秀",
        "reason": "二十个待评元素（排除三张商品头图）所有维度均符合商品卡片规范，评级为优秀",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "annotated-region",
          "criterion": "逐元素比对商家卡片分区规范：位置/分区、最大条数、层级优先级、字号字重、字体、颜色语义、标签底色/圆角/描边/阴影、收敛规则。任一维度不符即不达标。排除项：商品头图三张",
          "summary": "纳入评估的元素共二十个（排除三张商品主图）。所有文本元素均位于各自卡片的正确分区：标题区大号加粗文字、基础信息区小号中性色、标签区有彩色底标签（第一张卡）或中性标签（第二第三张卡）、价格区有彩色强调文字、商家区中号有彩色文字、下挂区小号文字。颜色语义均符合闪购商品卡规范。空白元素不影响合规性评估",
          "overview": {"total": 23, "excellent": 23, "pass": 0, "fail": 0, "failRate": "0%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png"
          },
          "issues": []
        }
      }
    ]
  },
  {
    "skill": "eval-3-page-color-logic",
    "dimension": "phase3-page_framework-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "达标",
        "reason": "整页排除商品主图后有效界面色彩共4个色系（红色/黄色/橙色/品红色），达到达标线，评级为达标",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "original-page",
          "criterion": "整页统计总颜色数量（36色标准，占比大于等于1%计入）与主导色数量（7色标准，占比大于5%计入），排除商家图片/营销类元素/金刚图标/图筛分类配图。不超过3色系优秀、4至5达标、大于5不达标",
          "summary": "整页排除三张商品主图后有效界面色彩合并统计：红色（价格文字加商家评分）、黄色（图筛高亮标签背景）、橙色（促销标签背景及促销文字）、品红色（标签细节）。总色系数为4，达到达标线",
          "overview": {"total": 1, "excellent": 0, "pass": 1, "fail": 0, "failRate": "0%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png",
            "assessmentRows": [
              {
                "validUiPixelCount": 124590,
                "excludedPhotoPixelCount": 330672,
                "colorFamilies": [
                  {"family":"红","pixelCount":22090,"ratio":0.5657},
                  {"family":"黄","pixelCount":9894,"ratio":0.2534},
                  {"family":"橙","pixelCount":6134,"ratio":0.1571},
                  {"family":"品红","pixelCount":1008,"ratio":0.0258}
                ],
                "colorFamilyCount": 4,
                "debugImage": ".artifacts/过程文件-指标测量/debug_page_安睡裤.png",
                "rating": "达标",
                "measurement": {
                  "tool": "scripts/extract_component_metrics.py",
                  "artifactPath": ".artifacts/过程文件-指标测量/metrics_安睡裤_eval-3-color-logic.json",
                  "parameters": {
                    "manifest": "screenshots-out/elements_安睡裤.json",
                    "screenshot": "screenshots/安睡裤_全部_1.png"
                  }
                }
              }
            ]
          },
          "issues": [
            {
              "pageArea": "结果列表三张商品卡区域",
              "dimension": "phase3-page_framework-eval",
              "description": "整页排除商品主图后有效界面色彩共4个色系（红色/黄色/橙色/品红色），多色集中在价格区、图筛标签和促销标签区域，达到达标线",
              "rating": "达标",
              "priority": "低",
              "priorityReason": "整页4个色系达标，均为功能性色彩使用，对页面整体视觉统一性影响可接受",
              "finding": {
                "observableFact": "整页有效界面含4个色系：红色22090像素（56.6%）、黄色9894像素（25.3%）、橙色6134像素（15.7%）、品红色1008像素（2.6%）",
                "ruleOrThreshold": "色系数不超过3优秀、4至5达标、大于5不达标，整页色系数为4",
                "verdictReason": "整页色系数4达到达标线，多色来源于价格红色、图筛黄色标签背景、促销橙色标签",
                "userImpact": "页面整体色彩在可接受范围内，功能性色彩分工清晰"
              },
              "recommendation": "可统一图筛标签背景色，减少黄色系使用，将整页色系降至3以下达到优秀"
            }
          ]
        }
      }
    ]
  },
  {
    "skill": "eval-4-element-complexity",
    "dimension": "phase3-card_or_component-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "达标",
        "reason": "第一张商品卡图标样式「2」种（达标），第二第三张商品卡图标样式0种且标签样式0种（优秀），取最差值为达标",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "annotated-region",
          "criterion": "逐组件统计图筛与商卡内的异形/异色标签样式和图标样式数量，标签样式不超过2且图标样式不超过1优秀，标签3至4或图标2至3达标，标签大于4或图标大于3不达标",
          "summary": "第一张商品卡：标签样式「1」种（橙色背景矩形优惠标），图标样式「2」种（大号红色描边图标和小号红色描边图标），图标样式数2种在达标范围。第二张商品卡：标签样式「0」种（优惠标为中性色纯文字排除），图标样式「0」种，优秀。第三张商品卡：标签样式「0」种，图标样式「0」种，优秀",
          "overview": {"total": 3, "excellent": 2, "pass": 1, "fail": 0, "failRate": "0%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png",
            "evaluatedUnitCount": 3,
            "assessmentRows": [
              {
                "componentId": "C1",
                "scannedRegions": ["头图区","标题区","基础信息区","标签区","价格区","商家区","下挂区"],
                "includedTagStyles": [
                  {
                    "elementId": "C1-tag-prom",
                    "content": "原文:优惠标签",
                    "styleKey": "tag|orange|优惠标|rect|无",
                    "countDecision": "橙色底色优惠标签，计入复杂度",
                    "dedupDecision": "独立标签，不去重"
                  }
                ],
                "includedIconStyles": [
                  {
                    "elementId": "C1-icon-large",
                    "content": "标签区大号红色描边图标（32×30像素）",
                    "styleKey": "icon|red|功能图标|outline|无",
                    "countDecision": "红色描边功能图标，计入复杂度",
                    "dedupDecision": "与小图标尺寸不同，独立计数"
                  },
                  {
                    "elementId": "C1-icon-small",
                    "content": "标签区小号红色描边图标（21×14像素）",
                    "styleKey": "icon|red|功能图标|outline|无",
                    "countDecision": "红色描边功能图标，计入复杂度",
                    "dedupDecision": "与大图标尺寸不同，独立计数"
                  }
                ],
                "excludedEntities": [{"elementId":"C1-img-head","reason":"商品主图非评测对象"}],
                "tagStyleCount": 1,
                "iconStyleCount": 2,
                "rating": "达标",
                "measurement": {
                  "tool": "scripts/extract_component_metrics.py",
                  "artifactPath": ".artifacts/过程文件-指标测量/metrics_安睡裤_eval-3-color-logic.json",
                  "parameters": {
                    "manifest": "screenshots-out/elements_安睡裤.json",
                    "screenshot": "screenshots/安睡裤_全部_1.png"
                  }
                }
              },
              {
                "componentId": "C2",
                "scannedRegions": ["头图区","标题区","基础信息区","标签区","价格区","商家区","下挂区"],
                "includedTagStyles": [],
                "includedIconStyles": [],
                "excludedEntities": [
                  {"elementId":"C2-img-head","reason":"商品主图非评测对象"},
                  {"elementId":"C2-tag-prom","reason":"中性色纯文字标签，无彩色底描边，排除"}
                ],
                "tagStyleCount": 0,
                "iconStyleCount": 0,
                "rating": "优秀",
                "measurement": {
                  "tool": "scripts/extract_component_metrics.py",
                  "artifactPath": ".artifacts/过程文件-指标测量/metrics_安睡裤_eval-3-color-logic.json",
                  "parameters": {
                    "manifest": "screenshots-out/elements_安睡裤.json",
                    "screenshot": "screenshots/安睡裤_全部_1.png"
                  }
                }
              },
              {
                "componentId": "C3",
                "scannedRegions": ["头图区","标题区","基础信息区","标签区","价格区","商家区","下挂区"],
                "includedTagStyles": [],
                "includedIconStyles": [],
                "excludedEntities": [
                  {"elementId":"C3-img-head","reason":"商品主图非评测对象"},
                  {"elementId":"C3-tag-prom","reason":"中性色纯文字标签，无彩色底描边，排除"}
                ],
                "tagStyleCount": 0,
                "iconStyleCount": 0,
                "rating": "优秀",
                "measurement": {
                  "tool": "scripts/extract_component_metrics.py",
                  "artifactPath": ".artifacts/过程文件-指标测量/metrics_安睡裤_eval-3-color-logic.json",
                  "parameters": {
                    "manifest": "screenshots-out/elements_安睡裤.json",
                    "screenshot": "screenshots/安睡裤_全部_1.png"
                  }
                }
              }
            ]
          },
          "issues": [
            {
              "elementId": "C1-tag-prom",
              "coord": [380, 1129, 200, 30],
              "component": "C1",
              "elementType": "标签",
              "content": "原文:优惠标签",
              "dimension": "元素复杂度",
              "description": "第一张商品卡标签区存在「2」种图标样式（大号红色描边图标和小号红色描边图标），图标样式数「2」种达到达标范围",
              "rating": "达标",
              "priority": "低",
              "priorityReason": "图标样式「2」种在达标范围，两种尺寸略有差异的同色系图标，对视觉复杂度影响较小",
              "finding": {
                "observableFact": "第一张商品卡标签区检测到「2」种图标样式：大号红色描边图标（32×30像素）和小号红色描边图标（21×14像素），标签样式「1」种（橙色背景矩形优惠标）",
                "ruleOrThreshold": "图标样式不超过1种优秀、2至3种达标、大于3种不达标，此卡图标样式数为「2」种",
                "verdictReason": "图标「2」种样式达到达标线，评级达标",
                "userImpact": "两种略有差异的图标样式对视觉统一性有轻微影响"
              },
              "recommendation": "可统一标签区图标为单一尺寸规格，将图标样式数降至1种以下达到优秀",
              "evidenceImage": "screenshots-out/evidence/evidence_eval-4-element-complexity_C1-tag-prom_安睡裤_全部.png"
            }
          ]
        }
      }
    ]
  },
  {
    "skill": "eval-4-info-authenticity-single-element",
    "dimension": "phase3-single_element-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "优秀",
        "reason": "二十个待评元素（排除三张商品头图）信息语义均真实无歧义，评级为优秀",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "annotated-region",
          "criterion": "逐元素判断信息是否存在歧义（文案多重含义/图标语义不明/折扣表述模糊）或虚假/误导（标题诱导/价格误导/促销可疑/条件不透明）。排除项：商品头图三张",
          "summary": "纳入评估的元素共二十个（排除三张商品主图）。所有标题为安睡裤商品名称，无诱导性话术。基础信息区评分销量配送时效表意清晰。标签区优惠标签语义明确。价格区有彩色强调文字为商品价格，表意直接。商家区为商家名称及评分，无歧义。下挂区促销文字为常规营销表述。空白元素无内容可评",
          "overview": {"total": 23, "excellent": 23, "pass": 0, "fail": 0, "failRate": "0%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png"
          },
          "issues": []
        }
      }
    ]
  },
  {
    "skill": "eval-4-static-component-complexity",
    "dimension": "phase3-page_framework-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "达标",
        "reason": "首屏功能区数量为4（频道标签栏/图筛/排序筛选条/营销横幅），在4至5达标范围，评级为达标",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "original-page",
          "criterion": "识别首屏中除顶部搜索框外的独立功能区个数，不超过3优秀、4至5达标、大于5不达标",
          "summary": "首屏除搜索框外含4个独立功能区：频道切换标签栏、图筛品类筛选区、排序筛选条、营销横幅。功能区数量4，在达标范围，结果列表有效起始位置后移",
          "overview": {"total": 1, "excellent": 0, "pass": 1, "fail": 0, "failRate": "0%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png",
            "assessmentRows": [
              {
                "firstScreenBounds": [0,0,1224,1200],
                "functionalModules": ["频道切换标签栏","图筛品类筛选","排序筛选条","营销横幅"],
                "moduleCount": 4,
                "rating": "达标"
              }
            ]
          },
          "issues": [
            {
              "pageArea": "首屏功能区",
              "dimension": "phase3-page_framework-eval",
              "description": "首屏含4个独立功能区（频道标签栏/图筛/排序筛选条/营销横幅），在达标范围，使结果列表有效起始位置后移，用户首屏可见商品卡数量减少",
              "rating": "达标",
              "priority": "中",
              "priorityReason": "4个功能区使结果列表起始位置延后，用户首屏可见商品卡数量减少",
              "finding": {
                "observableFact": "首屏功能区共4个：频道标签栏、图筛品类筛选、排序筛选条、营销横幅，结果列表起始纵向坐标约952",
                "ruleOrThreshold": "不超过3个优秀、4至5个达标、大于5个不达标，当前为4个",
                "verdictReason": "4个功能区达到达标线",
                "userImpact": "首屏结果内容较少，用户需要更多滚动才能看到更多商品结果"
              },
              "recommendation": "可考虑将营销横幅整合至图筛区域内，减少首屏功能区数量至3个以内达到优秀"
            }
          ]
        }
      }
    ]
  },
  {
    "skill": "eval-5-browsing-flow-smoothness",
    "dimension": "phase3-page_framework-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "优秀",
        "reason": "结果列表三张卡片全为同构形态（闪购左图右文商品卡），异构形态数量为0，评级为优秀",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "original-page",
          "criterion": "统计结果列表前10个有效列表位中的异构形态数量，0个优秀、1至2个达标、大于等于3个不达标",
          "summary": "结果列表可见三个列表位，均为闪购业态左图右文商品卡，同构形态，无打断纵向浏览动线的异构卡片",
          "overview": {"total": 1, "excellent": 1, "pass": 0, "fail": 0, "failRate": "0%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png",
            "assessmentRows": [
              {
                "listPositions": [
                  {"position":1,"cardId":"C1","heterogeneous":False},
                  {"position":2,"cardId":"C2","heterogeneous":False},
                  {"position":3,"cardId":"C3","heterogeneous":False}
                ],
                "visibleListPositionCount": 3,
                "coverageStatus": "完整",
                "heterogeneousCount": 0,
                "rating": "优秀"
              }
            ]
          },
          "issues": []
        }
      }
    ]
  },
  {
    "skill": "eval-5-info-hierarchy",
    "dimension": "phase3-card_or_component-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "优秀",
        "reason": "三张商品卡视觉层级数均为5档，全部达到优秀标准",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "annotated-region",
          "criterion": "逐组件识别可区分的视觉权重档位数（视觉层级数），3至5档优秀，小于3或大于5不达标",
          "summary": "三张商品卡均为左图右文加七区域布局。视觉权重档位分析：第一档商品主图（大面积332×332像素）、第二档标题（大号加粗有彩色）、第三档价格（中号有彩色强调）、第四档商家（中号有彩色次级）、第五档基础信息加标签加下挂（小号或非彩色），共5档，全部优秀",
          "overview": {"total": 3, "excellent": 3, "pass": 0, "fail": 0, "failRate": "0%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png",
            "evaluatedUnitCount": 3,
            "assessmentRows": [
              {
                "componentId": "C1",
                "sourceElements": ["C1-img-head","C1-title","C1-price","C1-merchant","C1-meta-info","C1-tag-prom","C1-text-append"],
                "weightSequence": ["商品主图（大面积图片）","标题（大号加粗有彩色）","价格（中号有彩色强调）","商家（中号有彩色次级）","基础信息加标签加下挂（小号或非彩色）"],
                "tierTrace": [
                  {"tier":1,"members":["C1-img-head"],"basis":"大面积图片332×332像素，视觉权重最高"},
                  {"tier":2,"members":["C1-title"],"basis":"标题字高47像素加粗有彩色，均值颜色约97/92/59"},
                  {"tier":3,"members":["C1-price"],"basis":"价格字高37像素有彩色强调，均值颜色约233/87/99"},
                  {"tier":4,"members":["C1-merchant"],"basis":"商家区字高37像素有彩色次级，均值颜色约150/124/110"},
                  {"tier":5,"members":["C1-meta-info","C1-tag-prom","C1-text-append"],"basis":"基础信息非彩色小号、标签小号、下挂非彩色，同档归并"}
                ],
                "levelCount": 5,
                "rating": "优秀"
              },
              {
                "componentId": "C2",
                "sourceElements": ["C2-img-head","C2-title","C2-price","C2-merchant","C2-meta-info","C2-tag-prom","C2-text-append-1","C2-text-append-2"],
                "weightSequence": ["商品主图（大面积图片）","标题（大号加粗有彩色）","价格（大号有彩色强调）","商家（中号有彩色次级）","基础信息加标签加下挂（小号或非彩色）"],
                "tierTrace": [
                  {"tier":1,"members":["C2-img-head"],"basis":"大面积图片332×332像素"},
                  {"tier":2,"members":["C2-title"],"basis":"标题字高47像素有彩色"},
                  {"tier":3,"members":["C2-price"],"basis":"价格字高48像素有彩色强调，均值颜色约216/111/100"},
                  {"tier":4,"members":["C2-merchant"],"basis":"商家区字高36像素有彩色，均值颜色约222/86/108"},
                  {"tier":5,"members":["C2-meta-info","C2-tag-prom","C2-text-append-1","C2-text-append-2"],"basis":"非彩色小号同档，含空白元素"}
                ],
                "levelCount": 5,
                "rating": "优秀"
              },
              {
                "componentId": "C3",
                "sourceElements": ["C3-img-head","C3-title","C3-price","C3-merchant","C3-meta-info","C3-tag-prom","C3-text-append-1","C3-text-append-2"],
                "weightSequence": ["商品主图（大面积图片）","标题（大号加粗有彩色）","价格（大号有彩色橙红）","商家（中号有彩色次级）","基础信息加标签加下挂（小号或非彩色）"],
                "tierTrace": [
                  {"tier":1,"members":["C3-img-head"],"basis":"大面积图片332×332像素"},
                  {"tier":2,"members":["C3-title"],"basis":"标题字高47像素有彩色"},
                  {"tier":3,"members":["C3-price"],"basis":"价格字高49像素有彩色橙红，均值颜色约239/112/72"},
                  {"tier":4,"members":["C3-merchant"],"basis":"商家区字高36像素有彩色，均值颜色约225/85/108"},
                  {"tier":5,"members":["C3-meta-info","C3-tag-prom","C3-text-append-1","C3-text-append-2"],"basis":"非彩色小号同档"}
                ],
                "levelCount": 5,
                "rating": "优秀"
              }
            ]
          },
          "issues": []
        }
      }
    ]
  },
  {
    "skill": "eval-6-info-comparability",
    "dimension": "phase3-page_framework-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "不达标",
        "reason": "同类型商品卡标签区样式不一致（第一张卡橙色底矩形标签，第二第三张卡中性色文字标签），不一致数为1，评级为不达标",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "original-page",
          "criterion": "对比同类型卡片间的同一客观信息字段（标题、评分、距离、人均等）是否在展示位置、格式、语义上一致，不一致数大于等于1不达标",
          "summary": "三张卡片同为闪购左图右文商品卡，标题区/基础信息区/价格区/商家区/下挂区格式一致。但标签区不一致：第一张卡使用橙色底色矩形样式的优惠标签，第二第三张卡的优惠标签为中性色纯文字样式。同类型商品卡同字段视觉表现格式不一致，不一致数为1",
          "overview": {"total": 1, "excellent": 0, "pass": 0, "fail": 1, "failRate": "100%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png",
            "assessmentRows": [
              {
                "cardGroups": [
                  {"groupKey":"闪购左图右文商品卡","cards":["C1","C2","C3"]}
                ],
                "comparableFields": ["标题","基础信息","标签","价格","商家","下挂"],
                "comparisons": [
                  {"group":"闪购左图右文商品卡","field":"标题","cards":["C1","C2","C3"],"consistent":True},
                  {"group":"闪购左图右文商品卡","field":"基础信息","cards":["C1","C2","C3"],"consistent":True},
                  {"group":"闪购左图右文商品卡","field":"标签","cards":["C1","C2","C3"],"consistent":False,"inconsistencyDetail":"第一张卡标签为橙色底矩形样式，第二第三张卡标签为中性色文字样式"},
                  {"group":"闪购左图右文商品卡","field":"价格","cards":["C1","C2","C3"],"consistent":True},
                  {"group":"闪购左图右文商品卡","field":"商家","cards":["C1","C2","C3"],"consistent":True},
                  {"group":"闪购左图右文商品卡","field":"下挂","cards":["C1","C2","C3"],"consistent":True}
                ],
                "inconsistencyCount": 1,
                "rating": "不达标"
              }
            ]
          },
          "issues": [
            {
              "pageArea": "结果列表标签区",
              "dimension": "phase3-page_framework-eval",
              "description": "同类型商品卡（闪购左图右文）中，第一张卡优惠标签使用橙色底矩形样式，第二第三张卡优惠标签使用中性色纯文字样式，同字段不同视觉表现，影响用户跨卡比较",
              "rating": "不达标",
              "priority": "中",
              "priorityReason": "同类卡片标签样式不一致，影响用户视觉扫读和跨卡比较的一致性体验",
              "finding": {
                "observableFact": "第一张卡标签区：橙色背景矩形容器优惠标签；第二第三张卡标签区：中性色纯文字无底色标签",
                "ruleOrThreshold": "同类型卡片同字段表现格式不一致数大于等于1不达标",
                "verdictReason": "标签区视觉样式不一致，不一致数为1，评级不达标",
                "userImpact": "用户在同类型商品卡间比较优惠信息时，视觉权重不一致导致扫读效率下降"
              },
              "recommendation": "统一同类型商品卡标签区的视觉样式，建议全部使用橙色底矩形标签或全部使用中性色文字标签"
            }
          ]
        }
      }
    ]
  },
  {
    "skill": "eval-6-info-partitioning",
    "dimension": "phase3-card_or_component-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "不达标",
        "reason": "第一张商品卡分区边界全部清晰（优秀），第二张有2处边界不清晰（不达标），第三张有4处边界不清晰（不达标），取最差值为不达标",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "annotated-region",
          "criterion": "逐组件判断信息/功能分区边界是否清晰（物理边界/空间边界/视觉边界），问题数为0优秀，问题数大于等于1不达标",
          "summary": "第一张商品卡：六个区域边界均清晰（最小间距22像素），全部清晰，优秀。第二张商品卡：基础信息区与标签区间距仅1像素（不清晰），价格区与商家区间距仅1像素（不清晰），共2处不清晰，不达标。第三张商品卡：标题区与基础信息区、基础信息区与标签区、价格区与商家区、商家区与下挂区，共4处边界不清晰，不达标",
          "overview": {"total": 3, "excellent": 1, "pass": 0, "fail": 2, "failRate": "66.7%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png",
            "evaluatedUnitCount": 3,
            "assessmentRows": [
              {
                "componentId": "C1",
                "partitions": [
                  {"name":"头图区","coord":[32,952,332,332]},
                  {"name":"标题区","coord":[380,956,810,47]},
                  {"name":"基础信息区","coord":[380,1024,810,80]},
                  {"name":"标签区","coord":[380,1129,810,49]},
                  {"name":"价格区","coord":[380,1202,810,66]},
                  {"name":"商家区","coord":[380,1268,810,37]},
                  {"name":"下挂区","coord":[18,1333,1188,36]}
                ],
                "adjacentBoundaryChecks": [
                  {"pair":"头图区→标题区","gapPx":33,"physical":True,"spatial":True,"visual":True,"clear":True},
                  {"pair":"标题区→基础信息区","gapPx":22,"physical":True,"spatial":True,"visual":False,"clear":True},
                  {"pair":"基础信息区→标签区","gapPx":61,"physical":False,"spatial":True,"visual":False,"clear":True},
                  {"pair":"标签区→价格区","gapPx":44,"physical":True,"spatial":True,"visual":False,"clear":True},
                  {"pair":"价格区→商家区","gapPx":30,"physical":False,"spatial":True,"visual":False,"clear":True},
                  {"pair":"商家区→下挂区","gapPx":29,"physical":False,"spatial":True,"visual":False,"clear":True}
                ],
                "issueCount": 0,
                "rating": "优秀",
                "measurement": {
                  "tool": "scripts/extract_component_metrics.py",
                  "artifactPath": ".artifacts/过程文件-指标测量/metrics_安睡裤_eval-3-color-logic.json",
                  "parameters": {
                    "manifest": "screenshots-out/elements_安睡裤.json",
                    "screenshot": "screenshots/安睡裤_全部_1.png"
                  }
                }
              },
              {
                "componentId": "C2",
                "partitions": [
                  {"name":"头图区","coord":[32,1454,332,332]},
                  {"name":"标题区","coord":[380,1458,810,47]},
                  {"name":"基础信息区","coord":[380,1527,810,75]},
                  {"name":"标签区","coord":[380,1602,810,91]},
                  {"name":"价格区","coord":[380,1693,810,72]},
                  {"name":"商家区","coord":[380,1765,810,36]},
                  {"name":"下挂区","coord":[18,1831,1188,65]}
                ],
                "adjacentBoundaryChecks": [
                  {"pair":"头图区→标题区","gapPx":33,"physical":True,"spatial":True,"visual":True,"clear":True},
                  {"pair":"标题区→基础信息区","gapPx":23,"physical":False,"spatial":True,"visual":False,"clear":True},
                  {"pair":"基础信息区→标签区","gapPx":1,"physical":False,"spatial":False,"visual":False,"clear":False},
                  {"pair":"标签区→价格区","gapPx":62,"physical":False,"spatial":True,"visual":False,"clear":True},
                  {"pair":"价格区→商家区","gapPx":1,"physical":False,"spatial":False,"visual":False,"clear":False},
                  {"pair":"商家区→下挂区","gapPx":31,"physical":False,"spatial":True,"visual":False,"clear":True}
                ],
                "issueCount": 2,
                "rating": "不达标",
                "measurement": {
                  "tool": "scripts/extract_component_metrics.py",
                  "artifactPath": ".artifacts/过程文件-指标测量/metrics_安睡裤_eval-3-color-logic.json",
                  "parameters": {
                    "manifest": "screenshots-out/elements_安睡裤.json",
                    "screenshot": "screenshots/安睡裤_全部_1.png"
                  }
                }
              },
              {
                "componentId": "C3",
                "partitions": [
                  {"name":"头图区","coord":[32,2017,332,332]},
                  {"name":"标题区","coord":[380,2021,810,47]},
                  {"name":"基础信息区","coord":[380,2090,810,65]},
                  {"name":"标签区","coord":[380,2176,810,80]},
                  {"name":"价格区","coord":[380,2256,810,72]},
                  {"name":"商家区","coord":[380,2328,810,36]},
                  {"name":"下挂区","coord":[18,2394,1188,101]}
                ],
                "adjacentBoundaryChecks": [
                  {"pair":"头图区→标题区","gapPx":33,"physical":True,"spatial":False,"visual":True,"clear":True},
                  {"pair":"标题区→基础信息区","gapPx":23,"physical":False,"spatial":False,"visual":False,"clear":False},
                  {"pair":"基础信息区→标签区","gapPx":43,"physical":False,"spatial":False,"visual":False,"clear":False},
                  {"pair":"标签区→价格区","gapPx":60,"physical":False,"spatial":True,"visual":False,"clear":True},
                  {"pair":"价格区→商家区","gapPx":1,"physical":False,"spatial":False,"visual":False,"clear":False},
                  {"pair":"商家区→下挂区","gapPx":31,"physical":False,"spatial":False,"visual":False,"clear":False}
                ],
                "issueCount": 4,
                "rating": "不达标",
                "measurement": {
                  "tool": "scripts/extract_component_metrics.py",
                  "artifactPath": ".artifacts/过程文件-指标测量/metrics_安睡裤_eval-3-color-logic.json",
                  "parameters": {
                    "manifest": "screenshots-out/elements_安睡裤.json",
                    "screenshot": "screenshots/安睡裤_全部_1.png"
                  }
                }
              }
            ]
          },
          "issues": [
            {
              "elementId": "C2-meta-info",
              "coord": [380, 1527, 810, 75],
              "component": "C2",
              "elementType": "文本",
              "content": "原文:评分销量配送时效等信息",
              "dimension": "信息分区",
              "description": "第二张商品卡基础信息区与标签区间距仅1像素，无物理边界、无空间边界、无视觉边界，分区边界不清晰",
              "rating": "不达标",
              "priority": "中",
              "priorityReason": "分区不清晰影响用户区分基础信息与优惠标签的视觉层次",
              "finding": {
                "observableFact": "第二张商品卡基础信息区到标签区间距测量为1像素，三种边界（物理/空间/视觉）均不满足",
                "ruleOrThreshold": "相邻区域无任何类型边界（物理/空间/视觉）判定为不清晰，问题数大于等于1不达标",
                "verdictReason": "1像素间距无任何支撑边界，分区不清晰，评级不达标",
                "userImpact": "用户难以快速区分基础信息区和标签区的视觉层次"
              },
              "recommendation": "此处分区不清晰数量已达1处触发不达标，建议在基础信息区与标签区之间增加1条视觉分割线或显著间距以消除该1处边界问题",
              "evidenceImage": "screenshots-out/evidence/evidence_eval-6-info-partitioning_C2-meta-info_安睡裤_全部.png"
            },
            {
              "elementId": "C3-title",
              "coord": [380, 2021, 810, 47],
              "component": "C3",
              "elementType": "文本",
              "content": "原文:安睡裤商品名称",
              "dimension": "信息分区",
              "description": "第三张商品卡有4处边界不清晰：标题区到基础信息区（间距23像素但区域内部中位间距29像素，间距不显著大于内部间距，不清晰）、基础信息区到标签区（间距43像素但内部中位间距29像素，不清晰）、价格区到商家区（间距1像素，不清晰）、商家区到下挂区（间距31像素但内部中位间距29像素，不清晰），共4处不清晰",
              "rating": "不达标",
              "priority": "高",
              "priorityReason": "4处分区边界不清晰，涉及标题到价格到商家多个核心区域，严重影响用户信息层次识别",
              "finding": {
                "observableFact": "第三张商品卡4处边界不清晰：标题到基础信息（23像素不及内部29像素）、基础信息到标签（43像素不足以区分内部29像素）、价格到商家（1像素）、商家到下挂（31像素不及内部29像素）",
                "ruleOrThreshold": "相邻区域间距不显著大于内部中位间距且无物理视觉边界判定为不清晰，问题数大于等于1不达标",
                "verdictReason": "4处边界均不清晰，评级不达标",
                "userImpact": "用户难以区分标题、基础信息、价格、商家和下挂各区域，多区域混杂影响信息识别效率"
              },
              "recommendation": "此商品卡分区不清晰数量达4处（每处均不达标），建议为各相邻区域各增加1条视觉分割线，使每处边界至少满足1种边界类型的清晰条件",
              "evidenceImage": "screenshots-out/evidence/evidence_eval-6-info-partitioning_C3-title_安睡裤_全部.png"
            }
          ]
        }
      }
    ]
  },
  {
    "skill": "eval-7-info-authenticity",
    "dimension": "phase3-card_or_component-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "优秀",
        "reason": "三张商品卡歧义数均为零，所有已检查关系状态均已确认，评级为优秀",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "original-page",
          "criterion": "逐组件分析信息歧义情况，统计歧义元素数量并评级，歧义为0优秀，歧义大于等于1不达标",
          "summary": "三张商品卡均无信息歧义。各卡片标题与头图的对应关系、标题与下挂促销的关联关系均已确认。各卡片标题、价格、促销文字在搜索安睡裤场景下含义明确，无歧义",
          "overview": {"total": 3, "excellent": 3, "pass": 0, "fail": 0, "failRate": "0%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png",
            "evaluatedUnitCount": 3,
            "assessmentRows": [
              {
                "componentId": "C1",
                "checkedRelations": ["title_to_image","title_to_append"],
                "relationStatuses": ["confirmed","confirmed"],
                "inapplicableChecks": [],
                "conflicts": [],
                "conflictCount": 0,
                "rating": "优秀"
              },
              {
                "componentId": "C2",
                "checkedRelations": ["title_to_image","title_to_append"],
                "relationStatuses": ["confirmed","confirmed"],
                "inapplicableChecks": [],
                "conflicts": [],
                "conflictCount": 0,
                "rating": "优秀"
              },
              {
                "componentId": "C3",
                "checkedRelations": ["title_to_image","title_to_append"],
                "relationStatuses": ["confirmed","confirmed"],
                "inapplicableChecks": [],
                "conflicts": [],
                "conflictCount": 0,
                "rating": "优秀"
              }
            ]
          },
          "issues": []
        }
      }
    ]
  },
  {
    "skill": "eval-7-info-redundancy",
    "dimension": "phase3-page_framework-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "优秀",
        "reason": "整页各区域无语义冗余，评级为优秀",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "original-page",
          "criterion": "整页扫描各区域间是否存在语义重复信息，冗余数为0优秀，大于等于1不达标",
          "summary": "三张商品卡分属不同商品，各区域信息虽存在相同语义角色（标题、基础信息等）但对应不同商品实体，不构成语义冗余。各卡片间无相同文字内容重复展示",
          "overview": {"total": 1, "excellent": 1, "pass": 0, "fail": 0, "failRate": "0%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png",
            "assessmentRows": [
              {
                "pageRegions": [
                  {"region":"第一张商品卡","elements":["C1-title","C1-meta-info","C1-tag-prom","C1-price","C1-merchant","C1-text-append"]},
                  {"region":"第二张商品卡","elements":["C2-title","C2-meta-info","C2-tag-prom","C2-price","C2-merchant","C2-text-append-1","C2-text-append-2"]},
                  {"region":"第三张商品卡","elements":["C3-title","C3-meta-info","C3-tag-prom","C3-price","C3-merchant","C3-text-append-1","C3-text-append-2"]}
                ],
                "candidatePairs": [],
                "redundancyCount": 0,
                "rating": "优秀"
              }
            ]
          },
          "issues": []
        }
      }
    ]
  },
  {
    "skill": "eval-8-info-redundancy",
    "dimension": "phase3-card_or_component-eval",
    "units": [
      {
        "tab": "全部",
        "rating": "优秀",
        "reason": "三张商品卡各区域均无语义重复，各卡分属不同商品实体，评级为优秀",
        "details": {
          "screenshot": "screenshots/安睡裤_全部_1.png",
          "evidenceMode": "original-page",
          "criterion": "逐区域分析语义重复情况，重复数为0优秀，重复数大于等于1不达标。同原文且坐标重叠的条目为标注缺陷不视为冗余",
          "summary": "三张商品卡分属不同商品，各区域信息虽存在相同语义角色但对应不同商品实体，不构成语义重复。卡内各字段各自表述单一语义，无内部重复。空白元素不产生重复问题",
          "overview": {"total": 3, "excellent": 3, "pass": 0, "fail": 0, "failRate": "0%"},
          "evidence": {
            "sourceManifestTotal": 23,
            "manifestPath": "screenshots-out/elements_安睡裤.json",
            "screenshotPath": "screenshots/安睡裤_全部_1.png",
            "evaluatedUnitCount": 3,
            "assessmentRows": [
              {
                "regionId": "C1",
                "regionType": "商品卡片",
                "examinedElements": ["C1-title","C1-meta-info","C1-tag-prom","C1-price","C1-merchant","C1-text-append"],
                "candidatePairs": [],
                "duplicateCount": 0,
                "rating": "优秀"
              },
              {
                "regionId": "C2",
                "regionType": "商品卡片",
                "examinedElements": ["C2-title","C2-meta-info","C2-tag-prom","C2-price","C2-merchant","C2-text-append-1","C2-text-append-2"],
                "candidatePairs": [],
                "duplicateCount": 0,
                "rating": "优秀"
              },
              {
                "regionId": "C3",
                "regionType": "商品卡片",
                "examinedElements": ["C3-title","C3-meta-info","C3-tag-prom","C3-price","C3-merchant","C3-text-append-1","C3-text-append-2"],
                "candidatePairs": [],
                "duplicateCount": 0,
                "rating": "优秀"
              }
            ]
          },
          "issues": []
        }
      }
    ]
  }
]

out = PROJECT / ".artifacts/过程文件-评测结果与审计/32词2.0_20260816/安睡裤/phase3/eval_results_安睡裤_全部.json"
out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out}")
print(f"skills: {len(results)}")
for r in results:
    print(f"  {r['skill']}: {r['units'][0]['rating']}")
