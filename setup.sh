#!/bin/bash
# 美团搜索结果页评测工作流：跨机器环境检查与可选真机准备。
# 用法：
#   bash setup.sh                # 仅检查本地评测/标注环境（已有截图场景）
#   bash setup.sh --with-device  # 额外检查 Android 真机、ADBKeyboard 与美团 App（现场截图场景）
#   bash setup.sh --help

set -u

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
WITH_DEVICE=false

case "${1:-}" in
  "") ;;
  --with-device) WITH_DEVICE=true ;;
  -h|--help)
    echo "用法: bash setup.sh [--with-device]"
    echo "  默认：检查 Python、Node、项目结构与 Python 图像依赖，适用于复用已有截图。"
    echo "  --with-device：额外检查 Android 真机、ADBKeyboard 和美团 App，适用于现场截图。"
    exit 0
    ;;
  *)
    echo "未知参数: $1（可用 --help 查看用法）" >&2
    exit 2
    ;;
esac

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'; NC='\033[0m'
ok() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err() { echo -e "${RED}[✗]${NC} $1"; }

FAILED=0
check_command() {
  local command_name="$1"
  local hint="$2"
  if command -v "$command_name" >/dev/null 2>&1; then
    ok "$command_name 已安装: $(command -v "$command_name")"
  else
    err "$command_name 未安装。$hint"
    FAILED=1
  fi
}

echo "================ 美团搜索结果页评测工作流：环境检查 ================"
echo "项目目录: $PROJECT_DIR"
echo "运行模式: $([ "$WITH_DEVICE" = true ] && echo '现场截图 + 评测' || echo '已有截图评测')"
echo

# ---------- 1. 项目结构 ----------
echo "--- 1/5 项目结构 ---"
for required_path in \
  "$PROJECT_DIR/workflow/meituan_eval_workflow.js" \
  "$PROJECT_DIR/phase1-screenshot/SKILL.md" \
  "$PROJECT_DIR/phase2-card-annotation/SKILL.md" \
  "$PROJECT_DIR/phase5-report/SKILL.md" \
  "$PROJECT_DIR/requirements.txt"; do
  if [ -r "$required_path" ]; then
    ok "可读取: ${required_path#$PROJECT_DIR/}"
  else
    err "缺失或不可读: ${required_path#$PROJECT_DIR/}"
    FAILED=1
  fi
done

# ---------- 2. 基础运行环境 ----------
echo
echo "--- 2/5 Python / Node ---"
check_command python3 "请安装 Python 3.10 或更高版本。"
check_command node "请安装 Node.js 18 或更高版本。"
if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PY'
import importlib.util
import sys
missing = [name for name, module in {
    "Pillow": "PIL",
    "numpy": "numpy",
    "opencv-python": "cv2",
    "PyYAML": "yaml",
}.items() if importlib.util.find_spec(module) is None]
if missing:
    print("[✗] 缺少 Python 依赖: " + ", ".join(missing))
    print("    安装命令: python3 -m pip install -r requirements.txt")
    sys.exit(1)
print("[✓] Python 图像与 YAML 依赖已就绪")
PY
  [ $? -eq 0 ] || FAILED=1
fi

# ---------- 3. CatPaw 工作流前置 ----------
echo
echo "--- 3/5 CatPaw 工作流前置 ---"
if [ -f "$PROJECT_DIR/CLAUDE.md" ] && [ -d "$PROJECT_DIR/.claude" ]; then
  ok "项目规则与 Agent 配置已就绪"
else
  warn "未发现完整的 .claude/ 配置；请确认在 CatPaw 中从项目根目录打开本仓库。"
fi
warn "请在 CatPaw 中打开项目根目录，并从 workflow/meituan_eval_workflow.js 发起工作流。"

# ---------- 4. 可选真机检查 ----------
echo
echo "--- 4/5 Android 真机（可选） ---"
if [ "$WITH_DEVICE" = false ]; then
  warn "已跳过真机检查；若只评已有 screenshots/，这是正常的。"
  warn "要现场截图时运行: bash setup.sh --with-device"
else
  check_command adb "macOS 可用 Homebrew 安装: brew install --cask android-platform-tools"
  if command -v adb >/dev/null 2>&1; then
    state=$(adb get-state 2>/dev/null || true)
    if [ "$state" = "device" ]; then
      ok "设备已连接: $(adb shell getprop ro.product.model 2>/dev/null || echo '未知设备')"
      if adb shell pm list packages 2>/dev/null | grep -q 'com.android.adbkeyboard'; then
        ok "ADBKeyBoard 已安装"
      elif [ -f "$PROJECT_DIR/ADBKeyboard.apk" ]; then
        warn "ADBKeyBoard 尚未安装；运行现场截图前可执行: adb install -r ADBKeyboard.apk"
      else
        err "未找到 ADBKeyboard.apk，无法准备中文 ADB 输入。"
        FAILED=1
      fi
      if adb shell pm list packages 2>/dev/null | grep -q 'com.sankuai.meituan'; then
        ok "美团 App 已安装（请使用者自行确认登录态）"
      else
        warn "未检测到美团 App；现场截图前请安装并登录。"
      fi
    else
      err "未检测到可用 Android 设备。请连接手机、开启 USB 调试并解锁屏幕。"
      FAILED=1
    fi
  fi
fi

# ---------- 5. macOS 文件权限 ----------
echo
echo "--- 5/5 文件权限 ---"
if [ "$(uname)" = "Darwin" ]; then
  if [ -r "$PROJECT_DIR/screenshots" ] || [ ! -e "$PROJECT_DIR/screenshots" ]; then
    ok "项目路径可访问"
  else
    err "无法访问 screenshots/，请检查目录权限。"
    FAILED=1
  fi
  warn "若 CatPaw 无法读取桌面截图，请在“系统设置 → 隐私与安全性 → 完全磁盘访问权限”中授予 CatPaw 访问权限后重启应用。"
fi

echo
if [ "$FAILED" -eq 0 ]; then
  ok "环境检查通过。下一步：在 CatPaw 中执行 /run-eval，或调用 workflow/meituan_eval_workflow.js。"
else
  err "环境检查发现问题；修复上述失败项后再运行工作流。"
  exit 1
fi
