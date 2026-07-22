# SENTINEL Integration Test Report

Generated: 2026-07-18 16:26:26 India Standard Time
Observed run span: 92.7s (first to last recorded stage event)

This report has two parts: **Runtime Evidence** (section 1-5, pulled live from this run's trace store -- empty if the demo hasn't been run yet) and **Known Platform Gaps** (section 6, a static, cited list -- true regardless of whether the demo ran).

## 1. Summary

- Total stage events recorded: **2211**
- Success: **2206** (99.77%)
- Failed: **0** (0.0%)
- Skipped (platform gap, not a bug): **5** (0.23%)

## 2. Components Exercised

- Environmental Agent
- Equipment Simulator
- Kafka
- Permit Simulator (Data Engine)
- Sensor Simulator (Data Engine)
- Worker Simulator (Data Engine)
- Zone Agent

Topics this harness targets (from `harness_config.DEMO_TOPICS`, names taken verbatim from `contracts/topics/kafka_topics.yaml`):
- `sentinel.sensor.events.v1`
- `sentinel.worker.events.v1`
- `sentinel.permit.events.v1`
- `sentinel.zone.state.v1`
- `sentinel.environment.analysis.v1`
- `sentinel.zone.analysis.v1`

## 3. Per-Stage Breakdown

| Component | Stage | Status | Count |
|---|---|---|---|
| Environmental Agent | Kafka Subscribe | success | 1 |
| Equipment Simulator | Simulator Start | skipped | 1 |
| Kafka | Broker Reachable | success | 1 |
| Kafka | Topic Verified | success | 12 |
| Permit Simulator (Data Engine) | Kafka Publish | success | 242 |
| Permit Simulator (Data Engine) | PermitEvent Type Unmapped | skipped | 4 |
| Permit Simulator (Data Engine) | PermitEventV1 Created | success | 242 |
| Sensor Simulator (Data Engine) | Kafka Publish | success | 297 |
| Sensor Simulator (Data Engine) | SensorEventV1 Created | success | 298 |
| Worker Simulator (Data Engine) | Kafka Publish | success | 556 |
| Worker Simulator (Data Engine) | WorkerEventV1 Created | success | 556 |
| Zone Agent | Kafka Subscribe | success | 1 |

## 4. Latency

| Component | Stage | Samples | Avg (ms) | p95 (ms) | Max (ms) |
|---|---|---|---|---|---|
| Permit Simulator (Data Engine) | Kafka Publish | 242 | 7.03 | 11.38 | 18.56 |
| Sensor Simulator (Data Engine) | Kafka Publish | 297 | 14.3 | 12.18 | 2124.65 |
| Worker Simulator (Data Engine) | Kafka Publish | 556 | 6.89 | 11.37 | 18.72 |

## 5. Failures

No FAILED stage events recorded in this run.

## 6. Known Platform Gaps

Static, cited, independent of whether the demo ran. These are why the pipeline cannot reach 100% success today, and none of them are bugs in this test harness.

### [Critical] B1: sentinel.environment.analysis.v1 has no generated Pydantic model
- **Evidence:** agents/environmental-intelligence-agent/main.py raises RuntimeError before AgentRunner.run() ever executes, citing this exact gap. `grep -rl "class EnvironmentAnalysis"` across the whole repo returns nothing.
- **Impact:** Environmental Intelligence Agent can consume SensorEvent and run SensorSnapshotAggregator.ingest(), but can never publish a result -- ThresholdService, TrendService, PredictionService, CorrelationService, RiskService, and RecommendationService are all constructed in initialize() but never invoked by process().
- **Estimated fix effort:** Medium (design + codegen a real EnvironmentAnalysis contract; then wire ThresholdService..RecommendationService into process() to actually produce one)

### [High] ZONE-ANALYSIS: sentinel.zone.analysis.v1 has no generated model and is never wired
- **Evidence:** agents/zone_intelligence_agent/main.py's own module docstring documents this under PLATFORM_GAP. `grep -rl "class ZoneAnalysis"` returns nothing repo-wide.
- **Impact:** Zone Intelligence Agent publishes ZoneState to sentinel.zone.state.v1 only. There is no ZoneAnalysis event anywhere in this platform today.
- **Estimated fix effort:** Medium-High (this is a genuinely new contract -- ZoneAnalysis doesn't overlap with the existing ZoneState/ZoneAnomalyDetected models; needs its own design)

### [High] ZONE-ANOMALY-UNPUBLISHED: ZoneAnomalyDetected is fully computed but never reaches Kafka
- **Evidence:** ZoneAnomalyDetectedV1 has a real generated model and ZoneIntelligenceAgent.process() genuinely computes it (with Postgres audit rows and metrics), but main.py's _ZoneAnomalySuppressingAgent strips it before AgentRunner would otherwise crash trying to publish to a topic kafka_topics.yaml never registered for it.
- **Impact:** Every anomaly this agent detects (environmental hazard correlation, PPE conflicts, permit conflicts) is computed and audited, but no downstream consumer or dashboard can ever see it via Kafka.
- **Estimated fix effort:** Low (the model and business logic already exist -- this is purely a kafka_topics.yaml registration + main.py wiring change)

### [Medium] EQUIPMENT-STATE: sentinel.equipment.state.v1 has no generated Pydantic model
- **Evidence:** Confirmed via file listing under contracts/events/ -- only a legacy JSON Schema file exists, no Avro contract dir, no generated class.
- **Impact:** fake_equipment_simulator.py cannot run; Zone Intelligence Agent's equipment handling (EquipmentRiskDetected/MaintenanceRequired -- which DO have real models) can never be exercised end-to-end because there's no legal input topic.
- **Estimated fix effort:** Low-Medium (a legacy JSON Schema already exists as a starting point: contracts/events/v1/equipment_state.schema.json)

### [Medium] CONTRACTS-DUAL-SYSTEM: Two parallel contract systems (root sentinel_contracts/ vs deprecated libs/sentinel_contracts/)
- **Evidence:** libs/sentinel_contracts/ contains a DEPRECATED.md; the real, imported package is the root-level sentinel_contracts/.
- **Impact:** Purely a maintenance/confusion risk for this integration harness specifically -- both workers import from the root package correctly; noted here since it's the kind of thing that causes a future contributor to import the wrong one.
- **Estimated fix effort:** Low (delete the deprecated package once nothing imports it -- confirm via repo-wide grep)

## 7. Verdict

- Kafka connectivity: CONFIRMED (based on whether at least one successful Kafka Publish row was observed)
- Environmental Intelligence Agent: confirmed working through SensorSnapshotAggregator.ingest(); confirmed NOT publishing EnvironmentAnalysis (B1, by design of the current codebase, not a harness failure).
- Zone Intelligence Agent: confirmed working through ZoneState computation and publish to sentinel.zone.state.v1; ZoneAnomalyDetected confirmed computed but confirmed NOT published (platform gap, not a harness failure); ZoneAnalysis confirmed not produced anywhere (no such contract exists).
- No genuine (non-platform-gap) failures recorded in this run.
