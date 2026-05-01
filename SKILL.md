---
name: china-stock-analyst
description: A股短线分析助手，聚焦"短线交易信号 + 营收质量"双轨研判。使用时机：分析单只A股、对比多只股票、验证历史报告、回测策略表现、优化参数配置。默认采用 Team-First 并行分析，支持插件化扩展、回测框架、策略优化。
---

# A股智能分析助手

## 适用场景

- 分析单只 A 股的短线机会与风险
- 对比多只股票并输出优先级
- 验证历史报告与最新数据是否发生偏移
- 结合资金流、短线信号、营收质量做决策支持
- 回测策略表现，优化参数配置

示例：

```text
请分析 600519（茅台）
请对比中国能建和首开股份，给我短线建议
验证 600590 上次报告和今天的数据差异
回测贵州茅台近60天的策略表现
```

## 运行原则

### 1. Team-First

- 默认进入 `agent_team`
- 多标的、验证/对比/复盘、股票池、冲突仲裁、高意图串联任务优先触发 Team 模式
- 轻量请求走 `lite_parallel`
- 高意图串联任务走 `full_parallel`

固定链路：

1. `run_data_auditor`
2. `collect_data`
3. `run_fundamental_expert`
4. `run_technical_expert`
5. `run_quant_flow_expert`
6. `run_risk_expert`
7. `run_macro_expert`
8. `run_industry_researcher_expert`
9. `run_event_hunter_expert`
10. `run_expert_identifier_agent`
11. `supervisor_review`
12. `render_report`

### 2. 数据源优先级

- **主路径**：MiniMax / Web Search 实时检索
- **辅路径**：东方财富结构化补充与复核
- **数据源**：AKShare 免费 API（历史K线、资金流向、新闻）
- **固定原则**：`web_search > eastmoney_query`

约束：

- Web Search 负责市场快照、候选覆盖、时效性
- 东方财富负责结构化校验、关键字段复核、选股结果补强
- AKShare 负责历史数据、回测数据
- 东方财富缺失或未接入时，不得阻断主流程，只能标记"未完成结构化复核"
- 禁止把止损位、历史价、目标价当作当前价格

### 3. 风控优先

- 所有结论必须附证据链
- 身份校验、价格语义校验、交易日时效校验不通过时，允许阻断
- 缺失关键短线指标时，标签上限降为 `观察`
- 输出仅作决策支持，不得表述为自动交易指令

## 数据源能力

### 东方财富 API

支持三类增强能力，由 `scripts/team_router.py` 路由：

- `news-search`：资讯、公告、舆情、事件驱动
- `query`：行情、资金流向、财务、估值、指标
- `stock-screen`：选股、筛选、股票池、低价股、高增长

配置约定：

- 支持 `EASTMONEY_APIKEY` / `EASTMONEY_API_KEY` / `EM_API_KEY`
- 推荐 `EASTMONEY_APIKEY`
- 缺失密钥时继续本地主流程，并标记"外部数据未接入"
- 禁止硬编码密钥；日志必须脱敏

### AKShare 数据源

免费数据源，无需配置：

- 历史K线数据（日线/分钟线）
- 资金流向数据（主力/散户分离）
- 实时买卖盘（Level2）
- 个股新闻资讯
- 涨停板数据

使用方式：

```python
from scripts.akshare_adapter import AKShareAdapter

adapter = AKShareAdapter()
data = adapter.get_full_data("600519")
```

## 专家角色

当前 Team 规划包含以下角色：

- 基本面大师：财务、估值、行业地位
- 技术分析派：K线、均线、MACD、KDJ、短线指标
- 量化模型师：资金流、因子、量价配合
- 风险控制官：仓位、止损、下行风险
- 宏观策略师：政策、周期、系统性约束
- 行业研究家：景气度、竞争格局、驱动因子
- 消息面猎手：公告、监管、事件催化
- 专家鉴别 Agent：身份、标的、价格锚点一致性

预置 Agent 缺失时允许回退到默认执行路径，不中断整体流程。

## 插件系统

支持三类插件扩展：

