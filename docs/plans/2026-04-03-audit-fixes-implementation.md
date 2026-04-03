# Audit Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复本轮独立审查中最影响可信度与一致性的核心问题，同时保持项目以 Web Search 为主、东财为补充复核的设计前提。

**Architecture:** 本轮不做大规模重构，优先修复规则收口与行为偏差。先用测试锁定目标行为，再以最小改动调整门禁逻辑、财报日期处理、报告模式判定和 Agent 命名一致性，最后跑针对性测试与全量回归。

**Tech Stack:** Python 标准库、unittest

---

### Task 1: 锁定主路径优先与门禁契约

**Files:**
- Modify: `tests/test_stock_skill.py`
- Modify: `scripts/generate_report.py`

**Step 1: 写失败测试**
- 新增测试：当 Web Search 审计通过、但东财结构化质量信息缺失时，采集质量门禁不应直接判失败，而应标记“未完成东财复核”并保持主路径可继续。

**Step 2: 运行测试确认失败**
- 运行新增单测，确认当前实现会因为缺失东财质量信息而失败。

**Step 3: 写最小实现**
- 调整采集质量门禁逻辑，区分：
  - Web Search 通过 + 东财缺失
  - Web Search 通过 + 东财失败
  - Web Search 失败

**Step 4: 运行测试确认通过**
- 运行新增单测，确认主路径优先策略成立。

---

### Task 2: 修复财报日期兜底语义

**Files:**
- Modify: `tests/test_stock_skill.py`
- Modify: `scripts/generate_report.py`

**Step 1: 写失败测试**
- 新增测试：当财务文本没有明确报告期时，`as_of` 不应回退为当天日期，而应显式为空并标记来源缺失。

**Step 2: 运行测试确认失败**
- 运行新增单测，确认当前实现会错误写入当天日期。

**Step 3: 写最小实现**
- 修改财务解析逻辑，保留“未知/缺失”语义，不伪造日期。

**Step 4: 运行测试确认通过**
- 运行新增单测并复查旧财报日期提取测试。

---

### Task 3: 收口 Agent 命名与报告模式

**Files:**
- Modify: `tests/test_stock_skill.py`
- Modify: `scripts/generate_report.py`
- Modify: `scripts/report_constants.py`
- Modify: `scripts/team_router.py`

**Step 1: 写失败测试**
- 新增测试：专家输出 `agent` 字段应统一为 `stock-*` 命名。
- 新增测试：单标的 `agent_team` 报告应仍按单票模式渲染。

**Step 2: 运行测试确认失败**
- 运行新增单测，确认当前实现仍使用 `expert_*` 且单标的 Team 报告走股票池模式。

**Step 3: 写最小实现**
- 统一常量、schema builder、专家输出和身份校验使用的 Agent 标识。
- 调整 Markdown 模式判定逻辑：单标的优先按 `single_stock` 输出。

**Step 4: 运行测试确认通过**
- 运行新增单测，并确保既有身份校验测试仍成立。

---

### Task 4: 回归验证

**Files:**
- Test: `tests/test_stock_skill.py`

**Step 1: 运行针对性测试**
- 运行本轮新增与受影响测试。

**Step 2: 运行全量回归**
- 运行 `python -m unittest tests/test_stock_skill.py -v`

**Step 3: 运行报告质量检查**
- 运行 `python scripts/run_report_quality_checks.py`
- 记录现有报告的通过/失败状态，确认代码修改未破坏脚本可执行性。
