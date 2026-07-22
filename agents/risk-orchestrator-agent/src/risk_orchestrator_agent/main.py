"""main.py -- the canonical Orchestrator entry point (master prompt S1-S2).

Was an empty stub in both source snapshots, and this codebase's own
internal comments (`memory/repository_manager.py`: "the actual pools are
constructed by agent.py's composition root") assumed a not-yet-created
`agent.py` would be that root instead. This file supersedes that
assumption deliberately: the master prompt asks for one main
orchestrator file, `main.py` is the file already reserved for that role
in every existing Dockerfile / pyproject entry point, and introducing a
second `agent.py` alongside it would recreate exactly the "which file is
authoritative" ambiguity this consolidation exists to remove (see
docs/RECONCILIATION_REPORT.md).

`build_orchestrator()` is pure composition -- construct every domain
service, wire the pipeline, return an `Orchestrator`. No I/O, fully
unit-testable without a running Kafka/Redis/Postgres/Neo4j.

`run()` is the process entry point: resolves real infra clients from
environment config, builds the orchestrator, and drives the consume loop.

**Gap, stated plainly** (docs/RECONCILIATION_REPORT.md S6, gap #6): the
bridge between `sentinel_eventbus.consumer.EventConsumer` (which
deserializes into typed Pydantic models) and `handlers/consumers.py`'s
`EventRouter` (which expects a raw dict per `AgentResultDTO.from_raw`) is
new, small, and untested against a live broker in this environment --
`_pydantic_to_raw` below is a reasonable, direct mapping, not a
claim that the full consume loop has been run end-to-end.
"""

from __future__ import annotations

import asyncio
import logging
import os

from risk_orchestrator_agent.application.orchestration_pipeline import Orchestrator
from risk_orchestrator_agent.application.scoring_pipeline import OperationalContextPipeline
from risk_orchestrator_agent.domain.context.context_builder import ContextBuilder
from risk_orchestrator_agent.domain.correlation.correlation_engine import CorrelationEngine
from risk_orchestrator_agent.domain.decision.decision_engine import DecisionEngine
from risk_orchestrator_agent.domain.explanation.explanation_builder import ExplanationBuilder
from risk_orchestrator_agent.domain.rules.rule_engine import RuleEngine
from risk_orchestrator_agent.domain.scoring.cross_zone import CrossZoneRiskAnalyzer
from risk_orchestrator_agent.domain.scoring.risk_scorer import RiskScorer
from risk_orchestrator_agent.dto.agent_result_dto import AgentResultDTO, AgentResultValidationError
from risk_orchestrator_agent.handlers.consumers import INBOUND_TOPICS, EventRouter
from risk_orchestrator_agent.handlers.publishers import LoggingEventPublisher, RiskScoreEventPublisher
from risk_orchestrator_agent.health import HealthRegistry
from risk_orchestrator_agent.memory.repository_manager import RepositoryManager
from risk_orchestrator_agent.services.context_replay_service import ContextReplayService

logger = logging.getLogger(__name__)


