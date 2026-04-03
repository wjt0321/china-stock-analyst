import json
import sys
from pathlib import Path

from report_quality_gate import run_quality_gate

RULE_REPAIR_GUIDANCE = {
    "missing_file": "确认报告文件路径是否正确，必要时重新生成报告文件。",
    "missing_candidate_table": "为股票池报告补充可解析的候选表区块，至少包含代码、名称、收盘价、今日涨跌。",
    "missing_recommendation_blocks": "补充可解析的推荐段，建议使用“名称(代码)”标题并包含价格与标签字段。",
    "missing_timestamp_anchor": "在推荐段补充“更新时间”或“数据时间”，避免价格时点不明。",
    "unconfirmed_change_with_fixed_close_price": "当候选表涨跌为待确认时，不要在推荐段写确定收盘价，或先补全确认数据。",
    "recommendation_price_drift": "统一推荐段与候选表的价格口径，确保两处价格来自同一时间锚点。",
    "stop_loss_above_current_price": "修正止损位逻辑，确保止损价低于当前价格。",
    "score_label_inconsistent": "统一综合评分与标签映射规则，避免高分回避或低分可做。",
    "high_risk_with_doable_label": "当风险等级偏高时，下调推荐标签或补充明确风险约束。",
}


def _collect_report_paths(args: list) -> list:
    if args:
        return [Path(item) for item in args]
    base = Path(__file__).resolve().parent.parent / "stock-reports"
    return sorted(base.glob("*.md"))


def _summarize_results(results: list) -> tuple[dict, dict]:
    rule_summary = {}
    severity_summary = {}
    for result in results:
        report_path = str(result.get("report_path", ""))
        for issue in result.get("issues", []):
            rule = str(issue.get("rule", "unknown"))
            severity = str(issue.get("severity", "unknown"))
            severity_summary[severity] = severity_summary.get(severity, 0) + 1
            bucket = rule_summary.setdefault(
                rule,
                {
                    "count": 0,
                    "severity": severity,
                    "reports": [],
                    "sample_message": str(issue.get("message", "")),
                },
            )
            bucket["count"] += 1
            if report_path and report_path not in bucket["reports"]:
                bucket["reports"].append(report_path)
            if bucket.get("severity") != "high" and severity == "high":
                bucket["severity"] = "high"
            elif bucket.get("severity") not in {"high", "medium"} and severity == "medium":
                bucket["severity"] = "medium"
    return rule_summary, severity_summary


def _build_repair_suggestions(rule_summary: dict) -> list:
    suggestions = []
    sorted_items = sorted(
        rule_summary.items(),
        key=lambda item: (-int(item[1].get("count", 0)), str(item[0])),
    )
    for rule, meta in sorted_items:
        suggestions.append(
            {
                "rule": rule,
                "severity": meta.get("severity", "unknown"),
                "count": meta.get("count", 0),
                "advice": RULE_REPAIR_GUIDANCE.get(rule, "按该规则的报错信息逐项修复，并补充对应回归测试。"),
            }
        )
    return suggestions


def build_quality_check_payload(results: list) -> dict:
    failed = [item for item in results if not item.get("passed", False)]
    rule_summary, severity_summary = _summarize_results(results)
    return {
        "total_reports": len(results),
        "failed_reports": len(failed),
        "passed": len(failed) == 0,
        "severity_summary": severity_summary,
        "rule_summary": rule_summary,
        "repair_suggestions": _build_repair_suggestions(rule_summary),
        "results": results,
    }


def render_repair_checklist_markdown(payload: dict) -> str:
    lines = [
        "# 报告质量修复清单",
        "",
        f"- 报告总数：{payload.get('total_reports', 0)}",
        f"- 未通过数：{payload.get('failed_reports', 0)}",
        f"- 总体结果：{'通过' if payload.get('passed') else '未通过'}",
        "",
        "## 规则聚合摘要",
        "",
        "| 规则 | 严重级别 | 次数 |",
        "|------|----------|------|",
    ]
    for rule, meta in sorted(payload.get("rule_summary", {}).items(), key=lambda item: (-int(item[1].get("count", 0)), str(item[0]))):
        lines.append(f"| {rule} | {meta.get('severity', 'unknown')} | {meta.get('count', 0)} |")
    lines.extend(["", "## 修复建议", ""])
    for item in payload.get("repair_suggestions", []):
        lines.append(f"- [{item.get('severity', 'unknown')}] {item.get('rule')}: {item.get('advice')}")
    lines.extend(["", "## 报告明细", ""])
    for result in payload.get("results", []):
        report_name = Path(str(result.get("report_path", ""))).name or str(result.get("report_path", ""))
        lines.append(f"### {report_name}")
        lines.append("")
        lines.append(f"- 问题数：{result.get('issue_count', 0)}")
        if result.get("passed"):
            lines.append("- 状态：通过")
        else:
            lines.append("- 状态：未通过")
            for issue in result.get("issues", []):
                lines.append(
                    f"- [{issue.get('severity', 'unknown')}] {issue.get('rule', 'unknown')}: {issue.get('message', '')}"
                )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def run_quality_checks(targets: list[Path]) -> dict:
    all_results = []
    for target in targets:
        if not target.exists():
            all_results.append(
                {
                    "report_path": str(target),
                    "issue_count": 1,
                    "issues": [{"severity": "high", "rule": "missing_file", "message": "报告文件不存在"}],
                    "passed": False,
                }
            )
            continue
        all_results.append(run_quality_gate(str(target)))
    return build_quality_check_payload(all_results)


def main():
    targets = _collect_report_paths(sys.argv[1:])
    if not targets:
        print("No report files found.")
        raise SystemExit(0)
    payload = run_quality_checks(targets)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0 if payload["passed"] else 2)


if __name__ == "__main__":
    main()
