---
title: "autoGit-MCP：基于大语言模型的 Git 自动化流程处理 MCP 工具"
date: 2025-11-05
permalink: /posts/2025/11/autogit-mcp-intro
author: Mapoet
excerpt: '一款功能强大的基于 Model Context Protocol (MCP) 的 Git 自动化工具，支持 GitHub/Gitee/GitLab 多平台，提供仓库查询、提交分析、工作日志生成、Git 组合命令等丰富功能，让 Git 操作通过大语言模型变得更智能、更高效。'
tags:
   - 工具介绍
   - Git
   - MCP
   - 自动化
   - 开源工具
   - GitHub
   - Gitee
   - GitLab
---

autoGit-MCP 是一款基于 Model Context Protocol (MCP) 的 Git 自动化流程处理工具。它通过大语言模型完成 Git 操作的自动化处理，支持 GitHub、Gitee、GitLab 三大平台，提供仓库查询、提交分析、工作日志生成、Git 组合命令等丰富功能，让开发者能够通过自然语言与 Git 仓库进行交互，大大提升开发效率。

## 核心特性

```mermaid
graph TD
    A[大语言模型] --> B[autoGit-MCP]
    B --> C[git_catalog 工具]
    B --> D[git_work 工具]
    B --> E[git_comb 工具]
    B --> F[health 工具]
    B --> G[reload_config 工具]
    C --> H[GitHub/Gitee/GitLab API]
    D --> H
    E --> I[本地 Git 命令]
    F --> J[配置检查]
    G --> K[配置重载]
    H --> L[仓库信息]
    H --> M[提交记录]
    I --> N[Git 操作结果]
    L --> O[MCP 响应]
    M --> O
    N --> O
    J --> O
    K --> O
```

### 多平台支持

autoGit-MCP 支持三大主流代码托管平台：

- **GitHub**：全球最大的代码托管平台，支持完整的 API 功能
- **Gitee（码云）**：中国领先的代码托管平台，支持国内开发者快速访问
- **GitLab**：企业级代码托管平台，支持私有部署和完整的 CI/CD 功能

所有工具通过统一的 `provider` 参数（`github`/`gitee`/`gitlab`）选择平台，保持接口一致性。

### git_catalog 工具

`git_catalog` 是 autoGit-MCP 的核心工具之一，提供 7 个强大的子命令用于查询仓库和提交活动：

#### 1. search_repos - 关键词检索仓库

根据关键词、语言、Star 数等条件搜索仓库：

**功能特性**：
- ✅ 支持关键词匹配（name/description/readme）
- ✅ 支持语言限定（如 "Python", "C++", "TypeScript"）
- ✅ 支持最小 Star 数过滤
- ✅ 支持最近活跃时间过滤
- ✅ 支持 topic 和 owner 限定
- ✅ 支持多种排序方式（updated/stars/forks）

**示例查询**：
```python
# 搜索 Python 相关的高 Star 仓库
{
    "keyword": "machine learning",
    "language": "Python",
    "min_stars": 1000,
    "sort": "stars",
    "order": "desc",
    "limit": 50
}
```

#### 2. org_repos - 组织仓库列表

列出指定组织的所有仓库：

**功能特性**：
- ✅ 支持仓库类型过滤（all/public/private/forks/sources/member）
- ✅ 支持是否包含 archived 仓库
- ✅ 支持多种排序方式
- ✅ 最多返回 5000 条记录

#### 3. cross_repos - 跨仓库提交查询

查询指定作者在多个仓库中的提交记录：

**功能特性**：
- ✅ 支持按作者登录名或邮箱查询
- ✅ 支持时间范围过滤（since/until）
- ✅ 支持每仓库最多抓取条数限制
- ✅ 自动去重和聚合

**应用场景**：
- 分析开发者在多个项目中的贡献
- 追踪跨项目的代码提交模式
- 生成多项目工作日志

#### 4. repo_authors - 仓库作者分析

分析同一仓库中不同作者的提交活动：

**功能特性**：
- ✅ 支持多作者同时查询
- ✅ 支持按登录名或邮箱查询
- ✅ 支持时间范围过滤
- ✅ 支持每作者最多抓取条数限制

