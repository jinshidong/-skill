# 微信公众号发布指南

本文档介绍如何使用 Playwright 自动化发布微信公众号文章。

## 功能特性

- ✅ **自动登录**（使用持久化浏览器 profile）
- ✅ **智能编辑器查找**（基于实际 DOM 结构，支持 uEditor/edui1）
- ✅ **自动填充标题和作者**（从 Markdown front matter 提取）
- ✅ **自动插入 HTML 内容**到编辑器正文
- ✅ **支持定时发布**（多任务批量定时）
- ✅ **支持多种风格模板**
- ✅ **交互模式**（手动操作和调试）

## 安装依赖

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 Playwright 浏览器

```bash
playwright install
```

这会下载 Chromium 浏览器，用于自动化操作。

## 快速开始

### 首次使用：设置登录

1. **运行发布脚本（首次会打开浏览器）**：

```bash
python publish_wechat.py --interactive
```

2. **在打开的浏览器中手动登录微信公众号后台**：
   - 访问 `https://mp.weixin.qq.com`
   - 使用微信扫码或账号密码登录
   - 登录成功后，关闭浏览器

3. **登录态已保存**：
   - 登录信息保存在 `./tmp_profile` 目录（默认）
   - 后续运行会自动使用该登录态

### 发布文章

#### 方式一：直接发布（推荐）

```bash
# 基本发布（自动填充标题、作者和正文）
python publish_wechat.py article.md

# 指定风格
python publish_wechat.py article.md --style festival

# 不清空编辑器（追加内容）
python publish_wechat.py article.md --no-clear
```

**发布流程**：
1. 自动打开浏览器并加载编辑器
2. **自动填充标题**（从 Markdown front matter 的 `title` 字段提取）
3. **自动填充作者**（从 Markdown front matter 的 `author` 字段提取）
4. **自动插入正文内容**（Markdown 转换后的 HTML）
5. 保持浏览器打开，您可以：
   - 检查内容
   - 手动调整格式
   - **手动点击"发布"或"群发"按钮**

#### 方式二：仅插入内容（需要手动发布）

```bash
python publish_wechat.py article.md --no-clear
```

脚本会执行相同的填充和插入操作，但不自动发布。

#### 方式三：定时发布

```bash
# 今天 20:30 定时发布（默认日期为今天）
python publish_wechat.py article.md \
    --auto-publish \
    --scheduled-time "20:30"

# 明天 20:30 定时发布
python publish_wechat.py article.md \
    --auto-publish \
    --scheduled-date "tomorrow" \
    --scheduled-time "20:30"

# 指定日期发布（如 2024-12-25 20:30）
python publish_wechat.py article.md \
    --auto-publish \
    --scheduled-date "2024-12-25" \
    --scheduled-time "20:30"

# 定时发布并启用群发通知
python publish_wechat.py article.md \
    --auto-publish \
    --scheduled-date "tomorrow" \
    --scheduled-time "20:30" \
    --enable-group-notify
```

**定时发布流程**：
1. 自动打开浏览器并加载编辑器
2. 自动填充标题、作者和正文
3. 自动点击"发布"按钮
4. **自动打开"定时发表"开关**
5. **自动选择日期**（今天、明天或指定日期）
6. **自动设置发布时间**（如 20:30）
7. 群发通知开关默认关闭（可通过 `--enable-group-notify` 启用）
8. 浏览器保持打开，您可以检查设置后手动确认发布

**日期和时间格式**：
- `--scheduled-date`：
  - `today` 或 `今天` - 今天发布
  - `tomorrow` 或 `明天` - 明天发布
  - `YYYY-MM-DD` - 指定日期，如 `2024-12-25`
  - 如果不指定，默认为 `today`
- `--scheduled-time`：格式为 `HH:MM`，如 `20:30`、`09:00`
- 支持选择七天内的时间（微信公众号限制）

**注意事项**：
- 建议配合 `--auto-publish` 使用，否则需要手动点击发布按钮
- 微信公众号只支持选择七天内的时间
- 日期选择器会自动显示"今天"、"明天"和未来几天的日期选项

## 定时发布

### 使用配置文件

创建 `publish_config.json`：

```json
{
  "tasks": [
    {
      "md_file": "examples/2020-05-22-blog-post-13.md",
      "publish_time": "2024-12-25 10:00:00",
      "style": "academic_gray",
      "user_data_dir": "./tmp_profile",
      "clear_editor": true,
      "auto_publish": false
    },
    {
      "md_file": "examples/2025-11-05-md2wechat-intro.md",
      "publish_time": "2024-12-26 14:30:00",
      "style": "tech",
      "user_data_dir": "./tmp_profile",
      "clear_editor": true,
      "auto_publish": false
    }
  ]
}
```

运行定时发布器：

