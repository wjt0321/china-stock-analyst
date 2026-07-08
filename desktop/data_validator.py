import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from desktop.config_manager import ConfigManager


@dataclass
class ValidatedField:
    value: Any = None
    sources: list[str] = field(default_factory=list)
    conflict: bool = False
    notes: list[str] = field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


class DataValidator:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.priority = config.get_source_priority()
        self.cfg = config.get_analysis_config()

    def validate(self, stock_code: str, raw_data: dict) -> dict[str, ValidatedField]:
        result: dict[str, ValidatedField] = {}

        numeric_fields = ["price", "change", "turnover"]
        for field in numeric_fields:
            values = []
            sources = []
            for source in self.priority:
                if source in raw_data and field in raw_data[source]:
                    v = raw_data[source][field]
                    if isinstance(v, (int, float)):
                        values.append((source, v))
                        sources.append(source)

            if not values:
                result[field] = ValidatedField(notes=["无有效数据源"])
                continue

            picked, method, conflict = self._resolve_numeric(values, field)
            notes = [f"来自 {len(values)} 个源", f"取值方式: {method}"]
            if conflict:
                notes.append("源间数值冲突")
            result[field] = ValidatedField(
                value=picked,
                sources=sources,
                conflict=conflict,
                notes=notes,
            )

        # Pass-through non-numeric data
        for source, fields in raw_data.items():
            for key in ["candles", "fund_flow", "news"]:
                if key in fields:
                    full_key = f"{source}_{key}"
                    result[full_key] = ValidatedField(
                        value=fields[key],
                        sources=[source],
                        conflict=False,
                    )

        return result

    def _resolve_numeric(self, values: list[tuple[str, float]], field: str) -> tuple[float, str, bool]:
        threshold = self.cfg.get(f"{field}_conflict_threshold", 0.01)
        if field == "change":
            threshold = self.cfg.get("change_conflict_threshold", 0.012)
        if field == "fund_flow":
            threshold = self.cfg.get("fund_flow_conflict_threshold", 0.35)

        # Round for voting
        rounded = [round(v, 2) for _, v in values]
        counts = Counter(rounded)
        most_common, count = counts.most_common(1)[0]

        if count >= 2 and len(values) >= 3:
            conflict = self._has_conflict([v for _, v in values], most_common, threshold)
            return most_common, "majority_vote", conflict

        # Median
        sorted_vals = sorted([v for _, v in values])
        median = statistics.median(sorted_vals)
        conflict = self._has_conflict(sorted_vals, median, threshold)

        # Priority fallback
        for source in self.priority:
            for src, val in values:
                if src == source:
                    return round(val, 2), "priority_fallback", conflict

        return round(median, 2), "median", conflict

    def _has_conflict(self, values: list[float], baseline: float, threshold: float) -> bool:
        if len(values) < 2:
            return False
        denom = max(abs(baseline), 1.0)
        return max(abs(v - baseline) for v in values) / denom > threshold
