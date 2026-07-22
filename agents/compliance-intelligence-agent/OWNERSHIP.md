# Ownership status: unresolved — blocked, not registered

This folder is **not** an independently registered agent, and unlike
`gas-intelligence-agent`, `ppe-detection-agent`, and
`equipment-health-intelligence-agent`, it does **not** clearly fold into an
existing registered agent either.

**Repository evidence:**
- None of the 9 registered agents in `contracts/agent-registry/agents.yaml`
  describe a compliance/regulatory responsibility (Factory Act, OISD, DGMS,
  OSHA, ISO, audit trail, violations). The closest adjacent artifact,
  `contracts/audit/audit_event.schema.json`, is owned by `audit-service`
  under `platform-services/` (a platform service, not an intelligence agent),
  and is not a substitute for a compliance-reasoning contract.
- No `sentinel.compliance.*` topic exists in `contracts/topics/kafka_topics.yaml`,
  and no `compliance_analysis` (or similar) schema exists anywhere under
  `contracts/agent-contracts/`.

**Resolution:** this cannot be fixed within this freeze pass. Registering it
as an independent agent would require inventing a new topic and a new
contract, which this pass is explicitly not authorized to do. Folding it into
an existing agent would misattribute a responsibility no registered agent
currently claims. This folder should remain unassigned until an architect
makes an explicit decision on where compliance reasoning lives — that
decision is new architecture and is out of scope here.
