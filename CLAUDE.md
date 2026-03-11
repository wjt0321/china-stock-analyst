# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

A股智能分析助手（china-stock-analyst）是一个 Claude Code 技能，用于 A 股短线交易分析。核心特点：双轨研判（短线交易信号 + 营收质量），支持单标的轻量分析（single_flow）和多标的专家团队分析（agent_team）两种模式。

## 运行测试

```bash
python -m unittest tests/test_stock_skill.py
```

## 目录结构

```
china-stock-analyst/
├── SKILL.md                    # 技能定义与核心流程文档
├── scripts/
│   ├── team_router.py          # 执行模式路由：single_flow vs agent_team
│   ├── generate_report.py      # 报告格式化、数据解析、路由规划
│   └── stock_utils.py          # 股票代码验证、搜索查询生成
├── tests/
│   └── test_stock_skill.py     # 单元测试
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

**触发 agent_team 模式**：
- 请求中出现 2 个及以上 A 股代码（6位数字，以 0/3/6 开头）
- 请求包含关键词：对比、验证、复盘、冲突、分歧、组合、股票池、候选、多股

**触发 single_flow 模式**：
- 单个股票分析请求
- 无验证/对比需求

### 固定技能链路

**agent_team 模式**（8步）：
```
collect_data → run_fundamental_expert → run_technical_expert →
run_quant_flow_expert → run_risk_expert → run_macro_expert →
supervisor_review → render_report
```

**single_flow 模式**（3步）：
```
collect_data → run_single_analysis → render_report
```

### 报告生成

`scripts/generate_report.py` 提供：

- `plan_analysis_route(user_request)` → 返回模式与技能步骤
- `format_obsidian_markdown_report(payload)` → 生成 Obsidian 兼容报告
- `parse_search_results_to_report()` → 解析搜索结果为结构化数据

报告模式自动判定：
- 单标的 → `single_stock` 模式（标题：`代码_名称_日期`）
- 多标的 → `stock_pool` 模式（标题：`股票池_日期_短线营收双轨分析`）

## 数据解析规则

### 资金流向（`_parse_fund_flow`）
- 统一单位为"万元"
- 净流入为正，净流出为负
- 需提取主力资金（main）和散户资金（retail）

### 营收快照（`_parse_financial`）
- 必需字段：revenue, yoy（同比）, qoq（环比）, as_of（日期）
- 单位：优先提取"亿元"，自动保留2位小数

### 证据链
- 每条结论需包含：结论、数据点、来源URL、分钟级时间戳

## 预警信号

### 资金流向反转预警
触发条件：近5日主力资金净流入 且 最新主力资金净流出

### 置信度降级
- 营收快照缺失字段 → 置信度降为"中"或"低"

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
# 运行测试
python -m unittest tests/test_stock_skill.py

# 测试股票代码验证
python scripts/stock_utils.py

# 测试报告生成
python scripts/generate_report.py
```

## 关键文件说明

| 文件 | 用途 |
|------|------|
| `SKILL.md` | 技能完整文档：5位专家角色、报告模块清单、预警信号规则 |
| `scripts/team_router.py` | 模式路由：`should_use_agent_team()`, `build_skill_chain_plan()` |
| `scripts/generate_report.py` | 报告生成：`format_obsidian_markdown_report()`, `plan_analysis_route()` |
| `assets/报告模板.md` | Obsidian Callout 格式模板 |
| `docs/agent-teams-blueprint.md` | Agent Teams 编排蓝图：角色定义、输出 schema、裁决规则 |