**应用场景**：
- 分析团队协作情况
- 统计项目贡献者
- 生成团队工作报告

#### 5. repos_by_author - 作者仓库列表

查询指定作者参与的所有仓库：

**功能特性**：
- ✅ 支持最小提交数阈值过滤
- ✅ 支持时间范围过滤
- ✅ 支持仓库类型过滤
- ✅ 自动统计每个仓库的提交数

#### 6. authors_by_repo - 仓库活跃作者

查询指定仓库的所有活跃作者：

**功能特性**：
- ✅ 支持最小提交数阈值过滤
- ✅ 支持时间范围过滤
- ✅ 支持作者主键偏好（login/email/name）
- ✅ 自动统计每个作者的提交数

#### 7. user_repos - 用户仓库列表

查询用户拥有或 Star 的项目列表：

**功能特性**：
- ✅ 支持 owned/starred/both 三种模式
- ✅ 支持私有仓库查询（需要 token 权限）
- ✅ 支持 archived 和 forks 过滤
- ✅ 支持多种排序方式
- ✅ 最多返回 5000 条记录

### git_work 工具

`git_work` 工具支持从本地或远程仓库收集提交记录并生成工作日志：

**功能特性**：
- ✅ **多数据源支持**：支持本地 Git 仓库、GitHub、Gitee、GitLab
- ✅ **工作会话分析**：自动计算工作会话，检测并行工作时间
- ✅ **AI 总结生成**：集成 DeepSeek 和 OpenAI，生成中文工作总结
- ✅ **多项目支持**：支持同时分析多个本地或远程仓库
- ✅ **时间范围过滤**：支持指定时间范围进行提交分析
- ✅ **智能去重**：自动去重相同提交，避免重复统计

**工作日志格式**：
```markdown
## 工作日志 - 2025-11-05

### 项目 1: example-project
- **会话 1**: 09:00-12:00 (3小时)
  - 提交 1: 修复代码块空格问题
  - 提交 2: 优化滚动兼容性
- **会话 2**: 14:00-17:30 (3.5小时)
  - 提交 3: 添加新功能模块

### AI 总结
今天主要完成了代码格式优化和新功能开发，共工作 6.5 小时...
```

### git_comb 工具

`git_comb` 工具提供 Git 组合命令功能，支持复杂的 Git 操作流程：

**功能特性**：
- ✅ **危险命令防护**：默认禁止执行危险命令（如 `reset --hard`、`push --force`）
- ✅ **Dry Run 模式**：支持预览执行计划，不实际执行
- ✅ **超时控制**：可配置命令执行超时时间
- ✅ **错误处理**：完善的错误处理和提示机制

**支持的组合命令**：
- `commit`：提交更改
- `merge`：合并分支
- `reset`：重置操作
- `revert`：撤销提交
- `clean`：清理未跟踪文件
- `stash`：暂存更改
- 其他标准 Git 命令

### health 工具

`health` 工具提供健康检查功能，可以检查配置状态和工具可用性：

**功能特性**：
- ✅ **配置检查**：检查所有必需和可选的环境变量
- ✅ **密钥掩码显示**：安全地显示配置状态（密钥以掩码形式显示）
- ✅ **工具可用性检查**：检查各个工具的可用性
- ✅ **详细状态报告**：提供详细的配置和工具状态报告

### reload_config 工具

`reload_config` 工具支持配置热重载，无需重启服务器即可重新加载配置：

**功能特性**：
- ✅ **热重载**：支持在不重启服务器的情况下重新加载环境变量
- ✅ **配置验证**：自动验证新配置的有效性
- ✅ **错误提示**：配置错误时提供清晰的错误提示

## 安全特性

### 危险命令防护

默认情况下，以下危险命令需要显式设置 `allow_destructive: true` 才能执行：

- `reset --hard` - 硬重置，会丢失未提交的更改
- `clean -fd` - 强制清理未跟踪文件
- `push --force` - 强制推送，可能覆盖远程分支
- `stash drop` / `stash clear` - 删除 stash，可能丢失暂存更改
- 其他可能导致数据丢失的操作

