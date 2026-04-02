# 微信公众号草稿发布指南

当前仓库默认的 `publish_wechat.py` 已经切换为微信官方草稿箱 API 方案。

默认链路如下：

1. 获取 `stable_token`
2. 上传正文图片到 `media/uploadimg`
3. 上传封面图到 `material/add_material?type=thumb`
4. 创建单篇图文草稿 `draft/add`

旧的 Playwright 浏览器自动化实现不再是默认方案，如需参考请查看 [Playwright.md](Playwright.md)。

## 适用范围

当前版本聚焦：

- 单篇标准图文草稿
- 本地 Markdown 渲染
- 微信官方接口上传

当前不覆盖：

- 多图文草稿
- 定时发表
- 浏览器自动登录和编辑器注入

## 环境要求

### 1. Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 环境变量

```bash
export WECHAT_APPID=""
export WECHAT_SECRET=""
```

### 3. 微信后台前置条件

需要确保：

- 对应公众号的 `AppID` / `AppSecret` 可用
- 当前出口 IP 已加入微信公众平台接口白名单

如果接口返回 `40164 invalid ip`，请以微信报错里返回的 IP 为准加入白名单。

## 发布命令

### 基本用法

```bash
python publish_wechat.py article.md --cover cover.jpg
```

如果 Markdown 的 front matter 已经包含 `cover`，可以省略 `--cover`：

```bash
python publish_wechat.py article.md
```

### 本地预检

```bash
python publish_wechat.py article.md --cover cover.jpg --dry-run
```

`--dry-run` 不会调用微信接口，适合在真实上传前先验证文章是否满足限制。

### 覆盖元信息

```bash
python publish_wechat.py article.md \
  --cover cover.jpg \
  --title "新的标题" \
  --author "新的作者" \
  --digest "新的摘要" \
  --source "文章来源" \
  --source-url "https://example.com/post"
```

## 元数据来源规则

- `title`：优先 `--title`，否则用 front matter 的 `title`
- `author`：优先 `--author`，否则用 front matter 的 `author`
- `digest`：优先 `--digest`，否则优先 `digest`，再回退 `excerpt`
- `content_source_url`：优先 `--source-url`，否则用 `permalink`
- `cover`：优先 `--cover`，否则用 front matter 的 `cover`

## 正文与图片处理

### 正文 HTML

Markdown 转 HTML 仍由本地 `md2wechat.py` 完成，发布阶段不会依赖远程“Markdown 转公众号 HTML”服务。

### 正文图片

正文中的图片会在发布前统一处理：

- 本地图、远程图、公式图、Mermaid 图都会被读取
- 自动转成微信可接受的图片格式
- 上传到微信 `media/uploadimg`
- HTML 中的 `<img src>` 会被替换成微信返回的 URL

因此最终提交到 `draft/add` 的正文中，不应残留：

- `data:image/...`
- 本地文件路径
- 第三方外链图片地址

### 封面图

封面图会被转换并压缩，然后上传到微信永久素材接口：

- 接口：`material/add_material?type=thumb`
- 返回：`thumb_media_id`

这个 `thumb_media_id` 会写入草稿 payload。

## 本地预检规则

`--dry-run` 和真实上传前都会执行本地预检，主要包括：

- 标题是否存在，长度是否超限
- 作者长度是否超限
- 摘要长度是否超限
- 正文 HTML 长度是否超限
- 封面路径是否存在
- 环境变量是否存在
- 正文图片是否都能成功处理

建议先跑：

```bash
python publish_wechat.py article.md --dry-run
```

## 常见报错

### 1. `errcode=40164 invalid ip`

含义：当前出口 IP 不在白名单中。

处理方式：

1. 看微信报错返回的具体 IP
2. 到微信公众平台后台加入接口白名单
3. 重新执行命令

### 2. `errcode=45004 description size out of limit`

含义：摘要过长。

当前实现已经支持：

- 自动将摘要缩短到更保守的长度后重试一次

但更推荐在文章 front matter 中直接写更短的 `excerpt` 或 `digest`。

### 3. `正文 HTML 长度超过微信限制`

含义：本地预检失败，正文内容过长。

处理方式：

- 缩短文章
- 减少超长代码块或复杂内容
- 先用短文做 smoke test 验证链路

### 4. 草稿箱里显示 `\uXXXX`

这是旧版 JSON 序列化方式造成的历史问题。  
当前实现已经显式使用 UTF-8 和 `ensure_ascii=False` 发送请求，新草稿应直接显示中文。

## 推荐验证流程

### 第一次接入公众号

1. 配置 `WECHAT_APPID` / `WECHAT_SECRET`
2. 确认公众号接口 IP 白名单
3. 用短文跑一次 `--dry-run`
4. 用短文创建真实草稿
5. 再迁移正式文章

### 推荐短文

可以直接使用仓库中的 smoke test：

```bash
python publish_wechat.py examples/2026-04-02-draft-api-smoke-test.md --dry-run
python publish_wechat.py examples/2026-04-02-draft-api-smoke-test.md
```

## Skill 配套脚本

如果你已经安装了统一 skill，可直接使用：

```bash
~/.agents/skills/md2wechat/scripts/validate_config.sh
~/.agents/skills/md2wechat/scripts/inspect.sh article.md
~/.agents/skills/md2wechat/scripts/dry_run.sh article.md --cover cover.jpg
~/.agents/skills/md2wechat/scripts/create_draft.sh article.md --cover cover.jpg
```

其中：

- `validate_config.sh`：检查环境变量、当前公网 IP、微信 token 接口可达性
- `inspect.sh`：检查文章元数据、封面和 readiness

## 相关文件

- `publish_wechat.py`
- `src/wechat_draft_api.py`
- `md2wechat.py`
- `examples/2026-04-02-draft-api-smoke-test.md`

## 历史链路说明

仓库里仍保留：

- `src/wechat_publisher.py`
- `schedule_publish.py`

它们属于旧的浏览器自动化方案，不再是当前默认发布链路，也不建议继续作为主流程文档入口。
