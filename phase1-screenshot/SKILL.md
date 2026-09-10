---
name: meituan-search-screenshot
description: 自动化在美团 Android App 按搜索词搜索并采集搜索结果页截图。每个搜索词在「全部/外卖/团购」三个 tab 下分别截取第一屏、第二屏、第三屏，共 9 张/词，供评测人员批量收集页面数据。当用户提到美团截图、搜索结果截图、采图、收集评测截图、搜索词截图时使用。
compatibility: 需要宿主可调用 adb、目标 Android 设备已授权 USB 调试且输入法可写入中文；结果页必须可稳定导出 UI XML 以定位 Tab
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

1. 先验证 `adb devices` 中目标状态为 `device`，读取厂商/机型/Android 版本与 `wm size`，确认设备已解锁、应用可达、当前输入法能写入中文；能力或状态不足时阻断并返回实际检测结果。设备未授权时，提示用户按本机系统设置路径手动开启开发者选项和 USB 调试并确认授权；Agent 不得自行修改这些系统开关。若未检测到 `com.android.adbkeyboard`，在设备或模拟器已连接后引导用户从源码安装：

```bash
git clone https://github.com/senzhk/ADBKeyBoard.git
cd ADBKeyBoard
export ANDROID_HOME=$HOME/Android/Sdk  # 或编辑 local.properties
./gradlew installDebug
```

安装后重新检查该输入法包；项目不再内置或安装 APK。
2. 只调用当前项目的 `phase1-screenshot/scripts/run_scroll.sh`；参数来自本次输入：

```bash
bash <projectDir>/phase1-screenshot/scripts/run_scroll.sh "<queries>" "<tabs>" "<screens>"
```

3. 大批量使用同目录 `capture_batch.py`。控制器每次只调用一次 `run_scroll.sh` 处理一个词，并写入追加式 receipt；暂停、恢复和观测必须通过控制器，不能同时启动第二个设备控制脚本。每词失败仅重试该词，不能用旧截图补齐。
4. 截图后检查每张文件存在、非零字节且可读取；再由 `phase1-screenshot/scripts/discover_screenshot_groups.py --screenshot-dir <projectDir>/screenshots` 产出规范分组、有效未命名候选和无效项。有效未命名图不得作为错误或阻断项。

## 宿主与失败处理

- 返回、输入框、搜索提交和 Tab 必须由当前 UI XML 动态定位：返回使用 `KEYCODE_BACK`，输入框选择可见 EditText 的 bounds，Tab 按文本/`content-desc` 的 bounds 定位并验证状态；不得使用历史机型坐标。唯一例外是**刚提交新搜索后的「全部」第一屏**：若已由 `SearchResultActivity` 验证进入结果页但 XML 暂不可用，可不点击 Tab，直接采集默认「全部」页；外卖/团购仍必须定位并验证 XML。其他 XML 缺失、Tab 不存在或点击后无法验证的情形，阻断当前词/Tab 并保留日志，不得回退到固定坐标。
- 每轮采集必须在日志中记录当前设备的搜索框 bounds/中心点、`KEYCODE_BACK` 已回到可写搜索框的验证，以及 XML 可用时「全部」Tab 的 bounds/中心点。这些是运行时校准记录，不得回写为任何设备固定坐标。
- 刚提交搜索后，每次处理 Tab 都先执行回到列表顶部的手势；默认「全部」不重复点击 Tab，随后立即截图。第 2/3 屏或非默认 Tab 再依目标屏数执行对应手势。动态页面无需等待两帧像素完全相同，不得基于直播卡、商户卡或任何内容识别决定是否截图。
- 若系统通知面板等覆盖层处于前台，必须阻断并请用户手动收起；不得用返回键、坐标点击或滑动去关闭覆盖层，以免改变美团页面位置。
- 滑动按当前 `wm size` 的屏幕比例计算，且必须验证页面指纹变化；未变化时不得将重复页面保存为下一屏。
- 设备断连、弹窗、输入失败或截屏失败只影响当前词/屏；保留失败产物和原因，修复环境后重跑该范围。
- 外部截图由 `phase1-screenshot/scripts/ingest_external_screenshots.py` 复制到项目 `screenshots/`，源文件只读保留。复制后同样必须 discover；未命名图由宿主读取当前像素形成 `screenshot.identity-map` 后分组，不能手工假定或要求先改名。

## 验收

返回本次有效截图路径、规范分组、有效未命名候选、无效文件和每个失败范围；不要输出任何评测结论。
