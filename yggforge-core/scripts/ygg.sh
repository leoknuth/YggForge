#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/ygg.py"

if command -v python3.8 >/dev/null 2>&1; then
  PYTHON_BIN="python3.8"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python 3 is required but neither python3.8, python3 nor python was found in PATH." >&2
  exit 1
fi

exec "$PYTHON_BIN" -X utf8 "$PYTHON_SCRIPT" "$@"
