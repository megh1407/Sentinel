# SENTINEL
### Industrial Safety Intelligence Platform

![Python](https://img.shields.io/badge/python-3.12-blue)
![Next.js](https://img.shields.io/badge/next.js-16-black)
![TypeScript](https://img.shields.io/badge/typescript-5-blue)
![Contract Validate](https://github.com/megh1407/Sentinel/actions/workflows/contract-validate.yml/badge.svg)
![Contract Test](https://github.com/megh1407/Sentinel/actions/workflows/contract-test.yml/badge.svg)

A multi-agent system that turns raw industrial sensor and event data into
explainable, correlated risk decisions — with the safety decision made
deterministically, never by an LLM.

> **At a glance**
> - Deterministic safety decision — the same inputs always produce the same risk score
> - LLM used for explanation only — never for scoring, severity, or escalation
> - Contract-first events — every message is schema-validated, producer and consumer
> - One-hop cross-zone correlation (not multi-hop/site-wide — see Roadmap)
> - In-memory transport (default, fully tested) + Kafka transport (code-complete, not live-verified)
> - 104 tests passing, zero external infrastructure required
> - Reference / development implementation — not production-hardened, no authentication yet, no LICENSE yet

---

## The Problem

Industrial sites generate safety-relevant signals from a dozen disconnected
sources: gas sensors, worker PPE compliance systems, permit trackers,
maintenance logs, incident reports. Each system sees its own slice in
isolation. A gas reading that's mildly elevated on its own, a permit that
expired an hour ago, and a worker without a required respirator in the same
zone are each individually unremarkable — but together, in the same zone,
at the same time, they're a compound hazard that no single-domain system is
positioned to catch. Most safety tooling either drowns operators in
uncorrelated alerts, or hides the decision logic behind a model nobody can
audit after an incident.

## What SENTINEL Does

SENTINEL runs a set of independent domain agents — one per hazard
category — that continuously analyze their own event stream and publish
structured findings onto a shared, schema-validated event bus. A central
Risk Orchestrator consumes those findings, scores risk deterministically
per zone, correlates risk *across* zones to catch compound hazards a single
zone's data wouldn't reveal, and attaches a mandatory, evidence-backed
explanation to every decision. A Response Agent proposes — but never
executes — mitigating actions. The pipeline has a single LLM integration,
isolated to the Safety Copilot, strictly to turn an already-finalized
decision into readable prose for a human operator.
## Why SENTINEL?

| Common failure mode | SENTINEL's answer |
|---|---|
| Uncorrelated alerts across disconnected systems | Cross-domain correlation via a shared event bus and a central orchestrator |
| Black-box safety decisions nobody can audit later | Deterministic scoring — same inputs, same output, every time |
| Handing risk decisions to an unpredictable model | LLM isolated to an explanation-only layer, downstream of the decision |
| Schema drift between producers and consumers | Contract-first events — every message validated against a shared registry |
| Automated systems that can act without a human in the loop | Response Agent proposes actions only; nothing executes automatically |
| Correlation logic that quietly expands to "the whole site" | Explicit, configured one-hop zone topology — no dynamic, unbounded search |

### Core Guarantees

These are architectural invariants — properties of how the code is
structured, not operational promises about deployment. See "Safety
Boundary" below for what the system can and cannot *do*.

- **Guaranteed:** the risk-scoring function is pure and deterministic.
- **Guaranteed:** the LLM has no code path into the score/severity/escalation decision.
- **Guaranteed:** every decision-bearing event fails validation if its `ExplanationObject` is missing.
- **Not guaranteed:** correctness of a specific numeric score for a given real-world scenario — that depends on the domain agents' own thresholds and configuration, not the orchestrator's architecture.
- **Not guaranteed:** behavior under live Kafka/Neo4j/Qdrant conditions — see Implementation Status.

## Example: Compound Hazard Detection

A single elevated methane reading in Zone A might not cross the threshold
for an alert on its own. But if the Maintenance Intelligence Agent has
already flagged that Zone A's ventilation equipment is overdue for
servicing, and the Permit Intelligence Agent shows the hot-work permit for
Zone B expired 40 minutes ago, the Risk Orchestrator's cross-zone
correlation factors that in — but only because Zone B is a **configured
one-hop neighbor** of Zone A in the zone topology, not because the system
searches the whole site for related findings. The correlation engine only
ever looks at a zone's immediate, explicitly-configured neighbors. The
combined risk score comes out well above what Zone A's local signal alone
would justify, and the resulting `RiskScore` event carries an
`ExplanationObject` that cites all three contributing findings by ID, not
just a number.

In compact form:

```text
Zone A                          Neighbor Zone B (one-hop, configured)
  ├─ methane finding               ├─ expired hot-work permit finding
  └─ overdue ventilation           
     maintenance finding
        │                                    │
        └───────────────┬────────────────────┘
                         ▼
       deterministic local scoring + one-hop cross-zone correlation
                         ▼
                     RiskScore
                       score: 71
                       evidence: [finding IDs from both zones]
                       explanation: ExplanationObject (required, non-null)
```

## Architecture

```text
                     ┌─────────────────────────────────────────┐
                     │            CONTRACT REGISTRY             │
                     │  Avro schemas + JSON Schema + agent      │
                     │  registry → generated Pydantic models    │
                     └───────────────┬───────────────────────────┘
                                     │ every producer/consumer validates against this
                                     ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
   │ Zone         │  │ Worker       │  │ Environmental│  │ Permit /     │
   │ Intelligence │  │ Safety       │  │ Intelligence │  │ Maintenance /│
   │ Agent        │  │ Agent        │  │ Agent        │  │ Incident...  │
   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
          │            publish findings as validated contract events    │
          └────────────────────┬───────────────────────────────────────┘
                                ▼
                     ┌─────────────────────┐
                     │   EVENT BUS          │  InMemoryTransport (default) or
                     │                       │  KafkaTransport — same interface,
                     └──────────┬────────────┘  no transport-specific agent code
                                ▼
                     ┌─────────────────────────────┐
                     │      RISK ORCHESTRATOR        │
                     │  deterministic local score →   │
                     │  one-hop cross-zone correlation │
                     │  → FINALIZED, evidence-backed   │
                     │    safety decision               │
                     └──────────────┬────────────────┘
                                    │
                     ┌──────────────┴───────────────┐
                     ▼                               ▼
          ┌─────────────────────┐        ┌─────────────────────────┐
          │   Response Agent     │        │   Safety Copilot (LLM)   │
          │  PROPOSES ONLY —      │        │  EXPLAINS ONLY —          │
          │  never executes       │        │  cannot modify score,     │
          │  actions               │        │  severity, evidence, or   │
          │                       │        │  escalation               │
          └─────────────────────┘        └─────────────────────────┘
                                    │
                                    ▼
                     ┌─────────────────────────────┐
                     │   API Gateway + Dashboard      │
                     │  FastAPI + WebSocket + Next.js  │
                     └─────────────────────────────┘
```

The Risk Orchestrator is where the safety decision is finalized. Both
branches below it consume that decision — neither branch can change it.

### Decision Flow (condensed)

```text
Raw events
   ↓
Domain agents
   ↓
Contract validation
   ↓
Event bus
   ↓
Risk Orchestrator
   ↓
deterministic scoring
   ↓
one-hop cross-zone correlation
   ↓
finalized RiskScore
   ↓
   ┌───────────────┬────────────────┐
   ▼                                ▼
Response Agent                Safety Copilot
proposes actions              explains the decision
(no execution)                (no scoring influence)
```

Neither downstream branch can modify the finalized `RiskScore` — both only
ever read it.

## Safety-Critical Design Principles

### 1. Deterministic Risk Decisions
The Risk Orchestrator's scoring math — local risk, then cross-zone
correlation, then global risk — is pure domain logic. The same inputs
always produce the same score, every time, with no model inference in the
decision path itself.

### 2. LLM Isolation

Gemini is integrated downstream of the finalized decision, solely to turn an `ExplanationObject` into operator-readable text. It
receives no raw events, and the code path gives it no mechanism to alter as core, severity, or escalation decision — this isn't a policy, it's how the data flows.

### 3. Contract-First Events
Every event type is defined once as an Avro schema, generates a Pydantic
model, and is validated on both the producer and consumer side. The agent
registry (`contracts/agent-registry/agents.yaml`) is the single source of
truth for who produces and consumes what, checked in CI.

### 4. Evidence-Backed Decisions
`RiskScore` and `AgentResult` — the two event types explicitly documented
in their own schemas as decision-bearing — both require a populated
`ExplanationObject`; it is never optional on either type. That
`ExplanationObject` in turn carries a confidence value and a list of
supporting evidence items — "the score was 72" is never the whole story
those events tell. `ConfidenceScore` is associated with individual
findings, evidence, and context objects and records explicit provenance
(`RULE_BASED`, `MODEL_BASED`, or `COMPOSITE`). It is not a confidence value
for the deterministic risk-scoring function itself.

### 5. Cross-Zone Correlation
Findings aren't scored in isolation. The orchestrator's correlation engine
combines a zone's local risk with signals from its immediate (one-hop)
neighbors — as defined by an explicit zone-topology configuration, not a
dynamic search — using a noisy-OR combination chosen specifically so the
global score is never lower than the local score, and equals it exactly
when there's no cross-zone interaction to report.

## Safety Boundary

**SENTINEL can:**
- detect and correlate hazards across configured, related zones
- calculate deterministic, evidence-backed risk scores
- surface the evidence behind every decision
- recommend mitigating actions
- generate human-readable explanations of an already-finalized decision

**SENTINEL does not:**
- autonomously control physical machinery
- execute physical shutdown commands or any other action directly
- allow an LLM to determine or adjust risk score, severity, or escalation
- claim industrial safety certification or regulatory compliance

## Event Flow

A concrete, simplified trace through the pipeline:

```text
1. SensorEvent (methane: 340ppm, zone: Z-104)
       │  published to sentinel.sensor.events.v1
       ▼
2. EnvironmentalIntelligenceAgent evaluates against zone thresholds
       │  publishes EnvironmentAnalysis (finding: elevated, confidence: 0.87)
       ▼
3. RiskOrchestrator's EventRouter deduplicates, validates, dispatches
       │  ContextBuilder assembles the zone's current state + one-hop neighbors
       │  RuleEngine + RiskScorer compute local + cross-zone risk
       ▼
4. RiskScore (zone: Z-104, score: 71, evidence: [contributing finding IDs])
       │  published to sentinel.risk.scores.v1
       ▼
5. ResponseAgent proposes an ActionPlan (e.g. "notify zone supervisor")
       │  never executes it — publishes ActionRequest only
       ▼
6. API Gateway serves the current state; SafetyCopilot generates a
   human-readable summary of the RiskScore's ExplanationObject on demand
       ▼
7. Dashboard renders the zone's live risk state over a WebSocket connection
```

## Agent Architecture

| Agent | Responsibility | Status |
|---|---|---|
| `zone_intelligence_agent` | Perception layer — zone state, anomaly detection | Implemented, self-tested |
| `environmental-intelligence-agent` | Gas/temperature/pressure hazard analysis | Implemented, 37 tests passing |
| `worker-safety-agent` | PPE compliance, worker location/status analysis | Implemented, 37 tests passing |
| `risk-orchestrator-agent` | Deterministic scoring, cross-zone correlation, explanation | Implemented, 30 tests passing |
| `response-agent` | Proposes mitigating actions (propose-only, no execution) | Implemented |
| `permit-intelligence-agent` | Permit validity and violation detection | Implemented |
| `maintenance-intelligence-agent` | Equipment maintenance status and overdue detection | Implemented |
| `incident-intelligence-agent` | Incident correlation and pattern detection | Implemented |
| `safety-copilot-agent` | LLM-backed natural-language explanation (isolated, see above) | Implemented |
| `hello_agent` | Minimal reference implementation for building new agents | Reference / example |

### Historical / Folded Components

| Component | Status |
|---|---|
| `compliance-intelligence-agent` | Unresolved — open architecture question, not yet assigned to an agent. Not implemented. |
| `gas-intelligence-agent` | Folded into other agents above; kept as documented history, not active |
| `ppe-detection-agent` | Folded into other agents above; kept as documented history, not active |
| `equipment-health-intelligence-agent` | Folded into other agents above; kept as documented history, not active |

## Repository Structure

```text
contracts/              Avro/.avsc + JSON Schema + agent registry (source of truth)
sentinel_contracts/     Generated Pydantic models
libs/
  sentinel_common/       Logging, errors, metrics, tracing
  sentinel_eventbus/      Transport abstraction, producer/consumer, DLQ, idempotency
  sentinel_state/         Redis / PostgreSQL / Neo4j / Qdrant repositories
  sentinel_agent_sdk/     BaseAgent, AgentRunner, DI container, health checks
agents/                  One directory per domain agent — see AGENT_GUIDE.md
platform-services/
  api-gateway/            FastAPI + WebSocket, orchestrates agents, serves the dashboard
dashboard/               Next.js real-time operations UI
scripts/                 Demo runners, contract validation, local dev-env docker-compose
```

## Implementation Status

**Quick summary:** the core pipeline (contracts, in-memory transport, risk
scoring, one-hop correlation, LLM explanation, API gateway, dashboard) is
implemented. Live verification against Kafka/Neo4j/Qdrant, multi-hop
correlation, five platform services, and authentication are not — see the
full breakdown below.

| Component | Status | Evidence |
|---|---|---|
| Contract validation | **Implemented** | `make validate-contracts` — all schemas pass |
| In-memory event transport | **Implemented** | Real complete local bus, not a mock; default for tests/demo |
| Kafka transport | **Implemented, unverified live** | Code-complete against confluent-kafka; no broker exercised in this environment |
| Risk scoring & one-hop correlation | **Implemented** | Deterministic, unit-tested; manually verified scenario runs documented in `docs/RECONCILIATION_REPORT.md` |
| Multi-hop / site-wide cascade correlation | **Planned, not implemented** | Only one-hop neighbor correlation currently exists |
| Redis / PostgreSQL repositories | **Implemented** | Code-complete; live-tested in prior development, not independently re-verified in this pass |
| Neo4j / Qdrant repositories | **Implemented, unverified live** | Code-complete; Neo4j never run against a live instance; Qdrant embeddings are a deterministic placeholder, not semantic |
| LLM explanation (Safety Copilot) | **Implemented** | Structurally isolated from scoring — see Design Principles above |
| API Gateway | **Implemented** | FastAPI, WebSocket, real routes serving live agent state |
| Dashboard | **Implemented** | Next.js, builds clean, 0 dependency vulnerabilities |
| `action-policy-gateway`, `audit-service`, `configuration-service`, `ingestion-gateway`, `notification-service` | **Not implemented** | Scaffolded (Dockerfile only), not required for the current pipeline |
| Authentication | **Not implemented** | See Limitations below |

## Quickstart

```bash
make install               # installs everything, including test deps
make validate-contracts    # validates every schema against the registry
make test                  # 104 tests, zero external infrastructure required
```

All three run entirely against the in-memory transport and in-memory
fakes — no Docker, Redis, or Kafka needed to see the core pipeline work.

## Running the Full Stack

For live infrastructure (Kafka, Schema Registry, Neo4j, Redis, Postgres):

```bash
docker compose -f scripts/dev-env/docker-compose.yml up
```

For the API gateway itself:

```bash
docker build -f platform-services/api-gateway/Dockerfile -t sentinel-api-gateway .
docker run -p 8000:8000 -e REDIS_HOST=<your-redis-host> sentinel-api-gateway
```

Build context must be the repository root — the gateway dynamically imports
agent source from `agents/` at runtime. This Dockerfile has not been
build-verified in every environment; verify locally before relying on it
in a deployment.

For the dashboard:

```bash
cd dashboard && npm ci && npm run dev
```

## Testing

```bash
make test
```

| Suite                              |           Tests |
| ----------------------------------- | ---------------: |
| `environmental-intelligence-agent` |      37 passing |
| `risk-orchestrator-agent` (unit)   |      30 passing |
| `worker-safety-agent`              |      37 passing |
| **Total**                          | **104 passing** |

> **In short:** `make test` runs the 104-test default suite above, with
> zero external infrastructure. Everything below this line requires live
> infrastructure or belongs to a separate sub-project, and is intentionally
> not part of that default run.

Not currently included in `make test` (out of scope, not silently broken):
`risk-orchestrator-agent`'s load/chaos/performance/production-validation
suites (require live infrastructure), `Sentinel_Data_Engine`'s own test
suite (separate sub-project), and the remaining agents that don't yet have
a wired test suite. See `AGENT_GUIDE.md` for per-agent status.

## Tech Stack

**Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy, confluent-kafka,
Avro/fastavro, OpenTelemetry, Prometheus, structlog, pytest.
**Frontend:** Next.js, TypeScript.
**Infrastructure (optional):** Kafka + Schema Registry, Redis, PostgreSQL,
Neo4j, Qdrant.
**AI:** Google Gemini — natural-language explanation generation only (see
Design Principles above).

## Design Decisions

- **Separate agent processes over a monolith.** Each domain agent is
  independently deployable and independently testable. The tradeoff is
  more moving parts; the benefit is stronger process and failure
  isolation: an agent failure does not inherently crash other agents,
  while domain-specific faults remain observable and containable at the
  event boundary.
- **Event-driven, not RPC.** Agents never call each other directly. They
  publish findings and consume topics — this is what makes the
  transport swap (in-memory ↔ Kafka) possible without transport-specific
  code in any agent, and what lets the Risk Orchestrator correlate
  findings from agents that have no knowledge of each other's existence.
- **In-memory transport as the default, not an afterthought.** Local
  development and the full test suite run against a real, complete
  implementation of the same `Transport` interface Kafka uses — not a
  simplified stand-in. Both transports satisfy the same contract and
  require no transport-specific agent code, but Kafka's own operational
  semantics (partitioning, broker failover, consumer-group rebalancing
  under load) are distinct from the in-memory transport's and have not
  been separately live-validated — see Implementation Status.
- **Propose, don't execute.** The Response Agent's output is an
  `ActionRequest`, not a side effect. Execution against real industrial
  systems is deliberately a separate, not-yet-built boundary
  (`action-policy-gateway`) — a system that recommends is a fundamentally
  different risk profile than one that acts.

## Limitations & Non-Goals

**Current limitations:**
- No authentication on any API route, and CORS is permissive by default in
  development. Not suitable for deployment reachable beyond localhost
  without adding real auth first.
- Multi-hop/site-wide cascade risk detection doesn't exist yet — only
  immediate-neighbor (one-hop) correlation.
- Five platform services are scaffolded, not implemented (see
  Implementation Status).
- Kafka, Neo4j, and Qdrant integrations are code-complete but not verified
  against live instances in this environment.
- No LICENSE has been chosen yet.

**Non-goals (by design, not oversight):**
- SENTINEL does not execute actions against physical industrial systems —
  the Response Agent proposes only. Closing that loop is a deliberate,
  separate, not-yet-built trust boundary, not a missing feature of this
  system.
- This is not a certified industrial safety product and makes no claim to
  regulatory compliance or physical hardware integration.
- SENTINEL does not use an LLM for safety decisions, by design — see
  Safety-Critical Design Principles above. This is a permanent architectural
  boundary, not a temporary limitation to be "upgraded" later.

## Roadmap

- Multi-hop / site-wide cascade correlation (`domain/site_state/`)
- Live verification against Kafka, Neo4j, and Qdrant instances
- `action-policy-gateway`, `audit-service`, `configuration-service`,
  `ingestion-gateway`, `notification-service`
- Authentication and production CORS configuration
- Resolve `compliance-intelligence-agent`'s architecture placement
- LICENSE decision

## Documentation

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — full architecture writeup
- [`AGENT_GUIDE.md`](AGENT_GUIDE.md) — how to build a new domain agent
- [`agents/risk-orchestrator-agent/docs/RECONCILIATION_REPORT.md`](agents/risk-orchestrator-agent/docs/RECONCILIATION_REPORT.md) — the orchestrator's own notes on what's proven vs. architected
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — setup and PR expectations
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — interaction standards
- [`SECURITY.md`](SECURITY.md) — how to report a vulnerability

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup, the exact commands CI
runs, and PR expectations. [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
covers interaction standards.

## Security

See [`SECURITY.md`](SECURITY.md) for how to report a vulnerability. This
is a local-development / reference-implementation configuration — no
authentication exists on any route, and CORS is permissive by default in
development (see Limitations above). Do not deploy this reachable beyond
localhost without adding real authentication first.

## License

No LICENSE file exists in this repository yet. Until one is added, default
copyright applies and no reuse rights are granted.
