# Report Quality Gate Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 扩展报告质量门禁，新增止损位、标签-分数一致性、风险-建议冲突三类校验，同时单独审查 SKILL.md 的冗长与失焦风险。

**Architecture:** 保持现有 Markdown 门禁脚本的轻量方案，不引入新依赖，也不重做报告数据模型。本轮先通过测试定义三个新增规则的文本匹配行为，再以最小改动扩展 `report_quality_gate.py`，最后验证批量检查脚本仍可工作，并输出 SKILL.md 审查结论。

**Tech Stack:** Python 标准库、unittest

---

### Task 1: 为 report_quality_gate 写失败测试

**Files:**
- Modify: `tests/test_stock_skill.py`
- Modify: `scripts/report_quality_gate.py`

**Step 1: Write the failing test**
- 新增“止损位高于当前价时报 high”的测试
- 新增“高分却写回避/低分却写可做时报 medium”的测试
- 新增“高风险却写可做时报 high”的测试

**Step 2: Run test to verify it fails**
- 只运行新增测试，确认当前门禁尚未覆盖这些规则。

**Step 3: Write minimal implementation**
- 在 `report_quality_gate.py` 中扩展推荐段解析字段
- 新增三类规则的文本提取与 issue 生成

**Step 4: Run test to verify it passes**
- 运行新增测试并确认通过

---

### Task 2: 保持批量检查脚本兼容

**Files:**
- Modify: `scripts/report_quality_gate.py`
- Test: `tests/test_stock_skill.py`

**Step 1: Verify existing behavior**
- 复查现有价格偏差、待确认涨跌、时间锚点三类规则不被破坏

**Step 2: Minimal compatibility changes**
- 若新增规则需要新的解析函数或更稳健的块提取，只做局部扩展，不改变 CLI 输入输出结构

**Step 3: Run focused tests**
- 运行与质量门禁相关的测试集合

---

### Task 3: 审查 SKILL.md 冗长度风险

**Files:**
- Review only: `SKILL.md`

**Step 1: Read for structure**
- 检查是否同时承担“产品说明 + 路由规则 + 细节实现 + 测试说明 + 迁移文档”过多职责

**Step 2: Assess risk**
- 判断其冗长是否会导致优先级冲突、提示词漂移、实现与文档不一致、模型注意力稀释

**Step 3: Produce recommendations**
- 只给出“保留什么、拆出去什么、哪些段落要缩短”的建议，不改文件

---

### Task 4: 回归验证

**Files:**
- Test: `tests/test_stock_skill.py`

**Step 1: Run targeted tests**
- 运行本轮新增与受影响测试

**Step 2: Run full suite**
- 运行 `python -m unittest tests/test_stock_skill.py -v`

**Step 3: Run report checks**
- 运行 `python scripts/run_report_quality_checks.py`
- 确认脚本仍可执行，并记录存量报告的失败是否来自真实内容问题
