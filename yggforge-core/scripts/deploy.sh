#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 兼容双风格：
# 1) 新：ygg 子命令风格（推荐）—— deploy.sh link cursor / deploy.sh status cursor
# 2) 旧：deploy.py 旗标风格 —— --action deploy --mode link --targets cursor

find_python() {
  if command -v python3 >/dev/null 2>&1; then echo python3
  elif command -v python >/dev/null 2>&1; then echo python
  else
    echo "Python 3 is required but neither python3 nor python was found in PATH." >&2
    exit 1
  fi
}

legacy=0
for a in "$@"; do
  case "$a" in
    --action|--mode|--targets|--preview-only|--preview-lines) legacy=1; break ;;
    --action=*|--mode=*|--targets=*|--preview-lines=*) legacy=1; break ;;
  esac
done

if [[ "$legacy" -eq 1 ]]; then
  PYTHON_BIN="$(find_python)"
  exec "$PYTHON_BIN" -X utf8 "$SCRIPT_DIR/cmds/ops/deploy.py" "$@"
fi

if [[ "${1:-}" == "status" || "${1:-}" == "import" ]]; then
  exec "$SCRIPT_DIR/ygg.sh" "$@"
fi

exec "$SCRIPT_DIR/ygg.sh" deploy "$@"
