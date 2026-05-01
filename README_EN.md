# China Stock Analyst

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-purple.svg)
![Tests](https://img.shields.io/badge/Tests-145%20Passed-success.svg)

**A-Share Short-term Trading Analysis Assistant | Team-First Parallel Expert System**

[Core Features](#-core-features) • [Quick Start](#-quick-start) • [Execution Flow](#-execution-flow) • [Report Capabilities](#-report-capabilities) • [Changelog](#-changelog)

</div>

---

## Overview

> A specialized A-share analysis skill designed for **Claude Code**, featuring a **"Short-term Trading Signals + Revenue Quality"** dual-track assessment system.

The current version has been upgraded to a **Team-First** architecture: default parallel expert collaboration, front-loaded data authenticity audit, enhanced automatic activation for complex instructions with non-interrupting execution, and now uses a **Web Search primary path + East Money structured verification** model.

### Claude Code Skills Compatibility

- **Overall fit: high**
- **Clear entrypoint**: `SKILL.md` is the actual Claude Code skill entry, while the README serves as install, engineering, and release documentation
- **Good repository shape for Skills**: `SKILL.md + Python helper scripts + regression tests`
- **Portable by design**: core scripts rely on Python standard library and relative paths
- **Strong guardrails**: authenticity audit, collection-quality gate, identity checks, and report post-checks are all implemented
- **Operational note**: this repository is not a standalone web service; scripts and tests are intended to run from the repository root

---

## Core Features

| Feature | Description |
|:---:|:---|
| **8 Expert Collaboration** | Fundamental Analyst / Technical Analyst / Quantitative Modeler / Risk Controller / Macro Strategist / Industry Researcher / Event Hunter / Expert Identifier Agent |
| **Team-First Default Parallel** | Defaults to `agent_team` mode, complex tasks enforce `full_parallel`, no longer using `single_flow` as main workflow |
| **Front-loaded Data Authenticity Audit** | `run_data_auditor` executes before all analysis, validating date rollback, timestamp conflicts, and source category sufficiency |
| **Identity & Price Dual Verification** | `run_expert_identifier_agent` validates expert identity, target consistency, and price anchor deviation; blocks process on anomalies |
| **Sentiment Noise Reduction** | Sentiment deduplication, quality scoring, low-quality removal, with capped impact on overall scores to prevent noise-driven recommendations |
| **Supervisor Conflict Arbitration** | Downgrades recommendations when industry signals conflict with event impacts, outputs "Actionable / Watch / Avoid" upper limits with reasons |
| **Traceable Evidence Chain** | Each key conclusion includes conclusion value, source URL, minute-level timestamp, and adoption/rejection basis |
| **Complex Instruction Continuity Guard** | Parallel nodes support isolated retry and aggregation, never falling back to single-line flow due to local issues |
| **Dual-path Data Strategy** | Build candidates from Web Search first, then verify key fields via East Money to balance quota and accuracy |
| **East Money Free API Integration** | Three new external capabilities: `news-search / query / stock-screen`, enhancing news, structured financial data, and stock screening credibility |
| **Secure Key Loading** | Supports `EASTMONEY_APIKEY` environment variable priority, fallback to project `.env.local/.env`, ignored by default in commits |
| **Free Quota Management** | Built-in 50 requests/day quota control, critical gating, cache deduplication, and empty result guidance to prioritize key data queries |

---

## Quick Start

### Installation

```bash
git clone https://github.com/wjt0321/china-stock-analyst.git
```

Copy the project to Claude Code skills directory:

| System | Path |
|:---|:---|
| Windows | `%USERPROFILE%\.claude\skills\china-stock-analyst` |
| macOS / Linux | `~/.claude/skills/china-stock-analyst` |

### Verify Installation

```bash
python -m unittest tests/test_stock_skill.py -v
```

Current test results: **145 test cases all passed**

### East Money API Configuration (Optional Enhancement)

1. Apply for your own API Key from the East Money Skills page (do not use others' keys).
2. Create `.env.local` (recommended) or `.env` in the project root:

```env
EASTMONEY_APIKEY=your_api_key_here
EASTMONEY_BASE_URL=https://mkapi2.dfcfs.com/finskillshub/api/claw
EASTMONEY_ENDPOINT_NEWS_SEARCH=/news-search
EASTMONEY_ENDPOINT_QUERY=/query
EASTMONEY_ENDPOINT_STOCK_SCREEN=/stock-screen
```

3. You can also use system environment variable `EASTMONEY_APIKEY`, which takes priority over `.env.local/.env`.
4. The repository provides `.env.example` template, and `.gitignore` excludes `.env` and `.env.local` by default to prevent key leakage.

Notes:

- **The main workflow still runs without an API key**
- The current primary path is **Web Search**
- East Money is used for structured supplementation, key-field verification, and stock screening enhancement

---

## Data Integration Details (v2.4.3)

### Why this integration

- Fix recurring mismatches between stock code, stock name, and price
- Reduce weak-web-source noise and model-side free completion
- Enforce a hard “validate-before-analyze” gate

### Integration strategy

- **Primary source switch**: key fields are built from Web Search candidates, then verified by East Money query
- **Source priority**: `web_search > eastmoney_query`
- **Responsibility split**: Web Search for coverage/candidates, East Money for structured key-field verification
- **Fallback behavior**: when East Money verification is unavailable, mark result as "not structurally verified" instead of fabricating validated values

### Implementation highlights

- `scripts/stock_utils.py`
  - Added dual-path field alignment and data quality summary
  - Added standardized output fields (`symbol/name/price/trade_date`)
  - Added unified error codes (empty result, invalid arguments, API failure)
- `scripts/generate_report.py`
  - Added identity consistency, price validity, and trading-day timeliness gates
  - Any failure blocks downstream conclusion and returns structured repair guidance
- `scripts/team_router.py`
  - Added symbol metadata passthrough (source function, fetched timestamp, validation conclusion, reason codes)
  - Unified reason codes and user-facing tips
- `scripts/report_quality_gate.py`
  - Added stop-loss, score-label consistency, and risk-vs-recommendation checks
  - Hardened detection for template variants, missing candidate tables, and missing recommendation blocks
- `scripts/run_report_quality_checks.py`
  - Added aggregated rule summary, severity summary, and repair suggestions
  - Produces structured output that can be turned into a repair checklist for historical reports

### Report-level changes

- Enhanced “Data Authenticity Verification” and “Data Source Metadata”
- Added source function, fetched timestamp, validation result, reason codes, and repair suggestions

---

## Usage Examples

### Single Stock Analysis

```text
Analyze 600519 (Moutai)
Check out Zhujiang Co. 600684
```

### Multi-Stock Comparison/Discussion

```text
Compare China Energy Engineering and Shoukai Shares, give me short-term advice
Analyze the power sector: Jinkong Power, Changyuan Power
```

### High-Intent Complex Requests (Auto full_parallel)

```text
Collect market data today, first screen 10 stocks, then organize expert discussion, finally recommend 3 stocks
```

### Verify Historical Reports

```text
Verify stock research report/Taihao Technology 600590 analysis report-20260307.md
Compare the March 7 report of Sinosteel International 000928 with today's data
```

---

## Execution Flow

### Routing Modes

| Mode | Trigger Characteristics | Description |
|:---|:---|:---|
| `full_parallel` | Multi-target/verification/conflict arbitration/high-intent serial tasks | Full expert parallel + continuity guard |
| `lite_parallel` | Lightweight requests | Same workflow paradigm downgrade, reducing some expert nodes |

### Fixed Pipeline

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

## Scoring & Governance

### Dual-Track Scoring

| Dimension | Weight | Description |
|:---|:---:|:---|
| Short-term Momentum Score | 40% | Capital flow, volume-price, key level breakthrough |
| Revenue Quality Score | 35% | Revenue YoY/QoQ, caliber consistency |
| Risk Constraint Score | 25% | Volatility, drawdown, regulatory and event risks |

Final Label: `Actionable` / `Watch` / `Avoid`

### Sentiment Governance Rules

- Sentiment is deduplicated before scoring; low-quality information doesn't enter core conclusions
- Sentiment impact scores have upper/lower limits, not allowed to dominate overall scores
- Reports display adoption basis and rejection basis, supporting review

---

## Report Capabilities

Generated reports include the following key modules:

| Module | Content |
|:---|:---|
| Timeliness & Caliber Warnings | Data cutoff time, signal validity period, revenue caliber description |
| Data Authenticity Audit | Date/timestamp/multi-source consistency audit conclusions and downgrade strategies |
| Revenue Snapshot | Revenue/YoY/QoQ/caliber/source/date |
| Dual-Track Scoring | Weighted total score and calibrated total score |
| Sentiment Noise Reduction | Adoption count, rejection count, reasons and impact scores |
| Expert Independent Conclusions | 8 expert opinions and evidence chains |
| Expert Identifier & Process Blocking | Identity/target/price verification results, blocking stage, follow-up actions |
| Supervisor Arbitration | Conflict items, label upper limits, arbitration reasons |
| Evidence Chain Summary | Conclusion → Data → Source → Timestamp |

---

## Project Structure

```text
china-stock-analyst/
├── SKILL.md
├── README.md
├── LICENSE
├── README_EN.md
├── scripts/
│   ├── team_router.py
│   ├── generate_report.py
│   ├── stock_utils.py
│   ├── report_constants.py
│   ├── report_quality_gate.py
│   └── run_report_quality_checks.py
├── agents/
│   ├── stock-data-auditor.md
│   ├── stock-fundamental-expert.md
│   ├── stock-technical-expert.md
│   ├── stock-quant-flow-expert.md
│   ├── stock-risk-expert.md
│   ├── stock-macro-expert.md
│   ├── stock-industry-researcher.md
│   ├── stock-event-hunter.md
│   └── stock-identity-auditor.md
├── tests/
│   └── test_stock_skill.py
├── assets/
│   └── report_template.md
├── references/
│   └── valuation_model_guide.md
└── docs/
    ├── agent-teams-blueprint.md
    ├── REPORT_QUALITY_REPAIR_CHECKLIST_20260403.md
    └── plans/
```

---

## Running Tests

```bash
python -m unittest tests/test_stock_skill.py -v
```

Test coverage includes:
- Routing and high-intent activation
- Data audit and resampling downgrade
- Expert identifier, identity and price verification, process blocking
- Sentiment noise reduction and score capping
- New experts and supervisor arbitration
- Report quality gates, batch quality checks, and repair suggestion aggregation
- Complex request end-to-end closed-loop verification
- Current regression test total: **145 items (all passed)**

Common quality-check commands:

```bash
python scripts/report_quality_gate.py stock-reports\\000767_晋控电力_20260310.md
python scripts/run_report_quality_checks.py
```

---

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## Changelog

### v2.4.3 (2026-04-03)

- Release/Tag: `2.4.3`
- **Documentation aligned with the current skill shape**
  - Rewrote `SKILL.md` into a concise Claude Code Skills-oriented rules file
  - Updated both READMEs to reflect the actual data-source strategy and repository layout
- **Report quality gate expanded**
  - Added stop-loss, score-label consistency, and risk-vs-recommendation checks
  - Hardened detection for title variants, missing candidate tables, and missing recommendation blocks
- **Batch quality checks improved**
  - `run_report_quality_checks.py` now outputs aggregated rule summaries, severity stats, and repair suggestions
  - Added a repair checklist document for the existing `stock-reports`
- Regression tests passed: **145/145**

### v2.4.2 (2026-03-17)

- Release/Tag: `2.4.2`
- **Added front-loaded data gates to improve data accuracy**
  - Before conclusion generation, the pipeline now enforces three hard gates: code-name consistency, price validity, and trading-day timeliness
  - Any gate failure blocks downstream analysis and prevents recommendation output with misleading risk
  - On block, the system returns structured repair guidance (reason codes + actionable fixes) for quick recollection and verification
- **Gate execution moved earlier in the pipeline**
  - Fixed right after `run_data_auditor` and before expert conclusion aggregation, ensuring all downstream reasoning uses validated data
- **Report traceability enhanced**
  - The “Data Authenticity Verification / Data Source Metadata” sections now display gate conclusions, reason codes, and repair guidance
- Regression tests passed: **95/95**

### v2.4.1 (2026-03-17)

- Release/Tag: `2.4.1`
- **AKShare deep cleanup completed**
  - Removed all AKShare code paths, dependency entries, and diagnostics scripts to avoid unstable-link impact on the main flow
  - Replaced routing/report passthrough with generic symbol metadata (`metadata_passthrough`)
- **AKShare usage difficulties (direct reason for removal)**
  - Intermittent `REMOTE_DISCONNECTED` under the same network conditions
  - Network probes passed while business-level requests remained unstable, reducing reproducibility and observability
  - Could not meet this skill's requirement for consistent analysis and auditable outputs
- **Data strategy refactor**
  - Key-field priority switched to `web_search > eastmoney_query`
  - East Money retained as a structured verification path with quota governance and quality scoring
- Regression tests passed: **95/95**

### v2.4.0 (2026-03-17)

- Release/Tag: `2.4.0`
- **Dual-path source governance completed**
  - Core fields now use `web_search > eastmoney_query`
  - Standardized field schema and unified error codes added to reduce cross-source drift
- **Authenticity gate upgrades**
  - Enforced pre-analysis checks: code-name consistency, price validity, and trading-day timeliness
  - Any failed check blocks the pipeline and returns structured repair suggestions
- **Source-governance upgrades**
  - Web search is downgraded to supplementary news usage only
  - Added source-priority control, reason codes, and user guidance mapping
- **Routing and report traceability enhancements**
  - Reports now include source function, fetched timestamp, validation conclusions, and reason codes
- Tests expanded to **94 cases, all passed**

### v2.3.1 (2026-03-14)

- Release/Tag: `2.3.1`
- Added timestamp governance:
  - Unified minute-level timestamp alignment and comparison to reduce misjudgments from cross-source granularity inconsistency
  - Added timestamp semantic hints in evidence chains and audit results to enhance "traceable + explainable" capability
- Closing price semantic convergence:
  - "Closing price" is only valid as current price when "same-day/today" semantics or verifiable date anchors are present
  - Ambiguity rejection for texts with "only closing price but missing same-day semantics" to prevent historical prices from being mistaken for current prices
- Routing strategy update (lite/full):
  - Both lite/full use unified Team orchestration main path to ensure process consistency
  - Only distinguish concurrency and inference depth through `execution_profile`, no longer forking core pipeline
- Target binding enhancement:
  - Enabled "name-code strong adjacency" constraint, requiring stable binding relationships within local windows
  - Trigger ambiguity rejection and block erroneous bindings when same code is adjacent to multiple names or vice versa
- ST semantic preservation:
  - ST prefix is preserved by default during name standardization, no removal processing
  - Compatible with ST/non-ST alias mapping to avoid risk semantics loss during normalization
- Tests expanded to **79 items all passed**, adding coverage for closing price same-day semantic judgment, lite/full team routing consistency, strong adjacency ambiguity rejection, and ST prefix preservation

### v2.3.0 (2026-03-13)

- Release/Tag: `2.3.0`
- Added East Money free API three capability integrations:
  - `news-search`: Financial news retrieval (news, announcements, research reports, event interpretation)
  - `query`: Structured financial data query (quotes, financials, relationship management, etc.)
  - `stock-screen`: Natural language intelligent stock screening and result export
- Added data correctness assurance mechanism:
  - Critical gating in Team-First process, non-critical requests don't consume external API
  - Quota management: Default 50 requests/day counting and upper limit interception
  - Cache deduplication: Repeated queries prioritize reusing results to reduce quota waste
  - Empty result and out-of-scope requests unified prompts, avoiding fake placeholder data
- Added security and portable configuration:
  - Users must apply for and configure `EASTMONEY_APIKEY` themselves
  - Supports system environment variable priority, project `.env.local/.env` fallback
  - Provides `.env.example` as migration template, not committing real keys
- Tests expanded to **71 items all passed**, covering request construction, routing triggers, quota control, desensitized output, and `.env` fallback loading

### v2.2.3 (2026-03-13)

- Added `agents/` preset expert directory: Pre-configured commonly used Team-First roles as reusable Agent definitions, reducing runtime prompt assembly overhead
- Routing added "preset priority + default fallback": Use `preconfigured` when hitting preset Agents, automatically fallback to `default` when missing, without interrupting process
- Output added role invocation source registration information for audit and troubleshooting
- `SKILL.md` supplemented preset Agent mapping, enable rules, and fallback strategy descriptions
- Tests expanded to 56 items all passed (including hit and fallback scenarios)

### v2.2.1 (2026-03-13)

- Target binding enhancement: `parse_search_results_to_report` supports `stock_name` input and injects `canonical_name/canonical_code`, making identity verification more robust in multi-target mixed texts
- Fund direction fallback: Conservative judgment for no-direction-word scenarios to avoid misjudging "amount-only descriptions" as inflow or outflow
- Audit regression enhancement: Added "no conflict within threshold" and "dual category pass" regression tests to reduce false positives while maintaining explainability
- Documentation improvement: Added data extraction principles (price anchor priority, multi-target filtering)
- Test expansion: Test set expanded to 54 items all passed

### v2.1.1 (2026-03-13)

- Price parsing: Prioritize extracting stock price from semantic anchors (latest price/current price/closing price, etc.), added A-share price range validation (0.1-600 yuan)
- Fund flow: Extended direction keyword list to prevent cross-role direction contamination
- Data source verification: Relaxed category requirement (3→2) and timestamp conflict threshold (90→179 minutes), expanded data source domain list

### v2.1.0 (2026-03-12)

- Added `run_expert_identifier_agent`: Expert identity, target consistency, price anchor deviation verification
- Added process blocking mechanism: Block `supervisor_review` when identity or price verification fails
- Report added "Expert Identifier & Identity-Price Verification" and "Process Blocking" sections
- Tests expanded to 42 items all passed

### v2.0.0 (2026-03-11)

- Architecture upgraded to Team-First default parallel execution
- Added data authenticity audit expert and front-loaded gate
- Added industry researcher and event hunter experts
- Introduced sentiment noise reduction governance and score impact capping
- Enhanced complex instruction automatic activation and continuity guard
- Tests expanded to 40 items all passed

### v1.1.0 (2025-03-11)

- Added short-term indicator enhancement (VWAP deviation/ATR stop-loss/volume ratio)
- Introduced calibration scoring mechanism and missing downgrade rules

---

## Disclaimer

> All analysis is for reference only and does not constitute investment advice. Stock market involves risks, invest cautiously.
