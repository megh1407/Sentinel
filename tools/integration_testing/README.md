# SENTINEL Integration Testing Harness

A temporary, fully removable testing harness that proves what the current
repository's event-driven pipeline actually does, using real Kafka, real
agents, and real generated contracts -- no mocks, no direct method calls
between components, no fabricated results. Delete this whole directory and
nothing outside it changes: no contract, schema, topic, registry, or agent
file is modified or depended on being modified.

## Read this first: what this pipeline can and can't do today

This harness does not "fix" or work around any of the below -- it tests up
to each boundary, reports exactly where it stops, and reports why, citing
the actual code.

| Hop | Status |
|---|---|
| Sensor/Worker/Permit Simulator -> Kafka | **Works.** Real `EventProducer` + `KafkaTransport` + `LocalSchemaProvider`. |
| Kafka -> Environmental Intelligence Agent | **Works.** Real `EventConsumer`, real `SensorSnapshotAggregator.ingest()`. |
| Environmental Agent -> engine services (Threshold/Trend/Prediction/Risk/Recommendation/...) | **Does not run.** Constructed in `initialize()`, never called from `process()`. Not this harness's bug -- read `environmental_intelligence_agent.py`'s `process()` docstring. |
| Environmental Agent -> `EnvironmentAnalysis` -> Kafka | **Cannot happen.** No generated Pydantic model exists for `sentinel.environment.analysis.v1` anywhere in the repo (`main.py` itself refuses to start over this, citing "migration report B1"). |
| Kafka -> Zone Intelligence Agent | **Works.** Real `EventConsumer`, real `AgentRunner`. |
| Zone Agent -> `ZoneState` -> Kafka | **Works**, fully, via `sentinel.zone.state.v1`. |
| Zone Agent -> `ZoneAnomalyDetected` | **Computed but never published.** Real logic, real Postgres audit rows -- no registered Kafka topic exists for it, so `main.py`'s own `_ZoneAnomalySuppressingAgent` strips it before publish. |
| Zone Agent -> `ZoneAnalysis` -> Kafka | **Does not exist.** No model, no wiring, anywhere. |
| Equipment events -> anything | **Does not exist.** No generated model for `equipment_state`; `EquipmentRiskDetected`/`MaintenanceRequired` have real models but no registered input/output topics. |

Every one of these is cited to a specific file in the code comments of the
relevant harness script (`environmental_agent_worker.py`,
`zone_agent_worker.py`, `fake_equipment_simulator.py`,
`failure_report.py`). `integration_report.md` (generated after each run)
restates them under "Known Platform Gaps" so they show up in the same
place as genuine runtime failures, clearly labeled as not the same thing.

## Requirements

- Docker (for Kafka/Redis/Postgres via `scripts/dev-env/docker-compose.yml`) -- or point `KAFKA_BOOTSTRAP_SERVERS`/`REDIS_HOST`/`REDIS_PORT` at an already-running cluster and pass `--skip-infra`.
- Python deps from the repo root's `requirements.txt` (`confluent-kafka`, `redis`, `pydantic`, `fastavro`, `PyYAML`, etc.) installed in whatever environment you run these scripts from.
- Nothing installs or runs inside this folder alone -- every script imports the real agent/library code from `../../agents/*` and `../../libs/*` via `harness_config.bootstrap_agent_sys_path()`.

## Quick start

```bash
cd tools/integration_testing
./start_demo.sh --duration 90
```

This will: reset the trace store, bring up Kafka/Redis/Postgres, create/verify
every demo topic (partition counts read from `contracts/topics/kafka_topics.yaml`,
replication factor forced to 1 for the local single-broker dev cluster --
see `reset_topics.py`'s docstring for why that's a safe local-only override),
start both agent workers, start the sensor/worker/permit simulators, run
for the given duration, stop everything, and write `integration_report.md`.

In a second terminal, while it's running:

```bash
python3 pipeline_visualizer.py       # live, colorized stage-by-stage feed
python3 kafka_topic_monitor.py --watch 5
python3 consumer_monitor.py --watch 5
python3 latency_monitor.py --watch 5
```

After it stops:

```bash
python3 trace_dashboard.py --list          # recent trace ids
python3 trace_dashboard.py <trace_id>       # full stage-by-stage path for one trace
python3 trace_dashboard.py --list-runs      # detected runs (time-window groupings; see below)
python3 trace_dashboard.py --report latest  # generate zone_environmental_integration_report.md
cat integration_report.md
```

