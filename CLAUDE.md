# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

A股智能分析助手（china-stock-analyst）是一个 Claude Code 技能，用于 A 股短线交易分析。核心特点：「短线交易信号 + 营收质量」双轨研判体系，采用 Team-First 默认并行架构，支持插件化扩展、回测框架、策略优化。

当前版本：**v3.1.0**

## 运行测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行主测试
python -m pytest tests/test_stock_skill.py -v

# 运行集成测试
python -m pytest tests/test_integration.py -v

# 运行单个测试方法
python -m unittest tests.test_stock_skill.TestStockSkill.test_should_enable_agent_team_for_multi_stock_request -v
```

测试覆盖范围：路由判定、数据审计、专家鉴别、舆情治理、东方财富 API 集成、回测框架、插件系统、策略优化、归因分析。当前回归测试：**145 项全部通过**。

## 目录结构

```
china-stock-analyst/
├── SKILL.md                    # 技能完整文档（v3.1.0）
├── README.md                   # 项目说明
├── CLAUDE.md                   # 开发者指南
├── requirements.txt            # Python 依赖
├── config/
│   └── settings.json           # 外置配置
├── scripts/
│   ├── team_router.py          # 执行模式路由、插件系统
│   ├── generate_report.py      # 报告生成、数据解析、评分计算
│   ├── stock_utils.py          # 股票验证、时间戳处理、东方财富 API 封装
│   ├── report_constants.py     # 报告常量
│   ├── technical_indicators.py # 技术指标计算
│   ├── technical_report.py     # 技术分析报告生成
│   ├── backtest_framework.py   # 回测框架
│   ├── backtest_runner.py      # 回测运行器
│   ├── akshare_adapter.py      # AKShare 数据适配器
│   ├── strategy_optimizer.py   # 策略参数优化器
│   ├── plugin_base.py          # 插件抽象基类
│   ├── plugin_loader.py        # 插件加载器
│   ├── config_loader.py        # 配置加载器
│   └── platform_paths.py       # 跨平台路径管理
├── plugins/
│   ├── __init__.py
│   └── expert/
│       ├── technical_indicators_plugin.py
│       └── fund_flow_plugin.py
├── agents/                     # 预配置专家 Agent 定义
├── tests/
│   ├── test_stock_skill.py     # 单元测试
│   └── test_integration.py     # 集成测试
├── docs/
│   └── WINDOWS_SETUP.md        # Windows 配置指南
└── assets/
    └── 报告模板.md              # Obsidian 风格报告模板
```

## 核心架构

### 双模式执行路由

由 `scripts/team_router.py` 的 `should_use_agent_team()` 判定：

**触发 full_parallel 模式**（高意图复杂任务）：
- 请求中出现 2 个及以上 A 股代码（6位数字，以 0/3/6 开头）
- 请求包含关键词：对比、验证、复盘、冲突、分歧、组合、股票池、候选、多股
- 高意图串联任务：「今日采集 + 10支筛选 + 专家讨论 + 3支推荐」

**触发 lite_parallel 模式**（轻量请求）：
- 轻量单标的分析请求
- 同一流程范式降级，减少部分专家节点

### 固定技能链路

**full_parallel 模式（12步）**：完整专家链
```
run_data_auditor → collect_data → run_fundamental_expert → run_technical_expert →
run_quant_flow_expert → run_risk_expert → run_macro_expert →
run_industry_researcher_expert → run_event_hunter_expert →
run_expert_identifier_agent → supervisor_review → render_report
```

### 8位专家角色

| 编号 | 角色 | 分析重点 | Agent 文件 |
|------|------|----------|------------|
| 01 | 基本面大师 | 财务数据、估值、行业地位 | `agents/stock-fundamental-expert.md` |
| 02 | 技术分析派 | K线形态、均线、MACD、KDJ、短线指标 | `agents/stock-technical-expert.md` |
| 03 | 量化模型师 | 数据驱动、因子分析、资金流向 | `agents/stock-quant-flow-expert.md` |
| 04 | 风险控制官 | 下行风险、仓位管理、止损位 | `agents/stock-risk-expert.md` |
| 05 | 宏观策略师 | 政策面、资金面、市场周期 | `agents/stock-macro-expert.md` |
| 06 | 行业研究家 | 行业景气、竞争格局、驱动因子 | `agents/stock-industry-researcher.md` |
| 07 | 消息面猎手 | 公告政策、监管信号、事件冲击 | `agents/stock-event-hunter.md` |
| 08 | 专家鉴别Agent | 身份校验、标的一致性、价格锚点偏差 | `agents/stock-identity-auditor.md` |

## 新增模块

### 1. 插件系统

**位置**：`scripts/plugin_base.py` + `scripts/plugin_loader.py`

**三类插件基类**：
- `ExpertPlugin`：专家插件，自定义分析逻辑
- `FilterPlugin`：过滤器插件，数据过滤
- `TransformPlugin`：转换器插件，数据转换

**使用方式**：
```python
from scripts.team_router import get_available_plugins, execute_plugin

# 获取可用插件
plugins = get_available_plugins()

