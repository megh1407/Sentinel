"""
metrics.py

Thin wrapper over prometheus_client, auto-prefixing every metric name with
`sentinel_{service}_` so dashboards are consistent across every agent
without each agent author hand-typing the prefix.
"""
from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


class MetricsRegistry:
    def __init__(self, service_name: str, registry: CollectorRegistry | None = None):
        self._service_name = service_name.replace("-", "_")
        self._registry = registry or CollectorRegistry()
        self._metrics: dict[str, Counter | Gauge | Histogram] = {}

    def _full_name(self, name: str) -> str:
        return f"sentinel_{self._service_name}_{name}"

    def counter(self, name: str, description: str, labels: list[str] | None = None) -> Counter:
        full = self._full_name(name)
        if full not in self._metrics:
            self._metrics[full] = Counter(full, description, labels or [], registry=self._registry)
        return self._metrics[full]

    def histogram(self, name: str, description: str, buckets: tuple[float, ...] | None = None,
                  labels: list[str] | None = None) -> Histogram:
        full = self._full_name(name)
        if full not in self._metrics:
            kwargs = {"registry": self._registry}
            if buckets is not None:
                kwargs["buckets"] = buckets
            self._metrics[full] = Histogram(full, description, labels or [], **kwargs)
        return self._metrics[full]

    def gauge(self, name: str, description: str, labels: list[str] | None = None) -> Gauge:
        full = self._full_name(name)
        if full not in self._metrics:
            self._metrics[full] = Gauge(full, description, labels or [], registry=self._registry)
        return self._metrics[full]

    @property
    def registry(self) -> CollectorRegistry:
        return self._registry
