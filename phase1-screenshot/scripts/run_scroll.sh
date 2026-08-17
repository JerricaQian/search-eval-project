#!/bin/bash
# 美团搜索结果页 截图（支持按需选择 搜索词/tab/屏数）
# 用法：
#   bash run_scroll.sh                                # 默认：全部16词 × 3tab × 3屏 = 144张
#   bash run_scroll.sh "库迪,蜜雪冰城"                 # 指定词（逗号分隔），tab/屏用默认全量
#   bash run_scroll.sh "库迪" "全部,外卖"              # 指定词 + 指定tab
#   bash run_scroll.sh "库迪" "全部,外卖" "1,3"        # 指定词 + 指定tab + 指定屏
#   bash run_scroll.sh "库迪,蜜雪冰城" "团购" "2"      # 多词单tab单屏
# tab 可选值：全部 / 外卖 / 团购
# 屏 可选值：1 / 2 / 3
# 命名：query_tab_1.png / query_tab_2.png / query_tab_3.png

# 输出目录：优先用环境变量 OUT（供 workflow 调用时指定项目内目录），否则默认 /tmp
OUT="${OUT:-/tmp/meituan_shots}"
LOG=/tmp/meituan_scroll.log

# 默认值
DEFAULT_QUERIES="库迪,解压体验馆,游乐场,露营,万象城,万达广场美食,蜜雪冰城,必胜客,隆江猪脚饭外卖,生日蛋糕,安睡裤,榴莲,啤酒,药店,布洛芬,生理盐水"
DEFAULT_TABS="全部,外卖,团购"
DEFAULT_SCREENS="1,2,3"

# 解析参数（逗号分隔 → 空格分隔的数组）
QUERIES_STR="${1:-$DEFAULT_QUERIES}"
TABS_STR="${2:-$DEFAULT_TABS}"
SCREENS_STR="${3:-$DEFAULT_SCREENS}"

IFS=',' read -ra QUERIES <<< "$QUERIES_STR"
IFS=',' read -ra TABS <<< "$TABS_STR"
IFS=',' read -ra SCREENS <<< "$SCREENS_STR"

# tab 名称 → 坐标映射
tab_coord() {
  case "$1" in
    全部) echo "385" ;;
    外卖) echo "573" ;;
    团购) echo "761" ;;
    *) echo "" ;;
  esac
}

dump_ui() {
  for t in 1 2 3 4; do
    adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1
    adb shell cat /sdcard/ui.xml > /tmp/mt_ui.xml 2>/dev/null
    sz=$(stat -f%z /tmp/mt_ui.xml 2>/dev/null)
    if [ -n "$sz" ] && [ "$sz" -gt 100 ]; then return 0; fi
    sleep 0.8
  done
  return 1
}

# 回到搜索输入页：点 search_back(68,202) 回搜索主页，再点搜索框
# SearchResultActivity 上 dump 经常返回0字节，不能仅靠 dump 判断
ensure_input_page() {
  for i in 1 2 3 4 5 6; do
    if dump_ui; then
      if grep -q 'android.widget.EditText' /tmp/mt_ui.xml 2>/dev/null; then return 0; fi
    fi
    adb shell input tap 68 202
    sleep 2.0
    adb shell input tap 465 365
    sleep 2.0
  done
  return 1
}

get_edittext_text() {
  dump_ui
  grep -o '<node[^>]*class="android.widget.EditText"[^>]*>' /tmp/mt_ui.xml 2>/dev/null \
    | head -1 | grep -o 'text="[^"]*"' | head -1 | sed 's/text="//;s/"$//'
}

clear_input() {
  adb shell am broadcast -a ADB_INPUT_CLEAR >/dev/null 2>&1
  sleep 0.4
  adb shell input keyevent KEYCODE_MOVE_END >/dev/null 2>&1
  sleep 0.2
  for i in $(seq 1 12); do adb shell input keyevent KEYCODE_DEL >/dev/null 2>&1; done
  sleep 0.3
}

input_query() {
  adb shell am broadcast -a ADB_INPUT_TEXT --es msg "$1" >/dev/null 2>&1
  sleep 1.3
}

