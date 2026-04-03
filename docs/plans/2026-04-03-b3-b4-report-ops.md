# B3 B4 Report Ops Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 先增强批量质量检查脚本的聚合摘要与修复建议输出，再基于现有 `stock-reports` 生成一份可执行的修复清单。

**Architecture:** B3 保持现有 CLI 输出 JSON 的兼容性，只增加规则聚合、严重级别汇总和修复建议字段；B4 不修改历史报告正文，而是根据批量检查结果生成 Markdown 形式的修复清单文档，便于人工逐项处理。

**Tech Stack:** Python 标准库、Markdown、unittest

---

### Task 1: 为 B3 写失败测试

**Files:**
- Modify: `tests/test_stock_skill.py`
- Modify: `scripts/run_report_quality_checks.py`

**Step 1: Write the failing test**
- 新增规则聚合摘要测试
- 新增修复建议测试
- 新增 Markdown 修复清单渲染测试

**Step 2: Run test to verify it fails**
- 只运行新增测试，确认当前脚本尚未提供对应函数与输出。

**Step 3: Write minimal implementation**
- 增加聚合摘要、严重级别汇总、修复建议和 Markdown 渲染函数。

**Step 4: Run test to verify it passes**
- 运行新增测试并确认通过。

---

### Task 2: 执行 B4

**Files:**
- Create: `docs/REPORT_QUALITY_REPAIR_CHECKLIST_20260403.md`

**Step 1: 运行质量检查**
- 对 `stock-reports/*.md` 执行批量检查。

**Step 2: 生成修复清单**
- 按规则摘要、修复建议、逐文件明细生成 Markdown 文档。

**Step 3: 人工复核**
- 确认清单仅列出问题，不改写历史报告正文。

---

### Task 3: 回归验证

**Files:**
- Test: `tests/test_stock_skill.py`

**Step 1: 运行针对性测试**
- 运行新增 B3 测试。

**Step 2: 运行全量回归**
- 运行 `python -m unittest tests/test_stock_skill.py -v`

**Step 3: 运行批量质量检查**
- 运行 `python scripts/run_report_quality_checks.py`
- 确认脚本输出新增摘要字段，且存量失败来自报告内容本身。
