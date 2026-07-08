# china-stock-analyst 桌面端重构设计文档

**版本**：v1.0  
**日期**：2026-07-08  
**状态**：设计阶段，待实现计划  

---

## 1. 背景与目标

### 1.1 项目现状

`china-stock-analyst` 当前是一个 Claude Code Skill，核心能力包括：

- **Team-First 12 步分析链路**：`run_data_auditor → collect_data → 8 位专家 → supervisor_review → render_report`。
- **双轨评分体系**：短线动量分（40%）+ 营收质量分（35%）+ 风险约束分（25%）。
- **数据源**：Web Search（主）+ 东方财富 API（复核）+ AKShare（免费历史/资金流/新闻）。
- **专家实现**：`agents/*.md` 作为 LLM prompt 模板，`generate_report.py` 用正则从搜索结果解析并评分。

### 1.2 重构目标

将现有项目改造为**独立桌面端软件**，并满足以下约束：

1. **保持框架和理念不变**：固定 12 步链路、8 位专家角色、双轨评分、最终标签 `可做/观察/回避` 均保留。
2. **减少 AI 依赖**：核心标签、评分、数据抓取由规则/确定性逻辑完成；AI 仅用于可选的“增强解读”。
3. **提高数据准确性**：用 [Scrapling](https://git.wxbfnnas.com/wxb/scrapling.git) 替代 Web Search，多源免费站点抓取并交叉验证。
4. **跨平台桌面体验**：优先 Windows，使用 **Tauri + Python 后端**。
5. **本地缓存与离线回看**：SQLite 持久化，支持历史报告回看。

---

## 2. 关键设计决策

| 决策项 | 选择 | 说明 |
|:---|:---|:---|
| 桌面框架 | Tauri + Python Sidecar | 前端现代化，Python 后端完整内嵌，用户开箱即用。 |
| 数据源 | AKShare + 东方财富 + 新浪财经 + 同花顺 + 腾讯财经 | 多源免费采集，交叉验证，不依赖单一主源。 |
| 冲突处理 | 多数投票 + 中位数 + 源优先级兜底 | 同字段多源取值，优先取多数源一致或中位数；无多数时按源优先级兜底。 |
| AI 边界 | 仅增强解读 | 核心评分和标签规则化，LLM 只生成自然语言段落。 |
| 默认 LLM 样板 | DeepSeek | 用户可配置 API Key，也支持替换为其他兼容 OpenAI API 的服务。 |
| 存储 | SQLite + JSON | 自选股、原始数据缓存、报告历史本地持久化。 |
| UI 形态 | 首页看板 + 分析向导 | 平时当行情工具，深度分析时进入完整链路。 |

---

## 3. 总体架构

```text
[Tauri 前端]  <-- JSON over STDIO/IPC -->  [Python Sidecar 分析服务]
                                                  |
            +-------------------+-------------------+-------------------+
            |                   |                   |                   |
      [数据采集层]         [分析引擎层]         [报告渲染层]         [本地存储层]
            |                   |                   |                   |
      [AKShare 适配器]     [规则化专家]        [Markdown/HTML]     [SQLite]
      [Scrapling 适配器]   [可选 LLM 增强]
      [源优先级/冲突校验]
```

### 3.1 前端（Tauri + Web 技术栈）

| 页面 | 功能 |
|:---|:---|
| 首页看板 | 自选股列表、最新价/涨跌幅/标签、快捷分析入口、刷新按钮。 |
| 分析向导 | 输入股票代码、选择模式（单股/对比/回测）、展示 12 步进度、输出报告。 |
| 报告阅读器 | 渲染 Markdown/HTML 报告，支持导出为 `.md` / `.pdf`。 |
| 设置页 | 数据源优先级排序、Scrapling 站点开关、LLM API 配置（DeepSeek 样板）、缓存清理。 |
| 历史记录 | 按股票/日期查看过往报告，支持“验证上次报告”。 |

### 3.3 前后端通信协议

Tauri 通过 **STDIN/STDOUT 发送 JSON 行（JSON Lines）** 与 Python Sidecar 通信，避免端口占用和 CORS 问题。

**请求示例**：

```json
{"cmd": "analyze", "codes": ["600519"], "mode": "single", "request_id": "uuid"}
```

**响应示例**：

```json
{"status": "success", "request_id": "uuid", "data": {"report_md": "...", "report_json": {...}}}
```

**异常响应**：

```json
{"status": "error", "request_id": "uuid", "error_code": "SOURCE_ALL_FAILED", "message": "..."}
```

### 3.4 Python Sidecar 模块

| 文件/模块 | 职责 |
|:---|:---|
| `service.py` | 进程入口，命令循环，错误隔离，日志转发。 |
| `data_fetcher.py` | 调度 AKShare 与多个 Scrapling 源并行抓取。 |
| `scrapling_adapters/eastmoney.py` | 东方财富页面适配器。 |
| `scrapling_adapters/sina.py` | 新浪财经页面适配器。 |
| `scrapling_adapters/ths.py` | 同花顺页面适配器。 |
| `scrapling_adapters/tencent.py` | 腾讯财经页面适配器。 |
| `data_validator.py` | 多源数据标准化、冲突检测、优先级决策、降级标记。 |
| `analysis_engine.py` | 12 步规则化专家流水线。 |
| `llm_adapter.py` | 可选 DeepSeek/OpenAI-compatible API，仅用于增强解读。 |
| `report_renderer.py` | Markdown/HTML 报告生成。 |
| `storage.py` | SQLite 读写：自选股、原始数据缓存、报告历史。 |
| `config_manager.py` | 配置读写，兼容现有 `config/settings.json`。 |

---

## 4. 数据流

### 4.1 单次分析标准流程

```text
用户输入 600519/贵州茅台
  ↓
Tauri 发送 {cmd:"analyze", codes:["600519"], mode:"single"}
  ↓
service.py 接收 → 读取本地配置
  ↓
data_fetcher.py 并行调用：
  ├─ AKShareAdapter：K线、资金流、新闻、盘口
  ├─ EastmoneyScraper：最新价、涨跌幅、成交额
  ├─ SinaScraper：新闻快讯、盘口
  ├─ ThsScraper：资金流、龙虎榜
  └─ TencentScraper：行情快照
  ↓
data_validator.py 标准化 + 交叉验证：
  ├─ 同一字段多源取值，优先取多数源一致值或中位数
  ├─ 无多数一致时，按源优先级兜底（默认：东财 > 新浪 > 同花顺 > 腾讯 > AKShare）
  ├─ 数值冲突 > 阈值 → 标记“源不一致”，置信度降级
  ├─ 单个源失败/缺失 → 不阻断流程，仅记录日志
  └─ 缺失关键字段 → 标签上限降为“观察”
  ↓
analysis_engine.py 规则化 12 步流水线：
  ├─ data_auditor：时间戳、来源类别、数值冲突审计
  ├─ fundamental/technical/quant/risk/macro/industry/event：规则评分
  ├─ identity_auditor：代码/名称/价格一致性校验
  ├─ supervisor_review：综合双轨评分
  └─ render_report：生成 Markdown
  ↓
（可选）llm_adapter.py 调用 DeepSeek 生成“增强解读”段落
  ↓
report_renderer.py 输出最终报告 JSON + Markdown
  ↓
Tauri 渲染报告，SQLite 缓存结果
```

### 4.2 Scrapling 适配器接口

所有 Scrapling 适配器实现统一接口，便于扩展和维护：

```python
class BaseStockScraper:
    name: str           # "eastmoney" / "sina" / "ths" / "tencent"
    priority: int       # 源优先级，数值越小优先级越高
    enabled: bool       # 用户可开关

    def fetch_quote(self, stock_code: str) -> QuoteSnapshot: ...
    def fetch_news(self, stock_code: str, limit: int = 10) -> list[NewsItem]: ...
    def fetch_fund_flow(self, stock_code: str) -> list[FundFlow]: ...
```

Scrapling 典型调用方式：

```python
from scrapling.fetchers import StealthyFetcher

fetcher = StealthyFetcher()
page = fetcher.fetch(url, headless=True, network_idle=True)
price = page.css_first('.price').text
```

### 4.3 多源冲突处理规则

1. **AKShare 与网页源地位平等**：AKShare 只是数据源之一，不当作唯一真理。
2. **同字段多源取值规则**：
   - 第一步：统计各源值，取**多数源一致值**（如 3/4 个源一致）。
   - 第二步：无多数一致时，取**中位数**。
   - 第三步：中位数也无法确定时，按**源优先级**兜底：东财 > 新浪 > 同花顺 > 腾讯 > AKShare。
3. **容灾与源失败**：
   - 单个源因网络抖动、反爬、超时失败 → 不阻断流程，记录 `source_logs`，用其余源继续。
   - 仅一个源可用 → 继续分析，但置信度上限“中”，报告中标注“单源数据”。
   - 全部源失败 → 阻断分析，返回错误提示用户重试。
4. **数值冲突**：
   - 差异 <= 阈值（价格 1%，涨跌幅 1.2%，资金流 35%）：按上述规则取有效值。
   - 差异 > 阈值：标记“源不一致”，置信度降级为“低”，标签上限“观察”，报告中列出冲突源。

---

## 5. AI 边界

### 5.1 不用 AI 的环节

- 网页数据抓取（Scrapling）。
- AKShare 结构化数据获取。
- 数据标准化、冲突校验、优先级决策。
- 技术指标计算（ATR、VWAP、RSI、支撑压力等）。
- 双轨评分与最终标签判定。
- 基础报告模板拼接。

### 5.2 可用 AI 的环节（可选，默认关闭）

- 增强型自然语言解读。
- 报告摘要生成。
- 多专家结论的连贯性润色。

### 5.3 LLM 调用约束

- **输入隔离**：LLM 只能接收已验证的 `report` 对象，禁止直接访问网页或生成价格/资金流。
- **防幻觉 Prompt**：必须包含“基于以下事实做解读，禁止编造数据”。
- **默认关闭**：未配置 API Key 时，界面隐藏“AI 增强”按钮，报告完全由规则生成。
- **失败回退**：LLM 调用失败时静默回退到规则模板报告。

---

## 6. 本地存储

### 6.1 SQLite 表结构

| 表名 | 说明 |
|:---|:---|
| `watchlist` | 自选股：代码、名称、排序、创建时间。 |
| `raw_data_cache` | 原始数据缓存：代码、日期、源、字段、值、时间戳。 |
| `reports` | 报告历史：ID、代码、模式、报告内容（Markdown）、生成时间。 |
| `settings` | 应用配置：JSON 存储，覆盖 `config/settings.json`。 |
| `source_logs` | 抓取日志：源名称、状态、失败原因、时间戳。 |

### 6.2 缓存策略

- **原始数据**：按 `(stock_code, date, source)` 缓存，当天分析优先读缓存，用户可手动刷新。
- **报告历史**：每次分析生成一条记录，支持离线回看和“验证上次报告”。
- **配置同步**：启动时将 `config/settings.json` 合并到 SQLite `settings` 表，运行期以 SQLite 为准。

---

## 7. 错误处理

| 场景 | 处理策略 |
|:---|:---|
| 单个数据源失败 | 记录失败原因，继续用其他源；全部失败则返回错误并提示用户重试。 |
| 同字段多源冲突 | 标记“源不一致”，置信度降级，标签上限“观察”，报告中列出冲突源。 |
| LLM API 失败 | 静默回退到规则模板报告，前端提示“AI 增强未启用”。 |
| Python Sidecar 崩溃 | Tauri 捕获退出码，自动重启子进程；任务状态持久化到 SQLite 以便恢复。 |
| 非交易时间数据 | 标注“非实时”，避免误用。 |
| 缺失关键短线指标 | 标签上限降为“观察”，置信度上限“中”。 |

---

## 8. 测试策略

### 8.1 单元测试

- 每个 Scrapling 适配器（使用 mock 响应）。
- `data_validator.py` 的冲突检测和优先级决策。
- `analysis_engine.py` 中各规则评分函数。
- `report_renderer.py` 输出格式校验。

### 8.2 集成测试

- 完整 `analyze` 命令端到端测试。
- 覆盖场景：AKShare 可用/不可用、单源失败、多源冲突、LLM 关闭/失败。

### 8.3 前端测试

- 看板渲染、自选股增删。
- 向导状态机、进度展示。
- 报告导出功能。

### 8.4 合规测试

- 确保只访问公开免费页面。
- 不绕过付费接口、不破解反爬。
- 遵守目标站点的 `robots.txt` 和访问频率。

---

## 9. 现有代码复用

| 现有文件 | 复用方式 |
|:---|:---|
| `scripts/akshare_adapter.py` | 整体迁移为 `data_fetcher.py` 的 AKShare 源。 |
| `scripts/technical_indicators.py` | 整体迁移，计算指标不变。 |
| `scripts/backtest_framework.py` | 迁移后接入分析向导的“回测”模式。 |
| `scripts/strategy_optimizer.py` | 迁移后作为“策略优化”高级功能。 |
| `scripts/stock_utils.py` | 迁移，保留股票代码校验、名称规范化等工具。 |
| `scripts/report_constants.py` | 迁移，作为规则引擎常量。 |
| `config/settings.json` | 兼容读取，运行期合并到 SQLite。 |
| `agents/*.md` | 人工提取输出 schema 和规则说明，映射为 Python 规则引擎约束（非运行时 NLP 解析）。 |

---

## 10. 打包与分发

### 10.1 推荐打包方案

| 方案 | 说明 | 适用阶段 |
|:---|:---|:---|
| **Tauri + 内嵌 Python（推荐）** | 安装包内含 Python runtime 和所有依赖，用户双击安装即可。 | 正式发布 |
| **Tauri + 外部 Python** | 用户需先安装 Python 3.10+，Tauri 启动时调用系统 Python。 | 开发调试 / 极客用户 |
| **PyInstaller 打包 Python 为 exe** | 把 Python 后端先打成独立 exe，Tauri 以 sidecar 调用。 | 可结合方案 1 减少体积 |

### 10.2 Windows 安装包形态

- `.msi` 安装程序（推荐，支持卸载、快捷方式）。
- 便携版 `.zip`（可选，适合不安装直接运行）。

### 10.3 自动更新

- 第一阶段可不做自动更新，用户手动下载新版本。
- 第二阶段可接入 Tauri 的 `updater` 插件，配合 GitHub Releases 或私有更新服务器。

---

## 11. 风险与待确认事项

| 风险 | 说明 | 缓解措施 |
|:---|:---|:---|
| 目标站点反爬升级 | Scrapling 可处理一般反爬，但站点结构变化会导致适配器失效。 | 每个适配器增加版本号和健康检查，失效时自动降级。 |
| 安装包体积大 | 内嵌 Python runtime + akshare + scrapling 会使安装包达到数百 MB。 | 评估 PyOxidizer/Nuitka 打包，或提供“需单独安装 Python”的轻量版。 |
| LLM 配置门槛 | 普通用户可能不清楚如何配置 DeepSeek API。 | 提供 DeepSeek 官方申请链接和配置样板。 |
| 法律法规风险 | 股票数据抓取需合规。 | 仅抓取公开免费页面，控制频率，明确免责声明。 |

---

## 12. 后续步骤

1. 用户确认本设计文档。
2. 调用 `writing-plans` skill 生成详细实施计划。
3. 按实施计划分阶段开发：先做 Python 后端改造，再做 Tauri 前端，最后打包测试。

---

## 13. 免责声明

> 所有分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。本项目仅抓取公开免费数据，使用者需自行确保符合相关法律法规和网站服务条款。
