# china-stock-analyst 技能审查报告

> 📅 审查日期：2026-03-22 | 审查标准：Claude Code Skills 官方最佳实践
> 审查模式：External Review（Mode 2）

---

## 一、总评

| 维度 | 评分 | 说明 |
|------|------|------|
| Frontmatter | ✅ 通过 | name/description 完整，第三人称，含触发条件 |
| 指令质量 | ✅ 通过 | 命令式语言，工作流清晰，检查清单完整 |
| 渐进式披露 | ⚠️ 警告 | SKILL.md 497行，接近500行上限 |
| 资源管理 | ⚠️ 警告 | 存在5个与股票分析无关的 Agent 文件 |
| 隐私安全 | ✅ 通过 | 无硬编码密钥，密钥脱敏正确，相对路径 |
| 测试覆盖 | ✅ 通过 | 115项测试全部通过 |
| 文档一致性 | ❌ 失败 | CLAUDE.md 测试计数过时（95 vs 115） |

**综合评级：良好（Good），有2个警告项、1个失败项需修复**

---

## 二、逐项检查详情

### 2.1 YAML Frontmatter ✅

SKILL.md frontmatter 规范：

```yaml
name: china-stock-analyst          # ✅ 有效，64字符内，小写+连字符
description: A股短线营收分析助手...  # ✅ 有效，第三人称，含4个触发条件
```

Agent 文件 frontmatter 全部规范：
- 9个股票相关 Agent 均有 `name`、`description`、`model` 字段 ✅
- 描述为第三人称 ✅
- 输出结构定义了统一 JSON Schema（v2） ✅

### 2.2 指令质量 ✅

- 使用命令式语言（"按...执行"、"禁止..."） ✅
- 明确的工作流步骤（12步 full_parallel / 9步 lite_parallel） ✅
- 报告必含模块清单（10项检查项） ✅
- 数据提取原则清晰（"仅提取最新价"、"禁止将止损位写入当前价格"） ✅

### 2.3 渐进式披露 ⚠️

| 文件 | 行数 | 状态 |
|------|------|------|
| SKILL.md | 497 | ⚠️ 接近500行上限 |
| README.md | 405 | ✅ 正常 |
| CLAUDE.md | 220 | ✅ 正常 |
| generate_report.py | 2750 | ✅ 脚本文件不计入 |
| team_router.py | 823 | ✅ 脚本文件不计入 |
| stock_utils.py | 1463 | ✅ 脚本文件不计入 |
| test_stock_skill.py | 1888 | ✅ 测试文件不计入 |

**建议**：SKILL.md 中「关键预警信号（基于验证经验）」和「短线指标建议与代码入口映射」可移至 `references/` 目录，预计可减少 80-100 行，使 SKILL.md 更聚焦于核心工作流指令。

### 2.4 资源管理 ⚠️

**股票相关 Agent（9个）** — 全部规范 ✅

| Agent | 前置 | JSON Schema | 状态 |
|-------|------|-------------|------|
| stock-data-auditor | ✅ | v2 | ✅ |
| stock-fundamental-expert | ✅ | v2 | ✅ |
| stock-technical-expert | ✅ | v2 | ✅ |
| stock-quant-flow-expert | ✅ | v2 | ✅ |
| stock-risk-expert | ✅ | v2 | ✅ |
| stock-macro-expert | ✅ | v2 | ✅ |
| stock-industry-researcher | ✅ | v2 | ✅ |
| stock-event-hunter | ✅ | v2 | ✅ |
| stock-identity-auditor | ✅ | v2 | ✅ |

**非股票相关 Agent（5个）** — 混入，建议清理 ⚠️

| Agent | 说明 | 建议 |
|-------|------|------|
| bug-analyzer.md | 代码调试专家 | 移除或移至通用 Agent 技能 |
| code-reviewer.md | 代码审查专家 | 移除或移至通用 Agent 技能 |
| dev-planner.md | 开发规划专家 | 移除或移至通用 Agent 技能 |
| story-generator.md | 用户故事生成 | 移除或移至通用 Agent 技能 |
| ui-sketcher.md | UI 草图专家 | 移除或移至通用 Agent 技能 |

这些 Agent 与股票分析技能无关，会：
- 增加技能目录体积
- 可能造成用户混淆（Claude Code 扫描所有 .md 文件作为 Agent）
- 不符合技能单一职责原则

### 2.5 隐私安全 ✅

| 检查项 | 状态 |
|--------|------|
| 硬编码 API Key | ✅ 未发现 |
| 硬编码绝对路径 | ✅ 未发现（脚本用 `Path(__file__).resolve()` 相对解析） |
| 密钥脱敏 | ✅ `stock_utils._mask_secret()` 正确实现 |
| .env 文件泄露 | ✅ `.gitignore` 已忽略 `.env` 和 `.env.local` |
| .env.example 模板 | ✅ 使用占位符，无真实密钥 |
| 日志脱敏 | ✅ POST 日志中 apikey 使用 `_mask_secret()` |

### 2.6 测试覆盖 ✅

```
Ran 115 tests in 0.118s — OK
```

| 测试类 | 覆盖内容 | 状态 |
|--------|----------|------|
| TestStockSkill | 路由、审计、鉴别、舆情、指标、评分、报告生成 | ✅ 115项全通过 |

