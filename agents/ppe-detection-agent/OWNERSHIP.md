# Ownership status: folded into `worker_safety_agent`

This folder is **not** an independently registered agent and should not be
implemented as one.

**Repository evidence:**
- `contracts/agent-registry/agents.yaml` registers `worker_safety_agent` with
  the description *"Human safety monitoring — PPE, location, biometrics"* —
  PPE is already explicitly in scope for that agent.
- `contracts/topics/kafka_topics.yaml`'s `sentinel.worker.events.v1` topic
  description is *"Worker location, PPE, biometric telemetry"*, produced in
  part by `ppe-vision-service`, and consumed by `worker_safety_agent`.
- No `sentinel.ppe.*` topic and no `ppe_*` schema exists anywhere under
  `contracts/`. There is no contract for this folder to implement against.

**Resolution:** PPE-detection logic belongs inside `worker_safety_agent`. This
folder is kept as an empty placeholder only; it has no registry entry, no
topic, and should not be assigned to an engineer as standalone work.