def build_orchestrator(
    repository_manager: RepositoryManager,
    *,
    publisher=None,
    event_producer=None,
    replay_service: ContextReplayService | None = None,
) -> tuple[Orchestrator, EventRouter]:
    """Pure composition root (master prompt S20 Step 5: "one canonical
    Orchestrator, one canonical execution lifecycle"). Returns the
    Orchestrator plus the EventRouter already wired to dispatch into it,
    so a caller only needs to feed `(topic, raw_dict)` pairs into
    `event_router.route(...)`.

    `publisher` takes precedence if given. Otherwise, `event_producer`
    (a `sentinel_eventbus.producer.EventProducer` -- Kafka-backed in
    production, `InMemoryTransport`-backed for local/dev/test) is wrapped
    in the real `RiskScoreEventPublisher`. With neither, this falls back
    to `LoggingEventPublisher` (Phase 6: "use ... an in-memory transport or
    runtime bridge for development ... rather than blocking the entire
    implementation on full production infrastructure").
    """
    if publisher is None:
        publisher = RiskScoreEventPublisher(event_producer) if event_producer is not None else LoggingEventPublisher()
    context_builder = ContextBuilder(
        context_port=repository_manager.context_repository,
        history_port=repository_manager.history_repository,
        graph_port=repository_manager.graph_repository,
    )
    correlation_engine = CorrelationEngine()
    context_pipeline = OperationalContextPipeline(
        context_builder=context_builder,
        correlation_engine=correlation_engine,
        replay_service=replay_service,
    )

    orchestrator = Orchestrator(
        context_pipeline=context_pipeline,
        rule_engine=RuleEngine(),
        risk_scorer=RiskScorer(),
        cross_zone_analyzer=CrossZoneRiskAnalyzer(),
        decision_engine=DecisionEngine(),
        explanation_builder=ExplanationBuilder(),
        publisher=publisher,
        history_port=repository_manager.history_repository,
    )

    async def _handler(dto: AgentResultDTO) -> None:
        await orchestrator.handle_event(dto)

    event_router = EventRouter(handler=_handler)
    return orchestrator, event_router


def _pydantic_to_raw(event) -> dict:
    """Bridges `sentinel_eventbus.consumer.EventConsumer`'s deserialized
    Pydantic model to the raw-dict shape `EventRouter`/`AgentResultDTO`
    expect. See module docstring gap #6."""
    return event.model_dump(mode="json")


def register_health_checks(health: HealthRegistry, repository_manager: RepositoryManager) -> None:
    async def _context_repo_check() -> bool:
        try:
            await repository_manager.context_repository.get("__health_check__")
            return True
        except Exception:  # noqa: BLE001
            return False

    health.register("context_repository", _context_repo_check)

    if repository_manager.history_repository is not None:
        async def _history_repo_check() -> bool:
            try:
                await repository_manager.history_repository.get_previous_severity("__health_check__")
                return True
            except Exception:  # noqa: BLE001
                return False

        health.register("history_repository", _history_repo_check)


async def run() -> None:
    """Process entry point. Resolves infra clients from environment
    config, builds the Orchestrator, and drives the Kafka consume loop.

    Left as an explicit, readable bootstrap rather than a framework/CLI
    wrapper, so the composition (`build_orchestrator`) stays the single
    part of this file worth unit-testing in isolation.
    """
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

    redis_client = None  # TODO: construct from REDIS_URL env var
    postgres_pool = None  # TODO: construct from POSTGRES_DSN env var
    neo4j_driver = None  # TODO: construct from NEO4J_URI env var

    if redis_client is None:
        raise RuntimeError(
            "main.run() needs a real Redis client wired in before it can serve "
            "traffic -- ContextBuilder cannot operate without ContextRepositoryPort. "
            "See docs/RECONCILIATION_REPORT.md S6, gap #7 (infra bootstrapping was "
            "out of scope for both source snapshots and for this consolidation pass)."
        )

    repository_manager = RepositoryManager.from_clients(
        redis_client=redis_client,
        postgres_pool=postgres_pool,
        neo4j_driver=neo4j_driver,
    )

    orchestrator, event_router = build_orchestrator(repository_manager)

    health = HealthRegistry()
    register_health_checks(health, repository_manager)

    # TODO (gap #6): construct sentinel_eventbus's Transport/EventConsumer
    # here, subscribe to INBOUND_TOPICS, and for each polled message call:
    #   await event_router.route(topic, _pydantic_to_raw(event))
    # Not wired in this pass -- no live broker/schema-registry connection
    # exists in this environment to validate the loop against.
    logger.info("orchestrator_composed", extra={"inbound_topics": list(INBOUND_TOPICS)})


if __name__ == "__main__":
    asyncio.run(run())
