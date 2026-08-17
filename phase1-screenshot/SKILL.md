---
name: meituan-search-screenshot
description: 自动化在美团 Android App 按搜索词搜索并采集搜索结果页截图。每个搜索词在「全部/外卖/团购」三个 tab 下分别截取第一屏、第二屏、第三屏，共 9 张/词，供评测人员批量收集页面数据。当用户提到美团截图、搜索结果截图、采图、收集评测截图、搜索词截图时使用。
compatibility: 需要 macOS/Linux + adb（PATH 可用）+ 已开启 USB 调试的华为 ABR-AL80（Android 12，分辨率 1224×2700），已安装 ADBKeyBoard 输入法（com.android.adbkeyboard）
metadata:
  author: qianjing
  version: "1.0"
  device: "HUAWEI ABR-AL80 (UDID: GNH0222920006491, Android 12, 1224x2700)"
  app: "com.sankuai.meituan"
allowed-tools: Bash(adb:*) Read Write
---

# 美团搜索结果页自动截图

## 能力概述

通过 ADB 自动化控制美团 Android App：按指定搜索词搜索，在搜索结果页的「全部」「外卖」「团购」三个 tab 下，分别截取**第一屏、第二屏、第三屏**的页面截图，**每个搜索词共 9 张**（3 tab × 3 屏），保存到指定文件夹，供评测人员收集页面数据。

**调用的美团搜索能力**（通过 ADB 模拟用户操作实现）：
- 搜索主页输入态进入、中文搜索词输入、搜索触发
- 搜索结果页 SearchResultActivity 的 tab 切换（全部/外卖/团购）
- 结果页内上下滚动翻屏（第一/二/三屏）
- 红包/弹窗关闭后截图

**命名格式**（统一带屏号后缀）：
- 第 1 屏：`{搜索词}_{tab}_1.png`（如 `库迪_全部_1.png`）
- 第 2 屏：`{搜索词}_{tab}_2.png`（如 `库迪_全部_2.png`）
- 第 3 屏：`{搜索词}_{tab}_3.png`（如 `库迪_全部_3.png`）

> 每个搜索词产出 9 张：`{词}_全部_1/2/3.png`、`{词}_外卖_1/2/3.png`、`{词}_团购_1/2/3.png`

## 快速开始

```bash
# 1. 手机 USB 连 Mac，开启 USB 调试，打开美团 App
# 2. 重连设备 + 切输入法
adb kill-server; adb start-server; sleep 1.5
adb shell ime set com.android.adbkeyboard/.AdbIME
# 3. 后台跑（脚本支持按需选择 词/tab/屏，见下文「按需选择」）
nohup bash scripts/run_scroll.sh > /tmp/scroll_run.out 2>&1 &
# 4. 盯进度（每个词截完出一条事件）
tail -f /tmp/meituan_scroll.log | grep -E "===|_ok|ALL_DONE|!!"
```

## 按需选择（搜索词 / tab / 屏数）

脚本接受 3 个可选参数（均逗号分隔，缺省则用默认全量）：

```
bash scripts/run_scroll.sh [搜索词] [tab] [屏]
```

| 参数 | 说明 | 可选值 | 默认 |
|------|------|--------|------|
| 搜索词 | 要搜的词，逗号分隔 | 任意中文词 | 全部 16 词 |
| tab | 要截的 tab，逗号分隔 | `全部` / `外卖` / `团购` | 全部 3 个 |
| 屏 | 要截的屏，逗号分隔 | `1` / `2` / `3` | 全部 3 屏 |

**示例**：

```bash
# 全量：16词 × 3tab × 3屏 = 144张
bash scripts/run_scroll.sh

# 指定词，tab/屏用默认全量（库迪+蜜雪冰城，各9张）
bash scripts/run_scroll.sh "库迪,蜜雪冰城"

# 指定词 + 指定tab（库迪，只截 全部+外卖）
bash scripts/run_scroll.sh "库迪" "全部,外卖"

# 指定词 + 指定tab + 指定屏（库迪，只截 团购 的 第1屏和第3屏）
bash scripts/run_scroll.sh "库迪" "团购" "1,3"

# 多词 + 单tab + 单屏（库迪和蜜雪冰城，只截 外卖 第2屏）
bash scripts/run_scroll.sh "库迪,蜜雪冰城" "外卖" "2"
```

> 屏的滚动逻辑：屏1=切tab后直接截；屏2=下滑1次后截；屏3=下滑2次后截。每个 tab 切换前都会先 `scroll_to_top` 滚回第一屏，确保从第1屏开始。

