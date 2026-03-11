import re
import sys
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_report as gr  # noqa: E402
from generate_report import parse_search_results_to_report, _generate_advice  # noqa: E402
from stock_utils import get_search_queries  # noqa: E402
from team_router import should_use_agent_team, build_skill_chain_plan  # noqa: E402


class TestStockSkill(unittest.TestCase):
    def test_runtime_should_expose_analysis_route_planner(self):
        self.assertTrue(callable(getattr(gr, "plan_analysis_route", None)))

    def test_runtime_should_choose_team_mode_for_complex_request(self):
        route = gr.plan_analysis_route("请对比中国能建和首开股份并验证上周报告")
        self.assertEqual(route["mode"], "agent_team")
        self.assertIn("supervisor_review", route["steps"])

    def test_runtime_should_choose_single_mode_for_simple_request(self):
        route = gr.plan_analysis_route("分析 600519")
        self.assertEqual(route["mode"], "single_flow")

    def test_should_enable_agent_team_for_multi_stock_request(self):
        decision = should_use_agent_team("请分析中国能建和首开股份，给我短线建议")
        self.assertTrue(decision["use_team"])
        self.assertIn("多标的", decision["reasons"])

    def test_should_enable_agent_team_for_validation_request(self):
        decision = should_use_agent_team("请验证上周报告和今天数据是否反转")
        self.assertTrue(decision["use_team"])
        self.assertIn("验证", decision["reasons"])

    def test_should_keep_single_flow_for_simple_request(self):
        decision = should_use_agent_team("分析 600519")
        self.assertFalse(decision["use_team"])

    def test_should_build_fixed_skill_chain_for_team_mode(self):
        plan = build_skill_chain_plan(use_team=True)
        self.assertEqual(plan["mode"], "agent_team")
        self.assertEqual(plan["steps"][0], "collect_data")
        self.assertIn("supervisor_review", plan["steps"])

    def test_should_have_obsidian_markdown_formatter(self):
        self.assertTrue(callable(getattr(gr, "format_obsidian_markdown_report", None)))

    def test_single_stock_mode_should_generate_single_title(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "000767",
                    "stock_name": "晋控电力",
                    "label": "可做",
                    "invalid_condition": "跌破3.50元止损位",
                    "price": "3.87",
                    "scores": {"momentum": 85, "revenue": 80, "risk": 70},
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("000767_晋控电力", content)
        self.assertNotIn("股票池", content)

    def test_stock_pool_mode_should_generate_pool_title(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {"stock_code": "000767", "stock_name": "晋控电力", "label": "可做", "scores": {}},
                {"stock_code": "000966", "stock_name": "长源电力", "label": "观察", "scores": {}},
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("股票池", content)
        self.assertIn("晋控电力", content)
        self.assertIn("长源电力", content)

    def test_should_trigger_reversal_warning_when_5d_inflow_but_latest_outflow(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "000767",
                    "stock_name": "晋控电力",
                    "label": "观察",
                    "scores": {},
                    "fund_flow": {"latest_main": "-4079.00", "five_day_main": "35500.00"},
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("资金流向反转预警", content)
        self.assertIn("方向反转", content)

    def test_should_show_weight_formula_and_rounded_total(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "601868",
                    "stock_name": "中国能建",
                    "label": "可做",
                    "scores": {"momentum": 85, "revenue": 75, "risk": 70},
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("加权总分计算", content)
        self.assertIn("77.8", content)

    def test_should_downgrade_confidence_when_revenue_fields_missing(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "601868",
                    "stock_name": "中国能建",
                    "label": "可做",
                    "scores": {"momentum": 85, "revenue": 75, "risk": 70},
                    "revenue_snapshot": {"revenue": "N/A", "yoy": "N/A", "qoq": "N/A"},
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("置信度：低", content)

    def test_should_render_evidence_chain_with_url_and_minute_timestamp(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "601868",
                    "stock_name": "中国能建",
                    "label": "可做",
                    "scores": {"momentum": 85, "revenue": 75, "risk": 70},
                    "evidences": [
                        {
                            "conclusion": "主力资金持续关注",
                            "value": "近5日净流入13.03亿元",
                            "source_url": "https://example.com/fund",
                            "timestamp": "2026-03-10 11:20",
                        }
                    ],
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("https://example.com/fund", content)
        self.assertIn("2026-03-10 11:20", content)

    def test_fund_flow_should_keep_direction_and_unify_unit(self):
        search_data = [
            {
                "title": "资金流向",
                "snippet": "主力资金净流出1.67亿元，散户资金净流入3200万元",
                "link": "http://example.com",
            }
        ]
        report = parse_search_results_to_report(search_data, "600000")
        self.assertEqual(report["fund_flow"]["main"], "-16700.00")
        self.assertEqual(report["fund_flow"]["retail"], "3200.00")

    def test_advice_should_identify_main_outflow(self):
        report = {"fund_flow": {"main": "-107.98"}, "price_info": {"change": "-1.2"}}
        advice = _generate_advice(report)
        self.assertIn("净流出", advice)

    def test_queries_should_use_dynamic_time_window(self):
        queries = get_search_queries("600684", "珠江股份")
        current_year = str(datetime.now().year)
        joined = " ".join(queries)
        self.assertIn(current_year, joined)
        self.assertNotIn("2025", joined)
        self.assertNotIn("2026年2月", joined)
        self.assertTrue(any("近5日" in q for q in queries))

    def test_financial_should_extract_revenue_fields(self):
        search_data = [
            {
                "title": "业绩快报",
                "snippet": "公司2025年三季度营业收入123.4亿元，同比增长12.5%，环比增长3.2%",
                "link": "http://example.com",
            }
        ]
        report = parse_search_results_to_report(search_data, "600000")
        financial = report["financial"]
        self.assertEqual(financial.get("revenue"), "123.40")
        self.assertEqual(financial.get("revenue_unit"), "亿元")
        self.assertEqual(financial.get("yoy"), "12.50")
        self.assertEqual(financial.get("qoq"), "3.20")
        self.assertTrue(re.match(r"\d{4}-\d{2}-\d{2}", financial.get("as_of", "")))


if __name__ == "__main__":
    unittest.main()
