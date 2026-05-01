# AGENTS.md

专家 Agent 定义说明文档。

## 项目概述

A股智能分析助手（china-stock-analyst）是一个 Claude Code 技能，用于 A 股短线交易分析。核心特点：「短线交易信号 + 营收质量」双轨研判体系，采用 Team-First 默认并行架构。

当前版本：**v3.1.0**

## 专家角色列表

| 编号 | 角色 | 分析重点 | Agent 文件 |
|------|------|----------|------------|
| 00 | 数据审计专家 | 日期回退、时间戳冲突、来源类别充分性 | `agents/stock-data-auditor.md` |
| 01 | 基本面大师 | 财务数据、估值、行业地位 | `agents/stock-fundamental-expert.md` |
| 02 | 技术分析派 | K线形态、均线、MACD、KDJ、短线指标 | `agents/stock-technical-expert.md` |
| 03 | 量化模型师 | 数据驱动、因子分析、资金流向 | `agents/stock-quant-flow-expert.md` |
| 04 | 风险控制官 | 下行风险、仓位管理、止损位 | `agents/stock-risk-expert.md` |
| 05 | 宏观策略师 | 政策面、资金面、市场周期 | `agents/stock-macro-expert.md` |
| 06 | 行业研究家 | 行业景气、竞争格局、驱动因子 | `agents/stock-industry-researcher.md` |
| 07 | 消息面猎手 | 公告政策、监管信号、事件冲击 | `agents/stock-event-hunter.md` |
| 08 | 专家鉴别Agent | 身份校验、标的一致性、价格锚点偏差 | `agents/stock-identity-auditor.md` |

## Agent 文件格式

每个 Agent 定义文件（`.md`）包含以下字段：

```yaml
---
name: stock-xxx-expert
version: "3.1.0"
schema_version: "v2"
description: 专家描述
category: fundamental/technical/flow/industry/event/risk
---

# 专家角色说明

## 分析重点

...

## 输出 Schema

...
```

## 执行顺序

Team-First 模式下的固定执行顺序：

1. `stock-data-auditor` - 数据真实性审计（前置门禁）
2. `stock-fundamental-expert` - 基本面分析
3. `stock-technical-expert` - 技术分析
4. `stock-quant-flow-expert` - 量化分析
5. `stock-risk-expert` - 风险评估
6. `stock-macro-expert` - 宏观分析
7. `stock-industry-researcher` - 行业研究
8. `stock-event-hunter` - 事件驱动
9. `stock-identity-auditor` - 身份校验（后置门禁）

## 插件扩展

除了预置的 Agent，还支持自定义专家插件：

**位置**：`plugins/expert/`

**示例插件**：
- `technical_indicators_plugin.py` - 技术指标分析插件
- `fund_flow_plugin.py` - 资金流向分析插件

**创建自定义插件**：

```python
from scripts.plugin_base import ExpertPlugin, PluginContext, PluginResult

class MyExpertPlugin(ExpertPlugin):
    name = "my_expert"
    version = "1.0.0"
    category = "custom"
    
    def can_handle(self, context: PluginContext) -> bool:
        return "自定义" in context.request
    
    def execute(self, context: PluginContext) -> PluginResult:
        return PluginResult(success=True, content="分析结果")
```

## 预置 Agent 加载规则

- 优先从 `agents/` 目录读取 `.md` 定义文件
- 若缺失则回退为默认执行路径，不中断整体流程
- 数据审计专家（`stock-data-auditor`）为前置门禁，必须首先执行
- 专家鉴别 Agent（`stock-identity-auditor`）为后置门禁，校验失败可阻断流程

## 详细文档

- `SKILL.md` - 技能完整文档
- `CLAUDE.md` - 开发者指南
- `docs/agent-teams-blueprint.md` - Agent Teams 编排蓝图
- `docs/agent-json-schema-standard.md` - 专家 Agent 统一 JSON Schema 标准
