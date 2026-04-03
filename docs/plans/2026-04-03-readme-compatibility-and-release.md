# README Compatibility And Release Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 评估本项目与 Claude Code Skills 的适配度，更新中英文 README 到当前真实状态，并在验证后准备发布 `v2.4.3`。

**Architecture:** 先以当前代码、SKILL、测试和报告门禁为基线评估适配度，再将关键结论收敛到 README.md 与 README_EN.md。文档更新后做一致性验证，最后检查 git 远程、标签与 Release 工具链；所有远程操作仅在再次确认后进行，并通过 10808 代理临时执行。

**Tech Stack:** Markdown、Python 标准库、git、可选 gh CLI

---

### Task 1: 审查 Claude Code Skills 适配度

**Files:**
- Read: `SKILL.md`
- Read: `README.md`
- Read: `README_EN.md`
- Read: `scripts/team_router.py`
- Read: `scripts/generate_report.py`
- Read: `tests/test_stock_skill.py`

**Step 1: 审查入口与主规则**
- 确认技能主文件是否聚焦、是否与当前实现一致。

**Step 2: 审查 Claude Code 适配点**
- 检查 Team-First、相对路径、标准库依赖、可回归测试、门禁与证据链是否符合 Skills 场景。

**Step 3: 形成结论**
- 产出“适配优势 / 已知风险 / README 应更新内容”。

---

### Task 2: 更新 README.md 与 README_EN.md

**Files:**
- Modify: `README.md`
- Modify: `README_EN.md`

**Step 1: 写入当前真实状态**
- 修正测试数量、版本号、主路径策略、门禁能力、质量检查能力和最新文档结构。

**Step 2: 收敛过期内容**
- 删除或弱化与当前实现不符的旧版本说明、过期测试数字和已漂移表述。

**Step 3: 保持双语一致**
- 中文 README 与英文 README 表达一致，但保留各自语言风格。

---

### Task 3: 验证文档一致性

**Files:**
- Test: `tests/test_stock_skill.py`

**Step 1: 运行回归**
- 运行 `python -m unittest tests/test_stock_skill.py -v`

**Step 2: 运行报告质量检查**
- 运行 `python scripts/run_report_quality_checks.py`

**Step 3: 复查 README**
- 核对版本、测试数量、数据源策略与当前实现是否一致。

---

### Task 4: 准备发布 v2.4.3

**Files:**
- Modify: git metadata only after confirmation

**Step 1: 检查远程与工具**
- 检查 `git remote -v`、当前分支、是否安装 `gh`、当前 tags。

**Step 2: 远程前再次确认**
- 因涉及 push/tag/release，必须再次向用户确认远程操作。

**Step 3: 执行远程操作**
- 使用 10808 代理临时执行 `git push`
- 创建并推送 tag `v2.4.3`
- 若环境支持，创建 Release；若不支持则说明阻塞点
- 操作完成后恢复代理环境
