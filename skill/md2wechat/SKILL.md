---
name: md2wechat
description: Unified skill for local Markdown-to-WeChat workflows. Use this whenever the user wants Markdown 转微信公众号 HTML, 公众号终稿 camera-ready 整理, 默认作者/封面配置, 微信公众号草稿箱上传, draft dry-run validation, real WeChat draft creation, local repo troubleshooting, cover upload checks, config inspection, or article/image readiness checks using the verified local repo at __REPO_ROOT__.
---

# MD2WeChat

Use this skill for the verified local MD2WeChat repo at `__REPO_ROOT__`.

## When To Use

- Convert local Markdown into WeChat-compatible HTML.
- Turn reviewer-style Markdown into a camera-ready WeChat article plus sidecar notes.
- Apply long-lived article defaults such as author name, cover path, digest, and source URL.
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

- `scripts/camera_ready.sh`
- `scripts/inspect.sh`
- `scripts/validate_config.sh`
- `scripts/dry_run.sh`
- `scripts/create_draft.sh`
- `scripts/convert_html.sh`

Read these references only when needed:

- `references/profile-config.md`
- `references/camera-ready.md`

## Workflow

1. If the user asks for “公众号稿件”“转终稿”“camera ready”“给 vibe 配作者/封面”等内容， read `references/profile-config.md` first.
2. If the user is converting a reviewer draft into a publishable article, read `references/camera-ready.md`, then run `scripts/camera_ready.sh article.md` to bootstrap:
   - `<stem>.camera-ready.md`
   - `<stem>.camera-ready.notes.md`
3. Rewrite `<stem>.camera-ready.md` into a reader-facing final article. Keep 5 个备选标题、封面 prompt、正文配图 prompt 只放在 `.camera-ready.notes.md`，不要混进主稿。
4. Run `scripts/inspect.sh article.md [cover]` to inspect metadata, selected publish source, file existence, resolved author/cover sources, and recommended next step. The script prefers `article.camera-ready.md` when it exists.
5. Run `scripts/validate_config.sh` before real upload to check:
   - `WECHAT_APPID`
   - `WECHAT_SECRET`
   - whether credentials came from env or config
   - public outbound IP
   - whether the WeChat token endpoint accepts the current IP
6. Run `scripts/dry_run.sh article.md [--cover cover.jpg]` before real upload unless the user explicitly wants immediate upload.
7. Run `scripts/create_draft.sh article.md [--cover cover.jpg]` only after validation passes or the user explicitly asks for real upload.

## Core Commands

Bootstrap camera-ready files:

```bash
~/.agents/skills/md2wechat/scripts/camera_ready.sh article.md
```

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

If `article.camera-ready.md` exists, these commands prefer it automatically. If `front matter.cover` exists, `--cover` is optional.

## Validation Rules

- Title should stay within 32 chars.
- Author should stay within 16 chars.
- Digest should stay within 128 chars; the repo already retries with a shorter digest when WeChat returns `45004`.
- Publish metadata precedence is: CLI > front matter > `article_defaults` in `~/.config/md2wechat/config.yaml` > built-in fallback.
- Author fallback is `路人甲`.
- Cover fallback is `article_defaults.cover`, then repo default `examples/images/frontpage.png`.
- Real upload accepts credentials from env first, then from `wechat.appid` / `wechat.secret` in `~/.config/md2wechat/config.yaml`.
- If WeChat returns `40164`, add the reported IP to the WeChat whitelist and retry.

## Output Notes

- `scripts/camera_ready.sh` creates a normalized main draft and a sidecar notes file.
- `.camera-ready.notes.md` is never a publish source.
- Successful draft creation returns `thumb_media_id` and draft `media_id`.
- The repo uploads body images to WeChat and rewrites HTML image URLs automatically.
- The repo sends UTF-8 JSON with `ensure_ascii=False`, so Chinese content should appear normally in the draft.

## Safety

- `inspect` and `validate_config` do not create drafts.
- `dry_run` does not call draft creation.
- Real draft creation uploads article content and images to WeChat.
- Do not do real upload unless the user asked for it.
