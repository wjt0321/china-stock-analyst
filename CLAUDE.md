# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

A股智能分析助手（china-stock-analyst）是一个 Claude Code 技能，用于 A 股短线交易分析。核心特点：「短线交易信号 + 营收质量」双轨研判体系，采用 Team-First 默认并行架构。

## 运行测试

```bash
python -m unittest tests/test_stock_skill.py
```

## 目录结构

```
china-stock-analyst/
├── SKILL.md                    # 技能完整文档（v2.1+）
├── README.md                   # 技能入口定义
├── scripts/
│   ├── team_router.py          # 执行模式路由：full_parallel vs lite_parallel
│   ├── generate_report.py       # 报告生成、数据解析、评分计算
│   └── stock_utils.py          # 股票代码验证、时间戳处理、来源分类
├── tests/
│   └── test_stock_skill.py     # 单元测试（42个用例）
├── assets/
│   └── 报告模板.md              # Obsidian 风格报告模板
├── references/
│   └── 估值模型说明.md          # 基本面分析估值方法参考
├── docs/
│   └── agent-teams-blueprint.md # Agent Teams 编排蓝图
└── stock-reports/              # 生成的报告输出目录
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

### 固定技能链路（12步）

```
run_data_auditor → collect_data → run_fundamental_expert → run_technical_expert →
run_quant_flow_expert → run_risk_expert → run_macro_expert →
run_industry_researcher_expert → run_event_hunter_expert →
run_expert_identifier_agent → supervisor_review → render_report
```

### 8位专家角色

| 编号 | 角色 | 分析重点 |
|------|------|----------|
| 01 | 基本面大师 | 财务数据、估值、行业地位 |
| 02 | 技术分析派 | K线形态、均线、MACD、KDJ、短线指标 |
| 03 | 量化模型师 | 数据驱动、因子分析、资金流向 |
| 04 | 风险控制官 | 下行风险、仓位管理、止损位 |
| 05 | 宏观策略师 | 政策面、资金面、市场周期 |
| 06 | 行业研究家 | 行业景气、竞争格局、驱动因子 |
| 07 | 消息面猎手 | 公告政策、监管信号、事件冲击 |
| 08 | 专家鉴别Agent | 身份校验、标的一致性、价格锚点偏差 |

### 报告生成

`scripts/generate_report.py` 提供：
- `plan_analysis_route(user_request)` → 返回模式与技能步骤
- `format_obsidian_markdown_report(payload)` → 生成 Obsidian 兼容报告
- `parse_search_results_to_report()` → 解析搜索结果为结构化数据
- `_generate_minimal_shortline_recommendation()` → 短线指标计算（VWAP偏离、ATR止损、量比）
- `_build_reversal_warning()` → 资金流向反转预警

报告模式自动判定：
- 单标的 → `single_stock` 模式
- 多标的 → `stock_pool` 模式

## 关键特性

### 数据真实性审计（run_data_auditor）
- 日期回退校验
- 时间戳冲突检测
- 来源类别充分性检查

### 专家鉴别Agent（run_expert_identifier_agent）
- 专家身份校验
- 标的一致性校验
- 价格锚点偏差校验
- 流程阻断机制：校验失败时阻断 supervisor_review

### 舆情降噪治理
- 舆情去重、质量评分、低质量剔除
- 评分影响分设置上下限，避免噪声主导推荐

### 冲突仲裁规则
- 行业景气正向 + 事件冲击强负向 → 标签上限降为「观察」
- 行业景气负向 + 事件冲击负向 → 标签上限降为「回避」

## 数据解析规则

### 资金流向（`_parse_fund_flow`）
- 统一单位为「万元」
- 净流入为正，净流出为负
- 提取主力资金（main）和散户资金（retail）

### 营收快照（`_parse_financial`）
- 必需字段：revenue, yoy（同比）, qoq（环比）, as_of（日期）
- 单位：优先提取「亿元」，自动保留2位小数

### 证据链
- 每条结论需包含：结论、数据点、来源URL、分钟级时间戳

## 预警信号

### 资金流向反转预警
触发条件：近5日主力资金净流入 且 最新主力资金净流出

### 短线指标缺失降级
- 缺失 VWAP偏离/ATR止损/量比 任一关键项 → 标签上限「观察」
- `|VWAP偏离|>=4.0%` 且 `量比<1.0` → 标签上限「回避」

### 置信度降级
- 营收快照缺失字段 → 置信度降为「中」或「低」
- 缺失关键指标 → 置信度上限「中」

## 双轨评分公式

```
加权总分 = 短线动量分 × 40% + 营收质量分 × 35% + 风险约束分 × 25%
```

最终标签：可做 / 观察 / 回避

## 跨平台兼容性设计原则

1. **仅使用相对路径**：`stock-reports/`、`assets/`、`references/`、`scripts/`
2. **Python 标准库**：`scripts/` 下脚本不依赖第三方包
3. **Web Search 抽象**：不绑定特定 MCP 名称，优先使用环境可用的搜索工具
4. **降级策略**：网络受限时输出结构化模板 + 数据缺失提示

## 常用命令

```bash
# 运行全部测试
python -m unittest tests/test_stock_skill.py -v

# 测试股票代码验证
python scripts/stock_utils.py
```

## 关键文件说明

| 文件 | 用途 |
|------|------|
| `SKILL.md` | 技能完整文档：8位专家角色、报告模块清单、预警信号规则 |
| `scripts/team_router.py` | 模式路由：`should_use_agent_team()`, `build_skill_chain_plan()`, `build_shortline_supervisor_rules()` |
| `scripts/generate_report.py` | 报告生成：数据解析、双轨评分、短线指标、舆情降噪 |
| `scripts/stock_utils.py` | 股票验证、时间戳处理、来源分类、短线指标定义 |
| `assets/报告模板.md` | Obsidian Callout 格式模板 |
| `docs/agent-teams-blueprint.md` | Agent Teams 编排蓝图：角色定义、输出 schema、裁决规则 |
