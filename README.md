# A股智能分析助手 (china-stock-analyst)

> A股短线交易分析助手，聚焦"短线交易信号 + 营收质量"双轨研判

一个用于 Claude Code 的技能（Skill），提供 A 股市场的多维度分析能力。支持 5 位专家独立分析与交叉质疑，输出可复核证据链、双轨评分与明确交易条件。

## 特性

- **双轨研判**：短线动量 + 营收质量双重评分
- **智能路由**：自动识别单标的分析 vs 多标的专家团队模式
- **5 位专家团队**：基本面、技术面、量化资金、风控、宏观策略
- **证据链追溯**：每条结论包含数据点、来源 URL 与时间戳
- **预警信号**：资金流向反转、涨停跌停后反转等关键预警

## 安装

将本项目克隆到 Claude Code 技能目录：

```bash
git clone https://github.com/wjt0321/china-stock-analyst.git
```

或将项目复制到：
- Windows: `%USERPROFILE%\.claude\skills\china-stock-analyst`
- macOS/Linux: `~/.claude/skills/china-stock-analyst`

## 使用方法

### 单标的分析

```
请分析 600519（茅台）
看看珠江股份 600684 怎么样
```

### 多标的对比分析

```
请对比中国能建和首开股份，给我短线建议
分析一下电力板块：晋控电力、长源电力
```

### 验证历史报告

```
验证股票研究报告/泰豪科技600590分析报告-20260307.md
对比一下 中钢国际000928 3月7日的报告和今天的数据
```

## 项目结构

```
china-stock-analyst/
├── SKILL.md                    # 技能定义与核心流程
├── CLAUDE.md                   # Claude Code 开发指南
├── README.md                   # 本文档
├── LICENSE                     # MIT 协议
├── scripts/
│   ├── team_router.py          # 执行模式路由
│   ├── generate_report.py      # 报告生成
│   └── stock_utils.py          # 工具函数
├── tests/
│   └── test_stock_skill.py     # 单元测试
├── assets/
│   └── 报告模板.md              # Obsidian 风格模板
├── references/
│   └── 估值模型说明.md          # 估值方法参考
└── stock-reports/              # 报告输出目录
```

## 运行测试

```bash
python -m unittest tests/test_stock_skill.py
```

## 双轨评分公式

```
加权总分 = 短线动量分 × 40% + 营收质量分 × 35% + 风险约束分 × 25%
```

最终标签：**可做 / 观察 / 回避**

## 执行模式

| 模式 | 触发条件 | 技能链路 |
|------|----------|----------|
| `single_flow` | 单股票分析 | collect_data → run_single_analysis → render_report |
| `agent_team` | 多股票/验证/对比 | collect_data → 5专家分析 → supervisor_review → render_report |

## 预警信号

- **资金流向反转预警**：近5日主力资金净流入 且 最新主力资金净流出
- **涨停/跌停后反转**：大幅异动后的资金流向变化
- **压力位触及预警**：股价触及预测止盈位后的回调风险

## 报告格式

输出 Obsidian 兼容的 Markdown 格式报告，包含：

- 时效性与口径警告
- 营收快照（营收/同比/环比/口径/来源）
- 双轨评分与置信度
- 资金流向数据与反转预警
- 支撑位/压力位/止损位
- 证据链表格（结论/数据/来源/时间戳）

## 免责声明

> 所有分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。

## 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 作者

wjt0321

---

*Made with ❤️ for A-share investors*
