# SENTINEL — Architecture

This document describes the architecture that already exists in this
repository. It does not introduce new architecture — every statement below
is backed by a specific file already in the repo.

## Repository Layers

The system is layered, lowest-dependency first:

1. **Contracts** (`contracts/`) — Avro schemas (`.avsc`) and JSON Schemas
   defining every event, common type (`BaseEvent`, `GeoLocation`, `Metadata`,
   `ConfidenceScore`, `EvidenceItem`, `RiskContributor`, `ExplanationObject`),
   agent output shape, Kafka topic (`contracts/topics/kafka_topics.yaml`),
   agent registry (`contracts/agent-registry/agents.yaml`), versioning policy
   (`contracts/versioning/compatibility_rules.md`), and numbered domain
   invariants (`contracts/common/domain_invariants.md`). Nothing below this
   layer may redefine a concept the contracts already own.
2. **Generated contract models** (`sentinel_contracts/`, root level) — Pydantic
   models generated from the Avro schemas via
   `tools/codegen/avro_to_pydantic.py`. This is the **only** generated-model
   package in the repository; import from it directly
   (`from sentinel_contracts.events.sensor_event_v1 import SensorEventV1`).
   Do not hand-edit these files or generate a second copy elsewhere.
3. **Runtime libraries** (`libs/`) — `sentinel_common` (logging, errors,
   metrics, tracing; no internal deps), `sentinel_eventbus` (producer,
   consumer, retry/DLQ, idempotency, `InMemoryTransport` and
   `KafkaTransport`), `sentinel_state` (Redis/Postgres/Neo4j/Vector
   repositories + `StateContainer`), `sentinel_agent_sdk` (`BaseAgent`,
   `AgentRunner`, DI container, health checks). Build order/dependency
   direction, per `README.md`:
   `sentinel_common → sentinel_eventbus → sentinel_state → sentinel_agent_sdk`.
4. **Agents** (`agents/`) — one folder per agent, registered in
   `contracts/agent-registry/agents.yaml`. Agents talk to each other **only**
   through Kafka topics and contracts — never through direct imports of
   another agent's package (verified: no agent currently imports another
   agent's internal code).
5. **Platform services** (`platform-services/`) — ingestion-gateway,
   notification-service, configuration-service, action-policy-gateway,
   api-gateway, audit-service. These sit outside the agent mesh as topic
   producers/consumers referenced in `kafka_topics.yaml` (e.g.
   `dashboard-service`, `audit-service`, `executive-reporting-service`,
   `operator-terminal-service`).

## Agent Responsibilities

Per `contracts/agent-registry/agents.yaml` (the single source of truth for
who consumes/produces what):

| Agent | Responsibility (from its registry description) |
|---|---|
| `zone_intelligence_agent` | Factory perception layer — understands every industrial zone |
| `permit_intelligence_agent` | Operational safety analyzer for work permits |
| `worker_safety_agent` | Human safety monitoring — PPE, location, biometrics |
| `maintenance_intelligence_agent` | Equipment health intelligence and failure prediction |
| `environmental_intelligence_agent` | Environmental hazard monitoring — gas, temperature, pressure |
| `incident_intelligence_agent` | Historical safety memory using vector DB, RAG, and knowledge graph |
| `risk_orchestrator_agent` | Main reasoning engine — the only agent that aggregates all other agents' outputs into a final risk score (`tier-0` criticality) |
| `response_agent` | Action planner — proposes actions, never executes them directly |
| `safety_copilot_agent` | Human explanation interface — generates explanations and answers operator queries |
| `action_gateway` | Executes approved actions — the only system with real-world execution authority |

Four agent folders exist (`gas-intelligence-agent`, `ppe-detection-agent`,
`compliance-intelligence-agent`, `equipment-health-intelligence-agent`) that
are **not** in the registry. See each folder's `OWNERSHIP.md` for its
resolved status (three fold into an existing agent above; one —
`compliance-intelligence-agent` — is unresolved pending an explicit
architecture decision, since no existing contract covers it).

## Contract Usage

Every event an agent consumes or produces has a matching Avro/JSON Schema
under `contracts/` and a generated Pydantic model under `sentinel_contracts/`.
An agent never constructs or parses an event by hand — it imports the
generated model, e.g.:

```python
from sentinel_contracts.events.sensor_event_v1 import SensorEventV1
from sentinel_contracts.common.geo_location import GeoLocation
```

Every decision-bearing output (a `RiskScore`, an `AgentResult`, or similar)
must carry a populated `ExplanationObject` — this is Domain Invariant #4,
registered in `contracts/common/domain_invariants.md`, and enforced even for
a `NO_FINDING` result.

## Kafka Communication

Agents communicate exclusively through Kafka topics defined in
`contracts/topics/kafka_topics.yaml`. Every topic declares: `schema`,
`producer`, `consumers`, `partition_key` (almost always `zone_id`),
`partitions`, `replication_factor`, `retention_ms`, and a `retry_policy`.
Tier-0 topics (`sentinel.risk.score.v1`, `sentinel.action.request.v1/v2`)
additionally set `acks: all` and, for the risk topic, `min_insync_replicas: 2`.
A dead-letter-queue convention (`sentinel.dlq.{topic}`) is created
automatically for every topic on first failure.

The full event graph has one intentional cycle:
`risk_orchestrator_agent → sentinel.risk.score.v1 → incident_intelligence_agent
→ sentinel.incident.analysis.v1 → risk_orchestrator_agent`. This is by
design — incident context feeds risk scoring, and risk scores feed incident
correlation search — the two directions carry different, non-overlapping
payloads. It is not architectural debt.

## How Contracts Evolve

Governed entirely by `contracts/versioning/compatibility_rules.md`:
- Default compatibility mode is **BACKWARD**, enforced by Schema Registry on
  every produce call.
- Non-breaking changes (new optional field, new enum value, widened numeric
  type, new topic, relaxed constraint) ship in place — same version.
- Breaking changes (removed/renamed required field, incompatible type
  change, removed enum value consumers depend on, changed field semantics,
  changed partition-key semantics, restructured payload, optional→required)
  require a new schema version and typically a new topic, following the
  documented dual-write migration procedure (minimum 30-day window, each
  consumer migrates independently, producer stops dual-write once
  `agents.yaml` shows zero consumers left on the old version).
- A deprecated schema/topic must stay functional for a minimum of 90 days.
- Both `agents.yaml` and `kafka_topics.yaml` are themselves versioned
  artifacts requiring PR review by the owning team and CI validation that
  every referenced topic/schema exists.

## How Generated Code Is Used

`sentinel_contracts/` is generated from `contracts/**/*.avsc` via
`tools/codegen/avro_to_pydantic.py` — never hand-edited. If you need a field
that isn't there, the fix is a contract change (see above), followed by
regeneration, not a manual patch to the generated file.

## Running Validation

```
make validate-contracts     # Avro syntax + envelope-conformance (schema_loader.py, envelope_conformance_lint.py)
make test                   # full pytest suite
make install                # pip install -r requirements.txt
```

These wrap the same checks `.github/workflows/contract-validate.yml` already
runs on every PR touching `contracts/**`, `schema_loader.py`, or
`envelope_conformance_lint.py`.
