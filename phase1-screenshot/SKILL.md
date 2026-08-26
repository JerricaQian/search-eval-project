---
name: meituan-search-screenshot
description: 自动化在美团 Android App 按搜索词搜索并采集搜索结果页截图。每个搜索词在「全部/外卖/团购」三个 tab 下分别截取第一屏、第二屏、第三屏，共 9 张/词，供评测人员批量收集页面数据。当用户提到美团截图、搜索结果截图、采图、收集评测截图、搜索词截图时使用。
compatibility: 需要宿主可调用 adb、目标 Android 设备已授权 USB 调试且输入法可写入中文
metadata:
  author: qianjing
  version: "1.0"
  app: "com.sankuai.meituan"
allowed-tools: Bash(adb:*) Read Write
---

# 美团搜索结果页自动截图

## 边界

仅负责现场截图；不做 Phase2 识别、Phase3 评级、Phase4 证据或 Phase5 报告。已有截图走 `discover`/`copy`，不得重新抓取或覆盖。

## 输入与产物

- 输入：当前设备、搜索词、目标 Tab、屏号和项目根目录。未提供 Tab/屏号时由调用方确认，不能假定固定词、固定设备、固定分辨率或固定坐标。
- 产物：`screenshots/<搜索词>_<Tab>_<屏>.<ext>`；同名且字节不同则保留为 `_副本N`，不覆盖。发现器以统一解析器识别 `_副本`、`_副本N`、`_副本(N)` 和 `_copyN` 为独立实例，不能把后缀并入搜索词。设备日志和失败记录写入当前批次 `.artifacts/`，不得只留在临时目录。

## 执行

1. 先验证 `adb devices` 中目标状态为 `device`，确认设备已解锁、应用可达、当前输入法能写入中文；能力或状态不足时阻断并返回实际检测结果。
2. 只调用当前项目的 `phase1-screenshot/scripts/run_scroll.sh`；参数来自本次输入：

```bash
bash <projectDir>/phase1-screenshot/scripts/run_scroll.sh "<queries>" "<tabs>" "<screens>"
```

3. 大批量可调用同目录 `loop_screenshot.sh`，但每词失败须保留日志、仅重试该词，不能用旧截图补齐。
4. 截图后检查每张文件存在、非零字节且可读取；再由 `phase1-screenshot/scripts/discover_screenshot_groups.py --screenshot-dir <projectDir>/screenshots` 产出可评测分组和无效/无法解析项。

## 宿主与失败处理

- 坐标、页面状态和输入方式属于当前设备事实；脚本不能适配时停止并记录，不在 Skill 内写入机型、UDID、分辨率或历史临时路径。
- 设备断连、弹窗、输入失败或截屏失败只影响当前词/屏；保留失败产物和原因，修复环境后重跑该范围。
- 外部截图由 `phase1-screenshot/scripts/ingest_external_screenshots.py` 复制到项目 `screenshots/`，源文件只读保留。复制后同样必须 discover，不能手工假定分组。

## 验收

返回本次有效截图路径、发现的分组、无效/无法解析文件和每个失败范围；不要输出任何评测结论。
