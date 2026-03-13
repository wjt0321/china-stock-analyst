# 🎯 A股智能分析助手

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-purple.svg)
![Tests](https://img.shields.io/badge/Tests-54%20Passed-success.svg)

**📈 A股短线交易分析助手 | Team-First 并行专家系统**

[核心特性](#-核心特性) • [快速开始](#-快速开始) • [执行流程](#-执行流程) • [报告能力](#-报告能力) • [更新日志](#-更新日志)

</div>

---

## 📖 简介

> 一个专为 **Claude Code** 设计的 A 股分析技能，采用「**短线交易信号 + 营收质量**」双轨研判体系。

当前版本已升级为 **Team-First** 架构：默认并行专家协作、前置数据真实性审计、强化复杂指令自动激活与不中断执行。

---

## 🌟 核心特性

| 特性 | 说明 |
|:---:|:---|
| 👥 **8位专家协同** | 基本面大师 / 技术分析派 / 量化模型师 / 风险控制官 / 宏观策略师 / 行业研究家 / 消息面猎手 / 专家鉴别Agent |
| 🧭 **Team-First 默认并行** | 默认进入 `agent_team`，复杂任务强制 `full_parallel`，不再以 `single_flow` 作为主流程 |
| 🛡️ **数据真实性审计前置** | `run_data_auditor` 在所有分析前执行，校验日期回退、时间戳冲突、来源类别充分性 |
| 🧾 **身份与价格双校验** | `run_expert_identifier_agent` 校验专家身份、标的一致性、价格锚点偏差，异常时流程阻断 |
| 🧹 **舆情降噪治理** | 舆情去重、质量评分、低质量剔除，且对综合评分影响封顶，避免噪声主导推荐 |
| ⚖️ **主管冲突仲裁** | 对行业信号与事件冲击冲突进行降档仲裁，输出“可做 / 观察 / 回避”上限与原因 |
| 🔍 **证据链可追溯** | 每条关键结论附结论值、来源 URL、分钟级时间戳与采纳/剔除依据 |
| 🔁 **复杂指令连续性守护** | 并行节点支持隔离重试与汇总，不因局部问题回退为单线流程 |

---

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/wjt0321/china-stock-analyst.git
```

将项目复制到 Claude Code 技能目录：

| 系统 | 路径 |
|:---|:---|
| 🪟 Windows | `%USERPROFILE%\.claude\skills\china-stock-analyst` |
| 🍎 macOS / 🐧 Linux | `~/.claude/skills/china-stock-analyst` |

### 验证安装

```bash
python -m unittest tests/test_stock_skill.py -v
```

当前测试结果：**54 个用例全部通过** ✅

---

## 💡 使用示例

### 📊 单标的分析

```text
请分析 600519（茅台）
看看珠江股份 600684 怎么样
```

### 🔍 多标的对比/讨论

```text
请对比中国能建和首开股份，给我短线建议
分析一下电力板块：晋控电力、长源电力
```

### ⚡ 高意图复杂请求（自动 full_parallel）

```text
请今日采集市场数据，先筛选10支，再组织专家讨论，最后推荐3支
```

### ✅ 验证历史报告

```text
验证股票研究报告/泰豪科技600590分析报告-20260307.md
对比一下 中钢国际000928 3月7日的报告和今天的数据
```

---

## 🎭 执行流程

### 路由模式

| 模式 | 触发特征 | 说明 |
|:---|:---|:---|
| `full_parallel` | 多标的/验证/冲突仲裁/高意图串联任务 | 全专家并行 + 连续性守护 |
| `lite_parallel` | 轻量请求 | 同流程范式降级，减少部分专家节点 |

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

## 📊 评分与治理

### 双轨评分

| 维度 | 权重 | 说明 |
|:---|:---:|:---|
| 📈 短线动量分 | 40% | 资金、量价、关键位突破 |
| 💰 营收质量分 | 35% | 营收同比/环比、口径一致性 |
| 🛡️ 风险约束分 | 25% | 波动率、回撤、监管与事件风险 |

最终标签：`可做` / `观察` / `回避`

### 舆情治理规则

- 舆情先去重再评分，低质量信息不进入核心结论
- 舆情影响分设置上下限，不允许主导综合评分
- 报告展示采纳依据与剔除依据，支持复核

---

## 📋 报告能力

生成报告包含以下关键模块：

| 模块 | 内容 |
|:---|:---|
| ⏰ 时效性与口径警告 | 数据截至时间、信号有效期、营收口径说明 |
| 🛡️ 数据真实性审计 | 日期/时间戳/多源一致性审计结论与降级策略 |
| 💰 营收快照 | 营收/同比/环比/口径/来源/日期 |
| 🎯 双轨评分 | 加权总分与校准后总分 |
| 🧹 舆情降噪治理 | 采纳数、剔除数、理由与影响分 |
| 🧠 专家独立结论 | 8位专家观点与证据链 |
| 🧾 专家鉴别与流程阻断 | 身份/标的/价格校验结果、阻断阶段、后续动作 |
| ⚖️ 主管仲裁 | 冲突项、标签上限、仲裁原因 |
| 🔗 证据链总表 | 结论→数据→来源→时间戳 |

---

## 📁 项目结构

```text
china-stock-analyst/
├── SKILL.md
├── README.md
├── LICENSE
├── scripts/
│   ├── team_router.py
│   ├── generate_report.py
│   └── stock_utils.py
├── tests/
│   └── test_stock_skill.py
├── assets/
│   └── 报告模板.md
├── references/
│   └── 估值模型说明.md
└── docs/
    └── agent-teams-blueprint.md
```

---

## 🧪 运行测试

```bash
python -m unittest tests/test_stock_skill.py -v
```

测试覆盖包含：
- 路由与高意图激活
- 数据审计与重采降级
- 专家鉴别、身份与价格校验、流程阻断
- 舆情降噪与评分封顶
- 新增专家与主管仲裁
- 复杂请求端到端闭环验证

---

## 📜 开源协议

本项目采用 **MIT License**。详见 [LICENSE](LICENSE)。

---

## 📅 更新日志

### v2.2.1 (2026-03-13)

- 标的绑定增强：`parse_search_results_to_report` 支持 `stock_name` 输入并注入 `canonical_name/canonical_code`，多标的混合文本下身份校验更稳健
- 资金方向兜底：无方向词场景改为保守判定，避免把“仅金额描述”误判为流入或流出
- 审计回归补强：新增“阈值内不冲突”“双类别通过”等回归测试，降低误报同时保证可解释性
- 文档完善：补充数据提取原则（价格锚点优先、多标的过滤）
- 测试扩展：测试集扩展至 54 项并全部通过

### v2.1.1 (2026-03-13)

- 价格解析：优先从语义锚点（最新价/现价/收盘价等）提取股价，添加 A 股价格区间校验（0.1-600 元）
- 资金流向：扩展方向关键词列表，防止跨角色方向污染
- 数据源验证：放宽类别要求（3→2）和时间戳冲突阈值（90→179 分钟），扩展数据源 domain 列表

### v2.1.0 (2026-03-12)

- 新增 `run_expert_identifier_agent`：专家身份、标的一致性、价格锚点偏差校验
- 新增流程阻断机制：身份或价格校验失败时阻断 `supervisor_review`
- 报告新增“专家鉴别与身份价格校验”“流程阻断”区块
- 测试扩展至 42 项并全部通过

### v2.0.0 (2026-03-11)

- 架构升级为 Team-First 默认并行执行
- 新增数据真实性审计专家并前置门禁
- 新增行业研究家与消息面猎手专家
- 引入舆情降噪治理与评分影响封顶
- 强化复杂指令自动激活与连续性守护
- 测试扩展至 40 项并全部通过

### v1.1.0 (2025-03-11)

- 新增短线指标增强（VWAP偏离/ATR止损/量比）
- 引入校准评分机制与缺失降级规则

---

## 📌 免责声明

> ⚠️ 所有分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。
