"""
container.py

The DI container BaseAgent.initialize() builds and exposes as self.state /
self.logger / self.metrics / self.producer -- agent authors never
manually construct any of these.
"""
from __future__ import annotations

from dataclasses import dataclass

from sentinel_common.logging import get_logger
from sentinel_common.metrics import MetricsRegistry
from sentinel_eventbus import EventProducer
from sentinel_state import StateContainer

from .health import HealthRegistry


@dataclass
class Container:
    agent_name: str
    state: StateContainer
    producer: EventProducer
    logger: object
    metrics: MetricsRegistry
    health: HealthRegistry


def build_container(agent_name: str, state: StateContainer, producer: EventProducer) -> Container:
    logger = get_logger(agent_name)
    metrics = MetricsRegistry(agent_name)
    health = HealthRegistry()
    health.register_from_state_container(state)
    return Container(agent_name=agent_name, state=state, producer=producer, logger=logger, metrics=metrics, health=health)
