import json
import sys
from pathlib import Path

from report_quality_gate import run_quality_gate


def _collect_report_paths(args: list) -> list:
    if args:
        return [Path(item) for item in args]
    base = Path(__file__).resolve().parent.parent / "stock-reports"
    return sorted(base.glob("*.md"))


def main():
    targets = _collect_report_paths(sys.argv[1:])
    if not targets:
        print("No report files found.")
        raise SystemExit(0)
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
    failed = [item for item in all_results if not item.get("passed", False)]
    payload = {
        "total_reports": len(all_results),
        "failed_reports": len(failed),
        "passed": len(failed) == 0,
        "results": all_results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0 if payload["passed"] else 2)


if __name__ == "__main__":
    main()