# 截图前关闭红包弹窗，含大小校验
shot_clean() {
  out="$1"
  for a in 1 2 3; do
    dump_ui
    node=$(grep -oE '<node[^>]*text="(关闭|我知道了|领取|暂不领取|取消|知道了|确定|残忍拒绝)"[^>]*>' /tmp/mt_ui.xml 2>/dev/null | head -1)
    if [ -n "$node" ]; then
      bnds=$(echo "$node" | grep -oE 'bounds="\[[0-9]+,[0-9]+\]\[[0-9]+,[0-9]+\]"' | head -1)
      if [ -n "$bnds" ]; then
        nums=$(echo "$bnds" | grep -oE '[0-9]+')
        x1=$(echo "$nums" | sed -n 1p); y1=$(echo "$nums" | sed -n 2p)
        x2=$(echo "$nums" | sed -n 3p); y2=$(echo "$nums" | sed -n 4p)
        cx=$(( (x1 + x2) / 2 )); cy=$(( (y1 + y2) / 2 ))
        adb shell input tap $cx $cy
        sleep 1.6
        continue
      fi
    fi
    adb exec-out screencap -p > "$out"
    for s in 1 2 3; do
      sz=$(stat -f%z "$out" 2>/dev/null)
      if [ -n "$sz" ] && [ "$sz" -gt 5000 ]; then return; fi
      sleep 1.0
      adb exec-out screencap -p > "$out"
    done
    return
  done
  adb exec-out screencap -p > "$out"
  for s in 1 2 3; do
    sz=$(stat -f%z "$out" 2>/dev/null)
    if [ -n "$sz" ] && [ "$sz" -gt 5000 ]; then return; fi
    sleep 1.0
    adb exec-out screencap -p > "$out"
  done
}

scroll_down() {
  adb shell input swipe 612 2000 612 700 400
  sleep 2.6
}

# 滚回第一屏
scroll_to_top() {
  for i in 1 2 3; do
    adb shell input swipe 612 700 612 2000 400
    sleep 1.2
  done
  sleep 1.0
}

tap_search() { adb shell input tap 1066 352; sleep 4; }
# 切 tab 前必须先滚回第一屏
tap_tab() { scroll_to_top; adb shell input tap $1 320; sleep 3.2; }

# 截指定屏：参数 (搜索词, tab名, tab坐标, 屏号)
# 屏1=直接截；屏2=下滑1次后截；屏3=下滑2次后截
shoot_screen() {
  local q="$1" tabname="$2" coord="$3" screen="$4"
  tap_tab "$coord"
  if [ "$screen" = "1" ]; then
    shot_clean "$OUT/${q}_${tabname}_1.png"; echo "  ${tabname}_1 ok" | tee -a "$LOG"
  elif [ "$screen" = "2" ]; then
    scroll_down; shot_clean "$OUT/${q}_${tabname}_2.png"; echo "  ${tabname}_2 ok" | tee -a "$LOG"
  elif [ "$screen" = "3" ]; then
    scroll_down; scroll_down; shot_clean "$OUT/${q}_${tabname}_3.png"; echo "  ${tabname}_3 ok" | tee -a "$LOG"
  fi
}

mkdir -p "$OUT"
echo "START $(date '+%H:%M:%S')" | tee "$LOG"
echo "  词: ${QUERIES[*]}" | tee -a "$LOG"
echo "  tab: ${TABS[*]}" | tee -a "$LOG"
echo "  屏: ${SCREENS[*]}" | tee -a "$LOG"

for q in "${QUERIES[@]}"; do
  echo "=== $q ===" | tee -a "$LOG"
  if ! ensure_input_page; then
    echo "  !! 无法回到搜索输入页，跳过 $q" | tee -a "$LOG"
    continue
  fi
  # 清空 + 输入 + 验证(重试3次)
  ok=0
  for try in 1 2 3; do
    clear_input
    input_query "$q"
    actual=$(get_edittext_text)
    if [ "$actual" = "$q" ]; then ok=1; break; fi
    echo "  输入验证($try): 实际='$actual' 期望='$q'" | tee -a "$LOG"
    sleep 1
  done
  if [ $ok -eq 0 ]; then
    echo "  !! 输入失败，跳过 $q" | tee -a "$LOG"
    continue
  fi
  tap_search
  # 遍历选定的 tab × 屏
  for tabname in "${TABS[@]}"; do
    coord=$(tab_coord "$tabname")
    if [ -z "$coord" ]; then
      echo "  !! 未知 tab: $tabname，跳过" | tee -a "$LOG"
      continue
    fi
    for screen in "${SCREENS[@]}"; do
      shoot_screen "$q" "$tabname" "$coord" "$screen"
    done
  done
done
echo "ALL_DONE $(date '+%H:%M:%S')" | tee -a "$LOG"
