# 🎯 A股智能分析助手

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-purple.svg)
![Tests](https://img.shields.io/badge/Tests-130%20Passed-success.svg)
![Version](https://img.shields.io/badge/Version-3.1.0-orange.svg)

**📈 A股短线交易分析助手 | Team-First 并行专家系统 | 插件化架构**

[核心特性](#-核心特性) • [快速开始](#-快速开始) • [功能模块](#-功能模块) • [更新日志](#-更新日志)

</div>

---

## 📖 简介

> 一个专为 **Claude Code** 设计的 A 股分析技能，采用「**短线交易信号 + 营收质量**」双轨研判体系。

当前版本已升级为 **v3.1.0**，具备完整的插件化架构、AKShare 数据源接入、回测框架、策略参数优化与归因分析能力。

### 与 Claude Code Skills 的适配度

- **适配度结论：高**
- **技能入口明确**：Claude Code 实际入口为 `SKILL.md`，README 主要承担安装、工程说明与发布说明
- **运行形态合适**：`SKILL.md + Python 辅助脚本 + 回归测试` 的结构，符合 Claude Code Skills 的仓库形态
- **迁移成本低**：核心脚本仅依赖 Python 标准库，路径以相对路径和 `Path(__file__)` 为主
- **质量约束完整**：具备数据真实性审计、采集质量门禁、身份校验、报告后置质量检查
- **插件化扩展**：支持自定义专家插件，动态发现与加载

---

## 🌟 核心特性

| 特性 | 说明 |
|:---:|:---|
| 👥 **8位专家协同** | 基本面大师 / 技术分析派 / 量化模型师 / 风险控制官 / 宏观策略师 / 行业研究家 / 消息面猎手 / 专家鉴别Agent |
| 🧭 **Team-First 默认并行** | 默认进入 `agent_team`，复杂任务强制 `full_parallel`，不再以 `single_flow` 作为主流程 |
| 🛡️ **数据真实性审计前置** | `run_data_auditor` 在所有分析前执行，校验日期回退、时间戳冲突、来源类别充分性 |
| 🔌 **插件化架构** | 支持 `ExpertPlugin` / `FilterPlugin` / `TransformPlugin` 三类插件，动态发现与加载 |
| 📊 **AKShare 数据源** | 接入 AKShare 免费数据源，支持历史K线、资金流向、新闻资讯等 |
| 🔄 **回测框架** | 内置回测引擎，支持信号生成、绩效指标计算、Markdown 报告输出 |
| 🎯 **策略参数优化** | Grid Search 自动寻优，支持评分权重、止损止盈参数优化 |
| 📈 **归因分析** | 分析策略盈亏因素，计算市场/交易/风险/胜率因子贡献度 |
| 🧾 **身份与价格双校验** | `run_expert_identifier_agent` 校验专家身份、标的一致性、价格锚点偏差 |
| 🔐 **安全密钥加载** | 支持 `EASTMONEY_APIKEY` 环境变量，回退读取 `.env.local/.env` |

---

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/wjt0321/china-stock-analyst.git
cd china-stock-analyst
pip install -r requirements.txt
```

将项目复制到 Claude Code 技能目录：

| 系统 | 路径 |
|:---|:---|
| 🪟 Windows | `%USERPROFILE%\.claude\skills\china-stock-analyst` |
| 🍎 macOS / 🐧 Linux | `~/.claude/skills/china-stock-analyst` |

### 验证安装

```bash
python -m pytest tests/test_stock_skill.py -v
```

当前测试结果：**130 个用例全部通过** ✅

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
| Web Search | 主数据源，高覆盖候选 |
| 东方财富 API | 结构化复核，关键字段校验 |
| AKShare | 免费数据源，历史K线/资金流向/新闻 |

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
├── SKILL.md                    # Claude Code 技能主入口
├── README.md                   # 项目说明
├── CLAUDE.md                   # 开发者指南
├── requirements.txt            # Python 依赖
├── config/
│   └── settings.json           # 外置配置
├── scripts/
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
├── tests/
│   ├── test_stock_skill.py     # 主测试
│   └── test_integration.py     # 集成测试
├── docs/
│   └── WINDOWS_SETUP.md        # Windows 配置指南
└── assets/
    └── 报告模板.md
```

---

## 🧪 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行主测试
python -m pytest tests/test_stock_skill.py -v

# 运行集成测试
python -m pytest tests/test_integration.py -v
```

测试覆盖：
- 路由与高意图激活
- 数据审计与重采降级
- 专家鉴别、身份与价格校验
- 回测框架与绩效指标
- 插件系统加载与执行
- 策略优化与归因分析
- **当前回归测试总量：130 项（全部通过）**

---

## 📜 开源协议

本项目采用 **MIT License**。详见 [LICENSE](LICENSE)。

---

## 📅 更新日志

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
