# Markdown to WeChat HTML Converter
demo文章：https://mp.weixin.qq.com/s/8YamtCoKVxrJb8kaSW9dmg

将 Markdown 转成微信公众号兼容 HTML，并通过微信官方草稿箱 API 自动创建单篇图文草稿。

MD2WeChat 现在同时覆盖三类工作流：

- 本地把 Markdown 渲染成微信公众号兼容 HTML
- 用微信官方接口创建真实草稿
- 把 reviewer 风格原稿整理成 camera-ready 的公众号终稿

## 快速安装

### 一键安装

```bash
git clone https://github.com/jinshidong/-skill.git
cd -skill
./scripts/install_skill.sh
```

### Agent 安装

```bash
npx skills add https://github.com/jinshidong/-skill/tree/main/skill/md2wechat -g -y
```

如果你是通过 `npx` 安装 skill，而不是直接在本仓库里运行脚本，还需要额外告诉 skill 你的本地仓库路径。推荐二选一：

```bash
export MD2WECHAT_REPO_ROOT="/absolute/path/to/MD2WeChat"
```

或：

```bash
mkdir -p ~/.config/md2wechat
echo "/absolute/path/to/MD2WeChat" > ~/.config/md2wechat/repo_root
```

## 安装依赖

```bash
pip install -r requirements.txt
```

依赖说明：

- 必需：`requests`
- 必需：`beautifulsoup4`
- 必需：`Pillow`
- 必需：`PyYAML`
- 推荐：`pygments`
- 可选：`matplotlib`、`sympy`
- 可选外部工具：`@mermaid-js/mermaid-cli`

安装 Mermaid CLI：

```bash
npm install -g @mermaid-js/mermaid-cli
```

## 配置公众号凭证与默认发布信息

真实发布时，公众号凭证优先读环境变量；如果环境变量缺失，会回退到 `~/.config/md2wechat/config.yaml`。

环境变量示例：

```bash
export WECHAT_APPID="wx..."
export WECHAT_SECRET="..."
export MD2WECHAT_REPO_ROOT="/absolute/path/to/MD2WeChat"
```

如果你长期使用，推荐统一写进配置文件：

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

元信息优先级：

- CLI 参数
- front matter
- `article_defaults`
- 内建 fallback

当前内建 fallback：

- 作者缺失时默认使用 `路人甲`
- 封面优先读 `article_defaults.cover`
- 如果仍未配置封面，则回退到 `examples/images/frontpage.png`

## 项目能力

- `md2wechat.py`：本地 Markdown -> 微信公众号兼容 HTML
- `publish_wechat.py`：调用微信官方接口创建单篇图文草稿
- `camera_ready_wechat.py`：生成 `.camera-ready.md` 与 `.camera-ready.notes.md`
- `skill/md2wechat`：给 agent / vibe 使用的检查、预检、发布脚本

当前默认发布链路：

- `stable_token`
- `media/uploadimg`
- `material/add_material?type=thumb`
- `draft/add`

项目已经支持：

- 多种主题风格：`academic_gray`、`festival`、`tech`、`announcement`
- 正文图片自动上传到微信并替换成微信图片 URL
- 封面图自动上传为 `thumb` 永久素材并生成 `thumb_media_id`
- 本地预检：标题、作者、摘要、封面、正文长度、图片可上传性
- UTF-8 中文内容直传，避免草稿箱出现 `\uXXXX` 字面量
- `45004 description size out of limit` 自动缩短摘要后重试
- camera-ready 终稿优先发布
- 微信凭证支持 `env -> ~/.config/md2wechat/config.yaml` 回退

## 多公众号池后台

如果你要让 OpenClaw / Telegram 直接把本机 Markdown 推到不同公众号草稿箱，现在可以启动内置的多账号后台：

```bash
python multi_account_service.py
```

默认监听：

- `0.0.0.0:1024`
- SQLite：`data/md2wechat_multiuser.sqlite`

管理台页面：

- `http://127.0.0.1:1024/accounts`：公众号账号 CRUD
- `http://127.0.0.1:1024/jobs`：发布历史、失败原因、手动重试

关键约束：

- 不做人登录，不做权限分层
- `wechat_appid` / `wechat_app_secret` 明文保存到 SQLite
- 顶部固定显示风险警告
- CLI 发布链路保持不变，仍然使用 `env -> ~/.config/md2wechat/config.yaml`
- 服务侧直接从数据库读取账号池凭证，再构造 `WeChatDraftClient`

账号表字段：

- `alias`
- `wechat_appid`
- `wechat_app_secret`
- `public_name`
- `description`
- `enabled`

任务表字段：

- `account_alias`
- `article_path`
- `source`
- `origin_chat_id`
- `origin_message_id`
- `request_text`
- `status`
- `title`
- `media_id`
- `thumb_media_id`
- `error_message`

OpenClaw 提交接口：

```bash
curl -X POST http://127.0.0.1:1024/api/drafts \
  -H 'Content-Type: application/json' \
  -d '{
    "account_alias": "tech_daily",
    "article_path": "/absolute/path/to/article.md",
    "source": "openclaw.telegram",
    "origin_chat_id": "123456",
    "origin_message_id": "789",
    "request_text": "生成公众号稿：公众号=tech_daily 主题=...",
    "style": "tech",
    "author": "Team MD2WeChat",
    "digest": "一段摘要",
    "source_url": "https://example.com/post"
  }'
```

