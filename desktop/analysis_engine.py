import logging
from typing import Any

from desktop.config_manager import ConfigManager
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

    def _technical_expert(self, validated_data: dict) -> dict:
        candles = validated_data.get("akshare_candles", {}).get("value", [])
        if not candles or len(candles) < 20:
            return {"view": "数据不足", "decision_hint": "观察", "evidences": ["K线数据不足"]}

        indicators = calc_full_indicators(candles)
        price = validated_data.get("price", {}).get("value")
        vwap_result = indicators.get("vwap")
        vwap = vwap_result.vwap if vwap_result else None
        rsi = indicators.get("rsi")
        atr_result = indicators.get("atr")
        atr = atr_result.atr if atr_result else None

        hints = []
        if price and vwap:
            deviation = (price - vwap) / vwap
            if deviation > 0.02:
                hints.append("价格高于 VWAP，短线偏强")
            elif deviation < -0.02:
                hints.append("价格低于 VWAP，短线偏弱")

        decision = "观察"
        if rsi is not None:
            if rsi > 70:
                decision = "回避"
            elif rsi < 30:
                decision = "可做"

        return {
            "view": "多头" if decision == "可做" else "空头" if decision == "回避" else "震荡",
            "decision_hint": decision,
            "indicators": {"vwap": vwap, "rsi": rsi, "atr": atr},
            "evidences": hints,
        }

    def _fundamental_expert(self, validated_data: dict) -> dict:
        return {"view": "中性", "decision_hint": "观察", "evidences": []}

    def _quant_flow_expert(self, validated_data: dict) -> dict:
        return {"view": "中性", "decision_hint": "观察", "evidences": []}

    def _risk_expert(self, validated_data: dict) -> dict:
        return {"view": "可控", "decision_hint": "观察", "evidences": []}

    def _macro_expert(self, validated_data: dict) -> dict:
        return {"view": "中性", "decision_hint": "观察", "evidences": []}

    def _industry_expert(self, validated_data: dict) -> dict:
        return {"view": "中性", "decision_hint": "观察", "evidences": []}

    def _event_expert(self, validated_data: dict) -> dict:
        return {"view": "中性", "decision_hint": "观察", "evidences": []}

    def _run_identity_gate(self, validated_data: dict) -> dict:
        return {"passed": True, "require_block": False, "notes": []}

    def _run_supervisor_review(self, report: dict) -> dict:
        return {"consensus": "观察", "conflict_items": []}

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
        return ["基于当前数据综合评分得出"]