## 前置条件

1. **设备连接**：华为 ABR-AL80（UDID `GNH0222920006491`），USB 连 Mac，手机端开启「USB 调试」，USB 模式选「传输文件」，屏幕保持解锁点亮。
2. **adb**：已安装并加入 PATH。
3. **ADBKeyBoard**（中文输入关键，包名 `com.android.adbkeyboard`，IME `com.android.adbkeyboard/.AdbIME`，APK 为 ADBKeyboard.apk v2.5-dev）。每次运行前必须切为当前输入法：
   ```bash
   adb shell ime enable com.android.adbkeyboard/.AdbIME
   adb shell ime set com.android.adbkeyboard/.AdbIME
   adb shell settings get secure default_input_method   # 应输出 com.android.adbkeyboard/.AdbIME
   ```
4. **美团 App**：已登录，停留在任意页面（脚本会自动回搜索主页）。

## 关键坐标（原始分辨率 1224×2700）

| 元素 | 坐标 | 说明 |
|------|------|------|
| 搜索框 EditText | (465, 365) | 点击进入搜索输入态 |
| 搜索按钮 | (1066, 352) | 点击触发搜索（**不要用 keyevent 84**，不可靠） |
| 全部 tab | (385, 320) | 结果页顶部 tab |
| 外卖 tab | (573, 320) | 结果页顶部 tab |
| 团购 tab | (761, 320) | 结果页顶部 tab |
| search_back 返回按钮 | (68, 202) | 结果页左上角返回（resource-id `search_back`，bounds [38,172][99,233]） |
| 滚动起止 | (612,2000)→(612,700) 下滑 / (612,700)→(612,2000) 上滑 | 翻屏 |

> ⚠️ **禁止点击 y<350 区域**（search_back 除外），否则会误触「问小团」入口，导致页面跳错。

## 核心工作流（每个搜索词循环执行）

### 步骤 1：回到搜索输入页 `ensure_input_page`

SearchResultActivity 上 `uiautomator dump` 经常返回 0 字节，**不能仅靠 dump 判断页面状态**。

```
循环最多 6 次：
  1. dump_ui()：重试最多 4 次，直到本地文件 /tmp/mt_ui.xml > 100 字节
  2. 若文件含 'android.widget.EditText' → 已在搜索输入态，返回成功
  3. 否则：点 search_back(68,202) → sleep 2s → 点搜索框(465,365) → sleep 2s
```

### 步骤 2：清空搜索框 `clear_input`（双保险，必须配合退格）

单独 `ADB_INPUT_CLEAR` 会残留上一个词，必须配合：
```bash
adb shell am broadcast -a ADB_INPUT_CLEAR
adb shell input keyevent KEYCODE_MOVE_END
for i in $(seq 1 12); do adb shell input keyevent KEYCODE_DEL; done
```

### 步骤 3：输入并验证 `input_query`（重试 3 次）

```bash
adb shell am broadcast -a ADB_INPUT_TEXT --es msg '搜索词'
```
然后 dump → 用 grep 提取 EditText 的 text → **必须等于目标词**，否则清空重试。重试 3 次仍失败则跳过该词（记日志 `!! 输入失败，跳过`），继续下一个词，事后单独补跑。

> ⚠️ **提取 EditText text 的正确方式**：text 属性在 class 之前，需先取整个 EditText 节点再取 text：
> ```bash
> grep -o '<node[^>]*class="android.widget.EditText"[^>]*>' /tmp/mt_ui.xml \
>   | head -1 | grep -o 'text="[^"]*"' | head -1 | sed 's/text="//;s/"$//'
> ```
> **不要用 `python3` 经管道读 /tmp 文件**（sandbox 会 Permission denied），改用 grep/sed 解析本地文件。

> ⚠️ **不验证会导致新旧词叠加**（如「蜜雪冰城」外卖==团购同图就是这个原因）。

### 步骤 4：触发搜索

```bash
adb shell input tap 1066 352   # 点搜索按钮，不要用 keyevent 84
sleep 4
```

### 步骤 5：逐 tab 截图（每个 tab 截第 1/2/3 屏）

对「全部(385,320)」「外卖(573,320)」「团购(761,320)」依次执行，每个 tab 截 3 屏：

