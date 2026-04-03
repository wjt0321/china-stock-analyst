import json
import re
import sys
from pathlib import Path

# 候选股票数据表章节标题模式，支持「10只」「10 只」等变体，便于模板调整
CANDIDATE_TABLE_SECTION_PATTERNS = [
    r"^##\s*八、[^\n]*候选股票完整数据[^\n]*\n(?P<section>.*?)(?=\n## |\n---|\Z)",
    r"^##\s*八、[^\n]*候选[^\n]*完整数据[^\n]*\n(?P<section>.*?)(?=\n## |\n---|\Z)",
    r"^##\s*八、[^\n]*候选股票[^\n]*数据[^\n]*\n(?P<section>.*?)(?=\n## |\n---|\Z)",
    r"^##\s*八、[^\n]*候选股[^\n]*数据[^\n]*\n(?P<section>.*?)(?=\n## |\n---|\Z)",
    r"^##\s*股票池总览\s*\n(?P<section>.*?)(?=\n## |\n---|\Z)",
]


def _extract_number(text: str):
    matched = re.search(r"\d+(?:\.\d+)?", str(text or ""))
    if not matched:
        return None
    try:
        return float(matched.group(0))
    except Exception:
        return None


def _extract_field_text(body: str, field_names: list[str]) -> str:
    for field_name in field_names:
        table_match = re.search(
            rf"\|\s*\*?\*?{re.escape(field_name)}\*?\*?\s*\|\s*(?P<value>[^|\n]+?)\s*\|",
            body,
        )
        if table_match:
            return table_match.group("value").strip()
        inline_match = re.search(
            rf"\*?\*?{re.escape(field_name)}\*?\*?\s*[：:]\s*(?P<value>[^\n]+)",
            body,
        )
        if inline_match:
            return inline_match.group("value").strip()
    return ""


def _extract_recommendation_blocks(content: str) -> list:
    pattern = re.compile(r"^#{1,3}\s+.*?[（(](?P<code>\d{6})[）)](?P<body>.*?)(?=\n#{1,3}\s|\n---|\Z)", re.S | re.M)
    blocks = []
    for matched in pattern.finditer(content):
        code = matched.group("code")
        body = matched.group("body")
        price_text = _extract_field_text(body, ["收盘价", "当前股价", "最新价"])
        score_text = _extract_field_text(body, ["综合评分", "加权总分", "短线校准后总分"])
        label_text = _extract_field_text(body, ["最终标签", "推荐标签", "结论标签", "标签"])
        stop_loss_text = _extract_field_text(body, ["止损位", "止损"])
        risk_level_text = _extract_field_text(body, ["风险等级", "风险评估", "风险级别"])
        price_match = price_text
        if not price_match:
            continue
        blocks.append(
            {
                "stock_code": code,
                "price_text": price_text,
                "score_text": score_text,
                "label_text": label_text,
                "stop_loss_text": stop_loss_text,
                "risk_level_text": risk_level_text,
                "body": body,
            }
        )
    return blocks


def _has_machine_readable_verdict(content: str) -> bool:
    return "<!-- VERDICT:" in content or "<!-- POOL_VERDICT:" in content


def _extract_candidate_table(content: str) -> dict:
    for pattern in CANDIDATE_TABLE_SECTION_PATTERNS:
        section_match = re.search(pattern, content, re.S | re.M)
        if section_match:
            break
    if not section_match:
        return {}
    section = section_match.group("section")
    rows = {}
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if len(parts) < 4:
            continue
        code = parts[0]
        if not re.fullmatch(r"\d{6}", code):
            continue
        close_price_text = parts[2] if len(parts) >= 5 else ""
        change_text = parts[3] if len(parts) >= 5 else ""
        rows[code] = {
            "name": parts[1],
            "close_price_text": close_price_text,
            "change_text": change_text,
        }
    return rows


