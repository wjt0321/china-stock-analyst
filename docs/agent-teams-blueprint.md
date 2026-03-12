# china-stock-analyst Agent Teams 编排蓝图

## 1. 目标

- 将现有 7 位专家升级为可并行执行的 Agent Teams
- 引入主管 Agent 做质量门控、冲突仲裁和最终结论输出
- 保留固定技能链路，降低输出漂移，提升可迁移性和可复核性

## 2. 团队角色

| 角色ID | 角色职责 | 主要输入 | 主要输出 |
|------|------|------|------|
| orchestrator | 任务拆分、并行调度、聚合结果 | 用户请求、基础行情数据 | 专家任务包、聚合上下文 |
| expert_fundamental | 营收质量与口径一致性分析 | 财报、业绩预告、估值快照 | 营收质量评分、证据链 |
| expert_technical | 短线技术面与关键位分析 | K线、均线、成交量、形态信号 | 动量评分、失效条件 |
| expert_quant_flow | 资金流向与反转识别 | 主力/散户资金、成交结构 | 资金评分、反转预警 |
| expert_risk | 仓位与回撤控制 | 波动、杠杆、行业风险 | 风险评分、仓位建议 |
| expert_macro | 政策与板块驱动分析 | 政策新闻、板块资金 | 宏观偏向、风险因子 |
| expert_industry_researcher | 行业景气与竞争格局分析 | 行业新闻、产业链动态、供需线索 | 行业景气结论、拐点判断、证据链 |
| expert_event_hunter | 事件冲击识别与监管跟踪 | 公告、政策、监管问询、突发事件 | 事件方向、冲击强度、时效窗口、证据链 |
| supervisor | 质量检查与最终裁决 | 全部专家结构化结果 | 最终标签、综合建议、证据链总表 |

## 3. 编排流程

1. orchestrator 接收用户请求，标准化为统一任务对象
2. 并行分发给 7 位专家 Agent
3. 每位专家按固定技能链输出标准化 JSON
4. supervisor 执行门控规则与冲突仲裁
5. 输出统一报告：可做 / 观察 / 回避 + 仓位 + 止损 + 证据链

## 4. 固定技能链路

每个专家固定执行以下顺序，不允许跨层混用：

1. 输入校验（字段完整性、时间有效性）
2. 指标计算（仅本领域）
3. 风险标注（仅本领域）
4. 证据链生成（结论、数据点、来源 URL、时间戳）
5. 结构化输出（统一 schema）

supervisor 固定执行：

1. 完整性检查
2. 冲突识别
3. 权重融合
4. 标签与行动建议输出

## 4.2 新增专家输出 Schema（含证据链）

```json
{
  "agent": "expert_industry_researcher",
  "as_of": "2026-03-11 10:30",
  "score": 72,
  "outlook": "景气上行",
  "inflection": "上行拐点初现",
  "competition_landscape": "头部集中度提升",
  "drivers": ["需求修复", "库存去化", "价格传导"],
  "risk_hint": "价格战风险",
  "decision_hint": "可做",
  "evidences": [
    {"conclusion": "行业景气证据", "value": "行业订单同比+12%", "source_url": "https://example.com/industry", "timestamp": "2026-03-11 10:22"}
  ]
}
```

```json
{
  "agent": "expert_event_hunter",
  "as_of": "2026-03-11 10:30",
  "score": 38,
  "impact_direction": "负向",
  "impact_strength": "强",
  "time_window": "1-3个交易日",
  "regulatory_signal": "高",
  "action_hint": "缩短复核周期",
  "decision_hint": "回避",
  "evidences": [
    {"conclusion": "事件冲击负向", "value": "收到监管问询", "source_url": "https://example.com/event", "timestamp": "2026-03-11 10:25"}
  ]
}
```

## 4.1 短线指标串联规则

### Team 模式强制触发场景

- 多标的请求
- 验证/复盘/冲突仲裁请求
- 明确提出“短线指标增强、补指标、改路由入口”的请求

### 专家分工与输入字段

| 步骤 | 专家 | 指标任务 | 主管必审字段 |
|------|------|----------|--------------|
| run_technical_expert | 技术分析派 | VWAP偏离、ATR止损、突破回踩确认 | indicator_signals |
| run_quant_flow_expert | 量化模型师 | 量比、5日资金斜率、反转检测 | indicator_missing |
| supervisor_review | 主管 | 冲突仲裁与降级执行 | downgrade_reason、evidences |

### 失败降级与冲突仲裁

- 关键指标缺失（VWAP偏离/ATR止损/量比）时：标签上限降为观察
- 技术看多与风控高风险冲突时：仓位上限按高风险档执行
- 资金斜率转负且量比失效时：强制输出等待二次确认

## 5. 统一输出 Schema

```json
{
  "agent": "expert_quant_flow",
  "symbol": "601868",
  "as_of": "2026-03-10 11:20",
  "score": 85,
  "confidence": "high",
  "signals": [
    {
      "name": "five_day_inflow",
      "value": "13.03亿元",
      "direction": "positive"
    }
  ],
  "risks": [
    {
      "name": "reversal_warning",
      "level": "high",
      "detail": "近5日净流入且最新净流出"
    }
  ],
  "evidences": [
    {
      "conclusion": "资金持续关注",
      "value": "5日净流入13.03亿元",
      "source_url": "https://example.com/fund",
      "timestamp": "2026-03-10 11:20"
    }
  ],
  "decision_hint": "观察",
  "invalid_condition": "跌破2.35元且放量"
}
```

## 6. 主管 Agent 裁决规则

### 6.1 门控规则

- 无证据链禁止输出强结论
- 营收快照字段缺失时，最终置信度上限为中
- 时间戳超出有效期时自动降级为观察

### 6.2 冲突规则

- 短线动量高但风险高时，标签降一档
- 资金强流入但触发反转预警时，仓位上限收缩
- 基本面与技术面冲突时，要求附失效条件

### 6.3 权重规则

- 短线动量分 40%
- 营收质量分 35%
- 风险约束分 25%

## 7. 最终输出要求

- 最终标签：可做 / 观察 / 回避
- 行动建议：仓位区间、止损位、止盈位
- 失效条件：触发即作废
- 证据链总表：每条结论必须有 URL 与分钟级时间戳
- 置信度：高 / 中 / 低，并说明降级原因

## 8. 可迁移性设计

### 8.1 设计原则

- 禁用绝对路径，统一使用相对路径
- 核心脚本仅依赖 Python 标准库
- 搜索能力采用“可用即用”策略，不绑定单一 MCP 名称
- 无网络时降级为结构化模板输出并标注数据缺失

### 8.2 跨机冒烟检查

1. `python -m unittest tests/test_stock_skill.py`
2. 运行单票样例，检查：
   - 模板模式为 single_stock
   - 评分公式与置信度存在
   - 证据链 URL 和分钟级时间戳存在
3. 运行双票样例，检查：
   - 模板模式为 stock_pool
   - 反转预警卡片触发

## 9. 最小实施路线

1. 第一步：只启用 orchestrator + supervisor + 2 位关键专家（资金、风控）
2. 第二步：补齐基础面、技术面、宏观面
3. 第三步：增加历史回测指标，迭代权重
4. 第四步：稳定后固化为默认团队模板
