import logging
from typing import Any

from desktop.config_manager import ConfigManager
from scripts.technical_indicators import calc_full_indicators, indicators_to_dict

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
        candles = self._extract_candles(validated_data)
        if candles:
            indicators = calc_full_indicators(candles)
            indicators = indicators_to_dict(indicators)
            decision_hint = self._hint_from_indicators(indicators)
            return {
                "view": indicators.get("interpretation", "震荡"),
                "decision_hint": decision_hint,
                "evidences": [indicators],
            }
        return {"view": "震荡", "decision_hint": "观察", "evidences": []}

    def _extract_candles(self, validated_data: dict) -> list:
        for key in ("akshare_candles", "candles"):
            if key in validated_data:
                value = validated_data[key]
                if isinstance(value, dict):
                    return value.get("value", []) or []
                return value or []
        for key, value in validated_data.items():
            if "candles" in key:
                if isinstance(value, dict):
                    return value.get("value", []) or []
                return value or []
        return []

    def _hint_from_indicators(self, indicators: dict) -> str:
        rsi = indicators.get("rsi", 50)
        momentum = indicators.get("momentum", 0)
        interpretation = indicators.get("interpretation", "")
        if "偏多" in interpretation or "强劲" in interpretation or rsi > 60 or momentum > 5:
            return "可做"
        if "偏空" in interpretation or "疲弱" in interpretation or rsi < 40 or momentum < -5:
            return "回避"
        return "观察"

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
        return {"short_term": 50, "fundamental": 50, "risk": 50, "total": 50}

    def _derive_verdict(self, report: dict) -> tuple[str, str]:
        total = report["scoring"]["total"]
        if total >= 70:
            return "可做", "中"
        if total >= 50:
            return "观察", "中"
        return "回避", "低"

    def _build_reasoning(self, report: dict) -> list[str]:
        return ["基于当前数据综合评分得出"]
