#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/resolve_repo_root.sh"
REPO_ROOT="$(resolve_md2wechat_repo_root)"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"

exec "$PYTHON_BIN" "$REPO_ROOT/camera_ready_wechat.py" "$@"
