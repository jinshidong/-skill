# 快速开始指南

本文档对应当前仓库已经切换后的默认方案：本地渲染 Markdown，再通过微信官方草稿箱 API 创建单篇图文草稿。

如果你想看旧的浏览器自动化实现，请改看 [Playwright.md](Playwright.md)。

## 1. 安装依赖

```bash
pip install -r requirements.txt
```

如果需要 Mermaid 图表转换，可额外安装：

```bash
npm install -g @mermaid-js/mermaid-cli
```

如果你想把这个项目作为 agent skill 安装到本机，也可以直接执行：

```bash
npx skills add https://github.com/jinshidong/-skill/tree/main/skill/md2wechat -g -y
```

如果你是通过 `npx` 安装 skill，建议额外配置仓库路径，二选一即可：

```bash
export MD2WECHAT_REPO_ROOT="/absolute/path/to/MD2WeChat"
```

或：

```bash
mkdir -p ~/.config/md2wechat
echo "/absolute/path/to/MD2WeChat" > ~/.config/md2wechat/repo_root
```

## 2. 配置微信凭证与默认元信息

真实上传微信草稿前，必须配置：

```bash
export WECHAT_APPID=""
export WECHAT_SECRET=""
```

如果你通过 `npx` 安装 skill，推荐同时配置：

```bash
export MD2WECHAT_REPO_ROOT="/absolute/path/to/MD2WeChat"
```

变量说明：

- `WECHAT_APPID`：必填，公众号后台 AppID
- `WECHAT_SECRET`：必填，公众号后台 AppSecret
- `MD2WECHAT_REPO_ROOT`：可选，`npx` 安装 skill 时推荐设置；直接在仓库内运行 `python publish_wechat.py` 时通常不需要

如果你是长期使用，建议写入 `~/.bashrc`：

```bash
export WECHAT_APPID=""
export WECHAT_SECRET=""
export MD2WECHAT_REPO_ROOT="/absolute/path/to/MD2WeChat"
```

写完后执行：

```bash
source ~/.bashrc
```

注意：

- 已经启动的 agent / openclaw 进程不一定会自动拿到你刚写进 `~/.bashrc` 的变量
- 更稳的方式是重启对应进程，或者把仓库路径写进 `~/.config/md2wechat/repo_root`

如果你希望给 vibe / agent 配固定作者、封面和摘要，也可以写入：

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

凭证解析优先级是：

1. 环境变量
2. `~/.config/md2wechat/config.yaml`

文章元信息优先级是：

1. CLI 参数
2. front matter
3. `article_defaults`
4. fallback

## 3. 准备 Markdown 文件

最小 front matter 示例：

```markdown
---
title: 我的第一篇草稿
date: 2026-04-02
author: 张三
excerpt: 这是一篇用于验证草稿箱 API 的短文。
cover: ./images/pro.png
tags:
  - 微信公众号
  - 草稿箱
---

# 标题

这是文章正文。
```

说明：

- `title`、`date` 必填
- `cover` 建议直接写在 front matter 里
- `excerpt` 会作为草稿摘要；如果同时存在 `digest`，优先使用 `digest`

## 4. 先生成 camera-ready 终稿（可选但推荐）

如果原稿还是 reviewer 口吻，可以先生成：

```bash
python camera_ready_wechat.py article.md
```

会得到：

- `article.camera-ready.md`
- `article.camera-ready.notes.md`

其中 `.notes.md` 不参与发布。

## 5. 先做本地预检

如果你是通过 skill 使用，建议先跑最前面的元数据自检：

```bash
~/.agents/skills/md2wechat/scripts/inspect.sh article.md
```

这一步会在真正 `dry_run` 之前先拦住硬限制问题，例如：

- 标题超过 32 字
- 作者超过 16 字
- 摘要超过 128 字

如果 `inspect.sh` 返回非 0，请先修正文案，再继续后面的 `dry_run` 或真实上传。

```bash
python publish_wechat.py article.md --dry-run
```

如果文章里没有 `front matter.cover`，需要显式传封面：

```bash
python publish_wechat.py article.md --cover cover.jpg --dry-run
```

如果 `--cover` 和 `front matter.cover` 都没提供，当前版本会自动回退到仓库内置默认封面：

- `examples/images/frontpage.png`

本地预检会检查：

- 标题长度
- 作者长度
- 摘要长度
- 正文 HTML 长度
- 封面是否存在
- 正文图片是否可处理

如果同目录存在 `article.camera-ready.md`，skill 脚本会自动优先使用它。

## 6. 创建真实草稿

```bash
python publish_wechat.py article.md
```

或者：

```bash
python publish_wechat.py article.md --cover cover.jpg
```

常用覆盖参数：

```bash
python publish_wechat.py article.md \
  --cover cover.jpg \
  --title "覆盖标题" \
  --author "覆盖作者" \
  --digest "覆盖摘要" \
  --source-url "https://example.com/post"
```

## 7. 只做 HTML 转换

```bash
python md2wechat.py article.md
python md2wechat.py article.md -o output.html -s tech
```

## 8. 用仓库自带短文做 smoke test

仓库内置了一篇已验证过长度约束的短文：

```bash
python publish_wechat.py examples/2026-04-02-draft-api-smoke-test.md --dry-run
python publish_wechat.py examples/2026-04-02-draft-api-smoke-test.md
```

## 常见问题

### 1. `errcode=40164 invalid ip`

说明当前出口 IP 不在公众号后台白名单里。  
去微信公众平台后台的接口 IP 白名单中加入报错里给出的 IP，再重试。

### 2. `description size out of limit`

说明摘要过长。  
当前实现已经会自动缩短摘要重试一次，但最好还是把 `excerpt` 或 `digest` 控制得更短。

### 3. `正文 HTML 长度超过微信限制`

说明文章太长，或者图片/代码块过多。  
可以先用更短的文章验证流程，再逐步迁移正式内容。

### 4. 草稿箱里出现 `\u65e5\u671f...`

这通常是旧版本请求序列化方式导致的历史草稿问题。  
当前实现已经改成显式 UTF-8 JSON 发送，新创建的草稿应正常显示中文。

## 推荐验证顺序

1. `python publish_wechat.py article.md --dry-run`
2. 处理本地预检错误
3. 确认凭证与 IP 白名单
4. `python publish_wechat.py article.md`

## 相关文档

- [PUBLISH_GUIDE.md](PUBLISH_GUIDE.md)
- [USAGE.md](USAGE.md)
- [MARKDOWN_FORMAT.md](MARKDOWN_FORMAT.md)