返回结果包含：

- `ok`
- `job_id`
- `status`
- `account_alias`
- `title`
- `media_id`
- `thumb_media_id`
- `error`

当 `account_alias` 缺失、账号不存在或账号被禁用时，接口会返回当前可投递的 alias 列表，方便 TG 侧直接提示用户。

## 微信官方平台入口变更

微信公众号 / 服务号的 `开发接口管理` 已迁移到微信开发者平台。官方说明见：

- [「开发接口管理」模块升级说明](https://developers.weixin.qq.com/doc/subscription/guide/dev/migration.html)

对 MD2WeChat 最相关的变化可以直接记成这几条：

- 旧入口 `微信公众平台 -> 设置与开发 -> 开发接口管理`，现在迁到 `微信开发者平台 -> 我的业务 -> 公众号/服务号`
- `AppID` 可在 `基础信息` 查看
- `AppSecret` 和 `API IP 白名单` 在 `基础信息 -> 开发密钥`
- `服务器配置`、`JS 接口安全域名`、`消息推送` 在 `基础信息 -> 域名与消息推送配置`
- 如果接口调用 IP 没加入白名单，微信会返回 `40164`
- 官方文档明确提示平台不会再次展示已生成的 `AppSecret`，重置后要自行妥善保存接口能不能调通，先看 `AppSecret` 是否已启用，再看出口 IP 是否已加入 `API IP 白名单`。

## Markdown 元信息格式

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

## 脚本地图

### 1. 本地转换 HTML

```bash
python md2wechat.py article.md
python md2wechat.py article.md -o output.html -s tech
```

### 2. 生成 camera-ready 终稿

如果原稿还是 reviewer / 草稿口吻，可以先生成终稿骨架：

```bash
python camera_ready_wechat.py article.md
```

这会生成：

- `article.camera-ready.md`
- `article.camera-ready.notes.md`

其中 `.notes.md` 只保存备选标题、封面 prompt 和正文配图 prompt，不参与发布。

### 3. 本地预检

```bash
python publish_wechat.py article.md --cover cover.jpg --dry-run
```

如果同目录存在 `article.camera-ready.md`，发布链路会优先使用终稿。

如果 `front matter.cover` 已配置，可以省略 `--cover`。如果 `--cover` 和 `front matter.cover` 都没有提供，当前版本会默认使用：

- `examples/images/frontpage.png`

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
  --source "来源名称" \
  --source-url "https://example.com/post"
```

## Skill 工作流

安装后可直接使用这些脚本：

- `~/.agents/skills/md2wechat/scripts/inspect.sh`
- `~/.agents/skills/md2wechat/scripts/camera_ready.sh`
- `~/.agents/skills/md2wechat/scripts/validate_config.sh`
- `~/.agents/skills/md2wechat/scripts/dry_run.sh`
- `~/.agents/skills/md2wechat/scripts/create_draft.sh`
- `~/.agents/skills/md2wechat/scripts/convert_html.sh`

推荐发布顺序：

1. `inspect.sh article.md`
2. `validate_config.sh`
3. `dry_run.sh article.md`
4. `create_draft.sh article.md`

如果使用这些脚本创建真实草稿，至少需要：

- `WECHAT_APPID`
- `WECHAT_SECRET`

如果是 `npx` 安装 skill，另外建议配置：

- `MD2WECHAT_REPO_ROOT`

## 命令行说明

### `md2wechat.py`

```bash
python md2wechat.py <input.md> [-o output.html] [-s style] [--source source]
```

### `publish_wechat.py`

```bash
python publish_wechat.py <article.md> [--cover cover.jpg] [--style style] [--dry-run]
```

主要参数：

- `--cover`：封面图片路径，优先级高于 `front matter.cover`
- `--title`：覆盖标题
- `--author`：覆盖作者
- `--digest`：覆盖摘要
- `--source`：覆盖文末来源信息
- `--source-url`：覆盖阅读原文链接
- `--dry-run`：只做本地预检，不调用微信接口

## 常见限制

- 标题建议不超过 32 字
- 作者建议不超过 16 字
- 摘要建议不超过 128 字
- 正文 HTML 需要控制在微信接口可接受范围内
- 真实上传前需要将当前出口 IP 加入公众号 `API IP 白名单`

## 历史实现

仓库里仍保留旧的 Playwright 浏览器自动化实现，供历史兼容和研究参考：

- [src/wechat_publisher.py](src/wechat_publisher.py)
- [docs/Playwright.md](docs/Playwright.md)

它不再是默认发布方式。

## 文档索引

- [docs/QUICK_START.md](docs/QUICK_START.md)：从零到一次成功验证
- [docs/PUBLISH_GUIDE.md](docs/PUBLISH_GUIDE.md)：官方草稿箱 API 发布说明
- [docs/USAGE.md](docs/USAGE.md)：Markdown 转 HTML 说明
- [docs/MARKDOWN_FORMAT.md](docs/MARKDOWN_FORMAT.md)：Front Matter 格式说明
- [docs/Playwright.md](docs/Playwright.md)：旧 Playwright 浏览器链路参考

## 许可证

MIT License
## 鸣谢
https://github.com/nashsu/Viral_Writer_Skill/tree/main

https://github.com/geekjourneyx/md2wechat-skill

https://github.com/Mapoet/MD2WeChat
