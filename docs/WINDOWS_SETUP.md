# Windows 11 环境配置指南

## 目录

- [环境要求](#环境要求)
- [Python 安装](#python-安装)
- [项目克隆](#项目克隆)
- [依赖安装](#依赖安装)
- [东方财富 API 配置](#东方财富-api-配置)
- [环境变量配置](#环境变量配置)
- [验证安装](#验证安装)
- [常见问题排查](#常见问题排查)

---

## 环境要求

| 组件 | 最低版本 | 推荐版本 |
|:---|:---|:---|
| Windows 11 | 22H2+ | 最新版本 |
| Python | 3.10 | 3.11 / 3.12 |
| Git | 2.40+ | 最新版本 |

---

## Python 安装

### 方式一：官网下载（推荐）

1. 访问 [Python 官网](https://www.python.org/downloads/windows/)
2. 下载 Python 3.11 或 3.12 Windows Installer
3. 运行安装程序，**务必勾选**：
   - [x] Add Python to PATH
   - [x] Install pip
   - [x] Install for all users（可选）

### 方式二：Microsoft Store

1. 打开 Microsoft Store
2. 搜索 "Python"
3. 选择 Python 3.11 或更高版本
4. 点击安装

### 方式三：winget（命令行）

```powershell
winget install Python.Python.3.11
```

### 验证安装

打开 PowerShell 或 CMD：

```powershell
python --version
pip --version
```

预期输出：
```
Python 3.11.x
pip xx.x.x from C:\Users\...\AppData\Local\Programs\Python\Python311\site-packages
```

---

## 项目克隆

### 克隆到本地

```powershell
# 方式1：克隆到自定义目录
git clone https://github.com/wjt0321/china-stock-analyst.git D:\Projects\china-stock-analyst

# 方式2：克隆到 Claude Code 技能目录
git clone https://github.com/wjt0321/china-stock-analyst.git "$env:USERPROFILE\.claude\skills\china-stock-analyst"
```

### 验证克隆成功

```powershell
cd "$env:USERPROFILE\.claude\skills\china-stock-analyst"
dir
```

预期看到以下文件：
```
AGENTS.md
CLAUDE.md
README.md
SKILL.md
scripts/
tests/
agents/
...
```

---

## 依赖安装

### 安装 Python 依赖

```powershell
cd "$env:USERPROFILE\.claude\skills\china-stock-analyst"
pip install -r requirements.txt
```

如果 `requirements.txt` 不存在或为空，使用：

```powershell
pip install pytest
```

### 验证依赖

```powershell
python -c "import sys; print(sys.executable)"
```

---

## 东方财富 API 配置

### 申请 API Key

1. 访问东方财富 Skills 平台
2. 注册/登录账号
3. 申请 API Key（免费额度 50次/日）
4. 复制生成的 Key

### 配置方式

#### 方式一：创建 .env.local 文件（推荐）

在项目根目录创建 `.env.local` 文件：

```powershell
# 在项目目录创建文件
cd "$env:USERPROFILE\.claude\skills\china-stock-analyst"
New-Item -ItemType File -Name ".env.local"
```

编辑文件内容：

```env
EASTMONEY_APIKEY=你的API密钥
EASTMONEY_BASE_URL=https://mkapi2.dfcfs.com/finskillshub/api/claw
EASTMONEY_ENDPOINT_NEWS_SEARCH=/news-search
EASTMONEY_ENDPOINT_QUERY=/query
EASTMONEY_ENDPOINT_STOCK_SCREEN=/stock-screen
```

#### 方式二：设置环境变量

```powershell
# 临时设置（当前会话有效）
$env:EASTMONEY_APIKEY = "你的API密钥"

# 永久设置（需要管理员权限）
[System.Environment]::SetEnvironmentVariable("EASTMONEY_APIKEY", "你的API密钥", [System.EnvironmentVariableTarget]::User)
```

#### 方式三：系统环境变量

1. 按 `Win + X` 选择 "系统"
2. 点击 "高级系统设置"
3. 点击 "环境变量"
4. 在 "用户变量" 或 "系统变量" 中点击 "新建"
5. 填写：
   - 变量名：`EASTMONEY_APIKEY`
   - 变量值：`你的API密钥`

### 验证配置

```powershell
python -c "from scripts.stock_utils import get_eastmoney_apikey; print(get_eastmoney_apikey(required=False) or '未配置')"
```

---

## 环境变量配置

### 必需的环境变量

| 变量名 | 必需 | 说明 | 获取方式 |
|:---|:---:|:---|:---|
| `EASTMONEY_APIKEY` | 可选 | 东方财富 API 密钥 | 东方财富 Skills 平台申请 |

### 可选的环境变量

| 变量名 | 说明 | 示例值 |
|:---|:---|:---|
| `EASTMONEY_BASE_URL` | API 地址 | `https://mkapi2.dfcfs.com/finskillshub/api/claw` |
| `CN_A_SHARE_HOLIDAYS` | 节假日（逗号分隔） | `2026-10-01,2026-10-02,2026-10-03` |
| `PYTHONPATH` | Python 模块路径 | `.` |

### Windows 环境变量设置方法

#### PowerShell（推荐）

```powershell
# 临时设置
$env:CN_A_SHARE_HOLIDAYS = "2026-10-01,2026-10-02"

# 永久设置
[System.Environment]::SetEnvironmentVariable("CN_A_SHARE_HOLIDAYS", "2026-10-01,2026-10-02", [System.Environment]::User)
```

#### CMD

```cmd
set CN_A_SHARE_HOLIDAYS=2026-10-01,2026-10-02
setx CN_A_SHARE_HOLIDAYS "2026-10-01,2026-10-02"
```

---

## 验证安装

### 运行单元测试

```powershell
cd "$env:USERPROFILE\.claude\skills\china-stock-analyst"
python -m unittest tests.test_stock_skill -v
```

预期输出：
```
----------------------------------------------------------------------
Ran 130 tests in 0.094s

OK
```

### 运行单个测试

```powershell
python -m unittest tests.test_stock_skill.TestStockSkill.test_should_enable_agent_team_for_multi_stock_request -v
```

### 测试报告质量检查

```powershell
python scripts\report_quality_gate.py stock-reports\000767_晋控电力_20260310.md
```

### 验证东方财富连接

```powershell
python -c "
from scripts.stock_utils import get_eastmoney_daily_usage
try:
    usage = get_eastmoney_daily_usage()
    print(f'API Key: 已配置')
    print(f'今日已用: {usage[\"count\"]} 次')
    print(f'剩余额度: {usage[\"remaining\"]} 次')
except Exception as e:
    print(f'配置状态: {e}')
"
```

---

## 常见问题排查

### 问题 1：Python 命令找不到

**症状**：
```
'python' is not recognized as an internal or external command
```

**解决**：
1. 重新运行 Python 安装程序
2. 勾选 "Add Python to PATH"
3. 或者手动添加到 PATH：
   ```powershell
   $env:PATH = "$env:PATH;C:\Users\你的用户名\AppData\Local\Programs\Python\Python311"
   ```

### 问题 2：pip 安装失败

**症状**：
```
WARNING: Retrying (Retry(total=0, connect=None, read=None, ...))
Connection error
```

**解决**：
```powershell
# 方法1：使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 方法2：检查网络代理
netsh winhttp show proxy
```

### 问题 3：API Key 读取失败

**症状**：
```
EastmoneyApiKeyMissingError: 环境变量 EASTMONEY_APIKEY 未配置
```

**解决**：
1. 确认 `.env.local` 文件在项目根目录
2. 确认 API Key 格式正确（无多余空格）
3. 重启终端/IDE 使环境变量生效

### 问题 4：编码错误

**症状**：
```
UnicodeDecodeError: 'gbk' codec can't decode byte 0xaf
```

**解决**：
在脚本开头添加编码声明，或设置环境变量：
```powershell
$env:PYTHONIOENCODING = "utf-8"
```

### 问题 5：缓存文件权限错误

**症状**：
```
PermissionError: [Errno 13] Permission denied: '.team_router_intent_cache.json'
```

**解决**：
项目已优化缓存路径，如仍有问题，尝试：
```powershell
# 清理缓存文件
Remove-Item "$env:USERPROFILE\.claude\skills\china-stock-analyst\scripts\.team_router_intent_cache.json" -ErrorAction SilentlyContinue
Remove-Item "$env:USERPROFILE\.claude\skills\china-stock-analyst\scripts\.eastmoney_daily_counter.json" -ErrorAction SilentlyContinue
```

### 问题 6：测试通过但实际运行报错

**解决**：
```powershell
# 清理 Python 缓存
Get-ChildItem -Path . -Include __pycache__ -Recurse -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Filter "*.pyc" -Recurse | Remove-Item -Force

# 重新运行测试
python -m unittest tests.test_stock_skill -v
```

---

## 快速启动命令汇总

```powershell
# 1. 进入项目目录
cd "$env:USERPROFILE\.claude\skills\china-stock-analyst"

# 2. 配置 API Key（如有）
# 创建 .env.local 文件并填入 EASTMONEY_APIKEY

# 3. 运行测试
python -m unittest tests.test_stock_skill -v

# 4. 分析单只股票
# 在 Claude Code 中输入：
# 请分析 600519（茅台）

# 5. 对比多只股票
# 在 Claude Code 中输入：
# 请对比中国能建和首开股份，给我短线建议
```

---

## 技术支持

- GitHub Issues: https://github.com/wjt0321/china-stock-analyst/issues
- 项目文档: 参见 `README.md` 和 `CLAUDE.md`
