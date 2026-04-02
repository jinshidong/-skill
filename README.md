# Markdown to WeChat HTML Converter

将 Markdown 转成微信公众号兼容 HTML，并通过微信官方草稿箱 API 自动创建单篇图文草稿。

## 当前默认工作流

- `md2wechat.py`：本地将 Markdown 渲染为微信公众号兼容 HTML
- `publish_wechat.py`：调用微信官方接口创建草稿
- 默认发布链路：
  - `stable_token`
  - `media/uploadimg`
  - `material/add_material?type=thumb`
  - `draft/add`

项目已经支持：

- 多种主题风格：`academic_gray`、`festival`、`tech`、`announcement`
- 正文图片自动上传到微信并替换为微信图片 URL
- 封面图自动转为 `thumb` 永久素材并生成 `thumb_media_id`
- 本地预检：标题、作者、摘要、封面、正文长度、图片可上传性
- UTF-8 中文内容直传，避免草稿箱出现 `\uXXXX` 字面量
- `45004 description size out of limit` 自动缩短摘要重试

## 历史实现

仓库里仍保留旧的 Playwright 浏览器自动化实现，供历史兼容和研究参考：

- [`src/wechat_publisher.py`](src/wechat_publisher.py)
- [`docs/Playwright.md`](docs/Playwright.md)

它不再是默认发布方式。

## 安装

### Python 依赖

```bash
pip install -r requirements.txt
```

### 依赖说明

- 必需：`requests`
- 必需：`beautifulsoup4`
- 必需：`Pillow`
- 推荐：`pygments`
- 可选：`matplotlib`、`sympy`
- 可选外部工具：`@mermaid-js/mermaid-cli`

安装 Mermaid CLI：

```bash
npm install -g @mermaid-js/mermaid-cli
```

## Markdown 格式

MD2WeChat 使用 YAML Front Matter 定义文章元信息。

常用字段：

- 必填：`title`、`date`
- 可选：`author`、`excerpt`、`digest`、`permalink`、`tags`、`cover`

示例：

```yaml
---
title: MD2WeChat 草稿箱验证
date: 2026-04-02
author: Team MD2WeChat
excerpt: 使用微信官方草稿箱 API 创建单篇图文草稿。
permalink: https://example.com/post
cover: ./images/pro.png
tags:
  - 微信公众号
  - 草稿箱
---
```

详细格式说明见：

- [docs/MARKDOWN_FORMAT.md](docs/MARKDOWN_FORMAT.md)

## 快速开始

### 1. 本地转换 HTML

```bash
python md2wechat.py article.md
python md2wechat.py article.md -o output.html -s tech
```

### 2. 配置微信凭证

需要环境变量：

```bash
export WECHAT_APPID=""
export WECHAT_SECRET=""
```

### 3. 本地预检

```bash
python publish_wechat.py article.md --cover cover.jpg --dry-run
```

如果 `front matter.cover` 已配置，可以省略 `--cover`。

### 4. 创建真实草稿

```bash
python publish_wechat.py article.md --cover cover.jpg
```

也可以覆盖元信息：

```bash
python publish_wechat.py article.md \
  --cover cover.jpg \
  --title "新的标题" \
  --author "新的作者" \
  --digest "新的摘要" \
  --source-url "https://example.com/post"
```

## 命令行说明

### `md2wechat.py`

```bash
python md2wechat.py <input.md> [-o output.html] [-s style] [--source source]
```

### `publish_wechat.py`

```bash
python publish_wechat.py <article.md> [--cover cover.jpg] [--style style] [--dry-run]
```

支持的主要参数：

- `--cover`：封面图片路径，优先级高于 `front matter.cover`
- `--title`：覆盖标题
- `--author`：覆盖作者
- `--digest`：覆盖摘要
- `--source`：覆盖文末来源信息
- `--source-url`：覆盖阅读原文链接
- `--dry-run`：只做本地预检，不调用微信接口

## 本地 skill 安装

仓库内置了统一 skill 模板，可安装到 `~/.agents/skills/md2wechat`：

```bash
./scripts/install_skill.sh
```

安装后可直接使用这些脚本：

- `~/.agents/skills/md2wechat/scripts/inspect.sh`
- `~/.agents/skills/md2wechat/scripts/validate_config.sh`
- `~/.agents/skills/md2wechat/scripts/dry_run.sh`
- `~/.agents/skills/md2wechat/scripts/create_draft.sh`
- `~/.agents/skills/md2wechat/scripts/convert_html.sh`

## 常见限制

- 标题建议不超过 32 字
- 作者建议不超过 16 字
- 摘要建议不超过 128 字
- 正文 HTML 需要控制在微信接口可接受范围内
- 真实上传前需要将当前出口 IP 加入公众号接口白名单

## 文档索引

- [docs/QUICK_START.md](docs/QUICK_START.md)：从零到一次成功验证
- [docs/PUBLISH_GUIDE.md](docs/PUBLISH_GUIDE.md)：官方草稿箱 API 发布说明
- [docs/USAGE.md](docs/USAGE.md)：Markdown 转 HTML 说明
- [docs/MARKDOWN_FORMAT.md](docs/MARKDOWN_FORMAT.md)：Front Matter 格式说明
- [docs/Playwright.md](docs/Playwright.md)：旧 Playwright 浏览器链路参考

## 许可证

MIT License
