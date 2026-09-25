"""
Analytics and telemetry engine for time-series aggregation, funnel tracking, and metric reporting.
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

try:
    from events import events
except ImportError:
    from src.events import events


VALID_AGGREGATIONS = {"avg", "sum", "count", "min", "max"}


@dataclass
class MetricDataPoint:
    """Represents a single time-series metric data point."""
    metric_name: str
    value: float
    unit: str = "count"
    tags: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AnalyticsEngine:
    """Manages telemetry metric ingestion, time-series aggregation, and funnel tracking."""

    def __init__(self, max_points: int = 10000):
        self._points: List[MetricDataPoint] = []
        self._funnels: Dict[str, List[Dict[str, Any]]] = {}
        self._max_points = max_points

    def record_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "count",
        tags: Optional[Dict[str, str]] = None,
    ) -> MetricDataPoint:
        """Record a time-series metric data point."""
        if not metric_name or not metric_name.strip():
            raise ValueError("Metric name cannot be empty.")

        clean_name = metric_name.strip().lower()
        point = MetricDataPoint(
            metric_name=clean_name,
            value=float(value),
            unit=unit,
            tags=tags or {},
            timestamp=time.time(),
        )

        self._points.append(point)
        if len(self._points) > self._max_points:
            self._points = self._points[-self._max_points:]

        events.publish("metric_recorded", {"metric": clean_name, "value": value, "unit": unit})
        return point

    def get_metric_series(
        self,
        metric_name: str,
        aggregation: str = "avg",
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Retrieve aggregated summary statistics for a metric series."""
        clean_name = metric_name.strip().lower()
        if aggregation not in VALID_AGGREGATIONS:
            raise ValueError(f"Invalid aggregation '{aggregation}'. Valid: {sorted(VALID_AGGREGATIONS)}")

        matched = [p for p in self._points if p.metric_name == clean_name]
        if limit and limit > 0:
            matched = matched[-limit:]

        if not matched:
            return {
                "metric_name": clean_name,
                "count": 0,
                "aggregation": aggregation,
                "aggregate_value": 0.0,
                "points": [],
            }

        values = [p.value for p in matched]
        if aggregation == "avg":
            agg_val = sum(values) / len(values)
        elif aggregation == "sum":
            agg_val = sum(values)
        elif aggregation == "count":
            agg_val = float(len(values))
        elif aggregation == "min":
            agg_val = min(values)
        elif aggregation == "max":
            agg_val = max(values)
        else:
            agg_val = sum(values) / len(values)

        return {
            "metric_name": clean_name,
            "count": len(matched),
            "aggregation": aggregation,
            "aggregate_value": round(agg_val, 4),
            "latest_value": matched[-1].value,
            "unit": matched[-1].unit,
            "points": [p.to_dict() for p in matched],
        }

    def track_funnel_step(self, funnel_name: str, step_name: str, user_id: str) -> Dict[str, Any]:
        """Track user progression into a specific funnel step."""
        if not funnel_name or not funnel_name.strip():
            raise ValueError("Funnel name cannot be empty.")
        if not step_name or not step_name.strip():
            raise ValueError("Step name cannot be empty.")
        if not user_id or not user_id.strip():
            raise ValueError("User ID cannot be empty.")

        f_name = funnel_name.strip().lower()
        s_name = step_name.strip().lower()
        u_id = user_id.strip()

        if f_name not in self._funnels:
            self._funnels[f_name] = []

        entry = {"step": s_name, "user_id": u_id, "timestamp": time.time()}
        self._funnels[f_name].append(entry)

        events.publish("funnel_step_tracked", {"funnel": f_name, "step": s_name, "user_id": u_id})
        return entry

    def get_funnel_report(self, funnel_name: str) -> Dict[str, Any]:
        """Compute funnel step counts and conversion drop-offs."""
        f_name = funnel_name.strip().lower()
        events_list = self._funnels.get(f_name, [])

        step_users: Dict[str, set] = {}
        ordered_steps = []
        for e in events_list:
            step = e["step"]
            if step not in step_users:
                step_users[step] = set()
                ordered_steps.append(step)
            step_users[step].add(e["user_id"])

        steps_data = []
        base_count = len(step_users[ordered_steps[0]]) if ordered_steps else 0

        for idx, step in enumerate(ordered_steps):
            count = len(step_users[step])
            conv_rate = (count / base_count * 100.0) if base_count > 0 else 0.0
            steps_data.append({
                "step": step,
                "unique_users": count,
                "conversion_rate_pct": round(conv_rate, 2),
            })

        return {
            "funnel_name": f_name,
            "total_events": len(events_list),
            "steps": steps_data,
        }

    def list_metric_names(self) -> List[str]:
        """List distinct metric names collected."""
        distinct = sorted(list(set(p.metric_name for p in self._points)))
        return distinct

    def get_stats(self) -> Dict[str, Any]:
        """Retrieve aggregated analytics telemetry stats."""
        distinct_metrics = self.list_metric_names()
        return {
            "total_data_points": len(self._points),
            "distinct_metrics_count": len(distinct_metrics),
            "metrics": distinct_metrics,
            "active_funnels_count": len(self._funnels),
        }

    def clear(self) -> None:
        """Clear all analytics and funnel data."""
        self._points.clear()
        self._funnels.clear()


# Global analytics engine instance
analytics = AnalyticsEngine()
