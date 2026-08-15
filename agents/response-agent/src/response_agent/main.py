"""
main.py

Response Agent's entrypoint. Per sentinel_agent_sdk's design, a conforming
agent's entire main.py is just wiring AgentRunner together -- no business
logic lives here (see agent.py / services/ / domain/).

TOPIC WIRING -- aligned to the registry (contracts/agent-registry/
agents.yaml + contracts/topics/kafka_topics.yaml) as of this task, which
fixed a pre-existing drift: kafka_topics.yaml already listed
response_agent as a consumer of sentinel.action.result.v1, but
agents.yaml's `consumes` list only had risk_score. Both now agree. See
agent.py's module docstring and README.md for the full boundary writeup.

# PLATFORM_GAP -- ActionRequest v2 (sentinel.action.request.v2) exists in
# kafka_topics.yaml, registered ahead of any real producer, with a note
# that dual-write to v1+v2 should begin "once a real producer exists". This
# agent is that producer, but it deliberately publishes ONLY to v1, for two
# independent reasons documented in full in README.md:
#   1. v2's only difference from v1 (as of this task) is an unrelated
#      field rename (justification -> explanation, per a prior,
#      already-decided migration this task did not initiate) -- the new
#      OPTIONAL fields this task added for the emergency-response model
#      were added to v1 directly (non-breaking, no version bump required
#      per compatibility_rules.md), so v1 already carries everything this
#      agent needs to say.
#   2. AgentRunner's output-topic routing (runner.py) dispatches by a
#      result's `event_type` string, and ActionRequestV1/V2 both default
#      `event_type` to the literal string "ActionRequest" -- there is no
#      way to route the "same" logical event to two different topics
#      through output_topics today. A real dual-write would need either a
#      runner-level change (out of scope here) or a second, explicit
#      producer.publish() call the SDK doesn't expose to agent authors by
#      design (base_agent.py: "no publish() API exposed to agent
#      authors"). Flagged rather than worked around with something that
#      would look like it works but silently only ever reach one topic.
"""
from __future__ import annotations

import os

from sentinel_agent_sdk import AgentRunner
from sentinel_contracts.events.action_result_v1 import ActionResultV1
from sentinel_contracts.events.risk_score_v1 import RiskScoreV1
from sentinel_eventbus import EventConsumer, EventProducer, KafkaTransport, LocalSchemaProvider
from sentinel_state import StateContainer, build_engine, build_session_factory

from response_agent.agent import ResponseAgent

INPUT_TOPICS = [
    "sentinel.risk.score.v1",
    "sentinel.action.result.v1",
]
EVENT_TYPES = {
    "RiskScore": RiskScoreV1,
    "ActionResult": ActionResultV1,
}
OUTPUT_TOPIC = "sentinel.action.request.v1"  # carries ActionRequestV1 -- see module docstring re: v2


def build_state_container() -> StateContainer:
    import redis

    redis_client = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
    )

    postgres_session_factory = None
    postgres_dsn = os.environ.get("POSTGRES_DSN")
    if postgres_dsn:
        engine = build_engine(postgres_dsn)
        postgres_session_factory = build_session_factory(engine)

    # Response Agent's idempotency/velocity/escalation memory
    # (self.state.response) only needs Redis -- matches StateContainer's
    # "don't require a backend this agent wasn't told to use" design.
    return StateContainer(redis_client=redis_client, postgres_session_factory=postgres_session_factory)


def main() -> None:
    schema_provider = LocalSchemaProvider()
    producer = EventProducer(KafkaTransport(client_id="response-agent-producer"), schema_provider)
    consumer = EventConsumer(
        KafkaTransport(client_id="response-agent-consumer"), schema_provider,
        EVENT_TYPES, group_id="response-agent",
    )
    state = build_state_container()
    agent = ResponseAgent()
    runner = AgentRunner(
        agent, consumer=consumer, producer=producer, state_container=state,
        input_topics=INPUT_TOPICS, output_topic=OUTPUT_TOPIC,
    )
    runner.run()


if __name__ == "__main__":
    main()
