# Markdown 转微信公众号 HTML 转换器使用说明

## 功能特性

- ✅ 支持 Markdown Front Matter（YAML 格式）解析
- ✅ 代码块缩进准确识别（使用 `<br>` + `&nbsp;` 方法）
- ✅ 图片自动转换为 base64 嵌入（支持本地路径和网络URL）
- ✅ 学术灰风格模板（默认）
- ✅ 可扩展的风格配置系统
- ✅ 微信公众号兼容的 HTML 标签（仅使用白名单标签）

## 安装依赖

```bash
# 基本依赖（图片处理）
pip install requests

# 公式渲染（推荐）
pip install sympy matplotlib

# 如果不想安装 sympy 或 matplotlib，工具会自动使用 CodeCogs 在线服务作为备选
```

## 使用方法

### 基本用法

```bash
python3 md2wechat.py <输入文件.md> [-o <输出文件.html>] [-s <风格名称>]
```

### 示例

```bash
# 转换 Markdown 文件，使用默认风格和输出文件名
python3 md2wechat.py 2020-05-22-blog-post-13.md

# 指定输出文件
python3 md2wechat.py 2020-05-22-blog-post-13.md -o output.html

# 使用指定风格（当前仅支持 academic_gray）
python3 md2wechat.py 2020-05-22-blog-post-13.md -s academic_gray
```

## 支持的 Markdown 语法

### Front Matter

```yaml
---
title: "文章标题"
date: 2020-05-22
tags:
   - 标签1
   - 标签2
---
```

### 标题

```markdown
# 一级标题
## 二级标题
### 三级标题
```

### 代码块

支持带语言标识的代码块：

````markdown
```c
double f(double a){
    static double a0=5;
    return a>a0?k1*(a-a0):k2*(a-a0);
}
```
````

代码块的缩进会被准确识别并保留。

### 图片

支持本地路径和网络URL：

```markdown
![图片描述](./images/example.png "图片标题")
![图片描述](http://example.com/image.png)
```

图片会自动转换为 base64 格式嵌入到 HTML 中。

### 数学公式

支持行内公式和块级公式，**本地渲染为图片并转为 base64 嵌入**：

**行内公式**：使用单个 `$` 包裹

```markdown
这是行内公式：$E=mc^2$ 和 $x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}$
```

**块级公式**：使用双 `$$` 包裹（居中显示）

```markdown
$$
\frac{\partial f(x)}{\partial v_i}=\sum_{j=1}^n \frac{\partial f(x)}{\partial u_j} \frac{\partial u_j}{\partial v_i}
$$
```

**渲染方式**：
- **优先使用 CodeCogs**：使用 CodeCogs 在线服务渲染公式，下载图片并转为 base64 嵌入。CodeCogs 支持复杂的 LaTeX 公式，渲染质量好
- **备选方案**：如果 CodeCogs 失败（如网络问题或某些复杂公式不支持），会自动回退到 sympy + matplotlib 或 matplotlib
- **图片嵌入**：所有公式图片都以 base64 形式嵌入 HTML，无需外部依赖，在微信公众号中显示稳定
- **自动清理**：转换完成后会自动删除临时渲染的图片文件
- **行内公式优化**：
  - 使用 `display:inline-block` 和 `vertical-align:middle` 确保与文本正确对齐
  - 使用 `width:auto` 和 `height:auto` 让宽度自适应渲染内容
  - 使用 `max-height:1.2em` 限制最大高度，避免过大

**优点**：
- ✅ 显示稳定，支持移动端
- ✅ 保留字体与排版
- ✅ 不会被微信清洗
- ✅ 图片以 base64 嵌入，无需外部依赖

### 其他语法

- **粗体**：`**粗体文本**` 或 `__粗体文本__`
- *斜体*：`*斜体文本*` 或 `_斜体文本_`
- `行内代码`：使用反引号包裹
- [链接](url)：`[链接文本](URL)`

## 风格配置

当前支持以下风格：

- `academic_gray`（默认）：学术灰风格，适合技术/科研文章

### 添加新风格

在 `md2wechat.py` 中的 `STYLES` 字典中添加新的 `StyleConfig`：

```python
STYLES = {
    "academic_gray": StyleConfig(...),
    "your_style": StyleConfig(
        name="你的风格名称",
        header_bg_color="#...",
        # ... 其他配置
    ),
}
```

## 输出格式

生成的 HTML 文件可以直接：
1. 在浏览器中打开查看效果
2. 全选复制到微信公众号编辑器正文区
3. 粘贴后即可在公众号中正常显示

## 注意事项

1. **图片路径**：相对路径基于 Markdown 文件所在目录解析
2. **代码块缩进**：使用空格或制表符都可以，工具会自动识别并保留相对缩进
3. **代码块横向滚动**：长代码支持横向滚动（`overflow-x:auto`），如果微信不支持会自动换行
4. **数学公式**：本地渲染为图片并转为 base64 嵌入，支持行内公式（`$...$`）和块级公式（`$$...$$`）
5. **微信兼容性**：仅使用微信白名单 HTML 标签，确保不会被编辑器过滤

## 技术细节

### 代码块缩进处理

- 计算所有非空行的最小前导空格数
- 每行相对最小缩进的空格数转换为 2 倍数量的 `&nbsp;`
- 使用 `<br>` 实现换行

### 图片处理

- 本地图片：读取文件并转换为 base64
- 网络图片：下载并转换为 base64
- 自动识别图片 MIME 类型

### HTML 标签限制

根据微信公众平台限制，仅使用以下标签：
- `<p>`, `<span>`, `<img>`, `<br>`
- `<strong>`, `<em>`
- 内联样式（`style` 属性）

## 常见问题

### Q: 图片无法显示？
A: 检查图片路径是否正确，确保图片文件存在或网络URL可访问。

### Q: 代码块缩进不正确？
A: 确保代码块使用空格或制表符进行缩进，不要混用。

### Q: 转换后的 HTML 在微信中显示异常？
A: 检查是否使用了微信不支持的标签，工具已自动过滤，但某些复杂样式可能被微信忽略。

## 许可证

MIT License

