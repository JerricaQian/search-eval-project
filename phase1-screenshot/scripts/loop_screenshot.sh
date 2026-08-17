#!/bin/bash
# 批量逐词截图,带设备掉线自动重连 + 落盘校验。
# 解决全量脚本一掉线连跳多词的问题:每词单独跑,跑完校验3张落盘,掉了只丢当前词。
#
# 用法:
#   1. 把要截的词写进词表文件,逗号分隔,如:
#        echo "库迪,蜜雪冰城,隆江猪脚饭" > ~/Desktop/search-eval-project/words.txt
#      或留空用脚本内置全量32词
#   2. bash loop_screenshot.sh [词表文件] [输出目录] [tab] [屏]
#      参数均可缺省:
#        词表文件  默认 项目根/words.txt(不存在则用内置32词)
#        输出目录  默认 项目根/screenshots
#        tab      默认 全部
#        屏       默认 1,2,3
#   3. 进度日志 /tmp/meituan_loop.log,用 Monitor 盯:
#        tail -f /tmp/meituan_loop.log | grep -E ">>>|✅|❌|LOOP_ALL_DONE|重连失败"
#
# 注意:macOS 无 timeout 命令,本脚本不依赖它,靠 run_scroll.sh 自身的 ALL_DONE 判断完成。

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$SKILL_DIR/scripts/run_scroll.sh"
# 项目根 = skill 目录的上一级(phase1-screenshot 的父目录)
PROJECT_DIR="$(cd "$SKILL_DIR/.." && pwd)"
WORDS_FILE="${1:-$PROJECT_DIR/words.txt}"
OUT="${2:-$PROJECT_DIR/screenshots}"
TABS="${3:-全部}"
SCREENS="${4:-1,2,3}"
LOG=/tmp/meituan_loop.log
: > "$LOG"

# 内置全量32词(词表文件不存在时用)
DEFAULT_WORDS="库迪,解压体验馆,游乐场,露营,万达广场,蜜雪冰城,隆江猪脚饭,生日蛋糕,安睡裤,榴莲,啤酒,药店,布洛芬,生理盐水,酒店,全季酒店,电竞房,迪士尼,相声,给阿嬷的情书,按摩,面部清洁,空调清洗,手机维修,剧本杀,体检,喜力啤酒整箱,烧烤,西瓜,盒马,理发,漂流"

if [ -f "$WORDS_FILE" ]; then
  WORDS_STR=$(cat "$WORDS_FILE")
else
  WORDS_STR="$DEFAULT_WORDS"
  echo "词表 $WORDS_FILE 不存在,用内置32词" | tee -a "$LOG"
fi

reconnect() {
  for i in $(seq 1 20); do
    adb kill-server 2>/dev/null; adb start-server 2>/dev/null; sleep 1.5
    [ "$(adb get-state 2>/dev/null)" = "device" ] && return 0
  done
  return 1
}

IFS=',' read -ra WORDS <<< "$WORDS_STR"
total=${#WORDS[@]}; idx=0; failed=""
mkdir -p "$OUT"

for w in "${WORDS[@]}"; do
  idx=$((idx+1))
  echo ">>> [$idx/$total] 开始: $w" | tee -a "$LOG"
  # 设备在线检查
  if [ "$(adb get-state 2>/dev/null)" != "device" ]; then
    echo "  设备掉线,重连中..." | tee -a "$LOG"
    reconnect || { echo "  !! 重连失败,跳过 $w" | tee -a "$LOG"; failed="$failed,$w"; continue; }
  fi
  adb shell ime set com.android.adbkeyboard/.AdbIME >/dev/null 2>&1
  # 回搜索输入页
  adb shell input tap 68 202 2>&1; sleep 2
  adb shell input tap 465 365 2>&1; sleep 2
  : > /tmp/meituan_scroll.log
  bash "$RUN" "$w" "$TABS" "$SCREENS" >> /tmp/scroll_run.out 2>&1
# 保留 0 字节截图（设备卡顿产物）以便审计；由工作流将路径和原因归档到 .artifacts。
# 落盘校验:每词应有 (tab数×屏数) 张,全部tab+3屏=3张
  n=$(ls "$OUT/${w}"_*.png 2>/dev/null | wc -l | tr -d ' ')
  if [ "$n" -ge 3 ]; then
    echo "  ✅ $w 完成 ($n张)" | tee -a "$LOG"
  else
    echo "  ❌ $w 未完成 ($n张),稍后补" | tee -a "$LOG"
    failed="$failed,$w"
  fi
done

echo "=== LOOP_ALL_DONE ===" | tee -a "$LOG"
if [ -n "$failed" ]; then
  failed="${failed#,}"
  echo "$failed" > /tmp/meituan_failed.txt
  echo "失败词已写入 /tmp/meituan_failed.txt: $failed" | tee -a "$LOG"
  echo "重跑: bash $0 /tmp/meituan_failed.txt \"$OUT\" \"$TABS\" \"$SCREENS\"" | tee -a "$LOG"
fi