```
切 tab 前必须先滚回第一屏（否则在滚到底的状态切 tab 会出错）：
  scroll_to_top：上滑 3 次（adb shell input swipe 612 700 612 2000 400），每次 sleep 1.2
点 tab 坐标 → sleep 3.2
第 1 屏：直接 shot_clean → 保存 {词}_{tab}_1.png
第 2 屏：scroll_down 一次（swipe 612 2000 → 612 700）→ sleep 2.6 → shot_clean → {词}_{tab}_2.png
第 3 屏：scroll_down 再一次 → sleep 2.6 → shot_clean → {词}_{tab}_3.png
```

### 步骤 6：截图并关弹窗 `shot_clean`（含大小校验）

```
循环最多 3 次：
  1. dump_ui()
  2. grep 找弹窗关闭按钮文本：关闭 / 我知道了 / 领取 / 暂不领取 / 取消 / 知道了 / 确定 / 残忍拒绝
  3. 若有 → 取其 bounds 中心点 → 点击 → sleep 1.6 → continue（再检查一次）
  4. 若无弹窗 → 截图：adb exec-out screencap -p > 目标文件
     校验文件大小 > 5000 字节；0 字节则重试最多 3 次（设备卡顿时 screencap 会输出空文件）
```

## 关键陷阱与对策（必读，均为实战踩坑）

| 陷阱 | 现象 | 对策 |
|------|------|------|
| keyevent 84 搜索键不可靠 | 搜索不触发 | 改用点搜索按钮坐标 (1066,352) |
| 点 y<350 误触「问小团」 | 回搜索主页时点到问小团入口 | 除 search_back(68,202) 外禁止点 y<350 |
| ADB_INPUT_CLEAR 残留 | 上一个词残留导致搜错 | CLEAR + MOVE_END + 12× DEL 双保险 |
| 不验证输入 → 新旧词叠加 | 蜜雪冰城外卖==团购同图 | dump 读 EditText text 必须 == 目标词，重试 3 次 |
| SearchResultActivity dump 0 字节 | has_edittext 误判失败，所有词被跳过 | dump 重试 4 次；失败时不靠 dump，直接点 search_back + 搜索框 |
| dump 0 字节时 ensure_input_page 死循环 | 全部跳过 | dump 失败也主动点返回 + 搜索框，多轮重试 |
| 切 tab 时在滚到底状态 | tab 切换出错、截错页 | 切 tab 前必须 scroll_to_top |
| 红包弹窗挡住截图 | 截到弹窗而非结果页 | shot_clean 截图前检测关闭按钮并点击 |
| screencap 输出 0 字节 | 空文件 | 截图后校验 > 5000 字节，0 则重试 |
| python3 读 /tmp 经管道 Permission denied | 验证/弹窗检测失败 | 改用 grep/sed 解析本地文件，不用 python3 管道 |
| USB 频繁掉线 | adb: no devices | adb kill-server / start-server 重连循环（最多 15 次） |
| Bash 2 分钟超时 | 批量任务被中断 | nohup 后台运行 + Monitor 工具盯进度日志 |
| macOS 无 `timeout` 命令 | 循环里 `timeout 180 bash ...` 直接失败，run_scroll.sh 根本没执行，全部词"假完成"0 产出 | 不用 timeout，靠 ALL_DONE 判断；或 `which timeout` 确认存在再用 |
| 日志报 ok 但文件没落盘 | nohup 子进程写 `~/Desktop` 被 TCC 拦成 Operation not permitted，shot_clean 先 echo ok 再校验 | 输出用 `/tmp`（TCC 豁免），跑完 cp 到 Desktop；独立校验 `ls 词_*.png \| wc -l` 每词数到 3 |
| 0 字节文件残留 | screencap 设备卡顿时输出 0 字节，重试 3 次仍失败被放过 | 终校验 `find -size 0` 兜底；loop_screenshot.sh 每词跑完自动删 0 字节并重跑 |
| 全量脚本掉线连跳多词 | 设备掉线→ensure_input_page 失败→连续跳过后续词 | 大批量用 loop_screenshot.sh 逐词循环 + 每词重连，最多丢当前 1 词 |

## 脚本执行

完整脚本见 `scripts/run_scroll.sh`（已含上述全部修复，支持按需参数）。批量执行：

```bash
# 1. 重连设备
for i in $(seq 1 15); do
  adb kill-server 2>/dev/null; adb start-server 2>/dev/null; sleep 1.5
  adb devices | grep -q "device$" && break
done
adb devices

# 2. 切输入法
adb shell ime set com.android.adbkeyboard/.AdbIME

# 3. 后台运行（按需传参，见「按需选择」；不传参=全量16词×3tab×3屏）
nohup bash scripts/run_scroll.sh > /tmp/scroll_run.out 2>&1 &
echo "PID=$!"
```

