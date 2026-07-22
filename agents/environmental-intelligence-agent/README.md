# Environmental Intelligence Agent

Consumes environmental sensor readings and produces hazard analysis for
`risk_orchestrator_agent`, per `contracts/agent-registry/agents.yaml`'s
`environmental_intelligence_agent` entry. Owns gas-hazard detection per
`OWNERSHIP.md`'s resolution for the former standalone `gas-intelligence-agent`.

## Status

Runs and passes tests today for the environmental signal types
`SensorEvent` already supports end-to-end (temperature, humidity,
pressure). Gas-hazard detection itself — the majority of this agent's
purpose — is implemented in full under `engine/` and unit-tested there,
but is **not yet reachable from live Kafka traffic**, and this agent
**cannot currently publish** its output topic. Both are blocked on gaps
in the platform's contract-generation pipeline, not on anything in this
codebase. See "Known gaps" below.

## Layout

```
main.py                              AgentRunner composition root
config.py                            Layered config (EnvironmentalConfig, GLOBAL_DEFAULTS)
environmental_intelligence_agent.py  BaseAgent subclass (process())
sensor_snapshot_aggregator.py        Buffers SensorEvent readings into per-zone snapshots
engine/                              Preserved gas-hazard analysis engine (business logic,
                                      migrated from the standalone gas-intelligence-agent
                                      service; algorithms and threshold/weight values
                                      unchanged -- only imports and configuration wiring
                                      were touched)
tests/unit/                          Relocated unit tests for engine/ (37 tests, all passing)
```

## Known gaps (tracked; not worked around)

- **B1** — `environment_analysis` (this agent's registered output schema)
  has an Avro source (`contracts/agent-contracts/v1/EnvironmentAnalysis.avsc`)
  but no generated model in `sentinel_contracts/`, and `EventProducer`'s
  schema resolution never loads from `contracts/agent-contracts/` at all
  (only `contracts/events/`). This agent cannot publish until both are
  fixed upstream. `main()` raises `RuntimeError` rather than starting in
  a misconfigured state.
- **B2** — `environmental_event` (a registered input schema) has no Avro
  source, only an unmigrated legacy JSON-Schema file. Not consumed.
- **B3** — `SensorEvent.payload.sensor_type` has one undifferentiated
  `GAS` value; there is no field identifying which gas species a `GAS`
  reading measured. `sensor_snapshot_aggregator.py` counts and logs these
  readings but cannot route them into the engine's per-species inputs.

Full evidence and what unblocks each is in the migration report.

## Running

```
KAFKA_BOOTSTRAP_SERVERS=<broker> python main.py
```

Will raise `RuntimeError` immediately (B1) rather than starting — this is
intentional, see `main.py`'s docstring.

To exercise the preserved engine directly (e.g. for validating detection
logic against recorded readings, independent of the blocked Kafka path),
construct `EnvironmentalIntelligenceAgent` and its `engine/*Service`
members directly, as `tests/unit/` already does.
