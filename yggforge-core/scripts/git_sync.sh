#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 兼容双风格：新 ygg sync/push；旧 --action update|update-push 直调 git_sync.py。

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
    --action|--repo|--remote|--branch) legacy=1; break ;;
    --action=*|--repo=*|--remote=*|--branch=*) legacy=1; break ;;
  esac
done

if [[ "$legacy" -eq 1 ]]; then
  PYTHON_BIN="$(find_python)"
  exec "$PYTHON_BIN" -X utf8 "$SCRIPT_DIR/cmds/ops/git_sync.py" "$@"
fi

joined=" $* "
if [[ "$joined" == *" push "* || "$joined" == *"update-push"* ]]; then
  exec "$SCRIPT_DIR/ygg.sh" push "$@"
fi

exec "$SCRIPT_DIR/ygg.sh" sync "$@"
