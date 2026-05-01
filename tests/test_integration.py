import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from team_router import should_use_agent_team
from stock_utils import normalize_stock_name, validate_stock_code
from technical_indicators import calc_atr, calc_vwap, calc_full_indicators, OHLCV
from backtest_framework import BacktestRunner, SignalType, run_simple_backtest


class TestIntegrationRouting(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_single_stock_routing(self):
        result = should_use_agent_team("分析贵州茅台的财务状况")

        self.assertIn("use_team", result)
        self.assertIsInstance(result["use_team"], bool)

    def test_multi_stock_routing(self):
        result = should_use_agent_team("对比中国能建和首开股份，给我短线建议")

        self.assertIn("use_team", result)


class TestIntegrationStockUtils(unittest.TestCase):
    def test_normalize_and_validate_integration(self):
        name = "贵州茅台"
        normalized = normalize_stock_name(name)
        self.assertEqual(normalized, "贵州茅台")

        if normalized:
            code = "600519"
            is_valid = validate_stock_code(code)
            self.assertTrue(is_valid)

    def test_stock_alias_resolution(self):
        aliases = ["中国能建", "中国能源建设", "中国能源建设股份有限公司"]
        for alias in aliases:
            normalized = normalize_stock_name(alias)
            self.assertIsNotNone(normalized)


class TestIntegrationTechnicalIndicators(unittest.TestCase):
    def setUp(self):
        self.sample_candles = [
            {"date": "2026-01-02", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.3, "volume": 1000000},
            {"date": "2026-01-03", "open": 10.3, "high": 10.8, "low": 10.2, "close": 10.5, "volume": 1100000},
            {"date": "2026-01-06", "open": 10.5, "high": 11.0, "low": 10.4, "close": 10.8, "volume": 1200000},
            {"date": "2026-01-07", "open": 10.8, "high": 11.2, "low": 10.7, "close": 11.0, "volume": 1300000},
            {"date": "2026-01-08", "open": 11.0, "high": 11.5, "low": 10.9, "close": 11.2, "volume": 1400000},
        ]

    def test_atr_vwap_integration(self):
        atr_result = calc_atr(self.sample_candles)
        self.assertGreater(atr_result.atr, 0)

        vwap_result = calc_vwap(self.sample_candles)
        self.assertGreater(vwap_result.vwap, 0)

        self.assertLess(abs(vwap_result.deviation), self.sample_candles[-1]["close"])

    def test_full_indicators_pipeline(self):
        indicators = calc_full_indicators(self.sample_candles)

        self.assertIn("price", indicators)
        self.assertIn("atr", indicators)
        self.assertIn("vwap", indicators)
        self.assertIn("rsi", indicators)
        self.assertIn("stop_loss", indicators)
        self.assertIn("interpretation", indicators)

        self.assertEqual(indicators["price"], self.sample_candles[-1]["close"])
        self.assertIsInstance(indicators["interpretation"], str)

    def test_ohlcv_dataclass(self):
        candle = self.sample_candles[0]
        ohlcv = OHLCV.from_dict(candle)

        self.assertEqual(ohlcv.date, "2026-01-02")
        self.assertEqual(ohlcv.open, 10.0)
        self.assertEqual(ohlcv.high, 10.5)
        self.assertEqual(ohlcv.low, 9.8)
        self.assertEqual(ohlcv.close, 10.3)
        self.assertEqual(ohlcv.volume, 1000000)


class TestIntegrationBacktest(unittest.TestCase):
    def setUp(self):
        self.sample_candles = [
            {"date": "2026-01-02", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.3, "volume": 1000000},
            {"date": "2026-01-03", "open": 10.3, "high": 10.8, "low": 10.2, "close": 10.5, "volume": 1100000},
            {"date": "2026-01-06", "open": 10.5, "high": 11.0, "low": 10.4, "close": 10.8, "volume": 1200000},
            {"date": "2026-01-07", "open": 10.8, "high": 11.2, "low": 10.7, "close": 11.0, "volume": 1300000},
            {"date": "2026-01-08", "open": 11.0, "high": 11.5, "low": 10.9, "close": 11.2, "volume": 1400000},
        ]

        self.sample_signals = [
            {"date": "2026-01-02", "action": "buy", "reason": "信号1"},
            {"date": "2026-01-07", "action": "sell", "reason": "信号2"},
        ]

    def test_backtest_with_indicators(self):
        indicators = calc_full_indicators(self.sample_candles)

        atr = indicators["atr"].atr
        stop_loss_pct = 0.05
        take_profit_pct = 0.10

        result = run_simple_backtest(
            "600000",
            self.sample_candles,
            self.sample_signals,
            initial_capital=50000.0
        )

        self.assertEqual(result.stock_code, "600000")
        self.assertEqual(result.initial_capital, 50000.0)
        self.assertGreater(result.final_capital, 0)
        self.assertGreater(len(result.trades), 0)
        self.assertIn("total_return", result.metrics.to_dict())

    def test_backtest_runner_reset(self):
        runner = BacktestRunner(initial_capital=100000)

        runner.buy("2026-01-02", 10.0)
        self.assertIsNotNone(runner.position)

        runner.reset()
        self.assertIsNone(runner.position)
        self.assertEqual(runner.cash, 100000)

    def test_backtest_stop_loss_trigger(self):
        runner = BacktestRunner(initial_capital=100000)

        runner.buy("2026-01-02", 10.0, stop_loss=9.5)
        self.assertIsNotNone(runner.position)

        triggered = runner.check_stop_loss("2026-01-03", 9.4)
        self.assertTrue(triggered)
        self.assertIsNone(runner.position)


class TestIntegrationReportQuality(unittest.TestCase):
    def test_quality_gate_module_import(self):
        from report_quality_gate import run_quality_gate
        self.assertTrue(callable(run_quality_gate))


class TestIntegrationCrossModule(unittest.TestCase):
    def test_stock_to_indicators_pipeline(self):
        code = "600519"
        name = normalize_stock_name("贵州茅台")
        self.assertIsNotNone(name)

        sample_data = [
            {"date": "2026-01-02", "open": 100.0, "high": 105.0, "low": 99.0, "close": 103.0, "volume": 5000000},
            {"date": "2026-01-03", "open": 103.0, "high": 108.0, "low": 102.0, "close": 106.0, "volume": 5500000},
        ]

        indicators = calc_full_indicators(sample_data)

        self.assertGreater(indicators["price"], 0)
        self.assertGreater(indicators["atr"].atr, 0)

    def test_indicators_to_backtest_pipeline(self):
        candles = [
            {"date": "2026-01-02", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.3, "volume": 1000000},
            {"date": "2026-01-03", "open": 10.3, "high": 10.8, "low": 10.2, "close": 10.5, "volume": 1100000},
            {"date": "2026-01-06", "open": 10.5, "high": 11.0, "low": 10.4, "close": 10.8, "volume": 1200000},
        ]

        indicators = calc_full_indicators(candles)

        signals = []
        if indicators["vwap"].deviation_pct > 2:
            signals.append({"date": candles[0]["date"], "action": "buy", "reason": "VWAP偏离"})
        if indicators["rsi"] > 70:
            signals.append({"date": candles[-1]["date"], "action": "sell", "reason": "RSI超买"})

        if not signals:
            signals = [{"date": candles[0]["date"], "action": "buy", "reason": "默认买入"}]

        result = run_simple_backtest("TEST", candles, signals, initial_capital=100000)

        self.assertIsNotNone(result)
        self.assertGreater(len(result.to_dict()), 0)


class TestIntegrationPlatformPaths(unittest.TestCase):
    def test_platform_paths_module(self):
        try:
            from platform_paths import get_platform_cache_dir, get_skill_root
            cache_dir = get_platform_cache_dir()
            self.assertIsInstance(cache_dir, Path)
            self.assertTrue(str(cache_dir))
        except ImportError:
            self.skipTest("platform_paths not available")

    def test_cross_module_cache_awareness(self):
        pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
