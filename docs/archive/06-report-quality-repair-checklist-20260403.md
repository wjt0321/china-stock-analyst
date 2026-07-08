# 报告质量修复清单

- 报告总数：3
- 未通过数：3
- 总体结果：未通过

## 规则聚合摘要

| 规则 | 严重级别 | 次数 |
|------|----------|------|
| missing_timestamp_anchor | medium | 6 |
| missing_candidate_table | high | 2 |
| unconfirmed_change_with_fixed_close_price | high | 1 |

## 修复建议

- [medium] missing_timestamp_anchor: 在推荐段补充“更新时间”或“数据时间”，避免价格时点不明。
- [high] missing_candidate_table: 为股票池报告补充可解析的候选表区块，至少包含代码、名称、收盘价、今日涨跌。
- [high] unconfirmed_change_with_fixed_close_price: 当候选表涨跌为待确认时，不要在推荐段写确定收盘价，或先补全确认数据。

## 报告明细

### 000767_晋控电力_20260310.md

- 问题数：2
- 状态：未通过
- [high] missing_candidate_table: 未识别到候选表数据区块，无法校验推荐段与候选表一致性。
- [medium] missing_timestamp_anchor: 推荐段缺少价格时间锚点（更新时间/数据时间）。

### 中国能建601868-首开股份600376-10元以下低价股推荐-20260310.md

- 问题数：3
- 状态：未通过
- [high] missing_candidate_table: 未识别到候选表数据区块，无法校验推荐段与候选表一致性。
- [medium] missing_timestamp_anchor: 推荐段缺少价格时间锚点（更新时间/数据时间）。
- [medium] missing_timestamp_anchor: 推荐段缺少价格时间锚点（更新时间/数据时间）。

### 低价优质股专家团分析-20260317.md

- 问题数：4
- 状态：未通过
- [medium] missing_timestamp_anchor: 推荐段缺少价格时间锚点（更新时间/数据时间）。
- [medium] missing_timestamp_anchor: 推荐段缺少价格时间锚点（更新时间/数据时间）。
- [high] unconfirmed_change_with_fixed_close_price: 候选表中“今日涨跌”为待确认，但推荐段写入了确定收盘价。
- [medium] missing_timestamp_anchor: 推荐段缺少价格时间锚点（更新时间/数据时间）。
