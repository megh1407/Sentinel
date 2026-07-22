# Phase 11 demo generator

`run_demo.py` publishes the exact T0-T5 scenario from the master
integration prompt onto the real Kafka(-equivalent) topics the four real
agents subscribe to -- not a frontend-only simulation, not fabricated
dashboard state.

## Two ways to run it

**Preferred -- against a running API gateway** (see
`platform-services/api-gateway/README.md`):

```bash
curl -X POST http://localhost:8000/api/demo/start
```

This runs the same scenario code (`run_demo()` from this file, imported
directly) inside the gateway process, so its events land in the same
`InMemoryTransport` instance the four agents are actually consuming from.

**Standalone** (`python scripts/demo/run_demo.py`): only useful for
inspecting the events themselves (they get printed) or once `KafkaTransport`
is swapped in (see the api-gateway README) and a real broker is running --
against `InMemoryTransport`, a standalone process's topic log is private to
that process and won't reach a separately-running gateway.

## What it does NOT do

Per the master prompt's Phase 11 instruction, this script does not compute
or claim any compound-risk decision -- it only publishes independent
signals (temperature, a gas reading, a permit going active, a PPE
violation) and lets each of the four real agents react independently. That
convergence is exactly the gap the future Risk Orchestrator fills.

It also does not pretend to solve B3 (gas-species disambiguation, see the
integration report): the "methane increases" step publishes a generic
`SensorType.GAS` reading, flagged inline in the script, because that's the
only value the real `SensorEventPayload` contract supports today.
