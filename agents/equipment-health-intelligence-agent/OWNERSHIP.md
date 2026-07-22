# Ownership status: folded into `maintenance_intelligence_agent`

This folder is **not** an independently registered agent and should not be
implemented as one.

**Repository evidence:**
- `contracts/agent-registry/agents.yaml` registers `maintenance_intelligence_agent`
  with the description *"Equipment health intelligence and failure
  prediction"* — this is the exact domain this folder's name describes.
- `contracts/topics/kafka_topics.yaml`'s `sentinel.equipment.state.v1` topic
  is produced by `maintenance_intelligence_agent` (see also the Fix 2
  reconciliation in `agents.yaml`, which now records this explicitly).
- No separate `sentinel.equipment_health.*` topic or schema exists anywhere
  under `contracts/`. There is no contract for this folder to implement
  against.

**Resolution:** equipment-health logic belongs inside
`maintenance_intelligence_agent`. This folder is kept as an empty placeholder
only; it has no registry entry, no topic, and should not be assigned to an
engineer as standalone work.
