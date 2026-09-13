"""
Metrics and telemetry collection layer for tracking API requests and latency.
"""

import time
from typing import Dict, Any, List


class MetricsCollector:
    """Collects endpoint invocation statistics, latencies, and error rates."""

    def __init__(self):
        self._request_counts: Dict[str, int] = {}
        self._error_counts: Dict[str, int] = {}
        self._latencies: Dict[str, List[float]] = {}
        self._start_time = time.time()

    def record_request(self, endpoint: str, duration_ms: float, status_code: int) -> None:
        """Record an individual request event."""
        self._request_counts[endpoint] = self._request_counts.get(endpoint, 0) + 1

        if status_code >= 400:
            self._error_counts[endpoint] = self._error_counts.get(endpoint, 0) + 1

        if endpoint not in self._latencies:
            self._latencies[endpoint] = []
        self._latencies[endpoint].append(duration_ms)

    def get_summary(self) -> Dict[str, Any]:
        """Generate aggregated performance metrics summary."""
        total_requests = sum(self._request_counts.values())
        total_errors = sum(self._error_counts.values())

        endpoint_stats = {}
        for endpoint, counts in self._request_counts.items():
            durations = self._latencies.get(endpoint, [])
            avg_latency = sum(durations) / len(durations) if durations else 0.0
            endpoint_stats[endpoint] = {
                "requests": counts,
                "errors": self._error_counts.get(endpoint, 0),
                "avg_latency_ms": round(avg_latency, 2),
            }

        return {
            "uptime_seconds": round(time.time() - self._start_time, 2),
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate_pct": round((total_errors / total_requests * 100) if total_requests > 0 else 0.0, 2),
            "endpoints": endpoint_stats,
        }

    def reset(self) -> None:
        """Reset collected metrics."""
        self._request_counts.clear()
        self._error_counts.clear()
        self._latencies.clear()
        self._start_time = time.time()


# Global metrics collector instance
metrics = MetricsCollector()
