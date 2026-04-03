# Skill Refactor And Gate Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 先强压缩重构 `SKILL.md`，再补强 `report_quality_gate.py` 的防漏检能力，同时保持现有主路径与 CLI 行为不变。

**Architecture:** `SKILL.md` 只保留主规则、主流程、数据源原则和输出要求，冗长示例与实现细节下沉到其他文档。`report_quality_gate.py` 继续保持轻量 Markdown 检查器定位，通过测试补充章节缺失、标题变体和候选表缺失等稳健性场景。

**Tech Stack:** Markdown、Python 标准库、unittest

---

### Task 1: 备份并重构 SKILL.md

**Files:**
- Create: `SKILL.backup-20260403.before-b1.md`
- Modify: `SKILL.md`

**Step 1: 备份原文**
- 创建完整备份文件，保留改写前全文。

**Step 2: 重写主文件**
- 保留：适用场景、Team-First、数据源优先级、风控原则、专家角色、报告必须项、评分与降级、验证流程、关键文件。
- 删除或下沉：长模板、详细验证样板、迁移说明、开发入口清单、重复规则。

**Step 3: 自检**
- 确认文档与“Web Search 主路径、东财补充复核”的项目现实一致。

---

### Task 2: 为 B2 写失败测试

**Files:**
- Modify: `tests/test_stock_skill.py`
- Modify: `scripts/report_quality_gate.py`

**Step 1: 写失败测试**
- 覆盖章节标题轻微变体
- 覆盖候选表缺失或无法解析
- 覆盖推荐块缺失时的非崩溃行为

**Step 2: 运行测试确认失败**
- 只运行新增测试，确认当前脚本会漏检或行为不稳。

---

### Task 3: 最小实现 B2

**Files:**
- Modify: `scripts/report_quality_gate.py`

**Step 1: 扩展解析稳健性**
- 放宽标题匹配
- 允许候选表缺失时给出可解释结果
- 保持 `run_quality_gate()` 返回结构与 CLI 兼容

**Step 2: 运行新增测试**
- 确认新增场景通过。

---

### Task 4: 回归验证

**Files:**
- Test: `tests/test_stock_skill.py`

**Step 1: 运行针对性测试**
- 运行 B2 新增测试和现有质量门禁测试。

**Step 2: 运行全量回归**
- 运行 `python -m unittest tests/test_stock_skill.py -v`

**Step 3: 运行质量检查脚本**
- 运行 `python scripts/run_report_quality_checks.py`
- 确认脚本可执行，剩余失败来自报告内容本身而不是脚本崩溃。