测试覆盖全面，包含：
- 路由判定与高意图激活
- 数据审计与时间戳冲突
- 专家身份与价格锚点校验、流程阻断
- 舆情去重与评分封顶
- 短线指标（VWAP/ATR/量比）提取与降级
- 双轨评分与校准
- Obsidian 报告渲染
- 东方财富 API 集成（意图路由、配额控制、密钥读取）

### 2.7 文档一致性 ❌

| 问题 | 位置 | 详情 |
|------|------|------|
| 测试计数过时 | CLAUDE.md:22 | 声称"95 项全部通过"，实际 115 项 |
| 版本引用 | CLAUDE.md:28 | 引用 `v2.3+`，README 已更新至 `v2.4.2` |
| 测试计数不一致 | README.md:8 vs SKILL.md | README badge 显示 115，一致 ✅ |

---

## 三、架构评审

### 3.1 亮点

1. **Team-First 并行架构设计精良**
   - 12步固定链路 + 9步精简链路，降级策略清晰
   - `should_use_agent_team()` 路由逻辑完善，含高意图检测、缓存去重、配额控制

2. **双轨评分体系**
   - 短线动量 × 40% + 营收质量 × 35% + 风险约束 × 25%
   - 校准规则（弱确认下调15分、缺失指标下调5分）逻辑严密

3. **数据真实性审计前置**
   - `run_data_auditor` 作为门禁，日期回退、时间戳冲突、来源充分性三重校验
   - 失败降级策略合理：不阻断但下调置信度

4. **安全设计**
   - 密钥脱敏、禁止硬编码、相对路径、配额控制
   - 三重环境变量支持（EASTMONEY_APIKEY / EASTMONEY_API_KEY / EM_API_KEY）

5. **跨平台兼容**
   - Python 标准库，无第三方依赖
   - 相对路径组织，支持 Windows/macOS/Linux

### 3.2 改进建议

| 优先级 | 建议 | 影响 |
|--------|------|------|
| 高 | 删除5个非股票相关 Agent 文件 | 减少混淆，符合单一职责 |
| 高 | 更新 CLAUDE.md 测试计数（95→115）和版本号 | 文档准确性 |
| 中 | SKILL.md 拆分长内容到 references/ | 接近500行上限 |
| 中 | agents/ 目录增加 README 说明加载规则 | 可维护性 |
| 低 | scripts/ 增加 `__init__.py` 或独立包结构 | 长期可维护性 |
| 低 | stock_utils.py（1463行）考虑拆分模块 | 单文件过大 |

---

## 四、Security Scan 结果

| 检查项 | 状态 |
|--------|------|
| 硬编码密钥/API Key | ✅ 未发现 |
| 硬编码密码 | ✅ 未发现 |
| 明文 Token | ✅ 未发现 |
| 绝对用户路径泄露 | ✅ 未发现 |
| 敏感信息日志泄露 | ✅ 已脱敏处理 |
| 第三方依赖风险 | ✅ 仅使用 Python 标准库 |

---

## 五、与官方最佳实践对标

| 最佳实践 | 状态 | 备注 |
|----------|------|------|
| name 字段（64字符内、小写连字符） | ✅ | `china-stock-analyst` |
| description 第三人称 + 触发条件 | ✅ | 含4个"使用时机" |
| 指令使用命令式语言 | ✅ | "按...执行"、"禁止..." |
| SKILL.md < 500 行 | ⚠️ | 497行，临界值 |
| 无硬编码路径/密钥 | ✅ | |
| 脚本有错误处理 | ✅ | `_mask_secret`、try/except、失败原因码 |
| 工作流检查清单 | ✅ | 10项报告必含模块 |
| 资源按需加载 | ✅ | agents 缺失时回退默认路径 |

---

## 六、修复建议（按优先级）

### 必须修复

1. **更新 CLAUDE.md 测试计数和版本号**
   ```markdown
   # CLAUDE.md:22
   - 当前回归测试：95 项全部通过。
   + 当前回归测试：115 项全部通过。
   ```

2. **移除非股票相关 Agent 文件**
   ```bash
   rm agents/bug-analyzer.md agents/code-reviewer.md agents/dev-planner.md \
      agents/story-generator.md agents/ui-sketcher.md
   ```

### 建议改进

3. **SKILL.md 拆分长内容至 references/**
   - 将「短线指标建议与代码入口映射」移至 `references/短线指标参考.md`
   - 将「关键预警信号」移至 `references/预警信号参考.md`
   - SKILL.md 保留核心工作流 + 指向 references 的链接

4. **stock_utils.py 模块拆分**（长期）
   - `stock_utils_eastmoney.py` — 东方财富 API 封装
   - `stock_utils_validator.py` — 股票代码/名称验证
   - `stock_utils_indicators.py` — 短线指标计算

---

## 七、结论

**china-stock-analyst 是一个设计精良、文档完善、测试充分的 Claude Code 技能。** 核心架构（Team-First 并行、双轨评分、数据审计前置）体现了较高的工程水平。主要问题集中在：

1. 5个无关 Agent 文件混入（影响单一职责）
2. CLAUDE.md 文档未同步更新（95→115）

修复上述2个问题后，该技能可达到 **优秀（Excellent）** 评级。

---

*审查人：Claude Code Skill Reviewer | 审查工具：skill-reviewer v1.0*
