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

## 2. 配置微信凭证

当前实现只读取环境变量：

```bash
export WECHAT_APPID=""
export WECHAT_SECRET=""
```

如果你是长期使用，建议写入 `~/.bashrc`：

```bash
export WECHAT_APPID=""
export WECHAT_SECRET=""
```

写完后执行：

```bash
source ~/.bashrc
```

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

## 4. 先做本地预检

```bash
python publish_wechat.py article.md --dry-run
```

如果文章里没有 `front matter.cover`，需要显式传封面：

```bash
python publish_wechat.py article.md --cover cover.jpg --dry-run
```

本地预检会检查：

- 标题长度
- 作者长度
- 摘要长度
- 正文 HTML 长度
- 封面是否存在
- 正文图片是否可处理

## 5. 创建真实草稿

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

## 6. 只做 HTML 转换

```bash
python md2wechat.py article.md
python md2wechat.py article.md -o output.html -s tech
```

## 7. 用仓库自带短文做 smoke test

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
