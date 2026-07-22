# SENTINEL Redis State Model

## Key Conventions
- TTL: all hot-state keys carry TTL; set via agent output `ttl_seconds`
- Serialization: JSON-encoded values
- Keyspace notifications: enabled for expiry events
- Clustering: consistent hashing on zone_id prefix

---

## Hot State Keys

### Zone State
**Key:** `sentinel:zone_state:{site_id}:{zone_id}`
**Type:** Hash · **TTL:** 60s
**Fields:** zone_state, risk_score, severity, worker_count, confidence, updated_at, agent_version, correlation_id
**Producer:** Zone Intelligence Agent · **Consumer:** Risk Orchestrator, Dashboard, Response Agent

### Live Risk Score
**Key:** `sentinel:risk:{site_id}:{zone_id}`
**Type:** Hash · **TTL:** 30s (matches risk_score.ttl_seconds)
**Fields:** risk_id, score, severity, explanation, computed_at
**Producer:** Risk Orchestrator · **Consumer:** Dashboard, Response Agent, Safety Copilot

### Active Permits Per Zone
**Key:** `sentinel:permits:{site_id}:{zone_id}`
**Type:** Set (permit UUIDs) · **TTL:** None
**Operations:** SADD on permit.activated, SREM on permit.suspended/revoked/expired
**Producer:** Permit Intelligence Agent

### Worker Presence
**Key:** `sentinel:workers:{site_id}:{zone_id}`
**Type:** Hash (worker_id → JSON) · **TTL:** 90s per field
**Value:** `{"x":12.3,"y":45.6,"floor":2,"ppe_compliance":0.95,"updated_at":"..."}`
**Producer:** Worker Safety Agent · **Consumer:** Zone Intelligence Agent

### Equipment Fault Flags
**Key:** `sentinel:equip_fault:{site_id}:{equipment_id}`
**Type:** String (JSON) · **TTL:** Until maintenance.completed clears it
**Value:** `{"fault_codes":["E001","E047"],"criticality":"high","flagged_at":"..."}`

### Correlation Trace Cache
**Key:** `sentinel:trace:{correlation_id}`
**Type:** List · **TTL:** 24h
**Purpose:** Fast trace lookup without hitting Postgres audit table

---

## Pub/Sub Channels

| Channel | Publisher | Subscribers |
|---------|-----------|-------------|
| `sentinel:alert:{site_id}:{zone_id}` | Risk Orchestrator | Dashboard, Safety Copilot |
| `sentinel:action:{site_id}` | Response Agent | Action Gateway |
| `sentinel:evacuation:{site_id}` | Response Agent | All zone channels |