```bash
python schedule_publish.py --config publish_config.json
```

### 命令行添加任务

```bash
# 添加单个任务
python schedule_publish.py \
  --md-file article.md \
  --publish-time "2024-12-25 10:00:00" \
  --style academic_gray

# 查看所有任务
python schedule_publish.py --list

# 运行定时器（默认检查间隔 60 秒）
python schedule_publish.py --check-interval 30
```

## 命令行选项

### publish_wechat.py

```
usage: publish_wechat.py [-h] [--style {academic_gray,festival,tech,announcement}]
                          [--user-data-dir USER_DATA_DIR] [--headless]
                          [--no-clear] [--auto-publish] [--scheduled-time SCHEDULED_TIME]
                          [--scheduled-date SCHEDULED_DATE] [--enable-group-notify]
                          [--interactive] [md_file]

发布 Markdown 文章到微信公众号

positional arguments:
  md_file               Markdown 文件路径

optional arguments:
  -h, --help            显示帮助信息
  -s, --style            HTML 风格（默认: academic_gray）
  -d, --user-data-dir    浏览器用户数据目录（默认: ./tmp_profile）
  --headless             使用无头模式（不显示浏览器窗口）
  --no-clear             不清空编辑器，在现有内容后追加
  --auto-publish         自动发布（不推荐，存在风险）
  --scheduled-time       定时发布时间，格式 HH:MM，如 20:30
  --scheduled-date       定时发布日期，格式 YYYY-MM-DD 或 today 或 tomorrow（默认: today）
  --enable-group-notify  启用群发通知（默认不启用）
  -i, --interactive      交互模式：仅打开浏览器，不插入内容
```

### schedule_publish.py

```
usage: schedule_publish.py [-h] [--config CONFIG] [--md-file MD_FILE]
                            [--publish-time PUBLISH_TIME] [--style STYLE]
                            [--list] [--check-interval CHECK_INTERVAL]
                            [--auto-publish]

定时发布微信公众号文章

optional arguments:
  -h, --help            显示帮助信息
  -c, --config           配置文件路径（JSON 格式）
  -f, --md-file          Markdown 文件路径
  -t, --publish-time     发布时间（格式：YYYY-MM-DD HH:MM:SS）
  -s, --style            HTML 风格
  -l, --list             列出所有任务
  -i, --check-interval   检查间隔（秒，默认 60）
  --auto-publish         自动发布（不推荐）
```

## 使用示例

### 示例 1：发布单篇文章

```bash
# 转换并发布
python publish_wechat.py examples/2020-05-22-blog-post-13.md --style academic_gray
```

### 示例 2：定时发布多篇文章

创建 `my_publish_config.json`：

```json
{
  "tasks": [
    {
      "md_file": "articles/article1.md",
      "publish_time": "2024-12-25 09:00:00",
      "style": "academic_gray"
    },
    {
      "md_file": "articles/article2.md",
      "publish_time": "2024-12-25 18:00:00",
      "style": "festival"
    }
  ]
}
```

运行：

```bash
python schedule_publish.py --config my_publish_config.json
```

### 示例 3：交互模式调试

```bash
# 打开浏览器，手动操作
python publish_wechat.py --interactive
```

## 注意事项

### ⚠️ 重要提示

1. **登录态管理**：
   - 首次使用需要手动登录
   - 登录态保存在 `user_data_dir` 目录
   - 不要删除该目录，否则需要重新登录

2. **自动发布风险**：
   - `--auto-publish` 选项会自动点击发布按钮
   - 建议不要使用，存在误发布风险
   - 推荐做法：插入内容后手动确认发布

3. **编辑器选择器**：
   - 微信公众号后台 DOM 结构可能变化
   - 如果插入失败，可能需要更新选择器
   - 可以查看 `src/wechat_publisher.py` 中的 `JS_FIND_EDITOR` 和 `JS_INSERT_AT_CURSOR`

4. **定时发布**：
   - 定时发布器需要持续运行
   - 建议在服务器或后台运行
   - 可以使用 `screen` 或 `tmux` 保持会话

5. **合规性**：
   - 遵守微信公众平台规则
   - 不要批量自动化发布
   - 确保内容经过人工审核

### 故障排查

#### 问题 1：找不到编辑器

**症状**：日志显示 "editor found: {found: false}" 或 "编辑器未找到"

**解决方案**：
1. 检查是否已登录（使用 `--interactive` 模式验证）
2. 检查是否在正确的编辑页面（应该在 `appmsg_edit` 页面）
3. 脚本会自动查找以下编辑器：
   - 标题框：`#title` 或 `textarea[name="title"]`
   - 作者框：`#author` 或 `input[name="author"]`
   - 正文编辑器：`edui1` iframe 或 contenteditable 元素
