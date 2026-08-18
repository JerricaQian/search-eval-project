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

# Keep local OCR from monopolising a laptop.  PaddleOCR is opt-in and must be
# run on bounded card/region crops; these caps also make an accidental full
# invocation less disruptive.
OCR_THREADS="${PHASE2_OCR_THREADS:-2}"
export OMP_NUM_THREADS="$OCR_THREADS"
export MKL_NUM_THREADS="$OCR_THREADS"
export OPENBLAS_NUM_THREADS="$OCR_THREADS"
export PADDLE_NUM_THREADS="$OCR_THREADS"

exec "$PYTHON_BIN" "$SCRIPT_DIR/extract_cv_facts.py" "$@"
