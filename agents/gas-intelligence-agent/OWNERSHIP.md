# Ownership status: folded into `environmental_intelligence_agent`

This folder is **not** an independently registered agent and should not be
implemented as one.

**Repository evidence:**
- `contracts/agent-registry/agents.yaml` registers `environmental_intelligence_agent`
  with the description *"Environmental hazard monitoring — gas, temperature,
  pressure"* — gas is already explicitly in scope for that agent.
- `contracts/topics/kafka_topics.yaml` has no `sentinel.gas.*` topic, and no
  `gas_*` schema exists anywhere under `contracts/`. There is no contract for
  this folder to implement against.
- `environmental_intelligence_agent` already consumes `sentinel.sensor.events.v1`
  (the same raw sensor stream a gas-specific agent would need) and produces
  `sentinel.environment.analysis.v1`.

**Resolution:** gas-hazard logic belongs inside `environmental_intelligence_agent`.
This folder is kept as an empty placeholder only; it has no registry entry, no
topic, and should not be assigned to an engineer as standalone work. If gas
detection later proves to need its own contract/topic, that is a new
architecture decision outside the scope of this freeze pass — not something
to build against today's scaffolding.
