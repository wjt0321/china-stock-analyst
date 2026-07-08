import logging
from typing import Any

from desktop.config_manager import ConfigManager
from desktop.quant_flow import calc_proxy_fund_flow
from scripts.technical_indicators import calc_full_indicators

LOGGER = logging.getLogger(__name__)


class AnalysisEngine:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.cfg = config.get_analysis_config()

    def analyze(self, stock_code: str, validated_data: dict) -> dict:
        report = {
            "stock_code": stock_code,
            "audit_gate": self._run_data_auditor(validated_data),
            "expert_outputs": self._run_experts(validated_data),
            "expert_identity_gate": self._run_identity_gate(validated_data),
            "supervisor_review": {},
            "scoring": {},
            "verdict": "观察",
            "confidence": "中",
            "reasoning": [],
        }
        report["supervisor_review"] = self._run_supervisor_review(report)
        report["scoring"] = self._calculate_score(report)
        report["verdict"], report["confidence"] = self._derive_verdict(report)
        report["reasoning"] = self._build_reasoning(report)
        return report

    def _run_data_auditor(self, validated_data: dict) -> dict:
        # Expanded in Task 10
        return {"passed": True, "notes": []}

    def _run_experts(self, validated_data: dict) -> dict:
        return {
            "technical": self._technical_expert(validated_data),
            "fundamental": self._fundamental_expert(validated_data),
            "quant_flow": self._quant_flow_expert(validated_data),
            "risk": self._risk_expert(validated_data),
            "macro": self._macro_expert(validated_data),
            "industry": self._industry_expert(validated_data),
            "event": self._event_expert(validated_data),
        }

    def _pick_candles(self, validated_data: dict) -> tuple[list, str]:
        """Return the best available OHLCV candles and the source name.

        Preference follows config.source_priority; any source suffixed with
        `_candles` is eligible.  This removes the hard dependency on AKShare
        when lightweight HTTP K-line APIs (Sina/Tencent) are available.
        """
        priority = self.config.get_source_priority()
        for source in priority:
            key = f"{source}_candles"
            field = validated_data.get(key)
            if not field:
                continue
            candles = field.get("value", [])
            if candles and len(candles) >= 20:
                return candles, source

        # Final fallback: any candles with enough history.
        for key, field in validated_data.items():
            if key.endswith("_candles"):
                candles = field.get("value", [])
                if candles and len(candles) >= 20:
                    return candles, key.replace("_candles", "")

        return [], ""

    def _technical_expert(self, validated_data: dict) -> dict:
        candles, source = self._pick_candles(validated_data)
        if not candles or len(candles) < 20:
            return {"view": "数据不足", "decision_hint": "观察", "evidences": ["K线数据不足"]}

        indicators = calc_full_indicators(candles)
        price = validated_data.get("price", {}).get("value")
        current_close = indicators.get("price")
        vwap_result = indicators.get("vwap")
        vwap = vwap_result.vwap if vwap_result else None
        rsi = indicators.get("rsi")
        atr_result = indicators.get("atr")
        atr = atr_result.atr if atr_result else None
        sr = indicators.get("support_resistance")
        volume_ratio = indicators.get("volume_ratio")
        momentum = indicators.get("momentum")
        interpretation = indicators.get("interpretation", "")

        hints = []
        if source:
            hints.append(f"K线来源: {source}，共 {len(candles)} 个交易日")

        if price is not None:
            hints.append(f"当前价 {price:.2f}")

        if vwap is not None and current_close:
            deviation = (current_close - vwap) / vwap
            position = "高于" if deviation > 0 else "低于"
            hints.append(
                f"收盘价 {current_close:.2f} {position} VWAP {vwap:.2f}（偏离 {deviation*100:.2f}%）"
            )

        if rsi is not None:
            rsi_desc = "超买" if rsi > 70 else "超卖" if rsi < 30 else "中性"
            hints.append(f"RSI({len(candles)-1:.0f}) = {rsi:.2f}，{rsi_desc}")

        if atr is not None and current_close:
            atr_pct = atr / current_close * 100
            hints.append(f"ATR = {atr:.4f}（约占当前价 {atr_pct:.2f}%，衡量日内波动）")

        nearest_support = sr.nearest_support if sr else None
        nearest_resistance = sr.nearest_resistance if sr else None
        if nearest_support is not None and nearest_resistance is not None:
            hints.append(
                f"最近支撑位 {nearest_support:.2f}，压力位 {nearest_resistance:.2f}"
            )
        elif nearest_support is not None:
            hints.append(f"最近支撑位 {nearest_support:.2f}")
        elif nearest_resistance is not None:
            hints.append(f"最近压力位 {nearest_resistance:.2f}")

        if volume_ratio is not None:
            vol_desc = "放大" if volume_ratio > 1.2 else "萎缩" if volume_ratio < 0.8 else "持平"
            hints.append(f"量比 {volume_ratio:.2f}，成交量较近期平均{vol_desc}")

        if momentum is not None:
            trend = "上涨" if momentum > 0 else "下跌"
            hints.append(f"近 {min(10, len(candles)-1)} 日动量 {momentum:.2f}%，趋势{trend}")

        if interpretation:
            hints.append(f"综合信号：{interpretation}")

        decision = "观察"
        if rsi is not None:
            if rsi > 70:
                decision = "回避"
            elif rsi < 30:
                decision = "可做"

        return {
            "view": "多头" if decision == "可做" else "空头" if decision == "回避" else "震荡",
            "decision_hint": decision,
            "indicators": {
                "vwap": vwap,
                "rsi": rsi,
                "atr": atr,
                "support_resistance": {
                    "nearest_support": nearest_support,
                    "nearest_resistance": nearest_resistance,
                },
                "volume_ratio": volume_ratio,
                "momentum": momentum,
                "current_close": current_close,
            },
            "evidences": hints,
        }

    def _fundamental_expert(self, validated_data: dict) -> dict:
        pe = validated_data.get("pe_ttm", {}).get("value")
        pb = validated_data.get("pb", {}).get("value")
        market_cap = validated_data.get("market_cap", {}).get("value")
        price = validated_data.get("price", {}).get("value")

        hints = []
        if price is not None:
            hints.append(f"最新价 {price:.2f} 元")
        if market_cap is not None:
            hints.append(f"总市值约 {market_cap:.2f} 亿元")
        if pe is not None:
            pe_desc = "偏高" if pe > 30 else "偏低" if pe < 10 else "合理"
            hints.append(f"市盈率(TTM) {pe:.2f} 倍，估值{pe_desc}")
        if pb is not None:
            pb_desc = "偏高" if pb > 3 else "偏低" if pb < 1 else "合理"
            hints.append(f"市净率 {pb:.2f} 倍，{pb_desc}")

        if not hints:
            return {"view": "数据不足", "decision_hint": "观察", "evidences": ["缺少估值/市值数据"]}

        # Simple rule-based valuation signal.
        score = 0
        if pe is not None:
            if pe < 15:
                score += 1
            elif pe > 50:
                score -= 1
        if pb is not None:
            if pb < 1.5:
                score += 1
            elif pb > 5:
                score -= 1

        decision = "可做" if score >= 2 else "回避" if score <= -2 else "观察"
        view = "低估" if decision == "可做" else "高估" if decision == "回避" else "中性"
        return {
            "view": view,
            "decision_hint": decision,
            "indicators": {"pe_ttm": pe, "pb": pb, "market_cap": market_cap},
            "evidences": hints,
        }

    def _quant_flow_expert(self, validated_data: dict) -> dict:
        candles, source = self._pick_candles(validated_data)
        if not candles or len(candles) < 5:
            return {"view": "数据不足", "decision_hint": "观察", "evidences": ["缺乏K线数据，无法估算资金流向"]}

        flow = calc_proxy_fund_flow(candles, recent_days=5)
        direction = flow.get("direction", "neutral")
        intensity = flow.get("intensity", "weak")
        recent_net_pct = flow.get("recent_net_pct", 0.0)

        hints = [
            f"数据来源: {source} K线（估算资金流向，非交易所真实资金流）",
            flow.get("summary", ""),
            f"近5日净流入占比: {recent_net_pct:.2f}%",
        ]

        decision = "观察"
        if direction == "inflow" and intensity in ("strong", "moderate"):
            decision = "可做"
        elif direction == "outflow" and intensity == "strong":
            decision = "回避"

        view = "多头" if decision == "可做" else "空头" if decision == "回避" else "中性"
        return {
            "view": view,
            "decision_hint": decision,
            "indicators": flow,
            "evidences": [h for h in hints if h],
        }

    def _risk_expert(self, validated_data: dict) -> dict:
        candles, source = self._pick_candles(validated_data)
        price = validated_data.get("price", {}).get("value")
        turnover_rate = validated_data.get("turnover_rate", {}).get("value")
        amplitude = validated_data.get("amplitude", {}).get("value")

        if not candles or len(candles) < 2 or price is None:
            return {"view": "数据不足", "decision_hint": "观察", "evidences": ["缺少K线或价格数据"]}

        indicators = calc_full_indicators(candles)
        atr_result = indicators.get("atr")
        atr = atr_result.atr if atr_result else None
        sr = indicators.get("support_resistance")
        nearest_support = sr.nearest_support if sr else None

        hints = []
        if atr is not None:
            stop_loss = price - atr * 2
            hints.append(f"ATR = {atr:.4f}，建议止损位约 {stop_loss:.2f} 元")
        if nearest_support is not None:
            hints.append(f"最近支撑位 {nearest_support:.2f} 元")
        if turnover_rate is not None:
            liquidity = "活跃" if turnover_rate > 3 else "一般" if turnover_rate > 1 else "清淡"
            hints.append(f"换手率 {turnover_rate:.2f}%，流动性{liquidity}")
        if amplitude is not None:
            vol_desc = "高波动" if amplitude > 5 else "中等波动" if amplitude > 2 else "低波动"
            hints.append(f"当日振幅 {amplitude:.2f}%，{vol_desc}")

        # Risk score: higher risk when high volatility + low liquidity.
        risk_score = 0
        if amplitude is not None and amplitude > 5:
            risk_score += 1
        if turnover_rate is not None and turnover_rate < 1:
            risk_score += 1
        if atr is not None and price and atr / price > 0.05:
            risk_score += 1

        decision = "回避" if risk_score >= 2 else "观察" if risk_score == 1 else "可做"
        view = "高风险" if decision == "回避" else "可控"
        return {
            "view": view,
            "decision_hint": decision,
            "indicators": {
                "atr": atr,
                "stop_loss": round(price - atr * 2, 2) if atr else None,
                "nearest_support": nearest_support,
                "turnover_rate": turnover_rate,
                "amplitude": amplitude,
            },
            "evidences": hints,
        }

    def _macro_expert(self, validated_data: dict) -> dict:
        macro = validated_data.get("akshare_macro", {}).get("value", {})
        if not macro:
            return {"view": "数据不足", "decision_hint": "观察", "evidences": ["缺少大盘指数数据"]}

        change_pct = macro.get("change_pct", 0.0)
        hints = [
            f"上证指数近{macro.get('days', 5)}日变化 {change_pct:+.2f}%",
            f"区间收盘 {macro.get('start_close')} -> {macro.get('end_close')}",
        ]

        if change_pct > 2:
            decision = "可做"
            view = "偏多"
        elif change_pct < -2:
            decision = "回避"
            view = "偏空"
        else:
            decision = "观察"
            view = "中性"

        return {
            "view": view,
            "decision_hint": decision,
            "indicators": macro,
            "evidences": hints,
        }

    def _industry_expert(self, validated_data: dict) -> dict:
        # Industry classification sources are blocked/unstable in this environment.
        # We keep the expert slot but mark it as lacking data.
        return {
            "view": "数据不足",
            "decision_hint": "观察",
            "evidences": ["行业分类数据源暂不可用，待接入后补充"],
        }

    def _event_expert(self, validated_data: dict) -> dict:
        news = validated_data.get("akshare_news", {}).get("value", [])
        if not news:
            return {"view": "数据不足", "decision_hint": "观察", "evidences": ["暂无相关新闻"]}

        headlines = [n.get("title", "") for n in news[:5]]
        hints = ["近期新闻标题:"] + [f"- {h}" for h in headlines if h]

        # Very simple sentiment proxy based on keyword matching.
        bullish = sum(1 for h in headlines if any(k in h for k in ["涨", "反弹", "利好", "预增", "突破", "增持"]))
        bearish = sum(1 for h in headlines if any(k in h for k in ["跌", "下跌", "利空", "预减", "减持", "监管", "处罚"]))

        if bullish > bearish:
            decision = "可做"
            view = "偏多"
        elif bearish > bullish:
            decision = "回避"
            view = "偏空"
        else:
            decision = "观察"
            view = "中性"

        return {
            "view": view,
            "decision_hint": decision,
            "indicators": {"headlines": headlines[:5], "bullish": bullish, "bearish": bearish},
            "evidences": hints,
        }

    def _run_identity_gate(self, validated_data: dict) -> dict:
        price = validated_data.get("price", {}).get("value")
        notes = []
        if price is None:
            notes.append("缺少实时价格，身份校验不完整")
        return {"passed": True, "require_block": False, "notes": notes}

    def _run_supervisor_review(self, report: dict) -> dict:
        hints = [e.get("decision_hint", "观察") for e in report["expert_outputs"].values()]
        bullish = hints.count("可做")
        bearish = hints.count("回避")
        neutral = len(hints) - bullish - bearish

        if bullish > bearish and bullish >= 3:
            consensus = "可做"
        elif bearish > bullish and bearish >= 3:
            consensus = "回避"
        else:
            consensus = "观察"

        conflict_items = []
        if bullish > 0 and bearish > 0:
            conflict_items.append(f"存在分歧：{bullish} 位专家看多，{bearish} 位专家看空")

        return {
            "consensus": consensus,
            "conflict_items": conflict_items,
            "summary": f"看多{bullish} / 看空{bearish} / 中性{neutral}",
        }

    def _calculate_score(self, report: dict) -> dict:
        cfg = self.cfg
        technical_hint = report["expert_outputs"]["technical"]["decision_hint"]
        quant_hint = report["expert_outputs"]["quant_flow"]["decision_hint"]

        short_term = self._hint_to_score(technical_hint) * 0.5 + self._hint_to_score(quant_hint) * 0.5
        fundamental = self._hint_to_score(report["expert_outputs"]["fundamental"]["decision_hint"])
        risk = self._hint_to_score(report["expert_outputs"]["risk"]["decision_hint"])

        total = (
            short_term * cfg["short_term_weight"]
            + fundamental * cfg["fundamental_weight"]
            + risk * cfg["sentiment_weight"]
        )
        return {"short_term": short_term, "fundamental": fundamental, "risk": risk, "total": round(total, 2)}

    def _hint_to_score(self, hint: str) -> float:
        mapping = {"可做": 80, "观察": 55, "回避": 30, "数据不足": 50, "中性": 55}
        return mapping.get(hint, 50)

    def _derive_verdict(self, report: dict) -> tuple[str, str]:
        total = report["scoring"]["total"]
        if total >= 70:
            return "可做", "中"
        if total >= 50:
            return "观察", "中"
        return "回避", "低"

    def _build_reasoning(self, report: dict) -> list[str]:
        technical = report["expert_outputs"].get("technical", {})
        reasoning: list[str] = []

        if technical.get("view") == "数据不足":
            reasoning.append("技术分析所需K线数据不足，建议待数据恢复后再评估。")
            return reasoning

        indicators = technical.get("indicators", {})
        rsi = indicators.get("rsi")
        momentum = indicators.get("momentum")
        vwap = indicators.get("vwap")
        current_close = indicators.get("current_close")

        view = technical.get("view", "震荡")
        hint = technical.get("decision_hint", "观察")
        reasoning.append(f"技术面判断为「{view}」，建议「{hint}」")

        if rsi is not None:
            rsi_desc = "超买区间" if rsi > 70 else "超卖区间" if rsi < 30 else "中性区间"
            reasoning.append(f"RSI 处于{rsi_desc}（{rsi:.2f}）")

        if momentum is not None:
            trend = "上涨" if momentum > 0 else "下跌"
            reasoning.append(f"短期动量 {momentum:.2f}%，呈{trend}趋势")

        if current_close and vwap:
            deviation = (current_close - vwap) / vwap * 100
            position = "上方" if deviation > 0 else "下方"
            reasoning.append(f"价格位于 VWAP {position}，偏离 {deviation:.2f}%")

        # Quant flow now also has a real signal derived from K-line.
        quant_flow = report["expert_outputs"].get("quant_flow", {})
        if quant_flow.get("evidences"):
            q_hint = quant_flow.get("decision_hint", "观察")
            q_view = quant_flow.get("view", "中性")
            reasoning.append(f"资金面（K线估算）判断为「{q_view}」，建议「{q_hint}」")
            q_summary = quant_flow.get("indicators", {}).get("summary", "")
            if q_summary:
                reasoning.append(q_summary)

        # Note when other experts are still placeholder/neutral.
        neutral_experts = [
            name
            for name, output in report["expert_outputs"].items()
            if name not in ("technical", "quant_flow") and output.get("decision_hint") == "观察" and not output.get("evidences")
        ]
        if neutral_experts:
            reasoning.append(
                f"{'、'.join(neutral_experts)} 等维度暂无有效数据源，整体评分偏保守。"
            )

        return reasoning
