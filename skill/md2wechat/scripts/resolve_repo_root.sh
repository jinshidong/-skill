#!/usr/bin/env bash
set -euo pipefail

resolve_md2wechat_repo_root() {
  local script_dir skill_dir config_root config_file candidate

  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  skill_dir="$(cd "$script_dir/.." && pwd)"
  config_root="${XDG_CONFIG_HOME:-$HOME/.config}/md2wechat"
  config_file="$config_root/repo_root"

  if [ -n "${MD2WECHAT_REPO_ROOT:-}" ] && [ -f "${MD2WECHAT_REPO_ROOT}/publish_wechat.py" ]; then
    printf '%s\n' "$MD2WECHAT_REPO_ROOT"
    return 0
  fi

  if [ -f "$config_file" ]; then
    candidate="$(tr -d '\r' < "$config_file")"
    if [ -n "$candidate" ] && [ -f "$candidate/publish_wechat.py" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  fi

  for candidate in \
    "$HOME/MD2WeChat" \
    "$HOME/md2wechat" \
    "$skill_dir/../../../MD2WeChat" \
    "$skill_dir/../../../md2wechat"
  do
    if [ -f "$candidate/publish_wechat.py" ]; then
      printf '%s\n' "$(cd "$candidate" && pwd)"
      return 0
    fi
  done

  cat >&2 <<'EOF'
Unable to locate MD2WeChat repo root.
Set one of the following and retry:
  1. export MD2WECHAT_REPO_ROOT=/absolute/path/to/MD2WeChat
  2. echo /absolute/path/to/MD2WeChat > ~/.config/md2wechat/repo_root
EOF
  return 1
}
