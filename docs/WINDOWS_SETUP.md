# Windows 11 环境配置指南

## 目录

- [环境要求](#环境要求)
- [Python 安装](#python-安装)
- [项目克隆](#项目克隆)
- [依赖安装](#依赖安装)
- [东方财富 API 配置](#东方财富-api-配置)
- [AKShare 配置](#akshare-配置)
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
config/
scripts/
plugins/
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

### 核心依赖

| 包名 | 用途 |
|:---|:---|
| `akshare` | 免费 A 股数据源 |
| `pytest` | 测试框架 |

### 验证依赖

```powershell
python -c "import akshare; print('AKShare:', akshare.__version__)"
python -c "import pytest; print('Pytest:', pytest.__version__)"
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
cd "$env:USERPROFILE\.claude\skills\china-stock-analyst"
New-Item -ItemType File -Name ".env.local"
```

编辑文件内容：

```env
EASTMONEY_APIKEY=你的API密钥
EASTMONEY_BASE_URL=https://mkapi2.dfcfs.com/finskillshub/api/claw
```

#### 方式二：设置环境变量

```powershell
# 临时设置（当前会话有效）
$env:EASTMONEY_APIKEY = "你的API密钥"

# 永久设置（需要管理员权限）
[System.Environment]::SetEnvironmentVariable("EASTMONEY_APIKEY", "你的API密钥", [System.EnvironmentVariableTarget]::User)
```

### 验证配置

```powershell
python -c "from scripts.stock_utils import get_eastmoney_apikey; print(get_eastmoney_apikey(required=False) or '未配置')"
```

---

## AKShare 配置

AKShare 是免费的 A 股数据源，**无需申请 API Key**。

### 安装

```powershell
pip install akshare
```

### 验证安装

```powershell
python -c "import akshare as ak; df = ak.stock_zh_a_hist(symbol='600519', period='daily', start_date='20260101', end_date='20260430', adjust='qfq'); print(f'获取到 {len(df)} 条K线数据')"
```

### 支持的数据

| 数据类型 | 说明 |
|:---|:---|
| 历史K线 | 日线/分钟线 |
| 资金流向 | 主力/散户分离 |
| 实时买卖盘 | Level2 五档 |
| 个股新闻 | 实时财经新闻 |
| 涨停板 | 当日涨停股列表 |

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

---

## 验证安装

### 运行单元测试

```powershell
cd "$env:USERPROFILE\.claude\skills\china-stock-analyst"
python -m pytest tests/test_stock_skill.py -v
```

预期输出：
```
============================= 130 passed in 0.28s ==============================
```

### 运行集成测试

```powershell
python -m pytest tests/test_integration.py -v
```

### 测试 AKShare 数据获取

```powershell
python -c "
from scripts.akshare_adapter import AKShareAdapter
adapter = AKShareAdapter()
data = adapter.get_full_data('600519')
print(f'股票: {data.stock_name}')
print(f'K线: {len(data.candles)} 条')
print(f'资金流向: {len(data.fund_flow)} 条')
"
```

### 测试插件系统

```powershell
python -c "
from scripts.team_router import get_available_plugins
plugins = get_available_plugins()
for p in plugins:
    print(f'{p[\"name\"]} (v{p[\"version\"]}) - {p[\"category\"]}')
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
# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 问题 3：AKShare 获取数据失败

**症状**：
```
ConnectionError: Unable to connect to remote server
```

**解决**：
1. 检查网络连接
2. 尝试使用代理：
   ```powershell
   $env:HTTP_PROXY = "http://127.0.0.1:7890"
   $env:HTTPS_PROXY = "http://127.0.0.1:7890"
   ```

### 问题 4：编码错误

**症状**：
```
UnicodeDecodeError: 'gbk' codec can't decode byte 0xaf
```

**解决**：
```powershell
$env:PYTHONIOENCODING = "utf-8"
```

### 问题 5：缓存文件权限错误

**解决**：
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
python -m pytest tests/test_stock_skill.py -v
```

---

## 快速启动命令汇总

```powershell
# 1. 进入项目目录
cd "$env:USERPROFILE\.claude\skills\china-stock-analyst"

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行测试
python -m pytest tests/test_stock_skill.py -v

# 4. 测试 AKShare
python -c "from scripts.akshare_adapter import AKShareAdapter; print(AKShareAdapter().get_full_data('600519').stock_name)"

# 5. 在 Claude Code 中使用
# 请分析 600519（茅台）
# 请对比中国能建和首开股份
```

---

## 新功能使用示例

### 回测分析

```powershell
python -c "
from scripts.backtest_runner import quick_backtest
result = quick_backtest('600519')
if result:
    print(f'总收益: {result.metrics.total_return:.2%}')
    print(f'夏普比率: {result.metrics.sharpe_ratio:.2f}')
"
```

### 策略优化

```powershell
python -c "
from scripts.strategy_optimizer import StrategyOptimizer
optimizer = StrategyOptimizer()
result = optimizer.optimize_scoring_weights('600519', objective='sharpe_ratio')
print(optimizer.get_optimization_report(result))
"
```

### 技术指标分析

```powershell
python -c "
from scripts.akshare_adapter import AKShareAdapter
from scripts.technical_report import render_technical_report_markdown

adapter = AKShareAdapter()
data = adapter.get_full_data('600519')
print(render_technical_report_markdown(data.candles))
"
```

---

## 技术支持

- GitHub Issues: https://github.com/wjt0321/china-stock-analyst/issues
- 项目文档: 参见 `README.md` 和 `CLAUDE.md`
