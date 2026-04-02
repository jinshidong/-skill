#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_TEMPLATE_DIR="$REPO_ROOT/skill/md2wechat"
TARGET_SKILL_DIR="${HOME}/.agents/skills/md2wechat"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python interpreter not found: $PYTHON_BIN" >&2
  exit 1
fi

mkdir -p "$REPO_ROOT/.venv"
if [ ! -x "$REPO_ROOT/.venv/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$REPO_ROOT/.venv"
fi

"$REPO_ROOT/.venv/bin/pip" install -r "$REPO_ROOT/requirements.txt"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$TMP_DIR/md2wechat"
cp -R "$SKILL_TEMPLATE_DIR"/. "$TMP_DIR/md2wechat/"

while IFS= read -r -d '' file; do
  sed -i "s|__REPO_ROOT__|$REPO_ROOT|g" "$file"
done < <(find "$TMP_DIR/md2wechat" -type f -print0)

mkdir -p "${HOME}/.agents/skills"
rm -rf "$TARGET_SKILL_DIR"
mkdir -p "$TARGET_SKILL_DIR"
cp -R "$TMP_DIR/md2wechat"/. "$TARGET_SKILL_DIR/"
chmod +x "$TARGET_SKILL_DIR"/scripts/*.sh

cat <<EOF
Installed md2wechat skill to:
  $TARGET_SKILL_DIR

Repo root:
  $REPO_ROOT

Quick checks:
  $TARGET_SKILL_DIR/scripts/validate_config.sh
  $TARGET_SKILL_DIR/scripts/inspect.sh $REPO_ROOT/examples/2026-04-02-draft-api-smoke-test.md
EOF