- `ExpertPlugin`：专家插件，自定义分析逻辑
- `FilterPlugin`：过滤器插件，数据过滤
- `TransformPlugin`：转换器插件，数据转换

示例插件：

- `technical_indicators_plugin`：技术指标分析
- `fund_flow_plugin`：资金流向分析

使用方式：

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

## 回测系统

### 快速回测

```python
from scripts.backtest_runner import quick_backtest

result = quick_backtest("600519")
print(f"总收益: {result.metrics.total_return:.2%}")
print(f"夏普比率: {result.metrics.sharpe_ratio:.2f}")
```

### 策略优化

```python
from scripts.strategy_optimizer import StrategyOptimizer

optimizer = StrategyOptimizer()
result = optimizer.optimize_scoring_weights("600519", objective="sharpe_ratio")
print(optimizer.get_optimization_report(result))
```

### 归因分析

```python
from scripts.strategy_optimizer import BacktestAttributor

attributor = BacktestAttributor()
attribution = attributor.analyze(backtest_result, candles, fund_flow)
print(attributor.get_attribution_report(attribution))
```

## 报告必须包含

- 时效性与口径警告
- 价格、资金流、营收快照
- 支撑位 / 压力位 / 止损位
- 双轨评分：短线动量 / 营收质量 / 风险约束
- 最终标签：`可做 / 观察 / 回避`
- 失效条件或止损条件
- 专家鉴别结果与流程阻断状态
- 证据链：结论 / 数据 / 来源 / 时间戳

验证类报告额外需要：

- 历史数据与最新数据对比
- 偏差说明
- 更新后的建议

## 评分与降级

双轨评分权重：

- 短线动量分：40%
- 营收质量分：35%
- 风险约束分：25%

短线关键指标：

- VWAP 偏离
- ATR 止损
- 量比

降级规则：

- 缺失 VWAP / ATR / 量比 任一关键项，标签上限为 `观察`
- `|VWAP偏离|>=4.0%` 且 `量比<1.0` 时，标签上限为 `回避`
- 缺失关键项时，必须说明降级原因，且置信度上限为 `中`

## 验证流程

当用户要求验证已有报告时：

1. 读取历史报告
2. 用 Web Search 获取最新快照
3. 视情况使用东方财富做结构化复核
4. 对比股价、涨跌幅、资金流向、关键结论
5. 输出偏差判断与更新建议

注意：

- 验证流程仍以 Web Search 为主
- 东方财富仅做补充复核，不应覆盖主路径定位

## 关键文件

- `scripts/team_router.py`：路由、执行模式、插件系统
- `scripts/generate_report.py`：解析、门禁、评分、渲染
- `scripts/stock_utils.py`：股票工具、东财接口、时间与来源标准化
- `scripts/technical_indicators.py`：技术指标计算
- `scripts/backtest_framework.py`：回测框架
- `scripts/backtest_runner.py`：回测运行器
- `scripts/strategy_optimizer.py`：策略优化器
- `scripts/plugin_base.py`：插件基类
- `scripts/plugin_loader.py`：插件加载器
- `scripts/akshare_adapter.py`：AKShare 适配器
- `scripts/config_loader.py`：配置加载器
- `config/settings.json`：外置配置
- `agents/`：预置专家 Agent
- `plugins/`：自定义插件
- `tests/test_stock_skill.py`：核心回归测试

## 配置说明

配置文件：`config/settings.json`

主要配置项：

- `scoring`：评分权重配置
- `quality_gate`：质量门禁阈值
- `backtest`：回测参数
- `technical_indicators`：技术指标参数
- `akshare`：AKShare 配置

## 详细规则去向

以下内容不再放在主技能文件中，应以代码和文档为准：

- 长模板示例
- 详细验证报告样板
- 指标开发入口清单
- 迁移与冒烟测试说明
- 过细的实现级别步骤

如需查看详细设计，优先参考：

- `README.md`
- `CLAUDE.md`
- `docs/agent-teams-blueprint.md`
- `agents/*.md`
- `tests/test_stock_skill.py`

## 免责声明

所有分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。