**修改输出目录**：编辑脚本顶部 `OUT=...` 变量。
**修改默认搜索词列表**：编辑脚本顶部 `DEFAULT_QUERIES=...` 变量。

## 批量截图（推荐：逐词带重连循环）

大批量（>10 词）用 `scripts/loop_screenshot.sh`，**不要直接 nohup 全量跑 run_scroll.sh**。原因：USB 掉线时全量脚本会连续跳过多词；逐词循环每词单独跑、跑完校验落盘、掉线自动重连，最多丢当前 1 词。

```bash
# 1. 写词表（逗号分隔），或留空用脚本内置 32 词
echo "库迪,蜜雪冰城,隆江猪脚饭" > /tmp/meituan_words.txt

# 2. 后台跑逐词循环（参数均可缺省：词表 输出目录 tab 屏）
nohup bash scripts/loop_screenshot.sh /tmp/meituan_words.txt /tmp/meituan_shots 全部 1,2,3 \
  > /tmp/meituan_loop.out 2>&1 &
echo "PID=$!"

# 3. Monitor 盯进度（每词完成/失败/全部完成）
#    tail -f /tmp/meituan_loop.log | grep -E ">>>|✅|❌|LOOP_ALL_DONE|重连失败"
```

- 脚本每词跑完只校验该词是否 ≥3 张有效截图；**不得删除** 0 字节或失败截图。把其路径和失败原因写入 `.artifacts/过程文件-评测结果与审计/<批次>/<搜索词>/phase1/` 的审计记录，原文件保留供复盘。
- 失败词自动写入 `.artifacts/过程文件-评测结果与审计/<批次>/<搜索词>/phase1/meituan_failed.txt`，结尾记录重跑命令；不得使用 `/tmp` 作为唯一留存位置。
- 截图运行缓存可使用 `/tmp` 以规避 TCC，但所有需要复盘的日志、图片及中间结果必须复制或直接写入 `.artifacts/`；不在完成后删除缓存或过程文件。
- **macOS 无 `timeout` 命令**，循环脚本不要用它；靠 run_scroll.sh 的 ALL_DONE 判断完成。

进度日志在 `/tmp/meituan_scroll.log`，用 Monitor 工具流式监控：
```
tail -n 0 -f /tmp/meituan_scroll.log | grep --line-buffered -E "===|_ok|ALL_DONE|!! |失败"
```

## 校验

每个搜索词完成后应有 9 张图（3 tab × 3 屏）。同一 tab 的第1/2/3屏 md5 必须各不相同（确认屏真翻动），同一屏的三个 tab md5 必须各不相同（确认 tab 真切换），文件大小必须 > 5000 字节：

```bash
# 输出目录对应脚本里的 OUT 变量；工作流统一传入项目根 screenshots/ 目录
# 统计每个词每个 tab 每屏的文件大小（应每词9张）
for q in 库迪 解压体验馆 游乐场 露营 万象城; do
  for tab in 全部 外卖 团购; do
    for n in 1 2 3; do
      f="输出目录/${q}_${tab}_${n}.png"
      echo "${q}_${tab}_${n}: $(stat -f%z "$f" 2>/dev/null) bytes"
    done
  done
done
# 检查空文件
find 输出目录 -name "*_*_*.png" -size 0
# 每词文件数应为 9
for q in 库迪 解压体验馆 游乐场 露营 万象城; do
  echo "$q: $(find 输出目录 -name "${q}_*_*.png" | wc -l) 张"
done
```

## 故障恢复

- **设备掉线**：重连循环，确认 `adb shell echo ok` 响应后再续跑。
- **某词被跳过**：单独把该词加入 `QUERIES` 数组重跑；已有正常文件不会覆盖（或先删空文件再跑）。
- **dump 一直 0 字节**：确认设备真在线（`adb shell echo ok`）、屏幕未锁屏、美团 App 未崩溃；必要时唤醒屏幕 `adb shell input keyevent 224`。
- **输入验证反复失败**：确认 ADBKeyBoard 已切为当前输入法（步骤见前置条件），百度输入法华为版会被切回，需重新 set。
- **批量任务中途中断**：保留空文件，在 `.artifacts/过程文件-评测结果与审计/<批次>/<搜索词>/phase1/` 记录其路径和设备状态；把未完成的词加入 QUERIES 续跑，不得删除历史截图。
