# SENTINEL — Agent Developer Guide

This guide describes the existing, working pattern for building an agent in
this repository. It does not propose a new one.

## 1. Find your assignment

Look up your agent in `contracts/agent-registry/agents.yaml`. That entry is
authoritative for:
- `consumes.topics` / `consumes.schemas` — what you read
- `produces.topics` / `produces.schemas` — what you publish
- `owner` — who to ask if something's unclear
- `dependencies` — which other agents' outputs you build on (informational —
  you still only ever talk to them through Kafka, never by importing them)
- `sla` and `scaling` — the operational targets your implementation is
  expected to meet

If your assigned folder is one of `gas-intelligence-agent`,
`ppe-detection-agent`, `equipment-health-intelligence-agent`, or
`compliance-intelligence-agent`, read that folder's `OWNERSHIP.md` first —
three of the four already belong inside an existing registered agent, and
the fourth is explicitly unresolved.

## 2. Use the working reference implementations

Two agents already have real, working code to build from:

- **`agents/zone_intelligence_agent/`** — the fullest reference. Shows the
  complete pattern: consuming multiple event types
  (`SensorEventV1 | WorkerEventV1 | PermitEventV1 | EquipmentRiskDetectedV1`),
  maintaining Redis-backed zone state, publishing analysis/state events, and
  a layered `config.py` (`rule > site > agent > environment > global`
  override precedence) with no external config service required.
- **`HelloAgent`** (per `README.md`) — the minimal reference: `process()`
  returns a Pydantic model (or `None`), and `AgentRunner` publishes it
  automatically. No agent ever calls `EventProducer` directly.

Copy the structure of whichever is closer to your agent's complexity — don't
invent a new agent skeleton shape.

## 3. Wiring pattern

- **Input:** `EventConsumer.subscribe(topics, handler)` — declare your input
  topics (from your `agents.yaml` entry) and you get typed, validated
  Pydantic events.
- **Output:** return a Pydantic model from `process()`; `AgentRunner`
  publishes it to your declared output topic. Don't call the producer
  yourself.
- **State:** `self.state.<repo>` via `StateContainer` — it only builds the
  repositories your agent's config says it needs (Redis/Postgres/Neo4j/Vector).
- **Health/metrics/tracing:** automatic — zero code required beyond
  `process()`.

## 4. Import contracts from one place only

```python
from sentinel_contracts.events.sensor_event_v1 import SensorEventV1
from sentinel_contracts.common.metadata import Metadata
```

`sentinel_contracts/` (root level) is the only generated-model package in
the repository. There is no second copy to choose between.

## 5. Explanation is not optional

Per Domain Invariant #4 (`contracts/common/domain_invariants.md`), every
decision-bearing output you publish — a risk score, an agent result, any
Intelligence/Action-category output — must carry a populated
`ExplanationObject`, including when your result is `NO_FINDING`. Never
publish with an empty or absent `evidence` list for a non-`NO_FINDING` result.

## 6. Adding a new versioned contract

Follow `contracts/versioning/compatibility_rules.md` exactly:

1. Register the new schema version (`io.sentinel.events.v2.{SchemaName}`) in
   Schema Registry.
2. Create the new Kafka topic (`sentinel.{domain}.{type}.v2`) in
   `contracts/topics/kafka_topics.yaml`.
3. Update the producer to dual-write to both v1 and v2 for a minimum 30-day
   migration window.
4. Each consumer migrates independently: deploy v2-capable code, switch
   consumer group to the v2 topic, confirm no errors for 48 hours.
5. Once `contracts/agent-registry/agents.yaml` shows zero consumers left on
   v1 for this schema, the producer stops dual-writing.
6. Retain the v1 topic for its configured retention period, then decommission.
7. Update both `agents.yaml` and `kafka_topics.yaml` to drop the v1
   references.

Any change to either registry file requires a PR reviewed by the owning team
(per the `owner` field) and CI validation that every referenced topic/schema
exists and that no consumer references a not-yet-GA topic version.

A deprecated schema/topic must keep working for a minimum of 90 days.

## 7. Running validation locally

```
make install              # pip install -r requirements.txt
make validate-contracts   # Avro syntax + envelope-conformance checks
make test                 # full pytest suite
```

Same checks CI runs on every PR touching `contracts/**`.
