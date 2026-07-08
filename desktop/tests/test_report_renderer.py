from desktop.report_renderer import ReportRenderer
from pathlib import Path
import tempfile


def test_render_markdown():
    renderer = ReportRenderer()
    report = {
        "stock_code": "600519",
        "verdict": "观察",
        "confidence": "中",
        "scoring": {"total": 55, "short_term": 55, "fundamental": 55, "risk": 55},
    }
    md = renderer.render(report)
    assert "600519" in md
    assert "观察" in md
    assert "中" in md
    assert "55" in md
    assert "免责声明" in md or "重要提醒" in md
    assert "# 600519(600519) 短线营收双轨分析报告" in md


def test_render_with_expert_outputs_and_reasoning():
    renderer = ReportRenderer()
    report = {
        "stock_code": "000001",
        "verdict": "买入",
        "confidence": "高",
        "scoring": {"total": 85, "short_term": 85, "fundamental": 85, "risk": 85},
        "expert_outputs": {
            "fundamental": {
                "view": "估值合理",
                "decision_hint": "逢低吸纳",
                "evidences": ["PE低于行业均值", "ROE连续增长"],
                "indicators": {"pe_ttm": 8.5, "pb": 1.2, "market_cap": 5000},
            },
            "technical": {
                "view": "突破均线",
                "decision_hint": "关注回调",
                "evidences": ["站上20日均线"],
                "indicators": {"current_close": 10.5, "rsi": 55},
            },
            "quant_flow": {
                "view": "中性",
                "decision_hint": "观察",
                "evidences": [],
                "indicators": {},
            },
            "risk": {
                "view": "可控",
                "decision_hint": "观察",
                "evidences": [],
                "indicators": {},
            },
            "macro": {
                "view": "中性",
                "decision_hint": "观察",
                "evidences": [],
                "indicators": {},
            },
            "industry": {
                "view": "数据不足",
                "decision_hint": "观察",
                "evidences": ["行业分类数据源暂不可用"],
            },
            "event": {
                "view": "中性",
                "decision_hint": "观察",
                "evidences": [],
                "indicators": {},
            },
        },
        "supervisor_review": {"consensus": "观察", "conflict_items": [], "summary": "1/0/6"},
        "expert_identity_gate": {"passed": True, "require_block": False, "notes": []},
        "reasoning": ["基本面稳健", "技术形态向好"],
    }
    md = renderer.render(report, stock_name="平安银行")
    assert "000001" in md
    assert "平安银行" in md
    assert "基本面大师" in md
    assert "PE低于行业均值" in md
    assert "技术分析派" in md
    assert "突破均线" in md
    assert "推理过程" in md
    assert "基本面稳健" in md


def test_render_missing_optional_fields():
    renderer = ReportRenderer()
    report = {
        "stock_code": "600519",
        "verdict": "观察",
        "confidence": "中",
    }
    md = renderer.render(report)
    assert "600519" in md
    assert "观察" in md
    assert "综合评分" in md
    assert "风险提示" in md


def test_save_to_file():
    renderer = ReportRenderer()
    md = "# test report"
    with tempfile.TemporaryDirectory() as tmp:
        path = renderer.save_to_file(md, "600519", Path(tmp))
        assert path.exists()
        assert path.read_text(encoding="utf-8") == md
