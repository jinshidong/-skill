---
name: md2wechat
description: Unified skill for local Markdown-to-WeChat workflows. Use this whenever the user wants Markdown 转微信公众号 HTML, 微信公众号草稿箱上传, draft dry-run validation, real WeChat draft creation, local repo troubleshooting, cover upload checks, config inspection, or article/image readiness checks using the verified local repo at __REPO_ROOT__.
---

# MD2WeChat

Use this skill for the verified local MD2WeChat repo at `__REPO_ROOT__`.

## When To Use

- Convert local Markdown into WeChat-compatible HTML.
- Inspect article metadata, cover requirements, and upload readiness.
- Dry-run a WeChat draft before upload.
- Create a real WeChat Official Account draft.
- Troubleshoot WeChat API failures such as `40164` whitelist errors or `45004` digest/content issues.

## Local Runtime

- Repo root: `__REPO_ROOT__`
- Preferred Python: `__REPO_ROOT__/.venv/bin/python`
- Draft CLI: `__REPO_ROOT__/publish_wechat.py`
- HTML converter: `__REPO_ROOT__/md2wechat.py`

Prefer the scripts bundled with this skill:

- `scripts/inspect.sh`
- `scripts/validate_config.sh`
- `scripts/dry_run.sh`
- `scripts/create_draft.sh`
- `scripts/convert_html.sh`

## Workflow

1. Run `scripts/inspect.sh article.md [cover]` to inspect metadata, file existence, and recommended next step.
2. Run `scripts/validate_config.sh` before real upload to check:
   - `WECHAT_APPID`
   - `WECHAT_SECRET`
   - public outbound IP
   - whether the WeChat token endpoint accepts the current IP
3. Run `scripts/dry_run.sh article.md [--cover cover.jpg]` before real upload unless the user explicitly wants immediate upload.
4. Run `scripts/create_draft.sh article.md [--cover cover.jpg]` only after validation passes or the user explicitly asks for real upload.

## Core Commands

Inspect article and environment:

```bash
~/.agents/skills/md2wechat/scripts/inspect.sh article.md
~/.agents/skills/md2wechat/scripts/validate_config.sh
```

Convert Markdown to local HTML:

```bash
~/.agents/skills/md2wechat/scripts/convert_html.sh article.md -o output.html
```

Dry-run a draft:

```bash
~/.agents/skills/md2wechat/scripts/dry_run.sh article.md --cover cover.jpg
```

Create a real draft:

```bash
~/.agents/skills/md2wechat/scripts/create_draft.sh article.md --cover cover.jpg
```

If `front matter.cover` exists, `--cover` is optional.

## Validation Rules

- Title should stay within 32 chars.
- Author should stay within 16 chars.
- Digest should stay within 128 chars; the repo already retries with a shorter digest when WeChat returns `45004`.
- Real upload requires `WECHAT_APPID` and `WECHAT_SECRET`.
- If WeChat returns `40164`, add the reported IP to the WeChat whitelist and retry.

## Output Notes

- Successful draft creation returns `thumb_media_id` and draft `media_id`.
- The repo uploads body images to WeChat and rewrites HTML image URLs automatically.
- The repo sends UTF-8 JSON with `ensure_ascii=False`, so Chinese content should appear normally in the draft.

## Safety

- `inspect` and `validate_config` do not create drafts.
- `dry_run` does not call draft creation.
- Real draft creation uploads article content and images to WeChat.
- Do not do real upload unless the user asked for it.
