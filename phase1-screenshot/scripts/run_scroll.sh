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

UI_XML=/tmp/mt_ui.xml
SCREEN_W=0
SCREEN_H=0
SEARCH_EDIT_BOUNDS=""
RESULT_XML_AVAILABLE=0
FRESH_DEFAULT_RESULT=0
RETURN_PENDING=0

device_preflight() {
  if [ "$(adb get-state 2>/dev/null)" != "device" ]; then
    echo "  !! ADB 未处于 device 状态；请在此设备的开发者选项中开启 USB 调试并授权此电脑" | tee -a "$LOG"
    return 1
  fi
  local manufacturer model release size
  manufacturer=$(adb shell getprop ro.product.manufacturer 2>/dev/null | tr -d '\r')
  model=$(adb shell getprop ro.product.model 2>/dev/null | tr -d '\r')
  release=$(adb shell getprop ro.build.version.release 2>/dev/null | tr -d '\r')
  size=$(adb shell wm size 2>/dev/null | tr -d '\r' | grep -Eo '[0-9]+x[0-9]+' | tail -1)
  SCREEN_W=${size%x*}; SCREEN_H=${size#*x}
  if ! [[ "$SCREEN_W" =~ ^[0-9]+$ && "$SCREEN_H" =~ ^[0-9]+$ ]] || [ "$SCREEN_W" -lt 200 ] || [ "$SCREEN_H" -lt 400 ]; then
    echo "  !! 无法读取当前设备屏幕尺寸（wm size='$size'）" | tee -a "$LOG"
    return 1
  fi
  echo "  设备: ${manufacturer:-未知} ${model:-未知} / Android ${release:-未知} / ${SCREEN_W}x${SCREEN_H}" | tee -a "$LOG"
  return 0
}

dump_ui() {
  local dump_pid waited
  for t in 1 2; do
    # SearchResultActivity on some OEM builds can leave uiautomator dump
    # hanging. Bound every attempt so one unavailable XML tree cannot stall a
    # whole batch; callers decide whether that operation may safely continue.
    adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1 &
    dump_pid=$!; waited=0
    while kill -0 "$dump_pid" 2>/dev/null && [ "$waited" -lt 10 ]; do
      sleep 0.2; waited=$((waited + 1))
    done
    if kill -0 "$dump_pid" 2>/dev/null; then
      kill -TERM "$dump_pid" 2>/dev/null
    fi
    wait "$dump_pid" 2>/dev/null
    adb shell cat /sdcard/ui.xml > "$UI_XML" 2>/dev/null
    sz=$(stat -f%z "$UI_XML" 2>/dev/null)
    if [ -n "$sz" ] && [ "$sz" -gt 100 ]; then return 0; fi
    sleep 0.3
  done
  return 1
}

node_bounds() {
  echo "$1" | grep -oE 'bounds="\[[0-9]+,[0-9]+\]\[[0-9]+,[0-9]+\]"' | head -1 | sed 's/^bounds="//;s/"$//'
}

bounds_center() {
  local nums x1 y1 x2 y2
  nums=$(echo "$1" | grep -oE '[0-9]+')
  x1=$(echo "$nums" | sed -n 1p); y1=$(echo "$nums" | sed -n 2p)
  x2=$(echo "$nums" | sed -n 3p); y2=$(echo "$nums" | sed -n 4p)
  [ -n "$x2" ] && [ -n "$y2" ] || return 1
  echo "$(( (x1 + x2) / 2 )) $(( (y1 + y2) / 2 ))"
}

bounds_top() {
  echo "$1" | grep -oE '[0-9]+' | sed -n 2p
}

find_edittext_bounds() {
  local node bounds fallback=""
  while IFS= read -r node; do
    [[ "$node" == *'enabled="true"'* ]] || continue
    bounds=$(node_bounds "$node")
    [ -n "$bounds" ] || continue
    if [[ "$node" == *'focused="true"'* ]]; then echo "$bounds"; return 0; fi
    [ -z "$fallback" ] && fallback="$bounds"
  done < <(grep -o '<node[^>]*class="android.widget.EditText"[^>]*>' "$UI_XML" 2>/dev/null)
  [ -n "$fallback" ] && echo "$fallback"
}

find_tab_bounds() {
  local label="$1" node bounds top fallback=""
  while IFS= read -r node; do
    [[ "$node" == *"text=\"$label\""* || "$node" == *"content-desc=\"$label\""* ]] || continue
    bounds=$(node_bounds "$node")
    [ -n "$bounds" ] || continue
    top=$(bounds_top "$bounds")
    [[ "$top" =~ ^[0-9]+$ ]] || continue
    # 结果卡中的同名文字不应被当作 Tab；顶部区域优先，且每次点击前重新定位。
    if [ "$top" -le $(( SCREEN_H * 45 / 100 )) ]; then echo "$bounds"; return 0; fi
    [ -z "$fallback" ] && fallback="$bounds"
  done < <(grep -o '<node[^>]*>' "$UI_XML" 2>/dev/null)
  return 1
}

ui_fingerprint() {
  if dump_ui; then shasum -a 256 "$UI_XML" | awk '{print $1}'; return 0; fi
  adb exec-out screencap -p 2>/dev/null | shasum -a 256 | awk '{print $1}'
}

# 回到搜索输入页：只使用系统返回键；不再假定返回按钮或搜索框的固定坐标。
ensure_input_page() {
  # Do not repeatedly dump a result page before trying Back: several Huawei
  # builds expose no result-page XML at all.  A single bounded probe preserves
  # the case where the caller already starts on the input page.
  if dump_ui; then
    SEARCH_EDIT_BOUNDS=$(find_edittext_bounds)
    if [ -n "$SEARCH_EDIT_BOUNDS" ]; then
      log_search_calibration
      return 0
    fi
  fi
  for i in 1 2 3 4 5 6; do
    adb shell input keyevent KEYCODE_BACK >/dev/null 2>&1
    sleep 1.5
    if dump_ui; then
      SEARCH_EDIT_BOUNDS=$(find_edittext_bounds)
      if [ -n "$SEARCH_EDIT_BOUNDS" ]; then
        log_search_calibration
        return 0
      fi
    fi
  done
  return 1
}

log_search_calibration() {
  local center
  center=$(bounds_center "$SEARCH_EDIT_BOUNDS") || return 0
  echo "  校准[搜索框]: bounds=$SEARCH_EDIT_BOUNDS center=$center" | tee -a "$LOG"
  if [ "$RETURN_PENDING" -eq 1 ]; then
    echo "  校准[返回操作]: KEYCODE_BACK -> 已回到可写搜索框" | tee -a "$LOG"
    RETURN_PENDING=0
  fi
}

get_edittext_text() {
  local node bounds fallback=""
  dump_ui || return 1
  while IFS= read -r node; do
    bounds=$(node_bounds "$node")
    [ -n "$bounds" ] || continue
    if [ "$bounds" = "$SEARCH_EDIT_BOUNDS" ]; then
      echo "$node" | grep -o 'text="[^"]*"' | head -1 | sed 's/text="//;s/"$//'
      return 0
    fi
    [ -z "$fallback" ] && fallback="$node"
  done < <(grep -o '<node[^>]*class="android.widget.EditText"[^>]*>' "$UI_XML" 2>/dev/null)
  [ -n "$fallback" ] && echo "$fallback" | grep -o 'text="[^"]*"' | head -1 | sed 's/text="//;s/"$//'
}

clear_input() {
  adb shell am broadcast -a ADB_CLEAR_TEXT >/dev/null 2>&1
  sleep 0.4
  adb shell input keyevent KEYCODE_MOVE_END >/dev/null 2>&1
  sleep 0.2
  for i in $(seq 1 12); do adb shell input keyevent KEYCODE_DEL >/dev/null 2>&1; done
  sleep 0.3
}

input_query() {
  local encoded
  # ADB_INPUT_TEXT is not UTF-8 safe on some Android shells.  The installed
  # ADBKeyBoard receives the same text reliably through its Base64 action.
  encoded=$(printf '%s' "$1" | base64 | tr -d '\n')
  adb shell am broadcast -a ADB_INPUT_B64 --es msg "$encoded" >/dev/null 2>&1
  sleep 1.3
}

restart_adb_keyboard() {
  local fallback_ime
  # A result-page search bar may look editable in XML but has no writable
  # InputConnection.  Return to SearchActivity before rebinding the IME.
  adb shell input keyevent KEYCODE_BACK >/dev/null 2>&1
  RETURN_PENDING=1
  sleep 0.7
  fallback_ime=$(adb shell ime list -s 2>/dev/null | tr -d '\r' | grep -v '^com\.android\.adbkeyboard/' | head -1)
  [ -n "$fallback_ime" ] && adb shell ime set "$fallback_ime" >/dev/null 2>&1
  adb shell ime set com.android.adbkeyboard/.AdbIME >/dev/null 2>&1
  sleep 1
}

tap_bounds() {
  local center
  center=$(bounds_center "$1") || return 1
  adb shell input tap $center
}

wait_for_result_page() {
  local bounds
  for i in 1 2 3 4 5 6 7 8; do
    if dump_ui; then
      bounds=$(find_tab_bounds "全部")
      if [ -n "$bounds" ]; then
        RESULT_XML_AVAILABLE=1; FRESH_DEFAULT_RESULT=1
        center=$(bounds_center "$bounds")
        echo "  校准[全部Tab]: bounds=$bounds center=$center" | tee -a "$LOG"
        return 0
      fi
    fi
    # A freshly submitted Meituan search opens SearchResultActivity on the
    # default “全部” tab.  This narrow fallback is safe only for that default
    # tab: it performs no coordinate click and never substitutes for locating
    # 外卖/团购 tabs by XML.
    if adb shell dumpsys window 2>/dev/null | grep -q 'SearchResultActivity'; then
      RESULT_XML_AVAILABLE=0
      FRESH_DEFAULT_RESULT=1
      return 0
    fi
    sleep 1
  done
  return 1
}

submit_search() {
  adb shell input keyevent KEYCODE_ENTER >/dev/null 2>&1
  sleep 2.5
  wait_for_result_page
}

# 截图前关闭红包弹窗，含大小校验
shot_clean() {
  out="$1"
  for a in 1 2 3; do
    dump_ui
    node=$(grep -oE '<node[^>]*text="(关闭|我知道了|领取|暂不领取|取消|知道了|确定|残忍拒绝)"[^>]*>' "$UI_XML" 2>/dev/null | head -1)
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
  local before after x start_y end_y
  before=$(ui_fingerprint) || return 1
  x=$(( SCREEN_W / 2 )); start_y=$(( SCREEN_H * 76 / 100 )); end_y=$(( SCREEN_H * 30 / 100 ))
  adb shell input swipe "$x" "$start_y" "$x" "$end_y" 420
  sleep 2.6
  after=$(ui_fingerprint) || return 1
  if [ "$before" = "$after" ]; then
    echo "  !! 滑动后页面未变化，拒绝把重复页面当作下一屏" | tee -a "$LOG"
    return 1
  fi
}

# 滚回第一屏
scroll_to_top() {
  local x start_y end_y
  x=$(( SCREEN_W / 2 )); start_y=$(( SCREEN_H * 30 / 100 )); end_y=$(( SCREEN_H * 76 / 100 ))
  for i in 1 2 3 4; do
    adb shell input swipe "$x" "$start_y" "$x" "$end_y" 420
    sleep 1.2
  done
  sleep 1.0
}

tab_is_selected() {
  local label="$1" node
  while IFS= read -r node; do
    [[ "$node" == *"text=\"$label\""* || "$node" == *"content-desc=\"$label\""* ]] || continue
    [[ "$node" == *'selected="true"'* || "$node" == *'checked="true"'* ]] && return 0
  done < <(grep -o '<node[^>]*>' "$UI_XML" 2>/dev/null)
  return 1
}

# 切 tab 前必须先滚回第一屏；只点 XML 当前返回的 bounds，并验证选中态或层级变化。
tap_tab() {
  local label="$1" bounds before after
  # `submit_search` has already proved that a fresh result page starts on
  # the default 全部 tab.  Do not scroll or click it again: on a loading
  # result page those gestures can be consumed by the list and turn screen 1
  # into a lower screen.
  if [ "$label" = "全部" ] && [ "$FRESH_DEFAULT_RESULT" -eq 1 ]; then
    return 0
  fi
  if [ "$label" = "全部" ] && [ "$RESULT_XML_AVAILABLE" -eq 0 ]; then
    echo "  结果页 XML 暂不可用；使用本次新搜索的默认全部 Tab，不执行坐标点击" | tee -a "$LOG"
    return 0
  fi
  FRESH_DEFAULT_RESULT=0
  scroll_to_top
  dump_ui || { echo "  !! 结果页 XML 不可用，无法动态定位 Tab '$label'" | tee -a "$LOG"; return 1; }
  bounds=$(find_tab_bounds "$label")
  [ -n "$bounds" ] || { echo "  !! 未在结果页 XML 中找到 Tab '$label'" | tee -a "$LOG"; return 1; }
  before=$(shasum -a 256 "$UI_XML" | awk '{print $1}')
  tap_bounds "$bounds" || return 1
  sleep 3.2
  dump_ui || { echo "  !! 点击 Tab 后 XML 不可用，无法验证 '$label'" | tee -a "$LOG"; return 1; }
  after=$(shasum -a 256 "$UI_XML" | awk '{print $1}')
  if tab_is_selected "$label" || [ "$before" != "$after" ]; then return 0; fi
  echo "  !! Tab '$label' 未显示选中态且页面层级未变化" | tee -a "$LOG"
  return 1
}

# 截指定屏：参数 (搜索词, tab名, tab坐标, 屏号)
# 屏1=直接截；屏2=下滑1次后截；屏3=下滑2次后截
shoot_screen() {
  local q="$1" tabname="$2" screen="$3"
  local target base n
  tap_tab "$tabname" || return 1
  base="$OUT/${q}_${tabname}_${screen}.png"
  target="$base"; n=1
  # macOS commonly uses a case-insensitive filesystem.  Keep `KTV` and
  # `ktv` (or any existing run output) as separate evidence files instead of
  # silently overwriting the earlier capture.
  while find "$OUT" -maxdepth 1 -type f -iname "$(basename "$target")" -print -quit | grep -q .; do
    target="${base%.png}_副本${n}.png"
    n=$((n + 1))
  done
  if [ "$screen" = "1" ]; then
    shot_clean "$target"; echo "  ${tabname}_1 ok" | tee -a "$LOG"
  elif [ "$screen" = "2" ]; then
    scroll_down || return 1
    shot_clean "$target"; echo "  ${tabname}_2 ok" | tee -a "$LOG"
  elif [ "$screen" = "3" ]; then
    scroll_down && scroll_down || return 1
    shot_clean "$target"; echo "  ${tabname}_3 ok" | tee -a "$LOG"
  fi
}

mkdir -p "$OUT"
echo "START $(date '+%H:%M:%S')" | tee "$LOG"
echo "  词: ${QUERIES[*]}" | tee -a "$LOG"
echo "  tab: ${TABS[*]}" | tee -a "$LOG"
echo "  屏: ${SCREENS[*]}" | tee -a "$LOG"
device_preflight || { echo "ALL_DONE $(date '+%H:%M:%S')" | tee -a "$LOG"; exit 1; }

for q in "${QUERIES[@]}"; do
  echo "=== $q ===" | tee -a "$LOG"
  # Start each query from a real SearchActivity input connection.  On this
  # device the result-page bar is visually similar but cannot receive IME
  # commits after navigation.
  restart_adb_keyboard
  if ! ensure_input_page; then
    echo "  !! 无法回到搜索输入页，跳过 $q" | tee -a "$LOG"
    continue
  fi
  tap_bounds "$SEARCH_EDIT_BOUNDS" || { echo "  !! 无法点击动态定位的搜索输入框，跳过 $q" | tee -a "$LOG"; continue; }
  # 清空 + 输入 + 验证(重试3次)
  ok=0
  for try in 1 2 3; do
    # Returning from a result page can leave the EditText visible in XML but
    # without an active InputConnection.  Re-focus for every retry before
    # asking ADBKeyBoard to clear or commit Unicode text.
    tap_bounds "$SEARCH_EDIT_BOUNDS" || continue
    sleep 0.4
    clear_input
    input_query "$q"
    actual=$(get_edittext_text)
    if [ "$actual" = "$q" ]; then ok=1; break; fi
    echo "  输入验证($try): 实际='$actual' 期望='$q'" | tee -a "$LOG"
    restart_adb_keyboard
    sleep 1
  done
  if [ $ok -eq 0 ]; then
    echo "  !! 输入失败，跳过 $q" | tee -a "$LOG"
    continue
  fi
  if ! submit_search; then
    echo "  !! 搜索提交后未验证到结果页 Tab，跳过 $q" | tee -a "$LOG"
    continue
  fi
  # 遍历选定的 tab × 屏
  for tabname in "${TABS[@]}"; do
    for screen in "${SCREENS[@]}"; do
      shoot_screen "$q" "$tabname" "$screen" || echo "  !! ${tabname}_${screen} 截图失败" | tee -a "$LOG"
    done
  done
done
echo "ALL_DONE $(date '+%H:%M:%S')" | tee -a "$LOG"
