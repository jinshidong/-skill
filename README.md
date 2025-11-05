# Markdown to WeChat HTML Converter

将 Markdown 文件转换为微信公众号兼容的 HTML 格式。

## 特性

- ✅ 支持多种风格模板
  - **学术灰风格** (`academic_gray`) - 适合学术论文和技术文档
  - **节日快乐色彩系** (`festival`) - 适合节日祝福和庆祝内容
  - **科技产品介绍色彩系** (`tech`) - 适合产品介绍和科技文章
  - **重大事情告知色彩系** (`announcement`) - 适合重要通知和公告
- ✅ 代码块缩进保留（使用 `<br>` + `&nbsp;`）
- ✅ 图片自动转换为 Base64 嵌入
- ✅ 支持数学公式渲染（CodeCogs / 本地渲染）
- ✅ 支持 Mermaid 图表转换
- ✅ 代码语法高亮（Pygments）
- ✅ H2/H3 标题卡片式布局
- ✅ 支持列表（有序/无序，支持嵌套）
- ✅ 支持表格（支持对齐方式）
- ✅ 支持链接（支持带标题的链接）
- ✅ 支持水平分割线（`---`, `***`, `___`）
- ✅ 100% 微信兼容（仅使用白名单标签）

## 安装

详细安装说明请参考 [INSTALL.md](INSTALL.md)

## Markdown 文件格式

MD2WeChat 使用 YAML Front Matter 来定义文章元信息。详细格式说明请参考 [docs/MARKDOWN_FORMAT.md](docs/MARKDOWN_FORMAT.md)。

快速参考：
- Front Matter 必须用 `---` 包裹
- 必需字段：`title`、`date`
- 可选字段：`author`、`excerpt`、`permalink`、`tags`
- Tags 使用 YAML 列表格式：每行以 `-` 开头（注意缩进）

## 许可证

本项目采用 [MIT License](LICENSE)。

### 快速安装学术灰风格

```bash
# 1. 克隆仓库
git clone <repository-url>
cd MD2WeChat

# 2. 安装 Python 依赖（推荐完整安装）
pip install -r requirements.txt

# 3. 安装 Mermaid CLI（可选，用于 Mermaid 图表转换）
npm install -g @mermaid-js/mermaid-cli
```

### 依赖说明

- **必需**：`requests` - 用于网络请求
- **推荐**：`pygments` - 代码语法高亮
- **可选**：`matplotlib`, `sympy` - 公式本地渲染
- **外部工具**：`@mermaid-js/mermaid-cli` - Mermaid 图表转换（需通过 npm 安装）

## 快速开始

### 基本使用

```bash
python md2wechat.py input.md
```

或指定输出文件和风格：

```bash
# 指定输出文件
python md2wechat.py input.md -o output.html

# 指定风格（默认：academic_gray）
python md2wechat.py input.md -s festival      # 节日快乐色彩系
python md2wechat.py input.md -s tech          # 科技产品介绍色彩系
python md2wechat.py input.md -s announcement # 重大事情告知色彩系
```

### 使用示例

```bash
# 转换示例文件
python md2wechat.py examples/2020-05-22-blog-post-13.md
```

## 项目结构

```
MD2WeChat/
├── md2wechat.py          # 命令行入口脚本
├── requirements.txt       # Python 依赖
├── README.md             # 项目说明
├── .gitignore            # Git 忽略文件
├── src/                  # 源代码目录
│   ├── __init__.py       # 包初始化文件
│   ├── md2wechat.py      # 主程序模块
│   └── inline_formatter.py  # Pygments 内联样式格式化器
├── docs/                 # 文档目录
│   ├── USAGE.md          # 使用文档
│   └── type.md           # 微信支持的 HTML 标签说明
├── examples/             # 示例文件
│   ├── 2020-05-22-blog-post-13.md    # 示例 Markdown（包含各种元素）
│   ├── 2020-05-22-blog-post-13.html  # 示例输出 HTML
│   ├── 2025-11-05-md2wechat-intro.md # 项目介绍文档
│   ├── 2025-11-05-md2wechat-intro.html # 项目介绍 HTML
│   └── images/           # 示例图片
└── tests/                # 测试目录
```

## 依赖说明

### 必需依赖

- **requests** (>=2.25.0): 用于从网络 URL 下载图片和公式

### 推荐依赖

- **pygments** (>=2.7.0): 用于代码块的语法高亮，强烈推荐安装

### 可选依赖

- **matplotlib** (>=3.3.0): 用于本地渲染数学公式（当 CodeCogs 不可用时）
- **sympy** (>=1.7.0): 用于优化和渲染复杂的 LaTeX 公式

### 外部工具

- **@mermaid-js/mermaid-cli**: 用于将 Mermaid 图表转换为 PNG 图片
  - 安装方式：`npm install -g @mermaid-js/mermaid-cli`
  - 需要先安装 Node.js

## 功能说明

### 支持的 Markdown 元素

- 标题（H1-H6）
- 段落和换行
- **粗体** 和 *斜体*
- `行内代码`
- 代码块（支持语法高亮）
- 图片（本地路径或 URL，自动转换为 Base64）
- 链接（支持带标题的链接）
- 数学公式（`$...$` 行内，`$$...$$` 块级）
- Mermaid 图表
- 列表（有序列表和无序列表，支持嵌套）
- 表格（支持对齐方式：左对齐、居中、右对齐）

### 样式特性

- **多种主题风格**：
  - 学术灰风格：灰色标题条 + 白色卡片，适合学术论文和技术文档
  - 节日快乐色彩系：红色/金色主题，适合节日祝福和庆祝内容
  - 科技产品介绍色彩系：蓝色/青色主题，适合产品介绍和科技文章
  - 重大事情告知色彩系：红色/橙色主题，适合重要通知和公告
- **H2/H3 卡片布局**：H2 和 H3 标题后的内容自动包裹在卡片中，每个主题有独特的配色
- **代码块横向滚动**：长代码自动横向滚动，代码块颜色随主题变化
- **透明背景**：公式和 Mermaid 图表使用透明背景

## 使用文档

详细使用说明请参考 [docs/USAGE.md](docs/USAGE.md)

## 许可证

MIT License
