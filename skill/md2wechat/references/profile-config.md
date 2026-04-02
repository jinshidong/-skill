# Profile Config

Use this reference when the task involves长期配置作者、封面、摘要、来源信息，或者要解释为什么发布链路读不到公众号凭证。

## Config File

- Path: `~/.config/md2wechat/config.yaml`
- Repo path discovery remains in `~/.config/md2wechat/repo_root`

## Supported Keys

```yaml
wechat:
  appid: wx...
  secret: ...

article_defaults:
  author: 路人甲
  cover: /absolute/path/to/cover.png
  digest: 默认摘要
  source: 来源名称
  source_url: https://example.com/post

camera_ready:
  enabled: true
  style: viral-writer-wechat
```

## Resolution Rules

- Publish credentials: env `WECHAT_APPID` / `WECHAT_SECRET` first, then `wechat.appid` / `wechat.secret`
- Metadata: CLI > front matter > `article_defaults` > built-in fallback
- Author fallback: `路人甲`
- Default cover fallback: `article_defaults.cover`, then repo default `examples/images/frontpage.png`

## Path Rules

- `article_defaults.cover` absolute path: use as-is
- `article_defaults.cover` relative path: resolve relative to the config file directory first, then fall back to CWD / article directory
- `front matter.cover` relative path: resolve relative to the article directory

## Inspect Expectations

`scripts/inspect.sh` should expose:

- `selected_article_path`
- `author_source`
- `cover_source`
- `credential_source`

Use these fields to explain why the agent selected a specific draft or why a default was applied.
