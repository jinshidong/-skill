# Markdown to WeChat HTML Converter

将 Markdown 文件转换为微信公众号兼容的 HTML 格式。

## 特性

- ✅ 支持多种风格模板
  - **学术灰风格** (`academic_gray`) - 适合学术论文和技术文档
  - **节日快乐色彩系** (`festival`) - 适合节日祝福和庆祝内容
  - **科技产品介绍色彩系** (`tech`) - 适合产品介绍和科技文章
  - **重大事情告知色彩系** (`announcement`) - 适合重要通知和公告
- ✅ 代码块缩进保留（使用 `<br>` + `&nbsp;`，逐行 `span + nowrap`）
- ✅ 代码块左侧显示行号（灰色、右对齐、不可选择）
- ✅ 代码块不插入零宽字符（可安全复制到 IDE）
- ✅ 代码块支持横向滚动（长代码行不换行）
- ✅ 图片自动转换为 Base64 嵌入
- ✅ 支持数学公式渲染（CodeCogs / 本地渲染），使用浅色背景强调
- ✅ 支持 Mermaid 图表转换，使用极浅绿色背景强调
- ✅ 代码语法高亮（Pygments）
- ✅ H2/H3 标题卡片式布局
- ✅ 支持列表（有序/无序，支持嵌套）
- ✅ 列表项智能换行（冒号不会单独出现在行首，描述文本可正常换行）
- ⚠️ **限制**：列表项中不要使用 `XXX:YYY` 格式（可能导致解析错误）
- ⚠️ **限制**：内联公式在微信公众号中会被过滤，建议优先使用块级公式
- ✅ 支持表格（支持对齐方式）
- ✅ 支持链接（支持带标题的链接）
- ✅ 支持水平分割线（`---`, `***`, `___`）
- ✅ 支持文字颜色和加粗组合（`**文字**{color:#ff0000}`、`[文字]{color:#ff0000}`）
- ✅ 100% 微信兼容（仅使用白名单标签）
- ✅ **微信公众号草稿箱 API 发布**（默认发布链路）
  - 使用微信官方 `stable_token`、`media/uploadimg`、`material/add_material`、`draft/add`
  - 自动上传正文图片并替换为微信图片 URL
  - 自动上传封面图并生成 `thumb_media_id`
  - 支持本地预检（`--dry-run`）
- ✅ **Playwright 浏览器发布链路**（保留为历史实现）
  - 旧的浏览器自动化代码仍保留在 `src/wechat_publisher.py`

## 安装

详细安装说明请参考 [INSTALL.md](INSTALL.md)

## Markdown 文件格式

MD2WeChat 使用 YAML Front Matter 来定义文章元信息。详细格式说明请参考 [docs/MARKDOWN_FORMAT.md](docs/MARKDOWN_FORMAT.md)。

快速参考：
- Front Matter 必须用 `---` 包裹
- 必需字段：`title`、`date`
- 可选字段：`author`、`excerpt`、`permalink`、`tags`
- Tags 使用 YAML 列表格式：每行以 `-` 开头（注意缩进）
- **`permalink` 功能**：如果提供了 `permalink`，会在生成的 HTML 文尾自动添加"原文链接"链接

### ⚠️ 重要限制

1. **内联公式限制**：内联公式（`$...$`）在微信公众号中会被过滤，需要不用或慎用
   - 当前程序可以识别并精准输出内联公式
   - 但微信公众号平台会过滤掉内联公式（小图片）
   - 建议：优先使用块级公式 `$$...$$`，对于复杂的内联公式可谨慎使用
   - 注意：简单的块状公式也有被过滤的现象，需要根据实际情况测试

2. **列表格式限制**：列表项中不要使用 `XXX:YYY` 格式
   - 无论使用英文冒号（`:`）还是中文冒号（`：`），无论冒号前后是否有空格，都可能导致解析错误
   - 建议使用其他格式，如 `**标题** 描述` 或 `标题 - 描述`

详细说明请参考 [docs/MARKDOWN_FORMAT.md](docs/MARKDOWN_FORMAT.md) 和 [docs/USAGE.md](docs/USAGE.md)。

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
- **必需**：`beautifulsoup4` - 用于重写 HTML 中的图片 URL
- **必需**：`Pillow` - 用于正文图片和封面图片压缩、转码
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
  - ⚠️ **重要限制**：内联公式在微信公众号中会被过滤，需要不用或慎用（详见上方"重要限制"部分）
- Mermaid 图表
- 列表（有序列表和无序列表，支持嵌套）
  - ⚠️ **重要限制**：不要使用 `XXX:YYY` 格式（无论英文或中文冒号，无论是否有空格，都可能导致解析错误，详见上方"重要限制"部分）
- 表格（支持对齐方式：左对齐、居中、右对齐）
- 文字颜色和加粗组合（支持多种颜色格式）

### 样式特性

- **多种主题风格**：
  - 学术灰风格：灰色标题条 + 白色卡片，适合学术论文和技术文档
  - 节日快乐色彩系：红色/金色主题，适合节日祝福和庆祝内容
  - 科技产品介绍色彩系：蓝色/青色主题，适合产品介绍和科技文章
  - 重大事情告知色彩系：红色/橙色主题，适合重要通知和公告
- **H2/H3 卡片布局**：H2 和 H3 标题后的内容自动包裹在卡片中，每个主题有独特的配色
- **代码块横向滚动**：长代码自动横向滚动，代码块颜色随主题变化
- **代码块安全复制**：不插入零宽字符，可直接复制到 IDE 使用
- **列表项智能换行**：冒号和前面的文本保持在同一行，描述文本可正常换行
- **透明背景**：公式和 Mermaid 图表使用透明背景

## 使用文档

- **Markdown 转换使用**：详细使用说明请参考 [docs/USAGE.md](docs/USAGE.md)
- **自动发表功能**：详细发表指南请参考 [docs/PUBLISH_GUIDE.md](docs/PUBLISH_GUIDE.md)

### 快速草稿示例

```bash
# 1. 配置微信凭证
export WECHAT_APPID="your-appid"
export WECHAT_SECRET="your-secret"

# 2. 创建公众号草稿
python publish_wechat.py article.md --cover cover.jpg --style academic_gray

# 3. 本地预检，不调用微信接口
python publish_wechat.py article.md --cover cover.jpg --dry-run
```

**草稿功能特性**：
- ✅ 自动从 Markdown 提取标题、作者、摘要、原文链接
- ✅ 自动上传正文图片并替换为微信图床 URL
- ✅ 自动上传封面图生成 `thumb_media_id`
- ✅ 本地预检微信限制：标题、作者、摘要、封面、正文长度

**说明**：
- `publish_wechat.py` 现在默认走微信官方草稿箱 API。
- 旧的 Playwright 浏览器自动化说明仍保留在 [docs/PUBLISH_GUIDE.md](docs/PUBLISH_GUIDE.md)，可作为历史实现参考。

## 许可证

MIT License
