"""
base_agent.py

Every SENTINEL agent inherits from BaseAgent and implements exactly one
method: process(). Everything else -- consuming, publishing, retries,
metrics, tracing, health checks, graceful shutdown -- is handled by
AgentRunner (runner.py). This is what makes the "no agent-to-agent calls,
everything through Kafka" invariant structural: there is no publish() API
exposed to agent authors at all, only a return value from process().
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from .container import Container


class BaseAgent(ABC):
    container: Container  # injected by AgentRunner before initialize() is called

    def initialize(self) -> None:
        """Default no-op. Override for agent-specific setup (e.g. loading
        an ML model into memory once at startup), calling super().initialize()
        first if overridden."""

    def shutdown(self) -> None:
        """Default no-op. Override for agent-specific teardown, calling
        super().shutdown() last if overridden."""

    @abstractmethod
    def process(self, event: BaseModel) -> BaseModel | list[BaseModel] | None:
        """The one method every agent author implements. Pure business
        logic: read needed state via self.state, return a result event, a
        list of result events (for agents publishing more than one event
        type from a single input), or None. MUST raise a typed
        SentinelError subclass on failure, never a bare exception the
        runner has to guess about."""

    # -- convenience properties, backed by the injected Container --
    @property
    def state(self):
        return self.container.state

    @property
    def logger(self):
        return self.container.logger

    @property
    def metrics(self):
        return self.container.metrics

    @property
    def agent_name(self) -> str:
        return self.container.agent_name
