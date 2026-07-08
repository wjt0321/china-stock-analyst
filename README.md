# 🎯 A股智能分析助手

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Tauri](https://img.shields.io/badge/Tauri-2.0+-24C8D8.svg)
![Tests](https://img.shields.io/badge/Tests-145%20Passed-success.svg)
![Version](https://img.shields.io/badge/Version-3.2.0-orange.svg)

**📈 A股短线交易分析助手 | Team-First 并行专家系统 | 插件化架构 | Tauri 桌面端**

[核心特性](#-核心特性) • [快速开始](#-快速开始) • [功能模块](#-功能模块) • [更新日志](#-更新日志)

</div>

---

## 📖 简介

> 一个 A 股短线分析工具，采用「**短线交易信号 + 营收质量**」双轨研判体系。

当前版本已升级为 **v3.2.0**，除了原有的 Claude Code Skill 能力，还新增了 **Tauri + Python Sidecar 桌面端**，
支持在 Windows 上独立运行：输入股票代码即可生成结构化短线分析报告，并可将标的加入自选看板长期跟踪。

### 运行形态

| 形态 | 入口 | 说明 |
|:---:|:---|:---|
| 💻 桌面端 | [`src-tauri/`](./src-tauri) + [`desktop/`](./desktop) | Tauri 2 + React + Python Sidecar，优先支持 Windows |
| 🤖 Claude Code Skill | 已归档至 [`docs/archive/02-skill-entry-20260403.md`](./docs/archive/02-skill-entry-20260403.md) | 早期以 Skill 方式运行，现由桌面端承载主要交互 |

### 核心适配度

- **质量约束完整**：具备数据真实性审计、采集质量门禁、身份校验、报告后置质量检查
- **插件化扩展**：支持自定义专家插件，动态发现与加载
- **多源交叉验证**：同时接入多个数据源，取多数一致值，降低单点错误风险

---

## 🌟 核心特性

| 特性 | 说明 |
|:---:|:---|
| 💻 **桌面端应用** | Tauri 2 + React 前端 + Python Sidecar，独立窗口运行，支持分析/看板/报告/设置 |
| 👥 **8位专家协同** | 基本面大师 / 技术分析派 / 量化模型师 / 风险控制官 / 宏观策略师 / 行业研究家 / 消息面猎手 / 专家鉴别Agent |
| 🧭 **Team-First 默认并行** | 默认进入 `agent_team`，复杂任务强制 `full_parallel`，不再以 `single_flow` 作为主流程 |
| 🛡️ **数据真实性审计前置** | `run_data_auditor` 在所有分析前执行，校验日期回退、时间戳冲突、来源类别充分性 |
| 🔌 **插件化架构** | 支持 `ExpertPlugin` / `FilterPlugin` / `TransformPlugin` 三类插件，动态发现与加载 |
| 📊 **多源交叉验证** | 同时接入东方财富、新浪财经、腾讯财经、同花顺、AKShare 等数据源，取多数一致值 |
| 🔄 **回测框架** | 内置回测引擎，支持信号生成、绩效指标计算、Markdown 报告输出 |
| 🎯 **策略参数优化** | Grid Search 自动寻优，支持评分权重、止损止盈参数优化 |
| 📈 **归因分析** | 分析策略盈亏因素，计算市场/交易/风险/胜率因子贡献度 |
| 🧾 **身份与价格双校验** | `run_expert_identifier_agent` 校验专家身份、标的一致性、价格锚点偏差 |
| 🔐 **安全密钥加载** | 支持 `EASTMONEY_APIKEY` 环境变量，回退读取 `.env.local/.env` |

---

## 🚀 快速开始

### 桌面端（推荐）

```bash
git clone https://github.com/wjt0321/china-stock-analyst.git
cd china-stock-analyst

# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖
cd src-tauri/ui && npm install
cd ../..

# 启动开发模式
npx --prefix src-tauri/ui tauri dev
```

首次启动会编译 Rust 端，请耐心等待窗口弹出。

### 原 Claude Code Skill 形态（已归档）

早期以 Claude Code Skill 方式运行，相关入口与说明已归档至 [`docs/archive/`](./docs/archive/)。
如仍需 Skill 形态，可参考：
- 技能定义：`docs/archive/02-skill-entry-20260403.md`
- 改进记录：`docs/archive/04-improvement-report-20260403.md`

### 验证安装

```bash
# 核心回归测试
python -m pytest tests/test_stock_skill.py -v

# 桌面端测试
python -m pytest desktop/tests -v
```

当前测试结果：**145 项核心测试 + 62 项桌面端测试全部通过** ✅

### 配置（可选）

**东方财富 API**（结构化数据增强）：

```env
# .env.local
EASTMONEY_APIKEY=你的API密钥
```

**AKShare**（免费数据源，无需配置）：

```bash
pip install akshare
```

---

## 📦 功能模块

### 1. 数据采集

| 模块 | 说明 |
|:---|:---|
| Scrapling 适配器 | 本地爬取东方财富、新浪财经、腾讯财经、同花顺等公开行情数据 |
| 东方财富 API | 结构化复核，关键字段校验（需配置 API Key） |
| AKShare | 免费数据源，历史K线/资金流向/新闻 |
| 多源对齐 | 同一字段多个源交叉验证，取多数一致值 |

### 2. 分析引擎

| 模块 | 文件 | 说明 |
|:---|:---|:---|
| 团队路由 | `scripts/team_router.py` | Team-First 并行调度 |
| 报告生成 | `scripts/generate_report.py` | Markdown 报告输出 |
| 技术指标 | `scripts/technical_indicators.py` | ATR/VWAP/RSI/支撑压力位 |
| 技术报告 | `scripts/technical_report.py` | 技术分析报告生成 |

### 3. 回测系统

| 模块 | 文件 | 说明 |
|:---|:---|:---|
| 回测框架 | `scripts/backtest_framework.py` | 信号回测引擎 |
| AKShare 集成 | `scripts/backtest_runner.py` | 数据源打通 |
| 策略优化 | `scripts/strategy_optimizer.py` | Grid Search 参数优化 |
| 归因分析 | `scripts/strategy_optimizer.py` | 盈亏因子分析 |

### 4. 插件系统

| 模块 | 文件 | 说明 |
|:---|:---|:---|
| 插件基类 | `scripts/plugin_base.py` | ExpertPlugin/FilterPlugin/TransformPlugin |
| 插件加载器 | `scripts/plugin_loader.py` | 动态发现与加载 |
| 示例插件 | `plugins/expert/` | 技术指标/资金流向插件 |

### 5. 配置系统

| 文件 | 说明 |
|:---|:---|
| `config/settings.json` | 外置配置（评分权重/质量门禁/回测参数） |
| `scripts/config_loader.py` | 配置加载器 |

---

## 💡 使用示例

### 📊 单标的分析

```text
请分析 600519（茅台）
看看珠江股份 600684 怎么样
```

### 🔍 多标的对比

```text
请对比中国能建和首开股份，给我短线建议
分析一下电力板块：晋控电力、长源电力
```

### ⚡ 高意图复杂请求

```text
请今日采集市场数据，先筛选10支，再组织专家讨论，最后推荐3支
```

### 🔄 回测分析

```python
from scripts.backtest_runner import quick_backtest

result = quick_backtest("600519")
print(f"总收益: {result.metrics.total_return:.2%}")
print(f"夏普比率: {result.metrics.sharpe_ratio:.2f}")
```

### 🎯 策略优化

```python
from scripts.strategy_optimizer import StrategyOptimizer

optimizer = StrategyOptimizer()
result = optimizer.optimize_scoring_weights("600519", objective="sharpe_ratio")
print(optimizer.get_optimization_report(result))
```

### 🔌 插件扩展

```python
from scripts.plugin_base import ExpertPlugin, PluginContext, PluginResult

class MyExpertPlugin(ExpertPlugin):
    name = "my_expert"
    version = "1.0.0"
    category = "custom"
    
    def can_handle(self, context: PluginContext) -> bool:
        return "自定义" in context.request
    
    def execute(self, context: PluginContext) -> PluginResult:
        # 你的分析逻辑
        return PluginResult(success=True, content="分析结果")
```

---

## 🎭 执行流程

### 固定链路

```text
run_data_auditor
→ collect_data
→ run_fundamental_expert
→ run_technical_expert
→ run_quant_flow_expert
→ run_risk_expert
→ run_macro_expert
→ run_industry_researcher_expert
→ run_event_hunter_expert
→ run_expert_identifier_agent
→ supervisor_review
→ render_report
```

---

## 📊 评分体系

### 双轨评分

| 维度 | 权重 | 说明 |
|:---|:---:|:---|
| 📈 短线动量分 | 40% | 资金、量价、关键位突破 |
| 💰 营收质量分 | 35% | 营收同比/环比、口径一致性 |
| 🛡️ 风险约束分 | 25% | 波动率、回撤、监管与事件风险 |

最终标签：`可做` / `观察` / `回避`

---

## 📁 项目结构

```text
china-stock-analyst/
├── README.md                   # 项目说明（本文件）
├── CLAUDE.md                   # 开发者指南
├── requirements.txt            # Python 依赖
├── config/
│   └── settings.json           # 外置配置
├── desktop/                    # Python Sidecar 服务
│   ├── service.py              # Sidecar 主服务
│   ├── storage.py              # SQLite 持久化
│   ├── data_fetcher.py         # 多源数据获取
│   ├── analysis_engine.py      # 分析引擎
│   ├── report_renderer.py      # Markdown 报告渲染
│   └── scrapling_adapters/     # Scrapling 数据源适配器
├── src-tauri/                  # Tauri 桌面端
│   ├── ui/                     # React + Vite 前端
│   └── src/                    # Rust 宿主代码
├── scripts/                    # 原 Skill 核心脚本
│   ├── team_router.py          # 团队路由
│   ├── generate_report.py      # 报告生成
│   ├── stock_utils.py          # 工具函数
│   ├── technical_indicators.py # 技术指标计算
│   ├── technical_report.py     # 技术分析报告
│   ├── backtest_framework.py   # 回测框架
│   ├── backtest_runner.py      # 回测运行器
│   ├── akshare_adapter.py      # AKShare 适配器
│   ├── strategy_optimizer.py   # 策略优化器
│   ├── plugin_base.py          # 插件基类
│   ├── plugin_loader.py        # 插件加载器
│   └── config_loader.py        # 配置加载器
├── plugins/
│   ├── __init__.py
│   └── expert/
│       ├── technical_indicators_plugin.py
│       └── fund_flow_plugin.py
├── agents/                     # 专家定义
├── tests/                      # 回归测试
├── stock-reports/              # 生成的 Markdown 报告
├── docs/
│   ├── archive/                # 历史文档归档（编号 01-06）
│   ├── plans/                  # 实施计划
│   ├── superpowers/            # 设计规格
│   └── WINDOWS_SETUP.md        # Windows 配置指南
└── assets/
    └── 报告模板.md
```

---

## 🧪 运行测试

```bash
# 运行核心回归测试
python -m pytest tests/ -v

# 运行主测试
python -m pytest tests/test_stock_skill.py -v

# 运行集成测试
python -m pytest tests/test_integration.py -v

# 运行桌面端测试
python -m pytest desktop/tests -v
```

测试覆盖：
- 路由与高意图激活
- 数据审计与重采降级
- 专家鉴别、身份与价格校验
- 回测框架与绩效指标
- 插件系统加载与执行
- 策略优化与归因分析
- 桌面端持久化与 Sidecar 命令
- **当前回归测试总量：145 项核心测试 + 62 项桌面端测试（全部通过）**

---

## 📜 开源协议

本项目采用 **MIT License**。详见 [LICENSE](LICENSE)。

---

## 💻 桌面端

项目已支持 **Tauri 2 + Python Sidecar** 桌面端，作为当前主推形态。

### 已具备的能力（MVP）

| 模块 | 功能 |
|:---|:---|
| 分析向导 | 输入股票代码，多源采集后生成结构化短线分析报告 |
| 自选股看板 | 在分析页点击「加入自选」添加，支持一键重新分析 |
| 报告列表 | 按标题展示历史报告，支持删除，点击标题查看正文 |
| 设置 | 数据源优先级、LLM 配置、分析参数（持续完善） |

### 开发运行

```bash
# 1. 安装前端依赖
cd src-tauri/ui && npm install

# 2. 安装 Python 依赖（项目根目录）
cd ../..
pip install -r requirements.txt

# 3. 启动 Tauri 开发模式
npx --prefix src-tauri/ui tauri dev
```

首次启动会编译 Rust 端，可能需要 1-3 分钟。

### 打包

```bash
python scripts/build_sidecar.py
cd src-tauri && cargo tauri build
```

### 相关文档

- 设计文档：`docs/superpowers/specs/2026-07-08-desktop-app-design.md`
- 实施计划：`docs/superpowers/plans/2026-07-08-desktop-app-implementation-plan.md`

---

## 🌐 数据来源与致谢

本项目坚持「**多源交叉验证，免费合规优先**」原则。分析时会从多个数据源获取同一字段，
通过多数一致机制降低单点错误风险。当前接入的数据源包括：

| 数据源 | 类型 | 主要用途 |
|:---|:---|:---|
| [Scrapling](https://git.wxbfnnas.com/wxb/scrapling.git) | 本地网页爬取框架 | 爬取东方财富、新浪财经、腾讯财经、同花顺等公开行情页 |
| [AKShare](https://www.akshare.xyz/) | 开源 Python 金融数据接口 | 历史K线、资金流向、基本面数据 |
| [东方财富](https://www.eastmoney.com/) | 公开市场数据 | 实时行情、财务指标复核 |
| [新浪财经](https://finance.sina.com.cn/) | 公开市场数据 | 实时行情、K线数据 |
| [腾讯财经](https://finance.qq.com/) | 公开市场数据 | 实时行情、K线数据 |
| [同花顺](https://www.10jqka.com.cn/) | 公开市场数据 | 行情与基本面数据 |

> 💡 **特别感谢**：
> - [Scrapling](https://git.wxbfnnas.com/wxb/scrapling.git) 提供了轻量、可扩展的本地网页爬取能力，
>   让项目能够在不依赖外部搜索 API 的情况下直接获取公开行情数据，显著提升了数据可控性与准确性。
> - [AKShare](https://www.akshare.xyz/) 社区提供了丰富、免费且持续维护的 A 股数据接口，
>   让个人开发者也能以合规方式获取高质量金融数据。
>
> 公开市场数据仅供学习研究，请勿用于高频交易或商业用途。

> ⚠️ **数据声明**：所有数据源均来自公开接口或开源库，项目不保证数据实时性与完整性。
> 分析结果仅供参考，不构成投资建议。

---

## 📅 更新日志

### v3.2.0 (2026-07-08)

- **桌面端 MVP**：
  - 新增 Tauri 2 + React + Python Sidecar 桌面端
  - 支持分析向导、自选股看板、报告列表、报告删除
  - 看板最近报告以标题展示，点击可跳转查看
- **历史文档归档**：
  - 将 SKILL.md、审查报告、改进报告等 6 份历史资料归档至 `docs/archive/`
  - README 新增数据来源致谢与桌面端使用说明

### v3.1.0 (2026-05-01)

- **策略参数优化器**：
  - Grid Search 自动寻优
  - 支持评分权重、止损止盈参数优化
  - 多目标函数（收益率/夏普比率/胜率/风险调整收益）
- **回测归因分析**：
  - 分析市场/交易/风险/胜率因子贡献度
  - 生成归因分析 Markdown 报告
- 测试回归通过：**130 项全部通过**

### v3.0.0 (2026-05-01)

- **插件化架构**：
  - 新增 `ExpertPlugin` / `FilterPlugin` / `TransformPlugin` 抽象基类
  - 动态发现与加载插件
  - 示例插件：技术指标分析、资金流向分析
- **team_router 集成**：
  - 新增 `get_available_plugins()` / `execute_plugin()` API
  - 延迟加载，可选依赖
- 测试回归通过：**130 项全部通过**

### v2.6.0 (2026-05-01)

- **配置模块集成**：
  - 硬编码常量迁移到 `config/settings.json`
  - 新增 `config_loader.py` 动态加载
- **回测框架与 AKShare 打通**：
  - 新增 `backtest_runner.py` 集成数据源
  - 支持自动信号生成
- **技术指标与报告联动**：
  - 新增 `technical_report.py` 生成技术分析报告
  - 支持 ATR/VWAP/RSI/支撑压力位/量比/动量分析
- **性能优化**：
  - 20+ 正则表达式预编译
- 测试回归通过：**145 项全部通过**

### v2.5.0 (2026-05-01)

- **AKShare 数据源接入**：
  - 新增 `akshare_adapter.py` 数据适配器
  - 支持历史K线、资金流向、新闻资讯
- **跨平台路径支持**：
  - 新增 `platform_paths.py` 统一路径管理
- **Windows 环境文档**：
  - 新增 `docs/WINDOWS_SETUP.md`
- **技术指标计算器**：
  - 新增 `technical_indicators.py`
  - ATR/VWAP/RSI/支撑压力位计算
- **回测框架**：
  - 新增 `backtest_framework.py`
  - 支持信号回测、绩效指标、Markdown 报告
- 测试回归通过：**145 项全部通过**

### v2.4.3 (2026-04-03)

- 发布 Release/Tag：`2.4.3`
- **README 与 SKILL 文档收敛**
- **报告质量门禁增强**
- **批量质量检查增强**
- 测试回归通过：**130 项全部通过**

---

## 📌 免责声明

> ⚠️ 所有分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。
