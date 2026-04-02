#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Support npx-installed skills where __REPO_ROOT__ is not templated.
source "$SCRIPT_DIR/resolve_repo_root.sh"
REPO_ROOT="$(resolve_md2wechat_repo_root)"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <article.md> [cover.jpg]"
  exit 1
fi

ARTICLE_PATH="$1"
COVER_PATH="${2:-}"

"$PYTHON_BIN" - <<'PY' "$ARTICLE_PATH" "$COVER_PATH" "$REPO_ROOT"
import re
import sys
from pathlib import Path

repo_root = sys.argv[3]
sys.path.insert(0, str(Path(repo_root) / "src"))
from md2wechat import MarkdownParser
from md2wechat_config import (
    DEFAULT_AUTHOR_NAME,
    get_article_defaults,
    get_camera_ready_config,
    load_md2wechat_config,
    resolve_path_from_value,
    resolve_publish_article_path,
    resolve_value,
    resolve_wechat_credentials,
)

TITLE_LIMIT = 32
AUTHOR_LIMIT = 16
DIGEST_LIMIT = 128

requested_article = Path(sys.argv[1]).expanduser().resolve()
cover_arg = sys.argv[2].strip() if len(sys.argv) > 2 else ""

try:
    article = resolve_publish_article_path(requested_article)
except ValueError as exc:
    print(f"article_error={exc}")
    raise SystemExit(1)

if not article.exists():
    print(f"article_exists=0 path={article}")
    raise SystemExit(1)

runtime_config = load_md2wechat_config()
article_defaults = get_article_defaults(runtime_config)
camera_ready = get_camera_ready_config(runtime_config)
credentials = resolve_wechat_credentials(runtime_config)

content = article.read_text(encoding="utf-8")
parser = MarkdownParser(content)
fm = parser.front_matter

title = str(fm.get("title", "") or "").strip()
raw_author = str(fm.get("author", "") or "").strip()
raw_digest = (
    str(fm.get("digest", "") or "")
    or str(fm.get("excerpt", "") or "")
    or str(fm.get("summary", "") or "")
    or str(fm.get("description", "") or "")
).strip()

heading = ""
for line in parser.body.splitlines():
    m = re.match(r"^\s{0,3}#\s+(.+?)\s*#*\s*$", line)
    if m:
        heading = m.group(1).strip()
        break

resolved_title = resolve_value(None, title, "", heading)
resolved_author = resolve_value(None, raw_author, article_defaults.get("author", ""), DEFAULT_AUTHOR_NAME)
resolved_digest = resolve_value(None, raw_digest, article_defaults.get("digest", ""), "")
resolved_source_url = resolve_value(None, fm.get("permalink", ""), article_defaults.get("source_url", ""), "")
resolved_cover = resolve_value(
    cover_arg or None,
    str(fm.get("cover", "") or fm.get("cover_image", "") or ""),
    article_defaults.get("cover", ""),
    "",
)

if resolved_cover.source == "fallback":
    cover_path = Path(repo_root) / "examples" / "images" / "frontpage.png"
else:
    bases = [Path.cwd(), article.parent]
    if resolved_cover.source == "config":
        bases.insert(0, runtime_config.path.parent)
    cover_path = resolve_path_from_value(resolved_cover.value, bases=bases)

issues = []

if not resolved_title.value:
    issues.append("title_missing")
elif len(resolved_title.value) > TITLE_LIMIT:
    issues.append(f"title_too_long>{TITLE_LIMIT}")

if len(resolved_author.value) > AUTHOR_LIMIT:
    issues.append(f"author_too_long>{AUTHOR_LIMIT}")

if len(resolved_digest.value) > DIGEST_LIMIT:
    issues.append(f"digest_too_long>{DIGEST_LIMIT}")
if not cover_path.exists():
    issues.append("cover_missing")

print(f"article_exists=1 path={article}")
print(f"requested_article_path={requested_article}")
print(f"selected_article_path={article}")
print(f"article_selection={'camera_ready' if article != requested_article else 'requested'}")
print(f"title={resolved_title.value}")
print(f"title_source={resolved_title.source}")
print(f"title_len={len(resolved_title.value)}")
print(f"title_limit={TITLE_LIMIT}")
print(f"author={resolved_author.value}")
print(f"resolved_author={resolved_author.value}")
print(f"author_source={resolved_author.source}")
print(f"author_len={len(resolved_author.value)}")
print(f"author_limit={AUTHOR_LIMIT}")
print(f"digest={resolved_digest.value}")
print(f"digest_source={resolved_digest.source}")
print(f"digest_len={len(resolved_digest.value)}")
print(f"digest_limit={DIGEST_LIMIT}")
print(f"permalink={resolved_source_url.value}")
print(f"source_url_source={resolved_source_url.source}")
print(f"cover_path={cover_path}")
print(f"resolved_cover_path={cover_path}")
print(f"cover_source={resolved_cover.source}")
print(f"cover_exists={1 if cover_path.exists() else 0}")
print(f"wechat_appid_set={1 if credentials.appid else 0}")
print(f"wechat_secret_set={1 if credentials.secret else 0}")
print(f"credential_source={credentials.source}")
print(f"config_path={runtime_config.path}")
print(f"camera_ready_enabled={1 if camera_ready['enabled'] else 0}")
print(f"camera_ready_style={camera_ready['style']}")
print(f"preflight_status={'pass' if not issues else 'fail'}")
print(f"issues={','.join(issues)}")
print(f"recommended_next_step={'dry_run' if not issues else 'fix_metadata'}")

if issues:
    raise SystemExit(2)
PY
