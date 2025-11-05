# 项目结构说明

```
MD2WeChat/
├── md2wechat.py              # 命令行入口脚本
├── requirements.txt           # Python 依赖列表
├── LICENSE                    # MIT 许可证
├── README.md                  # 项目主文档
├── INSTALL.md                 # 详细安装指南
├── PROJECT_STRUCTURE.md      # 项目结构说明
├── .gitignore                 # Git 忽略文件
│
├── src/                       # 源代码目录
│   ├── __init__.py            # 包初始化文件
│   ├── md2wechat.py           # 主程序模块（核心转换逻辑）
│   └── inline_formatter.py    # Pygments 内联样式格式化器
│
├── docs/                      # 文档目录
│   ├── USAGE.md               # 使用文档
│   ├── MARKDOWN_FORMAT.md     # Markdown 文件格式说明（Front Matter 格式）
│   └── type.md                # 微信支持的 HTML 标签说明
│
├── examples/                  # 示例文件
│   ├── 2020-05-22-blog-post-13.md    # 示例 Markdown（包含各种元素）
│   ├── 2020-05-22-blog-post-13.html  # 示例输出 HTML
│   ├── 2025-11-05-md2wechat-intro.md # 项目介绍文档
│   ├── 2025-11-05-md2wechat-intro.html # 项目介绍 HTML
│   └── images/                # 示例图片
│
└── tests/                     # 测试目录（预留）
```

## 文件说明

### 根目录文件

- **md2wechat.py**: 命令行入口，提供命令行界面
- **requirements.txt**: Python 包依赖列表
- **LICENSE**: MIT 许可证文件
- **README.md**: 项目概述和快速开始指南
- **INSTALL.md**: 详细的安装说明和依赖说明
- **PROJECT_STRUCTURE.md**: 项目结构说明文档
- **.gitignore**: Git 版本控制忽略规则

### src/ 目录

源代码模块：

- **md2wechat.py**: 
  - `WeChatHTMLConverter` 类：主转换器
    - 支持多种主题风格（学术灰、节日、科技、公告）
    - 支持列表解析和渲染（有序/无序、嵌套）
    - 支持表格解析和渲染（对齐方式）
    - 支持链接处理（带标题）
  - `MarkdownParser` 类：Markdown 解析器
    - Front matter 解析
    - 标题、段落、代码块、图片、公式、Mermaid、列表、表格解析
  - `CodeBlockFormatter` 类：代码块格式化（保留缩进、语法高亮）
  - `ImageProcessor` 类：图片处理（Base64 嵌入）
  - `FormulaProcessor` 类：公式处理（CodeCogs/本地渲染）
  - `MermaidProcessor` 类：Mermaid 图表处理（PNG 转换）
  - `StyleConfig` 数据类：主题样式配置
  - `main()` 函数：命令行入口

- **inline_formatter.py**: 
  - `InlineStyleFormatter` 类：Pygments 格式化器，输出内联样式

### docs/ 目录

文档文件：

- **USAGE.md**: 详细的使用说明和示例
- **MARKDOWN_FORMAT.md**: Markdown 文件格式说明，特别是 Front Matter（前置元数据）和 tags 格式
- **type.md**: 微信支持的 HTML 标签和样式列表

### examples/ 目录

示例文件，用于测试和演示：

- **2020-05-22-blog-post-13.md**: 包含各种 Markdown 元素的示例（代码块、公式、Mermaid、图片等）
- **2020-05-22-blog-post-13.html**: 对应的输出 HTML
- **2025-11-05-md2wechat-intro.md**: 项目介绍文档，展示工具功能和使用方法
- **2025-11-05-md2wechat-intro.html**: 项目介绍 HTML 输出
- **images/**: 示例图片资源

## 依赖关系

```
md2wechat.py (命令行入口)
    └── src/md2wechat.py (主模块)
        ├── src/inline_formatter.py (Pygments 格式化器)
        ├── requests (网络请求)
        ├── pygments (可选，语法高亮)
        ├── matplotlib (可选，公式渲染)
        └── sympy (可选，公式优化)
```

## 外部工具

- **mmdc** (@mermaid-js/mermaid-cli): 通过 npm 全局安装，用于 Mermaid 图表转换
