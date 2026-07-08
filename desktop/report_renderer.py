from datetime import datetime
from pathlib import Path
from typing import Any


class ReportRenderer:
    """Render analysis reports in the Obsidian-compatible template style."""

    def render(self, report: dict, stock_name: str = "") -> str:
        """Render a single-stock or multi-stock report.

        Args:
            report: The analysis report dict returned by AnalysisEngine.
            stock_name: Optional stock name (e.g. from Tencent quote).
        """
        stock_code = report.get("stock_code", "")
        date_str = datetime.now().strftime("%Y年%m月%d日")
        date_iso = datetime.now().strftime("%Y-%m-%d")
        verdict = report.get("verdict", "观察")
        confidence = report.get("confidence", "中")
        scoring = report.get("scoring", {})
        expert_outputs = report.get("expert_outputs", {})
        supervisor = report.get("supervisor_review", {})
        reasoning = report.get("reasoning", [])
        identity_gate = report.get("expert_identity_gate", {})

        lines: list[str] = []

        # YAML frontmatter
        lines.append("---")
        lines.append(f"title: {stock_name or stock_code}({stock_code}) 短线营收双轨分析报告")
        lines.append(f"date: {date_iso}")
        lines.append(f"tags: [A股, {stock_code}, 多维分析]")
        lines.append("---")
        lines.append("")

        # Header
        lines.append(f"# {stock_name or stock_code}({stock_code}) 短线营收双轨分析报告")
        lines.append("")
        lines.append("> [!NOTE]"
        )
        lines.append(f"> **分析日期**: {date_str}")
        lines.append(f"> **股票代码**: {stock_code}")
        if stock_name:
            lines.append(f"> **股票名称**: {stock_name}")
        lines.append(f"> **双轨结论**: {verdict}")
        lines.append(f"> **综合评分**: {scoring.get('total', 'N/A')} / 100")
        lines.append(f"> **置信度**: {confidence}")
        lines.append("")

        # Candidate pool (single row for single-stock mode)
        lines.append("## 候选股票池")
        lines.append("")
        lines.append("| 股票代码 | 股票名称 | 当前股价 | 最终标签 | 综合评分 |")
        lines.append("|----------|----------|----------|----------|----------|")
        lines.append(f"| {stock_code} | {stock_name or '-'} | 见基本面 | {verdict} | {scoring.get('total', 'N/A')} |")
        lines.append("")

        # Expert analyses
        lines.append("## 一、各专家独立分析")
        lines.append("")
        lines.append("> [!TIP]")
        lines.append("> 以下为各专家基于最新数据的独立分析观点")
        lines.append("")

        fundamental = expert_outputs.get("fundamental", {})
        technical = expert_outputs.get("technical", {})
        quant = expert_outputs.get("quant_flow", {})
        risk = expert_outputs.get("risk", {})
        macro = expert_outputs.get("macro", {})
        industry = expert_outputs.get("industry", {})
        event = expert_outputs.get("event", {})

        # Fundamental
        lines.append("### 1. 📊 基本面大师")
        lines.append("")
        lines.append("> 20年价值投资经验，擅长财务分析和估值")
        lines.append("")
        lines.append("| 指标 | 数据 |")
        lines.append("|------|------|")
        fund_ind = fundamental.get("indicators", {})
        tech_ind = technical.get("indicators", {})
        price = tech_ind.get("current_close")
        lines.append(f"| 最新价 | {self._fmt(price)} 元 |")
        lines.append(f"| 总市值 | 约 {self._fmt(fund_ind.get('market_cap'))} 亿元 |")
        lines.append(f"| 市盈率(TTM) | {self._fmt(fund_ind.get('pe_ttm'))} 倍 |")
        lines.append(f"| 市净率 | {self._fmt(fund_ind.get('pb'))} 倍 |")
        lines.append("")
        lines.append("**估值判断:**")
        for ev in fundamental.get("evidences", []):
            lines.append(f"- {ev}")
        lines.append("")
        lines.append(f"**投资观点:**")
        lines.append(f"> [!{self._callout_for_hint(fundamental.get('decision_hint'))}]")
        lines.append(f"> 观点：{fundamental.get('view', '中性')}，建议：{fundamental.get('decision_hint', '观察')}")
        lines.append("")

        # Technical
        lines.append("### 2. 📈 技术分析派")
        lines.append("")
        lines.append("> 15年短线交易经验，精通K线形态和技术指标")
        lines.append("")
        lines.append("**技术信号:**")
        for ev in technical.get("evidences", []):
            lines.append(f"- {ev}")
        lines.append("")
        lines.append("**交易建议:**")
        lines.append(f"> [!{self._callout_for_hint(technical.get('decision_hint'))}]")
        lines.append(f"> 观点：{technical.get('view', '震荡')}，建议：{technical.get('decision_hint', '观察')}")
        lines.append("")

        # Quant flow
        quant = expert_outputs.get("quant_flow", {})
        lines.append("### 3. 🔢 量化模型师")
        lines.append("")
        lines.append("> 机器学习/统计套利背景，数据驱动分析")
        lines.append("")
        lines.append("**资金流向估算:**")
        for ev in quant.get("evidences", []):
            lines.append(f"- {ev}")
        lines.append("")
        lines.append("**模型观点:**")
        lines.append(f"> [!{self._callout_for_hint(quant.get('decision_hint'))}]")
        lines.append(f"> 观点：{quant.get('view', '中性')}，建议：{quant.get('decision_hint', '观察')}")
        lines.append("")

        # Risk
        risk = expert_outputs.get("risk", {})
        lines.append("### 4. 🛡️ 风险控制官")
        lines.append("")
        lines.append("> 18年风控经验，擅长风险评估和仓位管理")
        lines.append("")
        lines.append("**风控指标:**")
        for ev in risk.get("evidences", []):
            lines.append(f"- {ev}")
        lines.append("")
        lines.append("**风控建议:**")
        lines.append(f"> [!{self._callout_for_hint(risk.get('decision_hint'))}]")
        lines.append(f"> 观点：{risk.get('view', '可控')}，建议：{risk.get('decision_hint', '观察')}")
        lines.append("")

        # Macro
        macro = expert_outputs.get("macro", {})
        lines.append("### 5. 🌍 宏观策略师")
        lines.append("")
        lines.append("> 全球宏观对冲基金背景，擅长政策分析和周期判断")
        lines.append("")
        lines.append("**宏观环境:**")
        for ev in macro.get("evidences", []):
            lines.append(f"- {ev}")
        lines.append("")
        lines.append("**策略观点:**")
        lines.append(f"> [!{self._callout_for_hint(macro.get('decision_hint'))}]")
        lines.append(f"> 观点：{macro.get('view', '中性')}，建议：{macro.get('decision_hint', '观察')}")
        lines.append("")

        # Industry
        industry = expert_outputs.get("industry", {})
        lines.append("### 6. 🏭 行业研究家")
        lines.append("")
        lines.append("> 产业研究背景，聚焦行业景气、竞争格局与产业链驱动")
        lines.append("")
        for ev in industry.get("evidences", []):
            lines.append(f"- {ev}")
        lines.append("")

        # Event
        event = expert_outputs.get("event", {})
        lines.append("### 7. 📰 消息面猎手")
        lines.append("")
        lines.append("> 事件驱动交易背景，覆盖公告、政策、监管、突发事件冲击")
        lines.append("")
        event_ind = event.get("indicators", {})
        headlines = event_ind.get("headlines", [])
        if headlines:
            lines.append("**近期新闻:**")
            for h in headlines[:5]:
                lines.append(f"- {h}")
            lines.append("")
        lines.append("**事件观点:**")
        lines.append(f"> [!{self._callout_for_hint(event.get('decision_hint'))}]")
        lines.append(f"> 观点：{event.get('view', '中性')}，建议：{event.get('decision_hint', '观察')}")
        lines.append("")

        # Expert discussion
        lines.append("## 二、专家讨论纪要")
        lines.append("")
        lines.append("> [!WARNING]")
        lines.append("> 以下为专家之间的关键分歧和讨论")
        lines.append("")
        lines.append("### 共识与分歧")
        lines.append("")
        lines.append("| 维度 | 建议 | 观点 |")
        lines.append("|------|------|------|")
        for expert, output in expert_outputs.items():
            lines.append(
                f"| {self._expert_cn(expert)} | {output.get('decision_hint', '观察')} | {output.get('view', '中性')} |"
            )
        lines.append("")
        conflict_items = supervisor.get("conflict_items", [])
        if conflict_items:
            lines.append("### 分歧说明")
            for item in conflict_items:
                lines.append(f"- {item}")
            lines.append("")

        # Comprehensive conclusion
        lines.append("## 三、综合结论")
        lines.append("")
        lines.append("> [!SUMMARY]")
        lines.append("")
        lines.append("### 核心判断")
        lines.append("")
        lines.append("| 项目 | 判断 | 权重 |")
        lines.append("|------|------|------|")
        lines.append(f"| 短线动量分 | {scoring.get('short_term', 'N/A')} | 40% |")
        lines.append(f"| 营收质量分 | {scoring.get('fundamental', 'N/A')} | 35% |")
        lines.append(f"| 风险约束分 | {scoring.get('risk', 'N/A')} | 25% |")
        lines.append(f"| 最终标签 | {verdict} | - |")
        lines.append("")

        lines.append("### 主管裁决")
        lines.append("")
        lines.append("| 检查项 | 结论 |")
        lines.append("|------|------|")
        lines.append(f"| 身份校验 | {'通过' if identity_gate.get('passed') else '未通过'} |")
        lines.append(f"| 督导共识 | {supervisor.get('consensus', '观察')} |")
        lines.append(f"| 专家投票 | {supervisor.get('summary', '')} |")
        lines.append("")

        lines.append("### 操作建议")
        lines.append("")
        lines.append("| 操作 | 建议 | 优先级 |")
        lines.append("|------|------|--------|")
        position_pct = self._suggest_position(verdict, risk)
        stop_loss = risk.get("indicators", {}).get("stop_loss")
        lines.append(f"| 仓位 | 不超过 {position_pct}% | 🟢 必须 |")
        lines.append(f"| 买入 | {'逢低布局' if verdict == '可做' else '观望'} | 🟡 推荐 |")
        lines.append(f"| 止损 | {stop_loss if stop_loss else '待确认'} 元 | 🟢 必须 |")
        lines.append(f"| 持有 | {'可持有' if verdict in ('可做', '观察') else '减仓'} | 🟡 推荐 |")
        lines.append("")

        if reasoning:
            lines.append("### 推理过程")
            for reason in reasoning:
                lines.append(f"- {reason}")
            lines.append("")

        # Risk warnings
        lines.append("## 风险提示")
        lines.append("")
        lines.append("> [!CAUTION]")
        lines.append("")
        lines.append("⚠️ **重要提醒**")
        lines.append("")
        lines.append("- 本报告基于公开行情数据与规则化算法生成，仅供参考")
        lines.append("- 资金流向为K线估算值，非交易所真实资金流")
        lines.append("- 行业与部分财务数据暂不可用，结论存在信息缺口")
        lines.append("- 股市有风险，投资需谨慎")
        lines.append("- **本报告不构成投资建议**")
        lines.append("")

        lines.append("---")
        lines.append("")
        lines.append(f"*报告生成时间: {date_str}*")
        lines.append("*分析团队: 量化交易多维专家团队*")
        lines.append("*格式: Obsidian Markdown*")

        return "\n".join(lines)

    def _fmt(self, value: Any) -> str:
        if value is None:
            return "-"
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    def _callout_for_hint(self, hint: str | None) -> str:
        if hint == "可做":
            return "SUCCESS"
        if hint == "回避":
            return "WARNING"
        return "INFO"

    def _expert_cn(self, name: str) -> str:
        mapping = {
            "fundamental": "基本面大师",
            "technical": "技术分析派",
            "quant_flow": "量化模型师",
            "risk": "风险控制官",
            "macro": "宏观策略师",
            "industry": "行业研究家",
            "event": "消息面猎手",
        }
        return mapping.get(name, name)

    def _suggest_position(self, verdict: str, risk: dict) -> int:
        risk_hint = risk.get("decision_hint", "观察")
        if verdict == "回避" or risk_hint == "回避":
            return 0
        if verdict == "可做":
            return 10 if risk_hint == "可做" else 5
        return 3

    def save_to_file(self, report_md: str, stock_code: str, output_dir: Path) -> Path:
        """Save the rendered report to the stock-reports directory."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{stock_code}_{datetime.now().strftime('%Y%m%d')}.md"
        path = output_dir / filename
        path.write_text(report_md, encoding="utf-8")
        return path
