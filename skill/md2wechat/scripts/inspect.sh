#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="__REPO_ROOT__"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <article.md> [cover.jpg]"
  exit 1
fi

ARTICLE_PATH="$1"
COVER_PATH="${2:-}"

"$PYTHON_BIN" - <<'PY' "$ARTICLE_PATH" "$COVER_PATH" "$REPO_ROOT"
import os
import re
import sys
from pathlib import Path

repo_root = sys.argv[3]
sys.path.insert(0, str(Path(repo_root) / "src"))
from md2wechat import MarkdownParser

article = Path(sys.argv[1]).expanduser().resolve()
cover_arg = sys.argv[2].strip() if len(sys.argv) > 2 else ""

if not article.exists():
    print(f"article_exists=0 path={article}")
    raise SystemExit(1)

content = article.read_text(encoding="utf-8")
parser = MarkdownParser(content)
fm = parser.front_matter

title = str(fm.get("title", "") or "").strip()
author = str(fm.get("author", "") or "").strip()
digest = (
    str(fm.get("digest", "") or "")
    or str(fm.get("excerpt", "") or "")
    or str(fm.get("summary", "") or "")
    or str(fm.get("description", "") or "")
).strip()
cover = cover_arg or str(fm.get("cover", "") or fm.get("cover_image", "") or "").strip()
if cover:
    cover_path = Path(cover).expanduser()
    if not cover_path.is_absolute():
        cover_path = (article.parent / cover_path).resolve()
else:
    cover_path = None

heading = ""
for line in parser.body.splitlines():
    m = re.match(r"^\s{0,3}#\s+(.+?)\s*#*\s*$", line)
    if m:
        heading = m.group(1).strip()
        break

resolved_title = title or heading
print(f"article_exists=1 path={article}")
print(f"title={resolved_title}")
print(f"title_len={len(resolved_title)}")
print(f"author={author}")
print(f"author_len={len(author)}")
print(f"digest={digest}")
print(f"digest_len={len(digest)}")
print(f"permalink={str(fm.get('permalink', '') or '').strip()}")
print(f"cover_path={cover_path if cover_path else ''}")
print(f"cover_exists={1 if cover_path and cover_path.exists() else 0}")
print(f"wechat_appid_set={1 if os.getenv('WECHAT_APPID') else 0}")
print(f"wechat_secret_set={1 if os.getenv('WECHAT_SECRET') else 0}")
print(f"recommended_next_step={'dry_run' if resolved_title else 'fix_metadata'}")
PY
