# SENTINEL Knowledge Graph Schema

Backend: Neo4j cluster. Used by the Incident Intelligence Agent for causal-chain reasoning that vector similarity alone cannot capture (e.g. "which equipment failures have historically preceded gas leaks in confined spaces").

---

## Node Types

### Zone
```
(:Zone {
  zone_id: string,
  site_id: string,
  zone_type: string,
  hazard_classes: [string]
})
```

### Equipment
```
(:Equipment {
  equipment_id: string,
  equipment_type: string,
  criticality: string
})
```

### Worker
```
(:Worker {
  worker_id: string,
  role: string,
  certifications: [string]
})
```
Note: PII-minimized. Worker nodes store role/certifications only — no names, no biometric history. Full worker identity stays in Postgres with access-controlled joins.

### Permit
```
(:Permit {
  permit_id: string,
  permit_type: string,
  issued_at: datetime
})
```

### Incident
```
(:Incident {
  incident_id: string,
  incident_type: string,
  severity: string,
  occurred_at: datetime,
  root_cause: string
})
```

### Hazard
```
(:Hazard {
  hazard_type: string,
  category: string  // chemical, mechanical, environmental, electrical
})
```

---

## Relationship Types

| Relationship | From → To | Properties |
|---|---|---|
| LOCATED_IN | Equipment → Zone | since: datetime |
| WORKED_IN | Worker → Zone | timestamp, duration_min |
| ISSUED_FOR | Permit → Zone | valid_from, valid_until |
| OCCURRED_IN | Incident → Zone | — |
| INVOLVED | Incident → Equipment | role: "cause" \| "affected" |
| INVOLVED | Incident → Worker | role: "injured" \| "witness" \| "responder" |
| PRECEDED_BY | Incident → Incident | time_gap_hours, contributing: boolean |
| EXHIBITS | Equipment → Hazard | first_observed: datetime |
| MITIGATES | Permit → Hazard | control_measure: string |
| CAUSED_BY | Incident → Hazard | confidence: float |

---

## Example Traversal Query

Used by Incident Agent to answer: "What equipment failure patterns preceded similar incidents in confined-space zones?"

```cypher
MATCH (current:Zone {zone_id: $zone_id})-[:EXHIBITS]-(h:Hazard {hazard_type: $hazard_type})
MATCH (past:Incident)-[:CAUSED_BY]->(h)
MATCH (past)-[:OCCURRED_IN]->(z:Zone {zone_type: current.zone_type})
MATCH (past)-[:INVOLVED]->(eq:Equipment)
WHERE past.severity IN ['major','critical','catastrophic']
RETURN past.incident_id, past.root_cause, eq.equipment_type, past.occurred_at
ORDER BY past.occurred_at DESC
LIMIT 10
```

## Sync Strategy

The knowledge graph is updated asynchronously via a dedicated consumer (`kg-sync-service`) that subscribes to `sentinel.incident.events.v1`, `sentinel.permit.events.v1`, and `sentinel.equipment.state.v1`. Graph writes are idempotent on `event_id` to support replay.
