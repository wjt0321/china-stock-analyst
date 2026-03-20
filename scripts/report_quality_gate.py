import json
import re
import sys
from pathlib import Path

# 候选股票数据表章节标题模式，支持「10只」「10 只」等变体，便于模板调整
CANDIDATE_TABLE_SECTION_PATTERNS = [
    r"## 八、\d*\s*只?候选股票完整数据(?P<section>.*?)(?=\n---|\Z)",
    r"## 八、.*候选.*完整数据(?P<section>.*?)(?=\n---|\Z)",
]


def _extract_number(text: str):
    matched = re.search(r"\d+(?:\.\d+)?", str(text or ""))
    if not matched:
        return None
    try:
        return float(matched.group(0))
    except Exception:
        return None


def _extract_recommendation_blocks(content: str) -> list:
    pattern = re.compile(r"### .*?（(?P<code>\d{6})）(?P<body>.*?)(?=\n### |\n---|\Z)", re.S)
    blocks = []
    for matched in pattern.finditer(content):
        code = matched.group("code")
        body = matched.group("body")
        price_match = re.search(r"\|\s*\*\*收盘价\*\*\s*\|\s*(?P<price>[^|]+?)\s*\|", body)
        if not price_match:
            continue
        blocks.append(
            {
                "stock_code": code,
                "price_text": price_match.group("price").strip(),
                "body": body,
            }
        )
    return blocks


def _extract_candidate_table(content: str) -> dict:
    for pattern in CANDIDATE_TABLE_SECTION_PATTERNS:
        section_match = re.search(pattern, content, re.S)
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
        if len(parts) < 5:
            continue
        code = parts[0]
        if not re.fullmatch(r"\d{6}", code):
            continue
        rows[code] = {
            "name": parts[1],
            "close_price_text": parts[2],
            "change_text": parts[3],
        }
    return rows


def run_quality_gate(report_path: str) -> dict:
    content = Path(report_path).read_text(encoding="utf-8")
    recommendations = _extract_recommendation_blocks(content)
    candidate_rows = _extract_candidate_table(content)
    issues = []
    for item in recommendations:
        code = item["stock_code"]
        rec_price_text = item["price_text"]
        rec_price = _extract_number(rec_price_text)
        candidate = candidate_rows.get(code, {})
        candidate_price_text = candidate.get("close_price_text", "")
        candidate_price = _extract_number(candidate_price_text)
        change_text = candidate.get("change_text", "")

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