# 执行插件
result = execute_plugin(
    plugin_name="technical_indicators",
    stock_code="600519",
    stock_name="贵州茅台",
    request="分析技术指标"
)
```

**示例插件**：
- `plugins/expert/technical_indicators_plugin.py`
- `plugins/expert/fund_flow_plugin.py`

### 2. 回测框架

**位置**：`scripts/backtest_framework.py` + `scripts/backtest_runner.py`

**快速回测**：
```python
from scripts.backtest_runner import quick_backtest

result = quick_backtest("600519")
print(f"总收益: {result.metrics.total_return:.2%}")
print(f"夏普比率: {result.metrics.sharpe_ratio:.2f}")
print(f"最大回撤: {result.metrics.max_drawdown:.2%}")
```

**绩效指标**：
- 总收益率
- 年化收益率
- 最大回撤
- 夏普比率
- 胜率
- 盈亏比

### 3. 策略参数优化

**位置**：`scripts/strategy_optimizer.py`

**Grid Search 优化**：
```python
from scripts.strategy_optimizer import StrategyOptimizer

optimizer = StrategyOptimizer()

# 优化评分权重
result = optimizer.optimize_scoring_weights("600519", objective="sharpe_ratio")

# 优化止损止盈
result = optimizer.optimize_stop_loss_take_profit("600519")

# 获取优化报告
print(optimizer.get_optimization_report(result))
```

**优化目标**：
- `total_return`：总收益率
- `sharpe_ratio`：夏普比率
- `win_rate`：胜率
- `risk_adjusted`：风险调整收益

### 4. 归因分析

**位置**：`scripts/strategy_optimizer.py`

**使用方式**：
```python
from scripts.strategy_optimizer import BacktestAttributor

attributor = BacktestAttributor()
attribution = attributor.analyze(backtest_result, candles, fund_flow)
print(attributor.get_attribution_report(attribution))
```

**归因因子**：
- 市场因子：基准收益贡献
- 交易因子：主动交易贡献
- 风险因子：回撤影响
- 胜率因子：胜率贡献

### 5. 技术指标计算

**位置**：`scripts/technical_indicators.py`

**支持的指标**：
- ATR（平均真实波幅）
- VWAP（成交量加权均价）
- RSI（相对强弱指标）
- 支撑/压力位
- 量比
- 动量

**使用方式**：
```python
from scripts.technical_indicators import calc_full_indicators

indicators = calc_full_indicators(candles)
print(f"ATR: {indicators['atr'].atr}")
print(f"VWAP: {indicators['vwap'].vwap}")
print(f"RSI: {indicators['rsi']}")
```

### 6. AKShare 数据适配器

**位置**：`scripts/akshare_adapter.py`

**支持的数据**：
- 历史K线数据（日线/分钟线）
- 资金流向数据（主力/散户分离）
- 实时买卖盘（Level2）
- 个股新闻资讯
- 涨停板数据

**使用方式**：
```python
from scripts.akshare_adapter import AKShareAdapter

adapter = AKShareAdapter()
data = adapter.get_full_data("600519")
print(f"K线数据: {len(data.candles)} 条")
print(f"资金流向: {len(data.fund_flow)} 条")
```

### 7. 配置系统

**位置**：`config/settings.json` + `scripts/config_loader.py`

**主要配置项**：
- `scoring`：评分权重配置
- `quality_gate`：质量门禁阈值
- `backtest`：回测参数
- `technical_indicators`：技术指标参数
- `akshare`：AKShare 配置

**使用方式**：
```python
from scripts.config_loader import get_scoring_weights, get_backtest_config

weights = get_scoring_weights()
backtest = get_backtest_config()
```

## 数据源配置

### 东方财富 API

| 端点 | 功能 | 触发关键词 |
|------|------|------------|
| `news-search` | 金融资讯检索 | 资讯、新闻、公告、研报、舆情 |
| `query` | 结构化金融数据查询 | 行情、资金流向、财务、估值、指标 |
| `stock-screen` | 自然语言智能选股 | 选股、筛选、股票池、低价股、高增长 |

配置方式：
1. 复制 `.env.example` 为 `.env.local`
2. 填入自己的 API Key（`EASTMONEY_APIKEY`）

### AKShare（免费，无需配置）

```bash
pip install akshare
```

## 双轨评分公式

```
加权总分 = 短线动量分 × 40% + 营收质量分 × 35% + 风险约束分 × 25%
```

最终标签：可做 / 观察 / 回避

## 关键文件说明

| 文件 | 用途 |
|------|------|
| `SKILL.md` | 技能完整文档 |
| `scripts/team_router.py` | 模式路由、插件系统 |
| `scripts/generate_report.py` | 报告生成 |
| `scripts/backtest_framework.py` | 回测框架 |
| `scripts/strategy_optimizer.py` | 策略优化器 |
| `scripts/plugin_base.py` | 插件抽象基类 |
| `scripts/plugin_loader.py` | 插件加载器 |
| `scripts/akshare_adapter.py` | AKShare 适配器 |
| `scripts/technical_indicators.py` | 技术指标计算 |
| `config/settings.json` | 外置配置 |
| `plugins/expert/` | 示例插件 |

## 开发建议

1. **修改评分权重**：编辑 `config/settings.json`
2. **新增专家插件**：在 `plugins/expert/` 创建新文件
3. **修改回测参数**：编辑 `config/settings.json` 的 `backtest` 节点
4. **新增技术指标**：修改 `scripts/technical_indicators.py`

## 免责声明

所有分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。
