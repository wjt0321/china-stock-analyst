import re
import sys
import tempfile
import unittest
import importlib
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_report as gr  # noqa: E402
import stock_utils as su  # noqa: E402
import team_router as tr  # noqa: E402
from generate_report import parse_search_results_to_report, _generate_advice  # noqa: E402
from stock_utils import get_search_queries, get_shortline_indicator_recommendations  # noqa: E402
from team_router import should_use_agent_team, build_skill_chain_plan  # noqa: E402


class TestStockSkill(unittest.TestCase):
    def _clear_team_router_runtime_state(self):
        for path in [getattr(tr, "_INTENT_CACHE_FILE", None), getattr(tr, "_INTENT_ROUTE_LOG_FILE", None)]:
            if path and path.exists():
                path.unlink()
        if hasattr(tr, "_INTENT_RUNTIME_FALLBACK"):
            tr._INTENT_RUNTIME_FALLBACK.clear()

    def _build_multi_source_core_data(self, timestamps):
        links = [
            "https://www.sse.com.cn/marketdata",
            "https://quote.eastmoney.com/600000.html",
            "https://www.yicai.com/news/stock",
        ]
        titles = ["交易所股价播报", "资金流向追踪", "财经快讯"]
        rows = []
        for idx, ts in enumerate(timestamps):
            rows.append(
                {
                    "title": titles[idx],
                    "snippet": f"最新价10.{idx}元，涨跌幅+1.{idx}%，成交额2.{idx}亿元，主力资金净流入1.{idx}亿元，散户资金净流出800万元，更新时间{ts}",
                    "link": links[idx],
                    "timestamp": ts,
                }
            )
        return rows

    def test_runtime_should_expose_analysis_route_planner(self):
        self.assertTrue(callable(getattr(gr, "plan_analysis_route", None)))

    def test_runtime_should_choose_team_mode_for_complex_request(self):
        route = gr.plan_analysis_route("请对比中国能建和首开股份并验证上周报告")
        self.assertEqual(route["mode"], "agent_team")
        self.assertIn("supervisor_review", route["steps"])
        self.assertIn("downgrade_policy", route["team_rules"])

    def test_runtime_should_choose_team_first_mode_for_simple_request(self):
        route = gr.plan_analysis_route("分析 600519")
        self.assertEqual(route["mode"], "agent_team")
        self.assertEqual(route["execution_profile"], "lite_parallel")

    def test_route_plan_should_keep_team_fixed_steps_even_in_lite_parallel(self):
        route = gr.plan_analysis_route("分析 600519")
        self.assertEqual(route["execution_profile"], "lite_parallel")
        self.assertIn("run_macro_expert", route["steps"])
        self.assertIn("run_industry_researcher_expert", route["steps"])
        self.assertIn("run_event_hunter_expert", route["steps"])
        self.assertIn("run_expert_identifier_agent", route["steps"])

    def test_should_enable_agent_team_for_multi_stock_request(self):
        decision = should_use_agent_team("请分析中国能建和首开股份，给我短线建议")
        self.assertTrue(decision["use_team"])
        self.assertIn("多标的", decision["reasons"])

    def test_should_enable_agent_team_for_validation_request(self):
        decision = should_use_agent_team("请验证上周报告和今天数据是否反转")
        self.assertTrue(decision["use_team"])
        self.assertIn("验证", decision["reasons"])

    def test_should_keep_team_first_for_simple_request(self):
        decision = should_use_agent_team("分析 600519")
        self.assertTrue(decision["use_team"])
        self.assertEqual(decision["execution_profile"], "lite_parallel")
        self.assertIn("eastmoney_router", decision)

    def test_eastmoney_router_should_classify_news_intent(self):
        self._clear_team_router_runtime_state()
        with mock.patch.object(
            tr,
            "_build_metadata_passthrough_meta",
            return_value={
                "provider": "eastmoney",
                "source_function": "stock_utils.eastmoney_query",
                "fetched_at": "2026-03-10 10:05:00",
                "validation_passed": True,
                "validation_conclusion": "标的元信息校验通过",
            },
        ):
            routed = tr.route_eastmoney_intent("请查600000最新公告与新闻舆情")
        self.assertEqual(routed.get("intent_category"), "news-search")
        self.assertTrue(routed.get("critical_gate", {}).get("passed"))
        self.assertTrue(routed.get("local_saved"))
        passthrough = routed.get("metadata_passthrough", {})
        self.assertEqual(passthrough.get("source_function"), "stock_utils.eastmoney_query")
        self.assertEqual(passthrough.get("fetched_at"), "2026-03-10 10:05:00")
        self.assertIn("校验通过", passthrough.get("validation_conclusion", ""))

    def test_eastmoney_router_should_block_query_without_target(self):
        self._clear_team_router_runtime_state()
        routed = tr.route_eastmoney_intent("帮我查行情和成交额")
        self.assertEqual(routed.get("intent_category"), "query")
        gate = routed.get("critical_gate", {})
        self.assertFalse(gate.get("passed"))
        self.assertTrue(gate.get("blocked_by_guardrail"))
        reasons = " ".join(gate.get("reasons", []))
        self.assertIn("缺少标的约束", reasons)
        self.assertIn("TARGET_REQUIRED", gate.get("reason_codes", []))
        self.assertTrue(any("股票代码" in tip or "股票名称" in tip for tip in gate.get("user_tips", [])))

    def test_eastmoney_router_should_block_when_limit_exceeds_threshold(self):
        self._clear_team_router_runtime_state()
        routed = tr.route_eastmoney_intent("请策略筛选120支低价股并按量价齐升排序")
        self.assertEqual(routed.get("intent_category"), "stock-screen")
        gate = routed.get("critical_gate", {})
        self.assertFalse(gate.get("passed"))
        self.assertTrue(gate.get("blocked_by_guardrail"))
        self.assertIn("返回数量超限", " ".join(gate.get("reasons", [])))
        self.assertIn("REQUEST_LIMIT_EXCEEDED", gate.get("reason_codes", []))

    def test_eastmoney_router_cache_should_trigger_duplicate_threshold(self):
        self._clear_team_router_runtime_state()
        request = "请查询600000行情成交额"
        results = [tr.route_eastmoney_intent(request) for _ in range(4)]
        latest = results[-1]
        cache = latest.get("cache", {})
        gate = latest.get("critical_gate", {})
        self.assertTrue(cache.get("cache_hit"))
        self.assertTrue(cache.get("duplicate_threshold_triggered"))
        self.assertFalse(gate.get("passed"))
        self.assertTrue(gate.get("blocked_by_guardrail"))
        self.assertIn("DUPLICATE_REQUEST", gate.get("reason_codes", []))

    def test_eastmoney_router_should_enter_fallback_mode_when_intent_not_matched(self):
        self._clear_team_router_runtime_state()
        routed = tr.route_eastmoney_intent("帮我看看最近市场有没有机会")
        gate = routed.get("critical_gate", {})
        self.assertEqual(routed.get("intent_category"), "none")
        self.assertTrue(routed.get("fallback_mode"))
        self.assertEqual(gate.get("fallback_action"), "use_local_analysis_only")
        self.assertIn("INTENT_NOT_MATCHED", gate.get("reason_codes", []))

    def test_eastmoney_router_should_keep_name_request_without_forcing_fallback(self):
        self._clear_team_router_runtime_state()
        routed = tr.route_eastmoney_intent("请查询浦发银行资金流向", stock_name="浦发银行")
        gate = routed.get("critical_gate", {})
        self.assertEqual(routed.get("intent_category"), "query")
        self.assertTrue(gate.get("passed"))
        self.assertFalse(routed.get("fallback_mode"))
        self.assertEqual(routed.get("metadata_passthrough", {}).get("symbol"), "")
        self.assertEqual(routed.get("metadata_passthrough", {}).get("symbol_resolved_via"), "name")

    def test_eastmoney_router_should_not_force_fallback_when_symbol_missing(self):
        self._clear_team_router_runtime_state()
        routed = tr.route_eastmoney_intent("请查询浦发银行资金流向", stock_name="浦发银行")
        gate = routed.get("critical_gate", {})
        self.assertEqual(routed.get("intent_category"), "query")
        self.assertTrue(gate.get("passed"))
        self.assertIn("SYMBOL_METADATA_UNAVAILABLE", gate.get("reason_codes", []))
        self.assertFalse(routed.get("fallback_mode"))

    def test_eastmoney_router_cache_should_reset_when_previous_cache_expired(self):
        self._clear_team_router_runtime_state()
        request = "请查询600000行情成交额"
        normalized = tr._normalize_request(request)
        cache_key = tr._build_intent_cache_key(normalized)
        expired_at = (datetime.now() - timedelta(seconds=tr.INTENT_CACHE_TTL_SECONDS + 5)).strftime("%Y-%m-%d %H:%M:%S")
        with mock.patch.object(tr, "_load_json_file", return_value={"items": {"legacy-key": {"updated_at": expired_at}}}), \
            mock.patch.object(tr, "_save_json_file", return_value=True):
            routed = tr.route_eastmoney_intent(request)
        cache = routed.get("cache", {})
        gate = routed.get("critical_gate", {})
        self.assertEqual(cache.get("key"), cache_key)
        self.assertFalse(cache.get("cache_hit"))
        self.assertEqual(cache.get("hit_count"), 1)
        self.assertFalse(cache.get("duplicate_threshold_triggered"))
        self.assertNotIn("DUPLICATE_REQUEST", gate.get("reason_codes", []))

    def test_should_auto_activate_full_parallel_for_today_collect_screen_discuss_recommend_request(self):
        request = "请今日采集市场数据，筛选10支，再组织专家讨论，最后推荐3支"
        decision = should_use_agent_team(request)
        self.assertTrue(decision["use_team"])
        self.assertEqual(decision["execution_profile"], "full_parallel")
        self.assertIn("高意图串联任务", decision["reasons"])
        self.assertIn("10支筛选", decision["reasons"])
        self.assertIn("3支推荐", decision["reasons"])

    def test_route_plan_should_keep_auditor_first_and_include_new_experts_for_complex_request(self):
        request = "请今日采集市场数据，筛选10支，再组织专家讨论，最后推荐3支"
        route = gr.plan_analysis_route(request)
        self.assertEqual(route["mode"], "agent_team")
        self.assertEqual(route["execution_profile"], "full_parallel")
        self.assertEqual(route["steps"][0], "run_data_auditor")
        self.assertIn("run_macro_expert", route["steps"])
        self.assertIn("run_industry_researcher_expert", route["steps"])
        self.assertIn("run_event_hunter_expert", route["steps"])
        self.assertIn("run_expert_identifier_agent", route["steps"])
        self.assertLess(route["steps"].index("run_data_auditor"), route["steps"].index("supervisor_review"))
        self.assertLess(route["steps"].index("run_expert_identifier_agent"), route["steps"].index("supervisor_review"))
        self.assertFalse(route["team_rules"].get("continuity_guard", {}).get("single_flow_fallback", True))

    def test_should_build_fixed_skill_chain_for_team_mode(self):
        plan = build_skill_chain_plan(use_team=True)
        self.assertEqual(plan["mode"], "agent_team")
        self.assertEqual(plan["steps"][0], "run_data_auditor")
        self.assertIn("run_industry_researcher_expert", plan["steps"])
        self.assertIn("run_event_hunter_expert", plan["steps"])
        self.assertIn("run_expert_identifier_agent", plan["steps"])
        self.assertIn("supervisor_review", plan["steps"])
        self.assertIn("expert_output_schema", plan["team_rules"])
        self.assertIn("conflict_arbitration_rules", plan["team_rules"])
        self.assertIn("run_expert_identifier_agent", plan["team_rules"].get("expert_output_schema", {}))

    def test_team_rules_should_include_continuity_guard_for_parallel_non_interrupt(self):
        plan = build_skill_chain_plan(use_team=True)
        continuity_guard = plan["team_rules"].get("continuity_guard", {})
        self.assertEqual(continuity_guard.get("parallel_strategy"), "strict_fanout_join")
        self.assertEqual(continuity_guard.get("failure_policy"), "isolate_and_continue")
        self.assertFalse(continuity_guard.get("single_flow_fallback", True))
        self.assertEqual(continuity_guard.get("retry_policy", {}).get("max_retries"), 2)

    def test_team_rules_should_expose_preconfigured_agent_registry(self):
        plan = build_skill_chain_plan(use_team=True)
        registry = plan["team_rules"].get("expert_agent_registry", {})
        self.assertIn("run_data_auditor", registry)
        self.assertIn("run_fundamental_expert", registry)
        self.assertIn("run_expert_identifier_agent", registry)
        self.assertIn(registry["run_data_auditor"].get("source"), ["preconfigured", "default"])

    def test_preconfigured_agent_should_fallback_when_mapping_file_missing(self):
        original = tr.PRECONFIGURED_EXPERT_AGENTS["run_data_auditor"]
        tr.PRECONFIGURED_EXPERT_AGENTS["run_data_auditor"] = "agent-file-not-exist-for-test"
        try:
            registry = tr.resolve_preconfigured_expert_agents()
        finally:
            tr.PRECONFIGURED_EXPERT_AGENTS["run_data_auditor"] = original
        self.assertEqual(registry["run_data_auditor"]["source"], "default")

    def test_should_have_obsidian_markdown_formatter(self):
        self.assertTrue(callable(getattr(gr, "format_obsidian_markdown_report", None)))

    def test_runtime_should_expose_minimal_shortline_upgrade_advice(self):
        advice = gr.get_minimal_shortline_upgrade_advice()
        self.assertIn("indicator_layers", advice)
        self.assertIn("必须", advice["indicator_layers"])
        self.assertTrue(any(item["indicator"] == "VWAP偏离" for item in advice["indicator_layers"]["必须"]))

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
        self.assertIn("短线校准后总分", content)

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

    def test_should_render_shortline_downgrade_reason_when_key_indicators_missing(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "601868",
                    "stock_name": "中国能建",
                    "label": "可做",
                    "scores": {"momentum": 85, "revenue": 75, "risk": 70},
                    "shortline_signals": {"vwap_deviation": "N/A", "atr_stop": "8.21", "volume_ratio": "2.10"},
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("短线信号确认", content)
        self.assertIn("降级原因：缺失关键指标", content)
        self.assertIn("建议上限标签：观察", content)

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

    def test_fund_flow_should_use_conservative_fallback_when_direction_missing(self):
        search_data = [
            {
                "title": "资金流向",
                "snippet": "主力资金1.67亿元，散户资金3200万元",
                "link": "http://example.com",
            }
        ]
        report = parse_search_results_to_report(search_data, "600000")
        self.assertNotIn("main", report["fund_flow"])
        self.assertNotIn("retail", report["fund_flow"])

    def test_price_should_prefer_anchor_when_multiple_yuan_values_exist(self):
        search_data = [
            {
                "title": "盘中快讯",
                "snippet": "止损3.50元，目标价12.80元，最新价4.85元，涨跌幅+0.82%，成交额2.3亿元",
                "link": "http://example.com",
            }
        ]
        report = parse_search_results_to_report(search_data, "600000")
        self.assertEqual(report["price_info"].get("price"), "4.85")

    def test_price_should_reject_non_same_day_close_semantic(self):
        search_data = [
            {
                "title": "股价播报",
                "snippet": "收盘价10.20元，更新时间2026-03-09 15:00，成交额2.3亿元",
                "link": "https://www.sse.com.cn/marketdata",
                "timestamp": "2026-03-09 15:00",
            }
        ]
        report = parse_search_results_to_report(search_data, "600000", request_date="2026-03-10")
        self.assertNotIn("price", report.get("price_info", {}))
        self.assertEqual(len(report.get("price_semantic_records", [])), 0)

    def test_price_should_accept_same_day_close_semantic(self):
        search_data = [
            {
                "title": "股价播报",
                "snippet": "今日收盘10.20元，更新时间2026-03-10 15:00，成交额2.3亿元",
                "link": "https://www.sse.com.cn/marketdata",
                "timestamp": "2026-03-10 15:00",
            }
        ]
        report = parse_search_results_to_report(search_data, "600000", request_date="2026-03-10")
        self.assertEqual(report.get("price_info", {}).get("price"), "10.20")
        self.assertGreaterEqual(len(report.get("price_semantic_records", [])), 1)

    def test_shortline_signals_should_extract_vwap_volume_ratio_and_atr_stop(self):
        search_data = [
            {
                "title": "技术指标追踪",
                "snippet": "VWAP偏离2.35%，量比1.92，ATR14为0.28，建议止损3.51元",
                "link": "http://example.com",
            }
        ]
        report = parse_search_results_to_report(search_data, "600000")
        signals = report.get("shortline_signals", {})
        self.assertEqual(signals.get("vwap_deviation"), "2.35")
        self.assertEqual(signals.get("volume_ratio"), "1.92")
        self.assertEqual(signals.get("atr_stop"), "3.51")

    def test_parse_report_should_inject_canonical_code_and_name_from_input(self):
        search_data = [
            {
                "title": "行情播报",
                "snippet": "600000 最新价10.20元，更新时间2026-03-10 10:05",
                "link": "https://www.sse.com.cn/marketdata",
                "timestamp": "2026-03-10 10:05",
            },
            {
                "title": "盘中快讯",
                "snippet": "代码600000 最新价10.22元，成交额2.1亿元，更新时间2026-03-10 10:06",
                "link": "https://www.yicai.com/news/stock",
                "timestamp": "2026-03-10 10:06",
            },
        ]
        report = parse_search_results_to_report(search_data, "600000", stock_name="浦发银行")
        self.assertEqual(report.get("canonical_code"), "600000")
        self.assertEqual(report.get("canonical_name"), "浦发银行")
        gate = report.get("expert_identity_gate", {})
        self.assertFalse(any("未提取到代码600000对应名称" in reason for reason in gate.get("failed_reasons", [])))
        identity_summary = gate.get("identity_source_summary", {})
        self.assertEqual(identity_summary.get("canonical_code"), "600000")
        self.assertEqual(identity_summary.get("canonical_name"), "浦发银行")

    def test_parse_report_should_include_debate_and_risk_judge(self):
        search_data = [
            {
                "title": "行业景气扩产跟踪",
                "snippet": "浦发银行(600000) 最新价10.20元 景气扩产 需求回暖 更新时间2026-03-10 10:00",
                "link": "https://www.sse.com.cn/marketdata",
                "timestamp": "2026-03-10 10:00",
            },
            {
                "title": "监管问询与处罚提示",
                "snippet": "浦发银行(600000) 监管问询 处罚 风险提示 最新价10.18元 更新时间2026-03-10 10:05",
                "link": "https://www.yicai.com/news/stock",
                "timestamp": "2026-03-10 10:05",
            },
        ]
        report = parse_search_results_to_report(search_data, "600000", stock_name="浦发银行", request_date="2026-03-10")
        self.assertIn("debate_state", report)
        self.assertIn("risk_judge", report)
        self.assertIn("data_quality_verdict", report)
        self.assertGreaterEqual(len(report.get("debate_state", {}).get("open_claims", [])), 2)
        self.assertIn(report.get("risk_judge", {}).get("verdict"), ("pass", "revise", "fail"))
        self.assertIn(report.get("data_quality_verdict", {}).get("verdict"), ("high", "medium", "low"))

    def test_identity_gate_should_use_input_canonical_name_as_binding_anchor(self):
        search_data = [
            {
                "title": "浦发银行(600000) 行情播报",
                "snippet": "浦发银行(600000) 最新价10.20元/股，更新时间2026-03-10 10:05",
                "link": "https://www.sse.com.cn/marketdata",
                "timestamp": "2026-03-10 10:05",
            },
            {
                "title": "招商银行(600000) 行情播报",
                "snippet": "招商银行(600000) 最新价10.21元/股，更新时间2026-03-10 10:06",
                "link": "https://www.yicai.com/news/stock",
                "timestamp": "2026-03-10 10:06",
            },
        ]
        report = parse_search_results_to_report(search_data, "600000", stock_name="浦发银行")
        gate = report.get("expert_identity_gate", {})
        self.assertFalse(gate.get("identity_passed"))
        self.assertIn("IDENTITY_CODE_NAME_MISMATCH", gate.get("failed_reason_codes", []))
        self.assertTrue(any("浦发银行 vs 招商银行" in reason for reason in gate.get("failed_reasons", [])))

    def test_identity_gate_should_not_cross_bind_name_in_multi_stock_single_snippet(self):
        search_data = [
            {
                "title": "行业对比",
                "snippet": "平安银行(000001) 与 浦发银行(600000) 同日上涨，浦发银行(600000) 最新价10.20元/股，更新时间2026-03-10 10:05",
                "link": "https://www.yicai.com/news/stock",
                "timestamp": "2026-03-10 10:05",
            },
            {
                "title": "交易所播报",
                "snippet": "浦发银行(600000) 最新价10.22元/股，更新时间2026-03-10 10:06",
                "link": "https://www.sse.com.cn/marketdata",
                "timestamp": "2026-03-10 10:06",
            },
        ]
        report = parse_search_results_to_report(search_data, "600000", stock_name="浦发银行")
        gate = report.get("expert_identity_gate", {})
        self.assertTrue(gate.get("identity_passed"))
        self.assertNotIn("IDENTITY_CODE_NAME_MISMATCH", gate.get("failed_reason_codes", []))

    def test_identity_should_reject_ambiguous_adjacent_bindings(self):
        search_data = [
            {
                "title": "盘口异动",
                "snippet": "浦发银行600000招商银行 最新价10.20元/股，更新时间2026-03-10 10:05",
                "link": "https://www.yicai.com/news/stock",
                "timestamp": "2026-03-10 10:05",
            },
            {
                "title": "交易所播报",
                "snippet": "浦发银行(600000) 最新价10.22元/股，更新时间2026-03-10 10:06",
                "link": "https://www.sse.com.cn/marketdata",
                "timestamp": "2026-03-10 10:06",
            },
        ]
        report = parse_search_results_to_report(search_data, "600000", stock_name="浦发银行")
        ambiguous_hit = [m for m in report.get("identity_mentions", []) if m.get("source_title") == "盘口异动"]
        self.assertEqual(len(ambiguous_hit), 0)

    def test_data_audit_should_require_resample_when_date_rolls_back(self):
        search_data = self._build_multi_source_core_data(
            ["2026-03-10 09:30", "2026-03-10 09:40", "2026-03-10 10:00"]
        )
        report = parse_search_results_to_report(search_data, "600000", request_date="2026-03-11")
        gate = report.get("audit_gate", {})
        self.assertFalse(gate.get("passed"))
        self.assertTrue(gate.get("require_resample"))
        self.assertIn("price", gate.get("failed_fields", []))

    def test_data_audit_should_mark_conflict_when_multi_source_timestamp_diverges(self):
        search_data = self._build_multi_source_core_data(
            ["2026-03-10 09:30", "2026-03-10 09:35", "2026-03-10 12:30"]
        )
        report = parse_search_results_to_report(search_data, "600000", request_date="2026-03-10")
        gate = report.get("audit_gate", {})
        self.assertFalse(gate.get("passed"))
        reasons = " ".join(gate.get("downgrade_reasons", []))
        self.assertIn("多源时间戳冲突", reasons)
        self.assertEqual(report.get("data_quality_verdict", {}).get("verdict"), "low")
        self.assertEqual(report.get("risk_judge", {}).get("verdict"), "fail")

    def test_data_audit_should_not_mark_conflict_within_threshold(self):
        search_data = self._build_multi_source_core_data(
            ["2026-03-10 09:30", "2026-03-10 09:35", "2026-03-10 12:29"]
        )
        report = parse_search_results_to_report(search_data, "600000", request_date="2026-03-10")
        gate = report.get("audit_gate", {})
        reasons = " ".join(gate.get("downgrade_reasons", []))
        self.assertNotIn("多源时间戳冲突", reasons)

    def test_data_audit_should_pass_when_source_categories_reach_two(self):
        search_data = self._build_multi_source_core_data(
            ["2026-03-10 09:30", "2026-03-10 09:35", "2026-03-10 09:45"]
        )
        report = parse_search_results_to_report(search_data, "600000", request_date="2026-03-10")
        gate = report.get("audit_gate", {})
        self.assertTrue(gate.get("passed"))

    def test_data_audit_should_fail_when_source_categories_are_insufficient(self):
        search_data = [
            {
                "title": "股价播报",
                "snippet": "最新价10.2元，涨跌幅+1.2%，成交额2.1亿元，更新时间2026-03-10 10:00",
                "link": "https://example.com/price",
                "timestamp": "2026-03-10 10:00",
            },
            {
                "title": "资金流向播报",
                "snippet": "主力资金净流入1.1亿元，散户资金净流出900万元，更新时间2026-03-10 10:05",
                "link": "https://example.com/fund",
                "timestamp": "2026-03-10 10:05",
            },
            {
                "title": "业绩快报",
                "snippet": "营业收入123.4亿元，同比增长12.5%，环比增长3.2%，更新时间2026-03-10 10:10",
                "link": "https://example.com/finance",
                "timestamp": "2026-03-10 10:10",
            },
        ]
        report = parse_search_results_to_report(search_data, "600000", request_date="2026-03-10")
        gate = report.get("audit_gate", {})
        self.assertFalse(gate.get("passed"))
        reasons = " ".join(gate.get("downgrade_reasons", []))
        self.assertIn("来源类别不足", reasons)

    def test_data_audit_should_downgrade_when_timestamp_missing_and_keep_news_timestamp_na(self):
        search_data = self._build_multi_source_core_data(
            ["", "2026-03-10 09:35", "2026-03-10 09:45"]
        )
        report = parse_search_results_to_report(search_data, "600000", request_date="2026-03-10")
        gate = report.get("audit_gate", {})
        reasons = " ".join(gate.get("downgrade_reasons", []))
        self.assertFalse(gate.get("passed"))
        self.assertTrue(gate.get("require_resample"))
        self.assertIn("缺失时间戳", reasons)
        self.assertEqual(report.get("news", [])[0].get("timestamp"), "N/A")
        self.assertEqual(report.get("shortline_signals", {}).get("audit_downgraded"), "true")

    def test_markdown_should_render_audit_downgrade_and_resample_reason(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "601868",
                    "stock_name": "中国能建",
                    "label": "观察",
                    "scores": {"momentum": 85, "revenue": 75, "risk": 70},
                    "shortline_signals": {"vwap_deviation": "1.20", "atr_stop": "8.21", "volume_ratio": "2.10"},
                    "audit_gate": {
                        "passed": False,
                        "require_resample": True,
                        "downgrade_reasons": ["price: 日期回退", "main: 多源时间戳冲突"],
                        "field_results": {
                            "price": {"consistency": "不一致", "source_count": 3, "category_count": 3, "reason": "日期回退"},
                        },
                    },
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("数据真实性审计", content)
        self.assertIn("审计状态：未通过", content)
        self.assertIn("数据真实性审计未通过，需先重采再评估", content)

    def test_markdown_should_append_machine_readable_verdict_blocks(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "601868",
                    "stock_name": "中国能建",
                    "label": "观察",
                    "scores": {"momentum": 85, "revenue": 75, "risk": 70},
                    "risk_judge": {"verdict": "pass", "result_label_cap": "观察"},
                    "data_quality_verdict": {"verdict": "medium", "score": 78},
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("<!-- VERDICT:", content)
        self.assertIn("<!-- RISK_JUDGE:", content)
        self.assertIn("<!-- DATA_QUALITY:", content)
        self.assertNotIn("<!-- POOL_VERDICT:", content)
        pool_content = gr.format_obsidian_markdown_report(
            {
                "date": "2026-03-10",
                "stocks": [
                    payload["stocks"][0],
                    {
                        "stock_code": "600000",
                        "stock_name": "浦发银行",
                        "label": "回避",
                        "scores": {"momentum": 70, "revenue": 60, "risk": 40},
                        "risk_judge": {"verdict": "fail", "result_label_cap": "回避"},
                        "data_quality_verdict": {"verdict": "low", "score": 45},
                    },
                ],
            }
        )
        self.assertIn("<!-- POOL_VERDICT:", pool_content)

    def test_shortline_recommendation_should_cap_label_when_signal_is_weak(self):
        recommendation = gr._generate_minimal_shortline_recommendation(
            {
                "shortline_signals": {
                    "vwap_deviation": "4.50",
                    "volume_ratio": "0.85",
                    "atr_stop": "3.21",
                }
            }
        )
        self.assertEqual(recommendation["label_cap"], "回避")

    def test_shortline_score_should_downgrade_when_signal_is_weak(self):
        result = gr._calc_shortline_adjusted_score(
            {"momentum": 85, "revenue": 75, "risk": 70},
            {"vwap_deviation": "4.50", "volume_ratio": "0.85", "atr_stop": "3.21"},
        )
        self.assertEqual(result["base_score"], "77.8")
        self.assertEqual(result["adjusted_score"], "62.8")

    def test_shortline_score_should_upgrade_when_confirmation_is_strong(self):
        result = gr._calc_shortline_adjusted_score(
            {"momentum": 85, "revenue": 75, "risk": 70},
            {"vwap_deviation": "1.20", "volume_ratio": "2.10", "atr_stop": "3.21"},
        )
        self.assertEqual(result["adjusted_score"], "80.8")

    def test_sentiment_governance_should_dedup_and_reject_low_quality_news(self):
        search_data = [
            {
                "title": "公司回购计划公布",
                "snippet": "2026-03-10 公司公告回购2亿元，属利好消息",
                "link": "https://www.cninfo.com.cn/disclosure",
                "timestamp": "2026-03-10 10:20",
            },
            {
                "title": "公司回购计划公布",
                "snippet": "2026-03-10 公司公告回购2亿元，属利好消息",
                "link": "https://www.cninfo.com.cn/disclosure",
                "timestamp": "2026-03-10 10:21",
            },
            {
                "title": "惊天内幕：明天必涨",
                "snippet": "论坛转载：小作文称该股必涨，未证实",
                "link": "https://example.com/post",
                "timestamp": "2026-03-10 10:30",
            },
        ]
        report = parse_search_results_to_report(search_data, "600000")
        governance = report.get("sentiment_governance", {})
        self.assertEqual(governance.get("deduped_count"), 1)
        self.assertEqual(governance.get("accepted_count"), 1)
        self.assertGreaterEqual(governance.get("rejected_count", 0), 2)
        rejected_reasons = " ".join(item.get("reason", "") for item in governance.get("rejected_items", []))
        self.assertIn("重复内容", rejected_reasons)

    def test_sentiment_adjustment_should_be_capped_to_2_points(self):
        result = gr._calc_shortline_adjusted_score(
            {"momentum": 85, "revenue": 75, "risk": 70},
            {"vwap_deviation": "1.20", "volume_ratio": "2.10", "atr_stop": "3.21"},
            sentiment_governance={"score_adjustment": "9.9"},
        )
        self.assertEqual(result["sentiment_adjustment"], "2.0")
        self.assertEqual(result["adjusted_score"], "82.8")

    def test_sentiment_negative_adjustment_should_be_capped_to_minus_2_points(self):
        result = gr._calc_shortline_adjusted_score(
            {"momentum": 85, "revenue": 75, "risk": 70},
            {"vwap_deviation": "1.20", "volume_ratio": "2.10", "atr_stop": "3.21"},
            sentiment_governance={"score_adjustment": "-9.9"},
        )
        self.assertEqual(result["sentiment_adjustment"], "-2.0")
        self.assertEqual(result["adjusted_score"], "78.8")

    def test_markdown_should_include_sentiment_acceptance_and_rejection_reasons(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "601868",
                    "stock_name": "中国能建",
                    "label": "可做",
                    "scores": {"momentum": 85, "revenue": 75, "risk": 70},
                    "sentiment_governance": {
                        "max_impact_cap": "2.0",
                        "deduped_count": 1,
                        "accepted_count": 1,
                        "rejected_count": 1,
                        "average_quality_score": "85.0",
                        "sentiment_score_raw": "1.00",
                        "score_adjustment": "1.7",
                        "accepted_items": [
                            {"title": "公司回购计划公布", "quality_score": 85, "reasons": ["包含可追溯链接", "包含可验证事实数据"]},
                        ],
                        "rejected_items": [
                            {"title": "惊天内幕：明天必涨", "quality_score": 30, "reason": "存在情绪化标题词"},
                        ],
                    },
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("舆情降噪治理", content)
        self.assertIn("采纳依据", content)
        self.assertIn("剔除依据", content)
        self.assertIn("封顶±2.0", content)

    def test_parse_report_should_include_industry_event_and_supervisor_outputs(self):
        search_data = [
            {
                "title": "行业景气回暖，龙头订单增长",
                "snippet": "2026-03-10 行业需求回暖，公司中标新订单",
                "link": "https://example.com/industry",
                "timestamp": "2026-03-10 10:20",
            },
            {
                "title": "监管问询函发布",
                "snippet": "2026-03-10 公司收到监管问询，短期冲击偏负向",
                "link": "https://example.com/event",
                "timestamp": "2026-03-10 10:30",
            },
        ]
        report = parse_search_results_to_report(search_data, "600000")
        self.assertIn("industry_researcher", report.get("expert_outputs", {}))
        self.assertIn("event_hunter", report.get("expert_outputs", {}))
        self.assertIn("supervisor_review", report)
        self.assertIn("result_label_cap", report.get("supervisor_review", {}))
        self.assertTrue(len(report.get("evidences", [])) >= 2)

    def test_new_expert_outputs_should_contain_required_fields(self):
        search_data = [
            {
                "title": "浦发银行(600000) 交易所行情播报",
                "snippet": "浦发银行(600000) 最新价10.20元/股，涨跌幅+1.10%，成交额2.30亿元，更新时间2026-03-10 10:05",
                "link": "https://www.sse.com.cn/marketdata",
                "timestamp": "2026-03-10 10:05",
            },
            {
                "title": "上海浦东发展银行600000 行业竞争格局改善，需求回暖",
                "snippet": "2026-03-10 上海浦东发展银行600000 最新价10.18元/股，行业景气改善，竞争格局优化",
                "link": "https://www.yicai.com/news/industry-research",
                "timestamp": "2026-03-10 09:40",
            },
            {
                "title": "浦发银行(600000) 监管问询与风险提示公告",
                "snippet": "2026-03-10 浦发银行(600000) 收到监管问询，短期事件冲击偏负向",
                "link": "https://example.com/event-research",
                "timestamp": "2026-03-10 10:10",
            },
        ]
        report = parse_search_results_to_report(search_data, "600000")
        industry_output = report.get("expert_outputs", {}).get("industry_researcher", {})
        event_output = report.get("expert_outputs", {}).get("event_hunter", {})
        for field in ["outlook", "inflection", "competition_landscape", "decision_hint", "evidences"]:
            self.assertIn(field, industry_output)
        for field in ["impact_direction", "impact_strength", "time_window", "regulatory_signal", "decision_hint", "evidences"]:
            self.assertIn(field, event_output)
        self.assertIn("expert_identity_gate", report)
        self.assertTrue(report.get("expert_identity_gate", {}).get("passed"))
        self.assertFalse(report.get("process_block", {}).get("blocked"))

    def test_identity_gate_should_support_code_name_alias_bi_directional_check(self):
        search_data = [
            {
                "title": "浦发银行(600000) 行情播报",
                "snippet": "浦发银行(600000) 最新价10.20元/股，更新时间2026-03-10 10:05",
                "link": "https://www.sse.com.cn/marketdata",
                "timestamp": "2026-03-10 10:05",
            },
            {
                "title": "上海浦东发展银行600000 盘中快讯",
                "snippet": "上海浦东发展银行600000 最新价10.22元/股，更新时间2026-03-10 10:06",
                "link": "https://www.yicai.com/news/stock",
                "timestamp": "2026-03-10 10:06",
            },
        ]
        report = parse_search_results_to_report(search_data, "600000")
        gate = report.get("expert_identity_gate", {})
        self.assertTrue(gate.get("identity_passed"))
        self.assertGreaterEqual(gate.get("identity_source_summary", {}).get("category_count", 0), 2)
        self.assertGreaterEqual(len(gate.get("identity_source_evidences", [])), 2)

    def test_identity_gate_should_fail_when_code_to_name_mapping_conflicts(self):
        search_data = [
            {
                "title": "浦发银行(600000) 行情播报",
                "snippet": "浦发银行(600000) 最新价10.20元/股，更新时间2026-03-10 10:05",
                "link": "https://www.sse.com.cn/marketdata",
                "timestamp": "2026-03-10 10:05",
            },
            {
                "title": "招商银行(600000) 行情播报",
                "snippet": "招商银行(600000) 最新价10.21元/股，更新时间2026-03-10 10:06",
                "link": "https://www.yicai.com/news/stock",
                "timestamp": "2026-03-10 10:06",
            },
        ]
        report = parse_search_results_to_report(search_data, "600000")
        gate = report.get("expert_identity_gate", {})
        self.assertFalse(gate.get("identity_passed"))
        self.assertIn("IDENTITY_CODE_NAME_MISMATCH", gate.get("failed_reason_codes", []))

    def test_identity_gate_should_fail_when_name_maps_to_other_code(self):
        search_data = [
            {
                "title": "浦发银行(600000) 行情播报",
                "snippet": "浦发银行(600000) 最新价10.20元/股，更新时间2026-03-10 10:05",
                "link": "https://www.sse.com.cn/marketdata",
                "timestamp": "2026-03-10 10:05",
            },
            {
                "title": "浦发银行(601000) 公告快讯",
                "snippet": "浦发银行(601000) 最新价10.18元/股，更新时间2026-03-10 10:06",
                "link": "https://www.yicai.com/news/stock",
                "timestamp": "2026-03-10 10:06",
            },
        ]
        report = parse_search_results_to_report(search_data, "600000")
        gate = report.get("expert_identity_gate", {})
        self.assertFalse(gate.get("identity_passed"))
        self.assertIn("IDENTITY_NAME_CODE_CONFLICT", gate.get("failed_reason_codes", []))

    def test_price_semantic_should_fail_when_currency_or_unit_cross_source_conflicts(self):
        search_data = [
            {
                "title": "浦发银行(600000) 行情播报",
                "snippet": "浦发银行(600000) 最新价10.20元/股，更新时间2026-03-10 10:05",
                "link": "https://www.sse.com.cn/marketdata",
                "timestamp": "2026-03-10 10:05",
            },
            {
                "title": "浦发银行(600000) 海外报价",
                "snippet": "浦发银行(600000) 最新价1.42美元/股，更新时间2026-03-10 10:06",
                "link": "https://www.yicai.com/news/stock",
                "timestamp": "2026-03-10 10:06",
            },
        ]
        report = parse_search_results_to_report(search_data, "600000")
        gate = report.get("expert_identity_gate", {})
        self.assertFalse(gate.get("price_passed"))
        self.assertIn("PRICE_CURRENCY_UNIT_INCONSISTENT", gate.get("failed_reason_codes", []))

    def test_expert_identity_gate_should_fail_when_price_out_of_valid_range(self):
        report = {
            "stock_code": "600000",
            "canonical_name": "浦发银行",
            "price_info": {"price": "9999"},
            "identity_mentions": [
                {
                    "stock_code": "600000",
                    "stock_name": "浦发银行",
                    "source_category": "交易所/监管",
                    "timestamp": "2026-03-10 10:05",
                },
                {
                    "stock_code": "600000",
                    "stock_name": "上海浦东发展银行",
                    "source_category": "财经媒体",
                    "timestamp": "2026-03-10 10:06",
                },
            ],
            "price_semantic_records": [
                {"currency": "CNY", "unit": "元/股", "source_category": "交易所/监管", "timestamp": "2026-03-10 10:05"},
                {"currency": "CNY", "unit": "元/股", "source_category": "财经媒体", "timestamp": "2026-03-10 10:06"},
            ],
        }
        gate = gr._run_expert_identity_gate(report)
        self.assertFalse(gate.get("passed"))
        self.assertFalse(gate.get("price_passed"))
        self.assertIn("PRICE_INVALID", gate.get("failed_reason_codes", []))
        categories = {item.get("category") for item in gate.get("repair_suggestions", [])}
        self.assertIn("price_validity", categories)

    def test_expert_identity_gate_should_fail_when_trading_day_timeliness_is_stale(self):
        report = {
            "stock_code": "600000",
            "request_date": "2026-03-10",
            "canonical_name": "浦发银行",
            "price_info": {"price": "10.20"},
            "identity_mentions": [
                {
                    "stock_code": "600000",
                    "stock_name": "浦发银行",
                    "source_category": "交易所/监管",
                    "timestamp": "2026-03-09 15:00",
                },
                {
                    "stock_code": "600000",
                    "stock_name": "上海浦东发展银行",
                    "source_category": "财经媒体",
                    "timestamp": "2026-03-09 15:01",
                },
            ],
            "price_semantic_records": [
                {"currency": "CNY", "unit": "元/股", "source_category": "交易所/监管", "timestamp": "2026-03-09 15:00"},
                {"currency": "CNY", "unit": "元/股", "source_category": "财经媒体", "timestamp": "2026-03-09 15:01"},
            ],
            "field_sources": {
                "price.price": [
                    {"value": "10.20", "timestamp": "2026-03-09 15:00"},
                ]
            },
            "expert_outputs": {
                "industry_researcher": {"agent": "expert_industry_researcher", "stock_code": "600000", "as_of_price": "10.20"},
                "event_hunter": {"agent": "expert_event_hunter", "stock_code": "600000", "as_of_price": "10.20"},
            },
        }
        gate = gr._run_expert_identity_gate(report)
        self.assertFalse(gate.get("passed"))
        self.assertFalse(gate.get("trading_day_passed"))
        self.assertIn("TRADING_DAY_STALE", gate.get("failed_reason_codes", []))
        categories = {item.get("category") for item in gate.get("repair_suggestions", [])}
        self.assertIn("trading_day_timeliness", categories)

    def test_parse_report_should_return_structured_repair_suggestions_when_blocked(self):
        search_data = [
            {
                "title": "交易所行情播报",
                "snippet": "浦发银行(600000) 最新价10.20元/股，更新时间2026-03-09 15:00",
                "link": "https://www.sse.com.cn/marketdata",
                "timestamp": "2026-03-09 15:00",
            },
            {
                "title": "财经媒体快讯",
                "snippet": "上海浦东发展银行600000 最新价10.21元/股，更新时间2026-03-09 15:01",
                "link": "https://www.yicai.com/news/stock",
                "timestamp": "2026-03-09 15:01",
            },
        ]
        report = parse_search_results_to_report(
            search_data,
            "600000",
            stock_name="浦发银行",
            request_date="2026-03-10",
        )
        self.assertTrue(report.get("process_block", {}).get("blocked"))
        suggestions = report.get("repair_suggestions", [])
        self.assertTrue(len(suggestions) >= 1)
        first = suggestions[0]
        self.assertIn("failure_code", first)
        self.assertIn("category", first)
        self.assertIn("required_action", first)
        self.assertIsInstance(first.get("steps"), list)

    def test_expert_identity_gate_should_block_when_agent_or_price_mismatch(self):
        report = {
            "stock_code": "600000",
            "price_info": {"price": "10.00"},
            "expert_outputs": {
                "industry_researcher": {"agent": "wrong_agent", "stock_code": "600000", "as_of_price": "11.20"},
                "event_hunter": {"agent": "expert_event_hunter", "stock_code": "601000", "as_of_price": "9.20"},
            },
        }
        gate = gr._run_expert_identity_gate(report)
        self.assertFalse(gate.get("passed"))
        self.assertTrue(gate.get("require_block"))
        reasons = " ".join(gate.get("failed_reasons", []))
        self.assertIn("身份不匹配", reasons)
        self.assertIn("标的不一致", reasons)
        self.assertIn("价格偏差超阈值", reasons)

    def test_markdown_should_render_expert_identity_and_process_block_section(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "601868",
                    "stock_name": "中国能建",
                    "label": "观察",
                    "scores": {"momentum": 85, "revenue": 75, "risk": 70},
                    "shortline_signals": {"vwap_deviation": "1.20", "atr_stop": "8.21", "volume_ratio": "2.10"},
                    "expert_identity_gate": {
                        "passed": False,
                        "identity_passed": False,
                        "price_passed": False,
                        "require_block": True,
                        "checked_stock_code": "601868",
                        "reference_price": "9.88",
                        "failed_agents": ["industry_researcher"],
                        "failed_reasons": ["industry_researcher身份不匹配", "industry_researcher价格偏差超阈值(12.0%>8.0%)"],
                    },
                    "process_block": {
                        "blocked": True,
                        "blocked_stage": "supervisor_review",
                        "reason": "industry_researcher身份不匹配；industry_researcher价格偏差超阈值(12.0%>8.0%)",
                        "next_action": "重采样并重新执行专家鉴别",
                    },
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("专家鉴别与身份价格校验", content)
        self.assertIn("流程阻断", content)
        self.assertIn("阻断状态：已阻断", content)
        self.assertIn("专家身份与价格校验未通过", content)

    def test_markdown_should_render_aggregated_authenticity_verification_block(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "600000",
                    "stock_name": "浦发银行",
                    "label": "观察",
                    "scores": {"momentum": 80, "revenue": 76, "risk": 72},
                    "expert_identity_gate": {
                        "passed": False,
                        "identity_passed": False,
                        "price_passed": False,
                        "failed_reason_codes": ["IDENTITY_CODE_NAME_MISMATCH", "PRICE_CURRENCY_UNIT_INCONSISTENT"],
                        "identity_source_summary": {"evidence_count": 3, "category_count": 2},
                        "price_semantic_summary": {"currency": "CNY", "unit": "元/股", "record_count": 3, "category_count": 2},
                        "authenticity_summary": {
                            "identity_status": "未通过",
                            "price_status": "未通过",
                            "source_count": 6,
                            "latest_timestamp": "2026-03-10 10:18",
                            "risk_tips": ["身份一致性存在风险", "价格语义一致性存在风险"],
                            "failed_reason_codes": ["IDENTITY_CODE_NAME_MISMATCH", "PRICE_CURRENCY_UNIT_INCONSISTENT"],
                        },
                    },
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("数据真实性鉴别结果", content)
        self.assertIn("最近校验时间戳：2026-03-10 10:18", content)
        self.assertIn("失败原因编码", content)
        self.assertIn("用户提示", content)
        self.assertIn("风险提示", content)

    def test_markdown_should_render_data_source_meta_and_unified_router_tips(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "600000",
                    "stock_name": "浦发银行",
                    "label": "观察",
                    "scores": {"momentum": 80, "revenue": 76, "risk": 72},
                    "eastmoney_router": {
                        "critical_gate": {
                            "reason_codes": ["REQUEST_LIMIT_EXCEEDED", "TARGET_REQUIRED"],
                            "user_tips": ["请降低返回条数（建议<=50）后重试。", "请补充股票代码或股票名称后再发起请求。"],
                        }
                    },
                    "metadata_passthrough": {
                        "source_function": "stock_utils.eastmoney_query",
                        "fetched_at": "2026-03-10 10:18:00",
                        "validation_conclusion": "标的元信息校验通过",
                    },
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("数据源元信息", content)
        self.assertIn("来源函数：stock_utils.eastmoney_query", content)
        self.assertIn("抓取时间：2026-03-10 10:18:00", content)
        self.assertIn("校验结论：标的元信息校验通过", content)
        self.assertIn("路由失败原因码：REQUEST_LIMIT_EXCEEDED; TARGET_REQUIRED", content)
        self.assertIn("路由用户提示", content)

    def test_complex_request_end_to_end_should_cover_full_closed_loop_dimensions(self):
        request = "请今日采集市场数据，筛选10支，再组织专家讨论，最后推荐3支"
        route = gr.plan_analysis_route(request)
        self.assertEqual(route.get("execution_profile"), "full_parallel")
        self.assertEqual(route.get("steps", [None])[0], "run_data_auditor")

        search_data = [
            {
                "title": "交易所行情与趋势播报",
                "snippet": "最新价10.20元，涨跌幅+1.20%，成交额2.10亿元，趋势转强，更新时间2026-03-10 10:00",
                "link": "https://www.sse.com.cn/marketdata",
                "timestamp": "2026-03-10 10:00",
            },
            {
                "title": "资金流向监测",
                "snippet": "主力资金净流入1.30亿元，散户资金净流出800万元，更新时间2026-03-10 10:05",
                "link": "https://quote.eastmoney.com/600000.html",
                "timestamp": "2026-03-10 10:05",
            },
            {
                "title": "政策支持与行业竞争格局优化",
                "snippet": "2026-03-10 政策支持加码，行业需求回暖，竞争格局改善并出现景气上行趋势",
                "link": "https://www.yicai.com/news/stock",
                "timestamp": "2026-03-10 10:10",
            },
            {
                "title": "监管问询风险提示事件",
                "snippet": "2026-03-10 监管问询函发布，短期事件冲击偏负向，提示交易风险",
                "link": "https://www.cninfo.com.cn/new/disclosure",
                "timestamp": "2026-03-10 10:12",
            },
            {
                "title": "技术指标跟踪",
                "snippet": "VWAP偏离1.20%，量比2.10，ATR14为0.28，建议止损9.78元",
                "link": "https://xueqiu.com/S/SH600000",
                "timestamp": "2026-03-10 10:15",
            },
            {
                "title": "业绩快报",
                "snippet": "公司2025年三季度营业收入123.4亿元，同比增长12.5%，环比增长3.2%",
                "link": "https://www.10jqka.com.cn/stock/600000",
                "timestamp": "2026-03-10 10:20",
            },
        ]
        report = parse_search_results_to_report(search_data, "600000", request_date="2026-03-10")
        stock_payload = {
            "stock_code": "600000",
            "stock_name": "浦发银行",
            "label": report.get("supervisor_review", {}).get("result_label_cap", "观察"),
            "scores": {"momentum": 82, "revenue": 78, "risk": 74},
            "shortline_signals": report.get("shortline_signals", {}),
            "audit_gate": report.get("audit_gate", {}),
            "sentiment_governance": report.get("sentiment_governance", {}),
            "industry_research_output": report.get("expert_outputs", {}).get("industry_researcher", {}),
            "event_hunter_output": report.get("expert_outputs", {}).get("event_hunter", {}),
            "supervisor_review": report.get("supervisor_review", {}),
            "evidences": report.get("evidences", []),
            "fund_flow": {"latest_main": "-200.00", "five_day_main": "1300.00"},
        }
        content = gr.format_obsidian_markdown_report({"date": "2026-03-10", "stocks": [stock_payload]})
        for keyword in ["数据", "趋势", "资金", "风险", "政策", "竞争", "事件"]:
            self.assertIn(keyword, content)
        self.assertIn("数据真实性审计", content)
        self.assertIn("行业研究家结论", content)
        self.assertIn("消息面猎手结论", content)
        self.assertIn("主管裁决与冲突仲裁", content)

    def test_markdown_should_render_industry_event_and_arbitration_modules(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "601868",
                    "stock_name": "中国能建",
                    "label": "观察",
                    "scores": {"momentum": 85, "revenue": 75, "risk": 70},
                    "industry_research_output": {
                        "outlook": "景气上行",
                        "inflection": "上行拐点初现",
                        "competition_landscape": "头部集中度提升",
                        "decision_hint": "可做",
                    },
                    "event_hunter_output": {
                        "impact_direction": "负向",
                        "impact_strength": "强",
                        "time_window": "1-3个交易日",
                        "regulatory_signal": "高",
                        "decision_hint": "回避",
                    },
                    "supervisor_review": {
                        "industry_decision_hint": "可做",
                        "event_decision_hint": "回避",
                        "result_label_cap": "回避",
                        "arbitration_reason": "优先控制短期事件冲击风险",
                        "conflict_items": ["负向事件强度高，触发强制降档"],
                    },
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("行业研究家结论", content)
        self.assertIn("消息面猎手结论", content)
        self.assertIn("主管裁决与冲突仲裁", content)
        self.assertIn("仲裁结论标签上限：回避", content)

    def test_markdown_should_render_fundamental_expert_v2_output(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "600000",
                    "stock_name": "浦发银行",
                    "label": "观察",
                    "scores": {"momentum": 82, "revenue": 78, "risk": 74},
                    "expert_outputs": {
                        "fundamental_expert": {
                            "schema_version": "v2",
                            "agent": "stock-fundamental-expert",
                            "summary": "营收与现金流改善，但估值修复仍需验证",
                            "positive_evidences": ["营收同比增长12.5%"],
                            "negative_evidences": ["短期利润弹性仍有限"],
                            "risk_tip": "若需求回落则估值承压",
                            "confidence": "中",
                            "decision_hint": "观察",
                            "evidences": [
                                {
                                    "conclusion": "营收增长",
                                    "value": "12.5%",
                                    "source_url": "https://www.cninfo.com.cn/new/disclosure",
                                    "timestamp": "2026-03-10 10:20",
                                }
                            ],
                        }
                    },
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("基本面专家结论", content)
        self.assertIn("营收与现金流改善", content)
        self.assertIn("决策建议：观察", content)
        self.assertIn("营收同比增长12.5%", content)

    def test_markdown_should_compat_legacy_fundamental_output_and_map_decision_hint(self):
        payload = {
            "date": "2026-03-10",
            "stocks": [
                {
                    "stock_code": "600000",
                    "stock_name": "浦发银行",
                    "label": "观察",
                    "scores": {"momentum": 82, "revenue": 78, "risk": 74},
                    "fundamental_expert_output": {
                        "观点摘要": "资产负债结构稳定，短线中性偏谨慎",
                        "正向证据": ["不良率控制稳定"],
                        "反向证据": ["净息差改善有限"],
                        "风险提示": "地产链波动可能拖累估值",
                        "置信度": "中",
                        "decision_hint": "看空",
                    },
                }
            ],
        }
        content = gr.format_obsidian_markdown_report(payload)
        self.assertIn("基本面专家结论", content)
        self.assertIn("资产负债结构稳定", content)
        self.assertIn("决策建议：回避", content)
        self.assertIn("不良率控制稳定", content)

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

    def test_shortline_indicator_recommendations_should_include_code_entries(self):
        recommendations = get_shortline_indicator_recommendations()
        self.assertIn("code_entry_mapping", recommendations)
        self.assertTrue(any(item["output_entry"] == "generate_report._build_shortline_signal_lines" for item in recommendations["code_entry_mapping"]))
        self.assertEqual(recommendations["minimum_rollout_order"][0]["step"], "先路由")

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

    def test_post_json_should_merge_default_and_custom_headers(self):
        captured = {}

        class _FakeResponse:
            status = 200

            def read(self):
                return b'{"ok": true}'

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def _fake_urlopen(request, timeout=10):
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            captured["body"] = request.data.decode("utf-8")
            return _FakeResponse()

        with mock.patch.object(su, "urlopen", side_effect=_fake_urlopen):
            result = su.post_json(
                url="https://example.com/post",
                payload={"name": "demo"},
                headers={"X-Test-Header": "yes"},
                timeout=12,
            )

        self.assertTrue(result.get("ok"))
        self.assertEqual(captured.get("timeout"), 12)
        headers = captured.get("headers", {})
        self.assertEqual(headers.get("Content-type"), "application/json; charset=utf-8")
        self.assertEqual(headers.get("Accept"), "application/json")
        self.assertEqual(headers.get("X-test-header"), "yes")
        self.assertIn('"name": "demo"', captured.get("body", ""))

    def test_post_eastmoney_should_inject_apikey_into_headers(self):
        with mock.patch.object(su, "get_eastmoney_apikey", return_value="abc123XYZ"), \
            mock.patch.object(su, "post_json_with_retry", return_value={"ok": 1}) as mocked_post:
            result = su.post_eastmoney(
                endpoint="query",
                payload={"question": "测试"},
                timeout=6,
                retries=3,
                use_daily_limit=False,
            )

        self.assertEqual(result, {"ok": 1})
        called_kwargs = mocked_post.call_args.kwargs
        self.assertEqual(called_kwargs["url"], su._build_eastmoney_url("query"))
        self.assertEqual(called_kwargs["headers"]["apikey"], "abc123XYZ")
        self.assertEqual(called_kwargs["headers"]["X-Api-Key"], "abc123XYZ")
        self.assertEqual(called_kwargs["timeout"], 6)
        self.assertEqual(called_kwargs["retries"], 3)

    def test_eastmoney_defaults_should_use_finskillshub_claw_path(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            importlib.reload(su)
            self.assertEqual(su.EASTMONEY_BASE_URL, su.DEFAULT_EASTMONEY_BASE_URL)
            self.assertEqual(su.EASTMONEY_ENDPOINT_NEWS_SEARCH, su.DEFAULT_EASTMONEY_ENDPOINT_NEWS_SEARCH)
            self.assertEqual(su.EASTMONEY_ENDPOINT_QUERY, su.DEFAULT_EASTMONEY_ENDPOINT_QUERY)
            self.assertEqual(su.EASTMONEY_ENDPOINT_STOCK_SCREEN, su.DEFAULT_EASTMONEY_ENDPOINT_STOCK_SCREEN)
            self.assertIn("/finskillshub/api/claw", su.EASTMONEY_BASE_URL)
            self.assertEqual(
                su._build_eastmoney_url(su.EASTMONEY_ENDPOINT_NEWS_SEARCH),
                "https://mkapi2.dfcfs.com/finskillshub/api/claw/news-search",
            )
            self.assertEqual(
                su._build_eastmoney_url(su.EASTMONEY_ENDPOINT_QUERY),
                "https://mkapi2.dfcfs.com/finskillshub/api/claw/query",
            )
            self.assertEqual(
                su._build_eastmoney_url(su.EASTMONEY_ENDPOINT_STOCK_SCREEN),
                "https://mkapi2.dfcfs.com/finskillshub/api/claw/stock-screen",
            )

    def test_eastmoney_env_should_override_defaults(self):
        with mock.patch.dict(
            "os.environ",
            {
                "EASTMONEY_BASE_URL": "https://custom.example.com/mkapi2",
                "EASTMONEY_ENDPOINT_NEWS_SEARCH": "/custom-news",
                "EASTMONEY_ENDPOINT_QUERY": "/custom-query",
                "EASTMONEY_ENDPOINT_STOCK_SCREEN": "/custom-screen",
            },
            clear=True,
        ):
            importlib.reload(su)
            self.assertEqual(su.EASTMONEY_BASE_URL, "https://custom.example.com/mkapi2")
            self.assertEqual(su.EASTMONEY_ENDPOINT_NEWS_SEARCH, "/custom-news")
            self.assertEqual(su.EASTMONEY_ENDPOINT_QUERY, "/custom-query")
            self.assertEqual(su.EASTMONEY_ENDPOINT_STOCK_SCREEN, "/custom-screen")
            self.assertEqual(su._build_eastmoney_url(su.EASTMONEY_ENDPOINT_NEWS_SEARCH), "https://custom.example.com/mkapi2/custom-news")

    def test_get_apikey_should_fallback_to_env_local_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".env.local").write_text("EASTMONEY_APIKEY=from_file_key\n", encoding="utf-8")
            with mock.patch.dict("os.environ", {}, clear=True), mock.patch.object(su, "_SKILL_ROOT", root):
                self.assertEqual(su.get_eastmoney_apikey(required=True), "from_file_key")

    def test_get_apikey_should_prioritize_system_env_over_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".env.local").write_text("EASTMONEY_APIKEY=from_file_key\n", encoding="utf-8")
            with mock.patch.dict("os.environ", {"EASTMONEY_APIKEY": "from_env_key"}, clear=True), mock.patch.object(
                su, "_SKILL_ROOT", root
            ):
                self.assertEqual(su.get_eastmoney_apikey(required=True), "from_env_key")

    def test_parse_news_search_should_mark_empty_result_and_tip(self):
        parsed = su.parse_eastmoney_news_search_response({"code": "0", "data": {"list": []}})
        self.assertTrue(parsed.get("success"))
        self.assertTrue(parsed.get("empty_result"))
        self.assertEqual(parsed.get("total"), 0)
        self.assertEqual(parsed.get("empty_result_tip"), su.EASTMONEY_EMPTY_RESULT_TIP)
        self.assertIn("前往东方财富妙想AI", parsed.get("empty_result_tip", ""))

    def test_parse_query_should_mark_empty_result_when_response_has_no_data(self):
        parsed = su.parse_eastmoney_query_response({"code": "0", "data": {"list": []}}, request_payload={"fields": ["price"]})
        self.assertTrue(parsed.get("success"))
        self.assertTrue(parsed.get("empty_result"))
        self.assertEqual(parsed.get("key_fields"), {})
        self.assertIn("price", parsed.get("missing_fields", []))

    def test_compile_stock_screen_conditions_should_parse_low_price_query(self):
        conditions = su._compile_stock_screen_conditions("筛选10元以下低价股")
        self.assertEqual(conditions.get("price_lte"), 10.0)

    def test_eastmoney_stock_screen_should_accept_query_alias_and_inject_keyword(self):
        fake_response = {
            "code": "0",
            "msg": "ok",
            "data": {
                "columns": [{"field": "stock_code", "label": "股票代码"}, {"field": "stock_name", "label": "股票名称"}],
                "rows": [{"stock_code": "600000", "stock_name": "浦发银行"}],
                "total": 1,
            },
        }
        with mock.patch.object(su, "post_eastmoney", return_value=fake_response) as mocked_post:
            parsed = su.eastmoney_stock_screen(query="筛选10元以下低价股", limit=10)
        self.assertTrue(parsed.get("success"))
        called_payload = mocked_post.call_args.kwargs.get("payload", {})
        self.assertIn("keyword", called_payload)
        self.assertEqual(called_payload.get("keyword"), "筛选10元以下低价股")
        self.assertEqual(called_payload.get("conditions", {}).get("price_lte"), 10.0)

    def test_eastmoney_stock_screen_should_accept_sort_rule_alias(self):
        fake_response = {"code": "0", "msg": "ok", "data": {"columns": [], "rows": []}}
        with mock.patch.object(su, "post_eastmoney", return_value=fake_response) as mocked_post:
            su.eastmoney_stock_screen(query="筛选10元以下低价股", sort_rule="主力净流入降序", limit=10)
        called_payload = mocked_post.call_args.kwargs.get("payload", {})
        self.assertEqual(called_payload.get("sort_by"), "主力净流入降序")

    def test_eastmoney_stock_screen_should_relax_conditions_when_empty(self):
        responses = [
            {"code": "0", "msg": "ok", "data": {"columns": [], "rows": [], "total": 0}},
            {
                "code": "0",
                "msg": "ok",
                "data": {"columns": [{"field": "stock_code", "label": "股票代码"}], "rows": [{"stock_code": "600000"}], "total": 1},
            },
        ]
        with mock.patch.object(su, "post_eastmoney", side_effect=responses) as mocked_post:
            parsed = su.eastmoney_stock_screen(
                query="筛选10元以下低价股，优先选择近期有资金流入的股票",
                limit=10,
            )
        self.assertTrue(parsed.get("success"))
        self.assertEqual(parsed.get("total"), 1)
        self.assertIn("price_only", parsed.get("relaxation_chain", []))
        self.assertGreaterEqual(mocked_post.call_count, 2)

    def test_parse_stock_screen_should_return_structured_error_when_meta_failed(self):
        parsed = su.parse_eastmoney_stock_screen_response({"code": 100, "message": "参数校验失败，选股条件关键词不能为空"})
        self.assertFalse(parsed.get("success"))
        self.assertEqual(parsed.get("error", {}).get("code"), su.STANDARD_ERROR_CODE_INVALID_ARGUMENT)
        details = parsed.get("error", {}).get("details", {})
        self.assertIn("response_meta", details)

    def test_daily_quota_should_persist_count_and_block_when_exceeded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_counter = Path(tmpdir) / ".eastmoney_daily_counter.json"
            with mock.patch.object(su, "_EASTMONEY_COUNTER_FILE", tmp_counter), \
                mock.patch.object(su, "EASTMONEY_DAILY_LIMIT", 2):
                usage1 = su.consume_eastmoney_daily_quota()
                usage2 = su.consume_eastmoney_daily_quota()

                self.assertEqual(usage1["count"], 1)
                self.assertEqual(usage2["count"], 2)
                self.assertEqual(usage2["remaining"], 0)

                with self.assertRaises(su.EastmoneyDailyLimitError):
                    su.consume_eastmoney_daily_quota()

                daily = su.get_eastmoney_daily_usage()
                self.assertEqual(daily["count"], 2)
                self.assertEqual(daily["remaining"], 0)
                self.assertEqual(daily["limit"], 2)

    def test_desensitize_payload_should_mask_sensitive_fields(self):
        payload = {
            "apikey": "abcdef123456",
            "token": "tok_998877",
            "password": "p@ss123456",
            "question": "600000 最新行情",
        }
        safe = su._desensitize_payload(payload)
        self.assertNotEqual(safe["apikey"], payload["apikey"])
        self.assertNotEqual(safe["token"], payload["token"])
        self.assertNotEqual(safe["password"], payload["password"])
        self.assertEqual(safe["question"], payload["question"])
        self.assertNotIn("abcdef123456", str(safe))

    def test_post_eastmoney_log_should_not_contain_plaintext_apikey_or_token(self):
        with mock.patch.object(su, "get_eastmoney_apikey", return_value="SENSITIVE_API_KEY_12345"), \
            mock.patch.object(su, "post_json_with_retry", return_value={"ok": 1}), \
            mock.patch.object(su.LOGGER, "info") as mocked_log:
            su.post_eastmoney(
                endpoint="news-search",
                payload={"question": "600000", "token": "SECRET_TOKEN_67890"},
                use_daily_limit=False,
            )

        args, kwargs = mocked_log.call_args
        rendered = " ".join(str(item) for item in list(args) + [str(kwargs)])
        self.assertNotIn("SENSITIVE_API_KEY_12345", rendered)
        self.assertNotIn("SECRET_TOKEN_67890", rendered)
        self.assertIn("SEN", rendered)
        self.assertIn("***", rendered)

    def test_parse_query_should_desensitize_request_payload_apikey(self):
        parsed = su.parse_eastmoney_query_response(
            {"code": "0", "data": {"list": [{"price": "10.2"}]}},
            request_payload={"question": "测试", "apikey": "REAL_API_KEY_001"},
        )
        request_payload = parsed.get("request_payload", {})
        self.assertIn("apikey", request_payload)
        self.assertNotEqual(request_payload["apikey"], "REAL_API_KEY_001")

    def test_parse_query_should_use_eastmoney_key_fields_and_track_quality(self):
        response = {"code": "0", "data": {"list": [{"price": 99.88, "change_percent": 9.9, "main_net_inflow": 12345}]}}
        parsed = su.parse_eastmoney_query_response(
            response,
            request_payload={"fields": ["price", "change_percent", "main_net_inflow"]},
        )
        self.assertEqual(parsed.get("key_fields_provider"), "eastmoney_query")
        self.assertEqual(parsed.get("key_fields_priority"), 1)
        self.assertTrue(parsed.get("model_completion_forbidden"))
        self.assertEqual(parsed.get("key_fields", {}).get("price"), 99.88)
        self.assertEqual(parsed.get("key_fields", {}).get("change_percent"), 9.9)
        self.assertEqual(parsed.get("key_fields", {}).get("main_net_inflow"), 12345)
        self.assertEqual(parsed.get("missing_fields"), [])
        standardized = parsed.get("standardized_key_fields", {})
        self.assertEqual(standardized.get("price"), 99.88)
        self.assertEqual(standardized.get("trade_date"), datetime.now().strftime("%Y-%m-%d"))
        quality_summary = parsed.get("data_quality_summary", {})
        self.assertTrue(quality_summary.get("is_usable"))
        self.assertEqual(quality_summary.get("provider"), "eastmoney_query")
        self.assertGreaterEqual(quality_summary.get("evidence_count", 0), 3)
        self.assertFalse(quality_summary.get("has_field_conflict"))
        self.assertEqual(parsed.get("field_conflict_summary", {}).get("has_conflict"), False)
        self.assertGreaterEqual(len(parsed.get("data_evidences", [])), 3)

    def test_parse_query_should_keep_usable_when_only_optional_fields_missing(self):
        response = {"code": "0", "data": {"list": [{"price": 10.28, "change_percent": 1.8}]}}
        parsed = su.parse_eastmoney_query_response(
            response,
            request_payload={"fields": ["price", "change_percent", "main_net_inflow"]},
        )
        self.assertEqual(parsed.get("key_fields_provider"), "eastmoney_query")
        self.assertEqual(parsed.get("key_fields_priority"), 1)
        self.assertEqual(parsed.get("key_fields", {}).get("price"), 10.28)
        self.assertEqual(parsed.get("key_fields", {}).get("change_percent"), 1.8)
        self.assertIn("main_net_inflow", parsed.get("missing_fields"))
        standardized = parsed.get("standardized_key_fields", {})
        self.assertEqual(standardized.get("price"), 10.28)
        self.assertEqual(standardized.get("trade_date"), datetime.now().strftime("%Y-%m-%d"))
        quality_summary = parsed.get("data_quality_summary", {})
        self.assertTrue(quality_summary.get("is_usable"))

    def test_parse_query_should_mark_conflict_when_price_values_inconsistent(self):
        response = {"code": "0", "data": {"list": [{"price": 9.91, "last_price": 10.21}]}}
        parsed = su.parse_eastmoney_query_response(
            response,
            request_payload={"fields": ["price"]},
        )
        conflict_summary = parsed.get("field_conflict_summary", {})
        self.assertTrue(conflict_summary.get("has_conflict"))
        quality_summary = parsed.get("data_quality_summary", {})
        self.assertFalse(quality_summary.get("is_usable"))
        self.assertGreaterEqual(quality_summary.get("field_conflict_count", 0), 1)

    def test_normalize_stock_name_should_keep_st_prefix_by_default(self):
        self.assertEqual(su.normalize_stock_name("ST中珠"), "ST中珠")
        self.assertEqual(su.normalize_stock_name(" *ST中珠 "), "ST中珠")

    def test_normalize_stock_name_should_map_alias_even_with_st_prefix(self):
        self.assertEqual(su.normalize_stock_name("ST上海浦东发展银行"), "浦发银行")
        self.assertEqual(su.normalize_stock_name("ＳＴ浦发"), "浦发银行")

    def test_is_stock_name_alias_should_support_st_prefixed_alias_mapping(self):
        self.assertTrue(su.is_stock_name_alias("ST上海浦东发展银行", "浦发银行"))

if __name__ == "__main__":
    unittest.main()
