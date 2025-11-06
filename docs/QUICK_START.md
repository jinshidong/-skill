# 快速开始指南

## 第一步：首次设置登录

### 1.1 安装依赖

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器（重要！）
playwright install
```

### 1.2 启动交互模式

```bash
python publish_wechat.py --interactive
```

### 1.3 在浏览器中登录

浏览器打开后，按以下步骤操作：

1. **如果看到登录页面**：
   - 使用微信扫码登录，或
   - 输入账号密码登录
   - 完成登录验证（如需要）

2. **登录成功后**：
   - 浏览器会自动跳转到微信公众号后台
   - 如果看到编辑器页面，说明登录成功

3. **保存登录态**：
   - 在终端按 `Enter` 键关闭浏览器
   - 登录信息已保存到 `./tmp_profile` 目录
   - 下次运行会自动使用该登录态

### 1.4 验证登录是否保存

再次运行交互模式，如果直接进入编辑器页面（无需再次登录），说明登录态保存成功：

```bash
python publish_wechat.py --interactive
```

---

## 第二步：发表第一篇文章

### 2.1 准备 Markdown 文件

确保你的 Markdown 文件格式正确，例如：

```markdown
---
title: 我的第一篇文章
date: 2024-12-25
tags:
  - 技术
  - 教程
---

# 文章标题

这是文章内容...
```

### 2.2 发表文章

```bash
# 基本发表（会打开浏览器，自动填充标题、作者和正文，然后保持打开状态）
python publish_wechat.py examples/2020-05-22-blog-post-13.md
```

**操作流程**：
1. 脚本会自动打开浏览器
2. 等待编辑器加载完成
3. **自动填充标题**（从 Markdown 的 `title` 字段提取）
4. **自动填充作者**（从 Markdown 的 `author` 字段提取，如果有）
5. **自动插入正文内容**（Markdown 转换后的 HTML）
6. 浏览器保持打开，您可以：
   - 检查标题、作者和内容是否正确
   - 手动调整格式
   - **手动点击"发表"或"群发"按钮**
   - 确认发表

### 2.3 指定风格发表

```bash
# 使用节日风格
python publish_wechat.py article.md --style festival

# 使用科技风格
python publish_wechat.py article.md --style tech

# 使用公告风格
python publish_wechat.py article.md --style announcement
```

### 2.4 定时发表

```bash
# 今天 20:30 定时发表（默认日期为今天）
python publish_wechat.py article.md \
    --auto-publish \
    --scheduled-time "20:30"

# 明天 20:30 定时发表
python publish_wechat.py article.md \
    --auto-publish \
    --scheduled-date "tomorrow" \
    --scheduled-time "20:30"

# 指定日期发表（如 2024-12-25 20:30）
python publish_wechat.py article.md \
    --auto-publish \
    --scheduled-date "2024-12-25" \
    --scheduled-time "20:30"
```

**日期格式说明**：
- `today` 或 `今天` - 今天发表
- `tomorrow` 或 `明天` - 明天发表
- `YYYY-MM-DD` - 指定日期，如 `2024-12-25`
- 支持选择七天内的时间（微信公众号限制）

### 2.5 不清空编辑器（追加内容）

如果您想在现有内容后追加，而不是替换：

```bash
python publish_wechat.py article.md --no-clear
```

---

## 第三步：定时发表（可选）

### 3.1 创建配置文件

创建 `my_publish_config.json`：

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
    }
  ]
}
```

### 3.2 运行定时发表器

```bash
# 使用配置文件
python schedule_publish.py --config my_publish_config.json

# 或者命令行添加任务
python schedule_publish.py \
  --md-file article.md \
  --publish-time "2024-12-25 10:00:00" \
  --style academic_gray
```

**注意**：定时发表器需要持续运行，建议：
- 在服务器上运行
- 使用 `screen` 或 `tmux` 保持会话
- 或使用 `nohup` 后台运行

---

## 常见操作场景

### 场景 1：快速发表一篇文章

```bash
# 1. 确保已登录（首次需要）
python publish_wechat.py --interactive
# 登录后按 Enter 关闭

# 2. 发表文章
python publish_wechat.py article.md
# 检查内容后手动点击发表
```

### 场景 2：批量定时发表

```bash
# 1. 创建配置文件（包含多个任务）
# 编辑 publish_config.json

# 2. 运行定时发表器
python schedule_publish.py --config publish_config.json

# 3. 保持脚本运行（不要关闭终端）
```

### 场景 3：调试和测试

```bash
# 交互模式：打开浏览器，手动测试
python publish_wechat.py --interactive

# 或者先用无头模式测试（不推荐，不利于调试）
python publish_wechat.py article.md --headless
```

---

## 故障排查

### 问题 1：浏览器打开但无法登录

**解决方案**：
- 检查网络连接
- 尝试手动访问 `https://mp.weixin.qq.com` 确认可以正常访问
- 清除 `./tmp_profile` 目录后重新登录

### 问题 2：提示"未登录"

**解决方案**：
```bash
# 删除旧的登录态
rm -rf ./tmp_profile

# 重新登录
python publish_wechat.py --interactive
```

### 问题 3：插入 HTML 失败或找不到编辑器

**症状**：日志显示 "编辑器未找到" 或 "插入 HTML 失败"

**解决方案**：
1. **检查编辑器是否加载完成**：脚本会自动等待最多 15 秒
2. **使用交互模式手动检查**：`python publish_wechat.py --interactive`
3. **检查 Markdown 文件格式**：确保 front matter 格式正确
4. **检查网络连接**：确保能正常访问微信公众号后台
5. **查看详细日志**：脚本会输出详细的查找和插入过程

**编辑器查找说明**：
- 脚本会自动查找标题框（`#title`）、作者框（`#author`）和正文编辑器
- 正文编辑器优先查找 `edui1` iframe（uEditor）
- 如果找不到 iframe，会查找 contenteditable 元素

### 问题 4：找不到发表按钮

**说明**：这是正常的，脚本会找到发表按钮但不会自动点击（安全考虑）
- 脚本会插入内容到编辑器
- 您需要手动点击"发表"或"群发"按钮
- 这是为了避免误发表的风险

---

## 重要提示

⚠️ **安全建议**：
- 不要使用 `--auto-publish` 选项（存在误发表风险）
- 发表前务必检查内容
- 遵守微信平台规则

⚠️ **登录态管理**：
- `./tmp_profile` 目录保存登录信息，不要删除
- 如果登录态失效，删除该目录重新登录

⚠️ **定时发表**：
- 定时发表器需要持续运行
- 建议在服务器上运行，使用 `screen` 保持会话

---

## 下一步

- 查看详细文档：[docs/PUBLISH_GUIDE.md](PUBLISH_GUIDE.md)
- 查看 Markdown 格式说明：[docs/MARKDOWN_FORMAT.md](MARKDOWN_FORMAT.md)
- 查看使用示例：[examples/](examples/)