4. 如果仍然找不到，请检查浏览器控制台是否有错误
5. 可以尝试等待更长时间（脚本默认等待 15 秒）

#### 问题 1.1：找到了编辑器但插入失败

**症状**：日志显示找到了编辑器，但插入 HTML 失败

**解决方案**：
1. 检查 HTML 内容是否包含微信不支持的标签
2. 检查编辑器是否完全加载（可能需要等待更长时间）
3. 尝试使用 `--no-clear` 选项

#### 问题 2：插入 HTML 失败

**症状**：`insert result: {ok: false, error: ...}`

**解决方案**：
1. 检查 HTML 内容是否包含微信不支持的标签
2. 尝试使用 `--no-clear` 选项
3. 使用交互模式手动检查编辑器状态

#### 问题 3：登录态失效

**症状**：每次运行都需要重新登录

**解决方案**：
1. 检查 `user_data_dir` 目录权限
2. 确保目录没有被删除
3. 重新运行 `--interactive` 模式登录

## 技术实现

#### 架构概述

```
publish_wechat.py (命令行工具)
    ↓
wechat_publisher.py (核心模块)
    ├── WeChatPublisher (浏览器控制)
    ├── publish_from_markdown (发布流程)
    │   ├── 提取标题和作者 (从 Markdown front matter)
    │   └── 转换 HTML (WeChatHTMLConverter)
    └── JavaScript 注入 (DOM 操作)
    ↓
md2wechat.py (Markdown 转换)
    └── WeChatHTMLConverter (HTML 生成)
```

#### 核心流程

1. **启动浏览器**：使用持久化 profile 启动 Chromium
2. **打开编辑器**：导航到微信公众号编辑页面
3. **检查登录**：验证登录状态
4. **查找编辑器**：智能查找标题、作者和正文编辑器
5. **提取元信息**：从 Markdown front matter 提取标题和作者
6. **转换 Markdown**：调用 `WeChatHTMLConverter` 生成 HTML
7. **填充标题和作者**：自动填充到对应的输入框
8. **插入 HTML**：使用 JavaScript 注入到正文编辑器
9. **发布**（可选）：查找并点击发布按钮

#### JavaScript 注入

使用 Playwright 的 `page.evaluate()` 在页面上下文中执行 JavaScript：

- **查找编辑器**：`JS_FIND_EDITOR` - 基于实际 XPath 查找：
  - 标题框：`#title` 或 `textarea[name="title"]`
  - 作者框：`#author` 或 `input[name="author"]`
  - 正文编辑器：优先查找 `edui1` iframe，其次查找 contenteditable 元素
- **填充标题和作者**：`JS_SET_TITLE_AUTHOR` - 填充输入框并触发事件
- **插入 HTML**：`JS_INSERT_AT_CURSOR` - 使用 Range API 插入内容（支持 iframe）
- **Bridge 注入**：`JS_INJECT_BRIDGE` - 注入全局桥接函数

#### 编辑器查找策略

脚本采用多层查找策略：

1. **优先查找**：`edui1` 相关的 iframe（uEditor 通常使用 iframe）
2. **次优查找**：`edui1` 相关的 contenteditable 元素
3. **兜底策略**：查找最大的可见 contenteditable 元素

这样可以适应不同的微信公众号编辑器版本和结构。

## 进阶使用

### 自定义编辑器选择器

如果默认选择器无法找到编辑器，可以修改 `src/wechat_publisher.py`：

**标题框选择器**：
```javascript
// 在 JS_FIND_EDITOR 中修改
const titleEl = document.querySelector('#title, textarea[name="title"], '自定义选择器');
```

**作者框选择器**：
```javascript
const authorEl = document.querySelector('#author, input[name="author"], '自定义选择器');
```

**正文编辑器选择器**：
```javascript
// 在 JS_INSERT_AT_CURSOR 中添加新的选择器
const eduiSelectors = [
    '#edui1',
    '[id*="edui1"]',
    '.edui-editor-body',
    '你的自定义选择器'  // 添加自定义选择器
];
```

### 自定义发布按钮选择器

修改 `JS_FIND_PUBLISH_BUTTON` 中的选择器列表。

### Markdown Front Matter 格式

确保你的 Markdown 文件包含正确的 front matter：

```yaml
---
title: "文章标题"  # 会自动填充到标题框
author: "作者名称"  # 会自动填充到作者框（可选）
date: 2024-12-25
tags:
  - 标签1
  - 标签2
---

正文内容...
```

脚本会自动从 front matter 提取 `title` 和 `author` 字段并填充到编辑器。

### 集成到 CI/CD

```yaml
# GitHub Actions 示例
- name: Publish WeChat Article
  run: |
    python publish_wechat.py article.md --headless
  env:
    DISPLAY: :99  # 用于无头模式
```

## 许可证

本项目采用 MIT License。

