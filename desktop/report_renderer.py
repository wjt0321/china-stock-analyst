from datetime import datetime


class ReportRenderer:
    def render(self, report: dict) -> str:
        lines = [
            f"# {report['stock_code']} 短线分析报告",
            "",
            f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **最终标签**: {report['verdict']}",
            f"- **置信度**: {report['confidence']}",
            f"- **综合评分**: {report.get('scoring', {}).get('total', 'N/A')}",
            "",
            "## 专家观点",
            "",
        ]
        for expert, output in report.get("expert_outputs", {}).items():
            lines.append(f"### {expert}")
            lines.append(f"- 观点: {output.get('view', 'N/A')}")
            lines.append(f"- 建议: {output.get('decision_hint', 'N/A')}")
            evidences = output.get("evidences", [])
            if evidences:
                lines.append("- 依据:")
                for ev in evidences:
                    lines.append(f"  - {ev}")
            lines.append("")

        lines.append("## 推理过程")
        for reason in report.get("reasoning", []):
            lines.append(f"- {reason}")
        lines.append("")
        lines.append("> 免责声明：所有分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。")
        return "\n".join(lines)
