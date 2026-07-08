from desktop.report_renderer import ReportRenderer


def test_render_markdown():
    renderer = ReportRenderer()
    report = {
        "stock_code": "600519",
        "verdict": "观察",
        "confidence": "中",
        "scoring": {"total": 55},
    }
    md = renderer.render(report)
    assert "600519" in md
    assert "观察" in md
    assert "中" in md
    assert "55" in md
    assert "免责声明" in md


def test_render_with_expert_outputs_and_reasoning():
    renderer = ReportRenderer()
    report = {
        "stock_code": "000001",
        "verdict": "买入",
        "confidence": "高",
        "scoring": {"total": 85},
        "expert_outputs": {
            "fundamental": {
                "view": "估值合理",
                "decision_hint": "逢低吸纳",
                "evidences": ["PE低于行业均值", "ROE连续增长"],
            },
            "technical": {
                "view": "突破均线",
                "decision_hint": "关注回调",
                "evidences": [],
            },
        },
        "reasoning": ["基本面稳健", "技术形态向好"],
    }
    md = renderer.render(report)
    assert "# 000001 短线分析报告" in md
    assert "### fundamental" in md
    assert "- 观点: 估值合理" in md
    assert "- 建议: 逢低吸纳" in md
    assert "  - PE低于行业均值" in md
    assert "### technical" in md
    assert "- 观点: 突破均线" in md
    assert "## 推理过程" in md
    assert "- 基本面稳健" in md


def test_render_missing_optional_fields():
    renderer = ReportRenderer()
    report = {
        "stock_code": "600519",
        "verdict": "观察",
        "confidence": "中",
    }
    md = renderer.render(report)
    assert "**综合评分**: N/A" in md
    assert "## 专家观点" in md
    assert "## 推理过程" in md
