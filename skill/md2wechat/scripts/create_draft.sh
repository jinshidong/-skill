#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="__REPO_ROOT__"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"

exec "$PYTHON_BIN" "$REPO_ROOT/publish_wechat.py" "$@"
