"""
runner.py

AgentRunner is the composition root: it wires EventConsumer, EventProducer,
and a BaseAgent subclass together and drives the poll -> process -> publish
-> commit loop, with automatic metrics, tracing, and graceful shutdown.
Agent authors never touch this file's logic directly; a conforming agent's
entire main.py is:

    AgentRunner(MyAgent(), consumer=..., producer=..., input_topics=[...],
                output_topic="...").run()
"""
from __future__ import annotations

import signal
import time

from pydantic import BaseModel
from sentinel_common.errors import SentinelError
from sentinel_common.logging_context import LoggingContext
from sentinel_common.tracing import start_span
from sentinel_eventbus import EventConsumer, EventProducer

from .base_agent import BaseAgent
from .container import Container, build_container
from .health import HealthRegistry


class AgentRunner:
    def __init__(
        self,
        agent: BaseAgent,
        consumer: EventConsumer,
        producer: EventProducer,
        state_container,
        input_topics: list[str],
        output_topic: str | None = None,
        output_topics: dict[str, str] | None = None,
        shutdown_timeout_seconds: float = 30.0,
    ):
        """`output_topic`: single topic used for every published result
        (HelloAgent's case -- one input event type in, one output event
        type out). `output_topics`: maps a result's `event_type` field to
        a specific topic, for agents that publish more than one kind of
        event (e.g. Zone Intelligence publishes both ZoneState and
        ZoneAnomalyDetected). At least one of the two must be provided;
        output_topics takes precedence when a result's event_type has an
        entry, falling back to output_topic otherwise."""
        self.agent = agent
        self.consumer = consumer
        self.producer = producer
        self.input_topics = input_topics
        self.output_topic = output_topic
        self.output_topics = output_topics or {}
        self.shutdown_timeout_seconds = shutdown_timeout_seconds

        if output_topic is None and not self.output_topics:
            raise ValueError("AgentRunner requires output_topic and/or output_topics")

        self._shutdown_requested = False
        self._in_flight = False
        self._iterations_processed = 0

        self._agent_name = type(agent).__name__
        self.agent.container = build_container(self._agent_name, state_container, producer)

        self._process_duration = self.agent.container.metrics.histogram(
            "agent_process_duration_seconds", "Time spent in agent.process() plus publish", labels=["outcome"]
        )
        self._process_total = self.agent.container.metrics.counter(
            "agent_process_total", "Count of processed events by outcome", labels=["outcome"]
        )
        self._result_confidence = self.agent.container.metrics.histogram(
            "agent_result_confidence", "Confidence of published results, when present"
        )

    @property
    def health(self) -> HealthRegistry:
        return self.agent.container.health

    def _handle(self, event: BaseModel) -> None:
        """The handler EventConsumer invokes per message. Wraps
        agent.process() with tracing/metrics/logging-context, publishes any
        returned result BEFORE returning (so EventConsumer's
        commit-after-handler-success ordering means we never commit an
        offset for a result that failed to publish)."""
        self._in_flight = True
        try:
            correlation_id = str(getattr(event, "correlation_id", ""))
            causation_id = str(getattr(event, "event_id", "")) or None

            with LoggingContext(correlation_id=correlation_id, causation_id=causation_id):
                start = time.time()
                with start_span(f"{self._agent_name}.process", attributes={"event_type": type(event).__name__}):
                    try:
                        result = self.agent.process(event)
                    except SentinelError:
                        self._process_total.labels(outcome="error").inc()
                        raise
                    except Exception as e:  # noqa: BLE001 -- unclassified exceptions must not vanish silently
                        self._process_total.labels(outcome="error").inc()
                        from sentinel_common.errors import FatalError
                        raise FatalError(f"unclassified exception in {self._agent_name}.process: {e}") from e

                    if result is not None:
                        results = result if isinstance(result, list) else [result]
                        for r in results:
                            topic = self.output_topics.get(getattr(r, "event_type", None), self.output_topic)
                            if topic is None:
                                raise RuntimeError(
                                    f"no output topic configured for event_type={getattr(r, 'event_type', None)!r} "
                                    f"-- add it to output_topics or set a default output_topic"
                                )
                            self.producer.publish(topic, r)
                            explanation = getattr(r, "explanation", None) or getattr(r, "justification", None)
                            if explanation is not None:
                                confidence = getattr(getattr(explanation, "confidence", None), "value", None)
                                if confidence is not None:
                                    self._result_confidence.observe(confidence)
                        self._process_total.labels(outcome="success_with_result").inc()
                    else:
                        self._process_total.labels(outcome="success_no_result").inc()

                duration = time.time() - start
                outcome_label = "success_with_result" if result is not None else "success_no_result"
                self._process_duration.labels(outcome=outcome_label).observe(duration)

                self.agent.container.logger.info(
                    "event processed", event_type=type(event).__name__,
                    produced_result=result is not None,
                )
        finally:
            self._in_flight = False
        self._iterations_processed += 1

    def _install_signal_handlers(self) -> None:
        def _on_term(signum, frame):
            self.agent.container.logger.info("shutdown signal received, draining")
            self._shutdown_requested = True

        try:
            signal.signal(signal.SIGTERM, _on_term)
            signal.signal(signal.SIGINT, _on_term)
        except ValueError:
            # signal.signal only works in the main thread -- tests running
            # AgentRunner in a worker thread skip installation gracefully.
            pass

    def run(self, max_iterations: int | None = None, poll_timeout_seconds: float = 0.5,
             max_empty_polls: int | None = None) -> None:
        """`max_empty_polls` (test-only convenience): stop after this many
        consecutive polls found nothing, instead of blocking forever --
        used by tests so a misconfigured topic subscription fails fast
        with a clear iteration count instead of hanging."""
        self.agent.initialize()
        self.consumer.subscribe(self.input_topics, handler=self._handle)
        self._install_signal_handlers()

        empty_polls = 0
        while not self._shutdown_requested:
            before = self._iterations_processed
            self.consumer.poll_once(poll_timeout_seconds)
            if self._iterations_processed == before:
                empty_polls += 1
                time.sleep(0.02)  # avoid an unthrottled busy-loop when the topic is empty
            else:
                empty_polls = 0
            if max_iterations is not None and self._iterations_processed >= max_iterations:
                break
            if max_empty_polls is not None and empty_polls >= max_empty_polls:
                break

        self.drain()
        self.agent.shutdown()

    def drain(self) -> None:
        """Waits (up to shutdown_timeout_seconds) for any in-flight process()
        call to finish before closing connections -- ensures no event is
        dropped mid-process during a rolling deploy or pod termination."""
        deadline = time.time() + self.shutdown_timeout_seconds
        while self._in_flight and time.time() < deadline:
            time.sleep(0.01)
        self.producer.flush(5.0)
        self.consumer.close()

    def request_shutdown(self) -> None:
        """Programmatic equivalent of receiving SIGTERM -- used by tests to
        exercise graceful shutdown deterministically without sending a real
        OS signal."""
        self._shutdown_requested = True
