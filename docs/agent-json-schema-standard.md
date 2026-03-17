# A股专家 Agent 统一 JSON Schema 标准（v2）

## 1. 目标与适用范围

本标准用于约束 `agents/stock-*.md` 下专家 Agent 的输出格式，确保：

- 输出可机读、可校验、可追溯
- 多专家结果可稳定聚合与仲裁
- 降低自由文本漂移导致的结果不一致

适用对象：

- `stock-data-auditor`
- `stock-identity-auditor`
- `stock-macro-expert`
- `stock-quant-flow-expert`
- `stock-risk-expert`
- `stock-technical-expert`
- `stock-industry-researcher`
- `stock-event-hunter`
- `stock-fundamental-expert`

## 2. 全局约束

所有专家输出必须满足以下规则：

1. 输出必须是单个 JSON 对象，不得混入解释性自然语言
2. 字段名必须与约定一致，不得临时改名
3. 枚举字段必须落在约定值集合
4. 时间统一格式：`YYYY-MM-DD HH:MM`
5. 未知值使用空字符串 `""` 或空数组 `[]`，禁止使用“随意占位词”
6. 证据条目必须包含来源链接与时间戳

## 3. 通用字段规范

### 3.1 基础元字段

- `schema_version`：固定 `"v2"`
- `agent`：Agent 标识（与提示词中 `name` 对应）

### 3.2 证据数组字段

多数专家包含 `evidences`（或审计专用 `key_evidences`），单条结构如下：

```json
{
  "conclusion": "证据结论",
  "value": "证据值",
  "source_url": "https://example.com/...",
  "timestamp": "2026-03-17 10:35"
}
```

审计专家使用 `key_evidences` 时，结构为：

```json
{
  "field": "price",
  "value": "10.23",
  "source_url": "https://example.com/...",
  "timestamp": "2026-03-17 10:35"
}
```

## 4. 各专家 Schema 清单

## 4.1 stock-data-auditor

必填字段：

- `schema_version`, `agent`
- `audit_verdict`: `pass|conditional_pass|fail`
- `severity`: `low|medium|high`
- `failed_fields`: `string[]`
- `conflicts`: `[{field, conflict_type, evidence}]`
- `key_evidences`: `[{field, value, source_url, timestamp}]`
- `risk_points`: `string[]`
- `next_action`: `continue|downgrade|resample`
- `user_tip`: `string`

## 4.2 stock-identity-auditor

必填字段：

- `schema_version`, `agent`
- `identity_verdict`: `pass|downgrade|block`
- `reason_codes`: `string[]`
- `conflict_items`: `[{field, expected, actual, evidence}]`
- `price_check`: `{passed, reference_price, observed_price}`
- `evidences`: `[{conclusion, value, source_url, timestamp}]`
- `action`: `continue|downgrade|block`
- `user_tip`: `string`

## 4.3 stock-macro-expert

必填字段：

- `schema_version`, `agent`
- `macro_view`: `risk_on|neutral|risk_off`
- `policy_cycle`: `宽松|中性|收紧`
- `systematic_risk_level`: `low|medium|high`
- `key_drivers`: `string[]`
- `impact_path`: `string`
- `constraints`: `string[]`
- `uncertainties`: `string[]`
- `decision_hint`: `可做|观察|回避`
- `evidences`: `[{conclusion, value, source_url, timestamp}]`

## 4.4 stock-quant-flow-expert

必填字段：

- `schema_version`, `agent`
- `flow_view`: `主力净流入|主力净流出|分歧`
- `flow_strength`: `strong|medium|weak`
- `key_metrics`: `{main_net_inflow, retail_net_inflow, turnover_rate, volume_ratio}`
- `persistence`: `延续|震荡|反转`
- `conflict_points`: `string[]`
- `risk_tips`: `string[]`
- `decision_hint`: `可做|观察|回避`
- `evidences`: `[{conclusion, value, source_url, timestamp}]`

## 4.5 stock-risk-expert

必填字段：

- `schema_version`, `agent`
- `risk_verdict`: `low|medium|high|extreme`
- `high_risk_factors`: `string[]`
- `trigger_conditions`: `string[]`
- `position_range`: `{min, max}`
- `stop_loss_plan`: `{stop_price, exit_rule}`
- `liquidity_risk`: `low|medium|high`
- `event_shock_risk`: `low|medium|high`
- `decision_hint`: `可做|观察|回避`
- `evidences`: `[{conclusion, value, source_url, timestamp}]`

## 4.6 stock-technical-expert

必填字段：

- `schema_version`, `agent`
- `technical_view`: `多头|震荡|空头`
- `trend_strength`: `strong|medium|weak`
- `key_levels`: `{support: string[], resistance: string[]}`
- `trigger_conditions`: `string[]`
- `invalidation_conditions`: `string[]`
- `risk_notes`: `string[]`
- `decision_hint`: `可做|观察|回避`
- `evidences`: `[{conclusion, value, source_url, timestamp}]`

## 4.7 stock-industry-researcher

必填字段：

- `schema_version`, `agent`
- `industry_outlook`: `景气上行|景气中性|景气承压`
- `decision_hint`: `可做|观察|回避`
- `score`: `number`
- `inflection`: `string`
- `drivers`: `string[]`
- `risk_hint`: `string`
- `evidences`: `[{conclusion, value, source_url, timestamp}]`

## 4.8 stock-event-hunter

必填字段：

- `schema_version`, `agent`
- `impact_direction`: `正向|中性|负向`
- `impact_strength`: `强|中|弱`
- `decision_hint`: `可做|观察|回避`
- `score`: `number`
- `time_window`: `string`
- `regulatory_signal`: `高|中|低`
- `action_hint`: `string`
- `evidences`: `[{conclusion, value, source_url, timestamp}]`

## 4.9 stock-fundamental-expert

必填字段：

- `schema_version`, `agent`
- `summary`: `string`
- `positive_evidences`: `string[]`
- `negative_evidences`: `string[]`
- `risk_tip`: `string`
- `confidence`: `高|中|低`
- `decision_hint`: `可做|观察|回避`
- `evidences`: `[{conclusion, value, source_url, timestamp}]`

兼容说明：

- 聚合层仍兼容旧字段：`观点摘要/正向证据/反向证据/风险提示/置信度`
- 旧枚举 `看多|中性|看空` 在聚合时映射为 `可做|观察|回避`

## 5. 最小校验清单

在接入或改动专家提示词时，至少校验：

1. 是否输出有效 JSON（可被 `json.loads` 解析）
2. `schema_version` 与 `agent` 是否存在
3. 枚举字段是否超出定义集合
4. 证据数组是否包含 `source_url` 与 `timestamp`
5. 关键结论字段是否为空

## 6. 版本策略

- 当前标准版本：`v2`
- 新增字段：可向后兼容追加
- 变更枚举或删除字段：需升级版本并同步更新对应 `agents/*.md`