### Dry Run 模式

对于以下命令支持 `dry_run: true` 预览执行计划：

- `commit`：预览提交内容
- `merge`：预览合并计划
- `reset`：预览重置操作
- `revert`：预览撤销操作
- `clean`：预览清理计划

### 错误处理

所有工具都包含完善的错误处理机制：

- **参数验证错误**：提供清晰的错误消息，指出哪个参数无效
- **命令执行错误**：返回 Git 命令的 stdout 和 stderr
- **超时错误**：可配置超时时间，超时时返回明确提示
- **网络错误**：区分 HTTP 错误和连接错误
- **API 密钥错误**：提示需要设置的环境变量

## 安装与配置

### 快速安装

```bash
# 1. 克隆仓库
git clone https://github.com/Mapoet/autoGit-MCP.git
cd autoGit-MCP

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 配置环境变量（见下方说明）
```

### 环境变量配置

autoGit-MCP 使用集中配置管理，支持从环境变量或 MCP 配置文件的 `env` 字段读取配置。

#### GitHub 配置

```bash
# GitHub Personal Access Token
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

#### Gitee 配置

```bash
# Gitee Personal Access Token
export GITEE_TOKEN=gitee_xxxxxxxxxxxxxxxxxxxx
```

#### GitLab 配置

```bash
# GitLab Personal Access Token
export GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
# GitLab 实例地址（可选，默认为 gitlab.com）
export GITLAB_URL=https://gitlab.com
```

#### AI 总结配置（可选）

```bash
# DeepSeek API Key（用于生成工作总结）
export DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
# 或使用 OpenAI API Key
export OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
```

#### 其他配置

```bash
# Git 命令超时时间（秒，默认 30）
export GIT_TIMEOUT=30
```

### MCP 配置文件示例

在 MCP 配置文件中添加 autoGit-MCP 服务器配置：

```json
{
  "mcpServers": {
    "autogit-mcp": {
      "command": "python",
      "args": ["http://localhost:9010/mcp/"],
      "env": {
        "GITHUB_TOKEN": "ghp_xxxxxxxxxxxxxxxxxxxx",
        "GITEE_TOKEN": "gitee_xxxxxxxxxxxxxxxxxxxx",
        "GITLAB_TOKEN": "glpat-xxxxxxxxxxxxxxxxxxxx",
        "DEEPSEEK_API_KEY": "sk-xxxxxxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

## 项目架构

autoGit-MCP 采用模块化设计，代码结构清晰：

```
autoGit-MCP/
├── README.md                    # 项目说明
├── requirements.txt             # Python 依赖
├── LICENSE                      # MIT 许可证
├── docs/                        # 文档目录
│   ├── code-structure.md       # 代码结构详细说明
│   ├── environment-variables.md # 环境变量详细说明
│   ├── git-cheatsheet.md       # Git 命令速查表
│   ├── git_comb.md             # Git 组合命令说明
│   ├── mcp-git-tool.md         # MCP Git 工具设计文档
│   └── troubleshooting.md      # 故障排查指南
├── src/                         # 源代码目录
│   └── git_tool/               # Git 工具模块
│       ├── __init__.py
│       ├── config.py           # 集中配置管理（Pydantic Settings）
│       ├── mcp_server.py       # MCP 服务器入口
│       ├── tools/               # 工具实现
│       │   ├── git_catalog.py   # 仓库查询工具
│       │   ├── git_work.py     # 工作日志工具
│       │   ├── git_comb.py     # Git 组合命令工具
│       │   ├── health.py       # 健康检查工具
│       │   └── reload_config.py # 配置重载工具
│       └── providers/          # 平台提供者
│           ├── github.py       # GitHub API 实现
│           ├── gitee.py        # Gitee API 实现
│           └── gitlab.py       # GitLab API 实现
└── tests/                       # 测试目录
```

### 核心组件

1. **config.py**：集中配置管理模块，使用 Pydantic Settings 管理环境变量
2. **git_catalog**：仓库和提交查询工具，支持 7 个子命令，覆盖 GitHub/Gitee/GitLab
3. **git_work**：工作日志生成工具，支持多数据源和 AI 总结
4. **git_comb**：Git 组合命令工具，支持危险命令防护和 Dry Run
5. **health**：健康检查工具，检查配置状态和工具可用性
6. **reload_config**：配置热重载工具，支持动态更新配置
7. **providers**：平台提供者模块，实现统一的 API 接口

## 使用场景

### 1. 代码仓库搜索与分析

**场景**：寻找特定技术栈的开源项目

```python
# 使用 git_catalog 搜索 Python 机器学习项目
{
    "tool": "git_catalog",
    "subcommand": "search_repos",
    "keyword": "machine learning",
    "language": "Python",
    "min_stars": 100,
    "sort": "stars",
    "order": "desc",
    "limit": 20
}
```

### 2. 跨项目贡献分析

**场景**：分析开发者在多个项目中的贡献情况

```python
# 使用 git_catalog 查询跨仓库提交
{
    "tool": "git_catalog",
    "subcommand": "cross_repos",
    "author_email": "developer@example.com",
    "owner": "my-org",
    "since": "2025-01-01",
    "until": "2025-11-05"
}
```

### 3. 工作日志生成

**场景**：自动生成每日/每周工作总结

```python
# 使用 git_work 生成工作日志
{
    "tool": "git_work",
    "sources": [
        {"type": "local", "path": "/path/to/project1"},
        {"type": "github", "repo": "owner/repo2"}
    ],
    "since": "2025-11-01",
    "until": "2025-11-05",
    "generate_summary": true
}
```

### 4. 团队协作分析

**场景**：分析团队在项目中的协作情况

```python
# 使用 git_catalog 查询仓库作者
{
    "tool": "git_catalog",
    "subcommand": "authors_by_repo",
    "repo_full": "my-org/my-project",
    "min_commits": 10,
    "since": "2025-01-01"
}
```

### 5. Git 操作自动化

**场景**：通过大语言模型执行复杂的 Git 操作

```python
# 使用 git_comb 执行 Git 操作
{
    "tool": "git_comb",
    "command": "commit",
    "args": {
        "message": "修复代码块空格问题",
        "allow_empty": false
    },
    "dry_run": false
}
```

## 技术亮点

### 1. 统一的平台接口

autoGit-MCP 通过统一的 `provider` 参数支持 GitHub/Gitee/GitLab 三大平台，所有工具都使用相同的接口设计，只需切换 `provider` 参数即可在不同平台间切换。

### 2. 集中配置管理

使用 Pydantic Settings 实现集中配置管理，支持：
- 从环境变量读取配置
- 从 MCP 配置文件的 `env` 字段读取配置
- 配置验证和类型检查
- 配置热重载

### 3. 完善的错误处理

所有工具都包含完善的错误处理机制：
- 参数验证错误：清晰的错误消息
- 命令执行错误：返回详细的 stdout 和 stderr
- 网络错误：区分 HTTP 错误和连接错误
- API 速率限制：自动处理速率限制

### 4. 安全防护机制

- **危险命令防护**：默认禁止执行危险命令
- **Dry Run 模式**：支持预览执行计划
- **密钥掩码显示**：健康检查时安全显示配置状态
- **超时控制**：防止命令执行超时

### 5. 智能工作日志

- **工作会话分析**：自动计算工作会话，检测并行工作时间
- **AI 总结生成**：集成 DeepSeek 和 OpenAI，生成中文工作总结
- **多项目支持**：支持同时分析多个项目
- **智能去重**：自动去重相同提交

## 版本更新

### v1.5（最新版本）

- ✅ **集中配置管理**：新增 `config.py` 模块，使用 Pydantic Settings 集中管理环境变量
- ✅ **健康检查工具**：新增 `health` 工具，检查配置状态和工具可用性
- ✅ **配置热重载**：新增 `reload_config` 工具，支持动态更新配置

### v1.4

- ✅ **多平台支持**：`git_catalog` 和 `git_work` 工具支持 Gitee 和 GitLab
- ✅ **统一接口设计**：通过 `provider` 参数选择平台
- ✅ **完整的 API 实现**：实现了所有 7 个子命令的 Gitee 和 GitLab 版本

### v1.3

- ✅ **新增 git_catalog 工具**：支持 7 个子命令查询 GitHub 仓库和提交活动
- ✅ **跨仓库提交查询**：支持查询指定作者在多个仓库中的提交记录
- ✅ **仓库作者统计**：支持查询仓库中多个作者的提交活动
- ✅ **速率限制优化**：优化 API 调用频率

### v1.2

- ✅ **新增 git_work 工具**：支持从本地/GitHub/Gitee/GitLab 收集提交并生成工作日志
- ✅ **工作会话分析**：自动计算工作会话，检测并行工作时间
- ✅ **AI 总结生成**：集成 DeepSeek 和 OpenAI

### v1.1

- ✅ **代码重构**：分离接口定义与实现逻辑
- ✅ **Pydantic V2 迁移**：所有验证器已迁移到 Pydantic V2
- ✅ **完善的错误处理**：为所有工具添加了分类异常处理

## 使用示例

### 示例 1：搜索高 Star 的 Python 项目

```python
{
    "tool": "git_catalog",
    "subcommand": "search_repos",
    "keyword": "data science",
    "language": "Python",
    "min_stars": 1000,
    "sort": "stars",
    "order": "desc",
    "limit": 10,
    "provider": "github"
}
```

### 示例 2：生成工作日志

```python
{
    "tool": "git_work",
    "sources": [
        {"type": "local", "path": "/path/to/project"},
        {"type": "github", "repo": "owner/repo"}
    ],
    "since": "2025-11-01",
    "until": "2025-11-05",
    "generate_summary": true,
    "ai_provider": "deepseek"
}
```

### 示例 3：执行 Git 操作（Dry Run）

```python
{
    "tool": "git_comb",
    "command": "merge",
    "args": {
        "branch": "feature-branch"
    },
    "dry_run": true
}
```

### 示例 4：检查配置状态

```python
{
    "tool": "health"
}
```

## 项目优势

### 1. 功能强大

- 支持三大主流代码托管平台（GitHub/Gitee/GitLab）
- 提供 7 个强大的仓库查询子命令
- 支持工作日志生成和 AI 总结
- 支持 Git 组合命令和自动化操作

### 2. 易于使用

- 统一的 MCP 接口，易于集成
- 清晰的文档和示例
- 完善的错误处理和提示
- 支持 Dry Run 模式，安全可靠

### 3. 安全可靠

- 危险命令防护机制
- 密钥掩码显示
- 超时控制
- 完善的错误处理

### 4. 可扩展性强

- 模块化设计
- 统一的平台接口
- 易于添加新功能
- 支持配置热重载

## 总结

autoGit-MCP 是一款专为大语言模型设计的 Git 自动化工具，它通过 Model Context Protocol (MCP) 提供强大的 Git 操作能力。无论是仓库搜索、提交分析、工作日志生成，还是 Git 操作自动化，autoGit-MCP 都能帮助开发者更高效地管理代码仓库。

```mermaid
graph LR
    A[大语言模型] -->|自然语言指令| B[autoGit-MCP]
    B -->|MCP 协议| C[Git 工具]
    C -->|API 调用| D[GitHub/Gitee/GitLab]
    C -->|Git 命令| E[本地仓库]
    D -->|数据返回| C
    E -->|结果返回| C
    C -->|结构化响应| B
    B -->|自然语言响应| A
    
    style A fill:#e3f2fd
    style B fill:#fff3e0
    style C fill:#f3e5f5
    style D fill:#e8f5e9
    style E fill:#e8f5e9
```

无论您是个人开发者、团队管理者，还是 DevOps 工程师，autoGit-MCP 都能帮助您通过大语言模型更智能、更高效地管理 Git 仓库，让代码管理变得更加简单。

---

**作者**：Mapoet  
**项目地址**：[https://github.com/Mapoet/autoGit-MCP](https://github.com/Mapoet/autoGit-MCP)  
**许可证**：MIT License  
**贡献**：欢迎提交 Issue 和 Pull Request

