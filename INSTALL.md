# 安装指南

## 系统要求

- Python 3.7 或更高版本
- pip（Python 包管理器）
- （可选）Node.js 和 npm（用于 Mermaid CLI）

## 安装步骤

### 1. 克隆或下载项目

```bash
git clone <repository-url>
cd MD2WeChat
```

或者直接下载项目文件到本地。

### 2. 安装 Python 依赖

#### 方式一：使用 requirements.txt（推荐）

```bash
pip install -r requirements.txt
```

这会安装所有依赖，包括：
- `requests`（必需）
- `pygments`（推荐，用于语法高亮）
- `matplotlib`（可选，用于公式本地渲染）
- `sympy`（可选，用于公式优化）

#### 方式二：最小安装（仅核心功能）

如果你只需要基本功能，可以只安装核心依赖：

```bash
pip install requests
```

**注意**：
- 不安装 `pygments` 时，代码块将没有语法高亮
- 不安装 `matplotlib` 和 `sympy` 时，公式渲染将只使用 CodeCogs 在线服务（需要网络连接）

#### 方式三：分步安装

```bash
# 核心依赖（必需）
pip install requests

# 语法高亮（推荐）
pip install pygments

# 公式本地渲染（可选）
pip install matplotlib sympy
```

### 3. 安装 Mermaid CLI（可选）

如果需要支持 Mermaid 图表转换，需要安装 `@mermaid-js/mermaid-cli`。

#### 先安装 Node.js

**方式一：从官网下载安装（推荐）**

访问 [Node.js 官网](https://nodejs.org/) 下载并安装 Node.js（推荐 LTS 版本）。

**方式二：使用包管理器安装**

- **Ubuntu/Debian**:
  ```bash
  curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
  sudo apt-get install -y nodejs
  ```

- **macOS（使用 Homebrew）**:
  ```bash
  brew install node
  ```

- **Windows（使用 Chocolatey）**:
  ```powershell
  choco install nodejs-lts
  ```

**方式三：使用 nvm（Node Version Manager）**

如果需要管理多个 Node.js 版本，可以使用 nvm：

```bash
# 安装 nvm（Linux/macOS）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# 安装并使用 LTS 版本
nvm install --lts
nvm use --lts
```

**验证 Node.js 安装**：
```bash
node --version
npm --version
```

如果两个命令都能正常显示版本号，说明安装成功。

#### 安装 Mermaid CLI

**步骤 1：全局安装 Mermaid CLI**

```bash
npm install -g @mermaid-js/mermaid-cli
```

**注意权限问题**：

- **Linux/macOS**：如果遇到权限错误，使用 `sudo`：
  ```bash
  sudo npm install -g @mermaid-js/mermaid-cli
  ```

- **Windows**：以管理员身份运行 PowerShell 或命令提示符

**步骤 2：安装 Chrome Headless Shell（必需）**

Mermaid CLI 使用 Puppeteer 渲染图表，需要 Chrome headless shell。**这是必需的步骤**，否则会报错找不到 Chrome。

```bash
npx puppeteer browsers install chrome-headless-shell
```

**注意**：
- 这会下载约 100-200 MB 的 Chrome headless shell 到 `~/.cache/puppeteer` 目录I
- 不需要安装完整的 Google Chrome 浏览器，只需要 headless shell 即可
- 如果下载速度慢，可以设置镜像源（可选）：
  ```bash
  export PUPPETEER_DOWNLOAD_HOST=https://npm.taobao.org/mirrors
  npx puppeteer browsers install chrome-headless-shell
  ```

**验证安装**：
```bash
mmdc --version
```

如果显示版本号（如 `10.x.x`），说明安装成功。

**测试转换功能**（推荐）：
```bash
# 创建一个测试文件
echo 'graph TD; A-->B;' > test.mmd

# 转换为 PNG
mmdc -i test.mmd -o test.png

# 如果成功生成 test.png，说明安装正确
rm test.mmd test.png  # 清理测试文件
```

**注意**：
- 如果不安装 Mermaid CLI，包含 Mermaid 图表的 Markdown 文件会显示错误提示，但其他内容仍可正常转换
- Mermaid CLI 是全局安装的，一次安装后可在任何项目中使用
- 如果使用 nvm，确保在正确的 Node.js 环境中安装
- **必须安装 Chrome headless shell**，否则 Mermaid 图表无法转换

### 4. 验证安装

运行帮助命令验证安装是否成功：

```bash
python md2wechat.py --help
```

如果看到帮助信息，说明安装成功。

## 依赖说明

### 必需依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| requests | >=2.25.0 | 从网络 URL 下载图片和公式 |

### 推荐依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| pygments | >=2.7.0 | 代码块语法高亮 |

### 可选依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| matplotlib | >=3.3.0 | 本地渲染数学公式（当 CodeCogs 不可用时） |
| sympy | >=1.7.0 | 优化和渲染复杂的 LaTeX 公式 |

### 外部工具

| 工具 | 安装方式 | 用途 |
|------|---------|------|
| @mermaid-js/mermaid-cli | `npm install -g @mermaid-js/mermaid-cli` | 将 Mermaid 图表转换为 PNG |

## 常见问题

### Q: 安装 pygments 失败？

A: 确保使用正确的 pip 版本：
```bash
python -m pip install --upgrade pip
pip install pygments
```

### Q: 安装 mmdc 失败？

A: 确保已安装 Node.js，并且有管理员权限（Windows）或使用 sudo（Linux/Mac）：
```bash
# Linux/Mac
sudo npm install -g @mermaid-js/mermaid-cli

# Windows（以管理员身份运行）
npm install -g @mermaid-js/mermaid-cli
```

### Q: 公式渲染失败？

A: 
1. 如果使用 CodeCogs（默认），确保网络连接正常
2. 如果网络不可用，安装 `matplotlib` 和 `sympy` 以使用本地渲染

### Q: Mermaid 图表无法转换？

A: 确保已安装 `@mermaid-js/mermaid-cli` 并且在 PATH 中可用：
```bash
which mmdc  # Linux/Mac
where mmdc  # Windows
```

### Q: 报错 "Could not find Chrome"？

A: 这是因为 Mermaid CLI 需要 Chrome headless shell 来渲染图表。**不需要安装完整的 Google Chrome 浏览器**，只需要安装 Chrome headless shell：

```bash
npx puppeteer browsers install chrome-headless-shell
```

如果下载速度慢，可以使用国内镜像：
```bash
export PUPPETEER_DOWNLOAD_HOST=https://npm.taobao.org/mirrors
npx puppeteer browsers install chrome-headless-shell
```

安装完成后，Chrome headless shell 会保存在 `~/.cache/puppeteer` 目录中。

## 开发环境设置（可选）

如果需要开发或修改代码，可以使用虚拟环境：

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

