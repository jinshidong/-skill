# Markdown 文件格式说明

本文档说明 MD2WeChat 工具支持的 Markdown 文件格式要求，特别是 Front Matter（前置元数据）部分的格式规范。

## Front Matter 格式

MD2WeChat 使用 YAML 格式的 Front Matter（前置元数据）来定义文章的元信息。Front Matter 必须放在文件开头，用 `---` 包裹。

### 基本格式

```yaml
---
title: "文章标题"
date: 2025-11-05
permalink: /posts/2025/11/article-name
author: 作者名称
excerpt: '文章摘要，简要描述文章内容。'
tags:
   - 标签1
   - 标签2
   - 标签3
---
```

### 字段说明

#### 必需字段

- **`title`** (字符串)：文章标题
  - 必须使用双引号包裹
  - 示例：`title: "MD2WeChat：Markdown 转微信公众号 HTML 转换工具"`

- **`date`** (日期字符串)：发布日期
  - 格式：`YYYY-MM-DD`
  - 示例：`date: 2025-11-05`

#### 可选字段

- **`permalink`** (字符串)：文章永久链接路径
  - 通常用于博客系统
  - 示例：`permalink: /posts/2025/11/md2wechat-intro`

- **`author`** (字符串)：作者名称
  - 示例：`author: Mapoet`

- **`excerpt`** (字符串)：文章摘要
  - 使用单引号或双引号包裹
  - 示例：`excerpt: '一款功能强大的 Markdown 转微信公众号 HTML 转换工具...'`

- **`tags`** (列表)：文章标签列表
  - 使用 YAML 列表格式，每个标签前加 `-` 和空格
  - 标签可以包含空格，但建议保持简洁
  - 示例：
    ```yaml
    tags:
       - 工具介绍
       - Markdown
       - 微信公众号
       - 内容创作
       - 开源工具
    ```

### Tags 格式详解

Tags（标签）部分使用 YAML 列表格式，有以下几种写法：

#### 标准列表格式（推荐）

```yaml
tags:
   - 标签1
   - 标签2
   - 标签3
```

**注意**：每个标签前必须有两个空格，然后是一个短横线 `-`，再跟一个空格，最后是标签内容。

#### 单行列表格式

```yaml
tags: [标签1, 标签2, 标签3]
```

#### 字符串格式（兼容）

```yaml
tags: 单个标签
```

如果只提供一个标签，可以直接使用字符串格式。工具会自动将其转换为列表。

### 完整示例

#### 示例 1：产品介绍文章

```yaml
---
title: "MD2WeChat：Markdown 转微信公众号 HTML 转换工具"
date: 2025-11-05
permalink: /posts/2025/11/md2wechat-intro
author: Mapoet
excerpt: '一款功能强大的 Markdown 转微信公众号 HTML 转换工具，支持多种主题风格、代码高亮、数学公式渲染、Mermaid 图表、列表、表格、链接、水平分割线等功能，完美适配微信公众号编辑器。'
tags:
   - 工具介绍
   - Markdown
   - 微信公众号
   - 内容创作
   - 开源工具
---
```

#### 示例 2：技术文章

```yaml
---
title: "自动微分中的连续性问题"
date: 2020-05-22
permalink: /posts/2020/05/blog-post-13
excerpt: '通过构建sigmoid函数来解决选择语句及分段函数的连续性问题。'
tags:
   - 自动微分 
   - 选择语句 
   - 连续性问题 
   - 人工智能 
---
```

### 注意事项

1. **Front Matter 分隔符**：必须使用 `---` 作为开始和结束标记
2. **缩进**：YAML 对缩进敏感，tags 列表中的每个标签必须使用相同的缩进（建议使用两个空格）
3. **引号**：字符串字段（title、excerpt、author）建议使用引号包裹，特别是包含特殊字符时
4. **标签格式**：
   - 标签可以包含空格，但建议保持简洁
   - 标签前后的空格会被保留（注意示例 2 中标签末尾有空格）
   - 建议标签末尾不要有空格，保持格式整洁

### Front Matter 处理逻辑

MD2WeChat 工具会：

1. 解析 Front Matter 中的各个字段
2. 将 `title` 显示在灰色标题框中
3. 将 `date` 和 `tags` 显示在标题下方的"tag head"区域
4. 如果提供了 `author`，会在文件末尾显示作者信息
5. `excerpt` 和 `permalink` 主要用于元数据，不会直接显示在 HTML 中

### 正文内容

Front Matter 之后的内容是文章正文，支持所有标准的 Markdown 语法：

- 标题（H1-H6）
- 段落和换行
- 列表（有序/无序，支持嵌套）
- 表格
- 链接
- 图片
- 代码块（支持语法高亮）
- 数学公式（行内 `$...$` 和块级 `$$...$$`）
- Mermaid 图表
- 水平分割线（`---`, `***`, `___`）
- 粗体、斜体、行内代码等内联格式

详细语法说明请参考 [USAGE.md](USAGE.md)。

## 参考文件

- `examples/2025-11-05-md2wechat-intro.md` - 产品介绍文章示例
- `examples/2020-05-22-blog-post-13.md` - 技术文章示例

