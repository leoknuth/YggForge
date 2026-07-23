#!/usr/bin/env bash
# Thin wrapper: forward to the deployable core CLI.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/yggforge-core/scripts/ygg.sh" "$@"
