#!/usr/bin/env bash
# Run CV/OCR extraction with the project virtual environment when available.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="${SEARCH_EVAL_PYTHON:-}"

if [[ -z "$PYTHON_BIN" && -x "$PROJECT_DIR/.venv/bin/python" ]] \
  && "$PROJECT_DIR/.venv/bin/python" -c 'import numpy, PIL, cv2' >/dev/null 2>&1; then
  PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
fi
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/extract_cv_facts.py" "$@"