**On `trace_id` vs "a run":** each `trace_id` is one event's path (one `SensorEvent`,
one `WorkerEvent`, ...) -- there's no single trace_id spanning an entire test
run, because every event gets its own `trace_id` derived from its own
`correlation_id`. A "run" (e.g. "the test that produced 2037 stage events")
is a time window containing hundreds of independent traces, detected via
`--list-runs` (groups by >30s gaps -- in the normal case, everything
currently in the store *is* one run, since `run_demo.py` wipes the store at
the start of each invocation). `--report <run_index|latest>` runs the real
Zone + Environmental/Gas correlation analysis (`zone_gas_report.py`) over
that run's window and writes `zone_environmental_integration_report.md` --
every number in it is a real query result over that window's trace rows,
not inferred.

`./stop_demo.sh` tears down the containers (`--wipe-state` also clears the
trace store). Data lives at `.state/trace_events.db` (SQLite, WAL mode) --
inspect it directly with any SQLite client if you want ad-hoc queries
beyond what `event_history.py` exposes.

## Optional: richer fake data via Sentinel_Data_Engine

By default (`--data-source random`), sensor/worker/permit traffic comes
from this harness's own simple random-value simulators
(`fake_sensor_simulator.py` etc.). `Sentinel_Data_Engine/` is vendored at
the repo root (a separate project, still read-only, never modified) -- a
tick-based, physically-correlated plant simulator with richer scenario
escalation, correlated multi-sensor readings, worker biometrics/fatigue/
PPE, and permit lifecycles. Use it instead with:

```bash
./start_demo.sh --data-source data-engine --duration 90
```

No extra setup needed -- `harness_config.DATA_ENGINE_ROOT` defaults to
`<repo_root>/Sentinel_Data_Engine`. If you keep your copy somewhere else
instead, override it: `export DATA_ENGINE_ROOT=/path/to/Sentinel_Data_Engine`.

This runs one process (`fake_data_engine_simulator.py`) instead of three,
ticking a single shared `MasterEventGenerator` (its plant/timeline/
scenario state has to be shared to stay correlated -- three independent
generator instances would each drift on their own random timeline).
`data_engine_adapter.py` is the only file that knows about both
codebases' shapes; it maps Data Engine's `SensorEvent`/`WorkerEvent`/
`PermitEvent` onto the real `sentinel_contracts` Pydantic models before
anything touches Kafka. **Nothing in Sentinel_Data_Engine itself is
modified** -- same read-only principle as the rest of this harness.

A few fields don't survive the mapping cleanly, and the adapter is honest
about all of them rather than fabricating or silently dropping data --
full detail in `data_engine_adapter.py`'s module docstring:
- Data Engine's "Flame Detector" and "Machine Temperature" sensor types have no
  real `SensorType` equivalent; mapped to `SMOKE`/`TEMPERATURE` with the
  original type preserved in `raw_metadata`.
- Permit types `chemical`/`radiation`/`cold_work`/`line_break` have no real
  `PermitType` equivalent; those permits are skipped (logged once each,
  not silently dropped).
- The real `WorkerEventPayload` has no field for raw biometric values
  (heart rate, body temp, etc.) -- only a `BIOMETRIC_ALERT` event kind
  when Data Engine's vitals cross a threshold, no room to carry the number.
- The real `GeoLocation` is WGS84 lat/long; Data Engine's worker location
  is a local plant x/y/floor grid -- semantically different units, so
  `location` is left unset rather than faked.

## Why the pieces are built the way they are

- **Everything only talks through Kafka.** Every simulator and both agent
  workers are separate OS processes (`subprocess.Popen` in `run_demo.py`).
  Nothing imports another component's runtime state.
- **`event_logger.py`** is a shared SQLite store (WAL mode) -- the one
  thing that *isn't* Kafka connecting these processes, because "which
  stage did this trace reach" isn't something Kafka itself remembers as a
  queryable concept, and this harness needs to answer that after the fact.
- **`tracing_transport.py`** wraps the real `KafkaTransport` to log every
  produce/poll/commit. Legal to do without touching `sentinel_eventbus`
  because `Transport` is documented as a swappable Protocol in its own
  module docstring. One honest limitation: `KafkaTransport.produce()`
  doesn't populate partition/offset (confluent-kafka's delivery report is
  async and currently discarded except for errors) -- reported as
  unavailable, not guessed.
