# Documentation Version Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 对 `README.md`、`README_EN.md` 和 `SKILL.md` 做一轮版本信息统一审查，清理残留的旧测试数字、旧版本号和已漂移口径。

**Architecture:** 先通过关键词扫描识别残留的版本漂移，再对三份文档做最小改动统一：优先保证“当前版本、测试数量、Web Search 主路径、东方财富补充复核”的口径一致。最后通过检索和必要的回归命令验证文档与当前实现一致。

**Tech Stack:** Markdown、ripgrep、Python 标准库

---

### Task 1: 扫描残留版本信息

**Files:**
- Read: `README.md`
- Read: `README_EN.md`
- Read: `SKILL.md`

**Step 1: 搜索版本号与测试数**
- 检查 `2.4.0 / 2.4.1 / 2.4.2 / 94 / 95 / 115 / 130 / 必做 / required` 等关键词。

**Step 2: 搜索主路径漂移**
- 检查是否仍存在“东财必做”“Web 降级为资讯补充”“双轨都要通过”之类旧口径。

**Step 3: 形成修改清单**
- 只记录真正与当前实现冲突或误导读者的条目。

---

### Task 2: 统一修正文档

**Files:**
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `SKILL.md`（仅在发现残留漂移时）

**Step 1: 修正测试数字**
- 所有面向当前状态的测试总量统一到最新实际值。

**Step 2: 修正版本描述**
- README 中当前版本相关表述与 Release 版本统一。

**Step 3: 修正数据源口径**
- 保证 Web Search 主路径、东方财富补充复核的描述一致。

---

### Task 3: 验证

**Files:**
- Test: `tests/test_stock_skill.py`

**Step 1: 文档关键词复查**
- 再次搜索旧版本号、旧测试数字、旧口径。

**Step 2: 运行必要命令**
- 运行 `python -m unittest tests/test_stock_skill.py -v`
- 如需确认质量检查说明未漂移，运行 `python scripts/run_report_quality_checks.py`

**Step 3: 人工复核**
- 确认三份文档对“版本、测试、主路径、东财定位”的表达一致。
