#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/resolve_repo_root.sh"
REPO_ROOT="$(resolve_md2wechat_repo_root)"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"

if [ "$#" -lt 1 ]; then
  exec "$PYTHON_BIN" "$REPO_ROOT/publish_wechat.py" "$@" --dry-run
fi

RESOLVED_ARTICLE="$("$PYTHON_BIN" - <<'PY' "$1" "$REPO_ROOT"
import sys
from pathlib import Path

repo_root = Path(sys.argv[2])
sys.path.insert(0, str(repo_root / "src"))
from md2wechat_config import resolve_publish_article_path

try:
    print(resolve_publish_article_path(sys.argv[1]))
except ValueError as exc:
    print(exc, file=sys.stderr)
    raise SystemExit(1)
PY
)"

shift
exec "$PYTHON_BIN" "$REPO_ROOT/publish_wechat.py" "$RESOLVED_ARTICLE" "$@" --dry-run