- **`environmental_agent_worker.py`** doesn't use `AgentRunner` -- it can't,
  legally (`AgentRunner` requires an output topic, and there is no legal
  one to give it for `EnvironmentAnalysis`). It drives
  `EnvironmentalIntelligenceAgent` directly, exactly as that agent's own
  `main.py` suggests in its comments.
- **`zone_agent_worker.py`** uses the real, unmodified `AgentRunner`. Its
  only addition is `_ObservedZoneAgent`, a subclass that calls the real
  `process()` exactly once (calling both the real class's `process()` *and*
  `main.py`'s filtering wrapper would double-execute stateful business
  logic -- Redis/Postgres writes, anomaly transition guards -- so the
  subclass replicates the wrapper's one-line, stateless filter instead of
  calling both).
- **`trace_id` == `str(correlation_id)`, always.** `producer.py`'s Kafka
  headers carry `correlation_id`, not the domain `trace_id` payload field --
  confirmed by reading it, not assumed. Every simulator sets its event's
  `trace_id` field equal to its `correlation_id` specifically so a trace
  can be followed through Kafka headers alone, without this harness
  re-implementing Avro deserialization just to read one field.

## Files

| File | Purpose |
|---|---|
| `harness_config.py` | Paths, topic names, Kafka/Redis config. (Named this, not `config.py`, to avoid colliding with the two agents' own `config.py` modules -- see its docstring.) |
| `event_logger.py` | Shared SQLite trace store + `timed_stage()`/`log_stage()` helpers. |
| `event_history.py` | Read-only query helpers over the store. |
| `tracing_transport.py` | Instrumented `Transport` wrapper. |
| `reset_topics.py` | Creates/verifies Kafka topics from the real registry. |
| `fake_sensor_simulator.py` | Publishes real `SensorEventV1` (9 scenarios, live-switchable). |
| `fake_worker_simulator.py` | Publishes real `WorkerEventV1`. |
| `fake_permit_simulator.py` | Publishes real `PermitEventV1` (deliberately includes conflicting permit pairs). |
| `fake_equipment_simulator.py` | Does not publish anything -- documents why (platform gap). |
| `data_engine_adapter.py` | Optional: maps Sentinel_Data_Engine's output onto the real contracts. |
| `fake_data_engine_simulator.py` | Optional: single process using the adapter above, replacing the 3 random simulators. |
| `environmental_agent_worker.py` | Drives the real Environmental Intelligence Agent. |
| `zone_agent_worker.py` | Drives the real Zone Intelligence Agent via real `AgentRunner`. |
| `kafka_topic_monitor.py` | Broker-level verification: topics, partitions, consumer group lag. |
| `consumer_monitor.py` | Agent-level stats: received/processed/failed/avg time. |
| `latency_monitor.py` | Throughput and latency (avg/p95) from the trace store. |
| `pipeline_visualizer.py` | Live colorized tail of the trace store. |
| `trace_dashboard.py` | Full stage-by-stage path for one trace ID, `--list-runs`, `--report`. |
| `zone_gas_report.py` | Generates `zone_environmental_integration_report.md` for one run window. |
| `failure_report.py` | Generates `integration_report.md`. |
| `run_demo.py` | Orchestrates all of the above. |
| `start_demo.sh` / `stop_demo.sh` | Thin shell wrappers. |
| `docker-compose.yml` | Healthcheck override on top of `scripts/dev-env/docker-compose.yml` (not a standalone stack). |

## A note on what "success" means here

A clean `integration_report.md` will never say 100% -- roughly a third of
the pipeline described in the original ask cannot exist until B1 (and the
`ZoneAnalysis`/equipment gaps) are fixed at the contract layer, which is
explicitly out of scope for this harness. What this harness proves is
everything on the "Works" side of the table above, with real Kafka
traffic, real trace IDs, and a report that says so exactly -- not more,
not less.

## What I could and couldn't verify from here

I read every file this harness touches and confirmed all imports/module
attributes resolve against your real code (`python3 -c "import ..."`
succeeds for every script in this folder, including both agent workers
pulling in `environmental_intelligence_agent`, `engine.*`,
`zone_intelligence_agent`, and both real `main.py` modules). I do not have
Docker or a Kafka broker in the sandbox I built this in, so I could not
run a live end-to-end pass myself -- `run_demo.py`'s actual Kafka
traffic, the consumer-lag numbers, and a populated `integration_report.md`
are all untested beyond the synthetic dry-run I used to validate
`failure_report.py`'s and `trace_dashboard.py`'s logic. Please run
`./start_demo.sh` yourself and treat the first real run as the actual
verification of this harness, not just of the platform.
