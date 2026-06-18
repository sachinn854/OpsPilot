"""
Monitoring tools — query service health and metrics.

Mocked for now. A production version would call Prometheus, Datadog, or a
custom metrics API using credentials from the environment.
"""
from backend.tools.base import Tool, ToolResult


class GetServiceHealthTool(Tool):
    name = "get_service_health"
    description = (
        "Check the health and status of a running service. "
        "Returns uptime, latency, error rate, and recent alerts."
    )
    parameters = {
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Service name, e.g. 'api', 'worker', 'database'.",
            },
        },
        "required": ["service"],
    }

    async def run(self, service: str) -> ToolResult:
        # Mocked — wire a real metrics backend (Prometheus/Datadog) when ready.
        return ToolResult(
            ok=True,
            data={
                "service": service,
                "status": "healthy",
                "uptime_pct": 99.9,
                "latency_p99_ms": 42,
                "error_rate_pct": 0.1,
                "alerts": [],
                "note": "simulated (no metrics backend configured)",
            },
        )


class GetMetricsTool(Tool):
    name = "get_metrics"
    description = (
        "Fetch a named metric for a service over a time window. "
        "Returns a time-series of values."
    )
    parameters = {
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Service name.",
            },
            "metric": {
                "type": "string",
                "description": "Metric name, e.g. 'latency_p99', 'error_rate', 'rps'.",
            },
            "window": {
                "type": "string",
                "description": "Time window, e.g. '1h', '24h', '7d'.",
                "default": "1h",
            },
        },
        "required": ["service", "metric"],
    }

    async def run(self, service: str, metric: str, window: str = "1h") -> ToolResult:
        # Mocked.
        return ToolResult(
            ok=True,
            data={
                "service": service,
                "metric": metric,
                "window": window,
                "values": [{"t": "T+0m", "v": 38}, {"t": "T+30m", "v": 42}, {"t": "T+60m", "v": 40}],
                "note": "simulated (no metrics backend configured)",
            },
        )