def run_quality_gate(report_path: str) -> dict:
    content = Path(report_path).read_text(encoding="utf-8")
    recommendations = _extract_recommendation_blocks(content)
    candidate_rows = _extract_candidate_table(content)
    has_machine_verdict = _has_machine_readable_verdict(content)
    issues = []
    if not recommendations and not has_machine_verdict:
        issues.append(
            {
                "stock_code": "",
                "severity": "high",
                "rule": "missing_recommendation_blocks",
                "message": "未识别到可校验的推荐段，质量门禁无法执行核心比对。",
            }
        )
    requires_candidate_table = len(recommendations) > 1 or "股票池" in content
    if recommendations and not candidate_rows and requires_candidate_table:
        issues.append(
            {
                "stock_code": "",
                "severity": "high",
                "rule": "missing_candidate_table",
                "message": "未识别到候选表数据区块，无法校验推荐段与候选表一致性。",
            }
        )
    for item in recommendations:
        code = item["stock_code"]
        rec_price_text = item["price_text"]
        rec_price = _extract_number(rec_price_text)
        candidate = candidate_rows.get(code, {})
        candidate_price_text = candidate.get("close_price_text", "")
        candidate_price = _extract_number(candidate_price_text)
        change_text = candidate.get("change_text", "")
        score_text = item.get("score_text", "")
        score_value = _extract_number(score_text)
        label_text = item.get("label_text", "")
        stop_loss_text = item.get("stop_loss_text", "")
        stop_loss_value = _extract_number(stop_loss_text)
        risk_level_text = item.get("risk_level_text", "")

        if rec_price is not None and "待确认" in change_text:
            issues.append(
                {
                    "stock_code": code,
                    "severity": "high",
                    "rule": "unconfirmed_change_with_fixed_close_price",
                    "message": "候选表中“今日涨跌”为待确认，但推荐段写入了确定收盘价。",
                    "recommendation_price": rec_price_text,
                    "candidate_change": change_text,
                }
            )
        if rec_price is not None and candidate_price is not None and candidate_price > 0:
            drift = abs(rec_price - candidate_price) / candidate_price
            if drift > 0.02:
                issues.append(
                    {
                        "stock_code": code,
                        "severity": "high",
                        "rule": "recommendation_price_drift",
                        "message": "推荐段收盘价与候选表收盘价偏差超过2%。",
                        "recommendation_price": rec_price_text,
                        "candidate_price": candidate_price_text,
                        "drift_ratio": round(drift, 4),
                    }
                )
        if rec_price is not None and stop_loss_value is not None and stop_loss_value >= rec_price:
            issues.append(
                {
                    "stock_code": code,
                    "severity": "high",
                    "rule": "stop_loss_above_current_price",
                    "message": "推荐段止损位高于或等于当前价格，止损逻辑异常。",
                    "recommendation_price": rec_price_text,
                    "stop_loss_price": stop_loss_text,
                }
            )
        if score_value is not None and label_text:
            if score_value >= 70 and "回避" in label_text:
                issues.append(
                    {
                        "stock_code": code,
                        "severity": "medium",
                        "rule": "score_label_inconsistent",
                        "message": "综合评分较高，但推荐标签为回避，存在评分与标签不一致。",
                        "score": score_text,
                        "label": label_text,
                    }
                )
            if score_value <= 50 and "可做" in label_text:
                issues.append(
                    {
                        "stock_code": code,
                        "severity": "medium",
                        "rule": "score_label_inconsistent",
                        "message": "综合评分较低，但推荐标签为可做，存在评分与标签不一致。",
                        "score": score_text,
                        "label": label_text,
                    }
                )
        if "高" in risk_level_text and "可做" in label_text:
            issues.append(
                {
                    "stock_code": code,
                    "severity": "high",
                    "rule": "high_risk_with_doable_label",
                    "message": "风险等级偏高，但推荐标签仍为可做，存在风险与建议冲突。",
                    "risk_level": risk_level_text,
                    "label": label_text,
                }
            )
        if "更新时间" not in item["body"] and "数据时间" not in item["body"]:
            issues.append(
                {
                    "stock_code": code,
                    "severity": "medium",
                    "rule": "missing_timestamp_anchor",
                    "message": "推荐段缺少价格时间锚点（更新时间/数据时间）。",
                }
            )
    return {
        "report_path": str(report_path),
        "issue_count": len(issues),
        "issues": issues,
        "passed": len(issues) == 0,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/report_quality_gate.py <report_path>")
        raise SystemExit(1)
    result = run_quality_gate(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("passed") else 2)


if __name__ == "__main__":
    main()
