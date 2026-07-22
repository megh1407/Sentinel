# PermitAnalysis: JSON Schema -> Avro field mapping (Phase 1)

Source: contracts/agent-contracts/v1/permit_analysis.schema.json (`allOf: agent_result.schema.json`)
Convention followed: ZoneAnalysis.avsc / EnvironmentAnalysis.avsc (envelope + agent_result fields
inlined, since Avro has no inheritance -- same pattern, same doc string convention).

## Envelope + AgentResult fields (identical across all *Analysis.avsc siblings -- copied verbatim,
## not reinvented)

event_id, event_type(default="PermitAnalysis"), event_version(default=1), event_timestamp,
correlation_id, causation_id(nullable), producer_service, producer_version, site_id,
zone_id(nullable), partition_key, trace_id(nullable), metadata, agent_id, agent_version,
input_events, result_type(default="permit_analysis"), confidence(double, required -- envelope-level,
distinct from payload.confidence below, matching ZoneAnalysis's own duplication of the field at both
levels), processing_time_ms(int), error(nullable PermitAnalysisError record), explanation(required
com.sentinel.common.ExplanationObject), payload(PermitAnalysisPayload, below).

## payload fields (PermitAnalysisPayload) -- the part that's actually PermitAnalysis-specific

| JSON Schema field       | In JSON `required`? | Avro field               | Avro type                                   | Default |
|--------------------------|:---:|---------------------------|----------------------------------------------|---------|
| `permit_id`               | yes | `permit_id`               | `string` (logicalType uuid)                   | none (required) |
| `permit_risk_level`       | no  | `permit_risk_level`       | `["null", enum{acceptable,elevated,high,unacceptable}]` | `null` |
| `risk_score`               | yes | `risk_score`               | `double`                                      | none (required) |
| `confidence`               | yes | `confidence`               | `double`                                      | none (required) |
| `conflicts`                | yes | `conflicts`                | `array<PermitConflict>`                       | none (required, may be empty array) |
| `conflicts[].conflicting_permit_id` | no (no `required` on sub-object) | `conflicting_permit_id` | `["null", string(uuid)]` | `null` |
| `conflicts[].conflict_type` | no | `conflict_type`           | `["null","string"]`                           | `null` |
| `conflicts[].severity`     | no  | `severity`                 | `["null", enum{advisory,warning,blocking}]`   | `null` |
| `zone_compatibility`       | no  | `zone_compatibility`       | `["null","boolean"]`                          | `null` (this is the Avro-level encoding of "UNKNOWN" -- matches the agent's own `bool | None` internal representation exactly) |
| `zone_risk_at_issuance`    | no  | `zone_risk_at_issuance`    | `["null","double"]`                           | `null` |
| `evidence`                 | yes | `evidence`                 | `array<string>`                               | none (required) |
| `recommendations`          | yes | `recommendations`          | `array<string>`                               | none (required) |
| `analyzed_at`              | yes | `analyzed_at`               | `long` (logicalType timestamp-millis)         | none (required) |

No fields invented beyond what `permit_analysis.schema.json` declares. No enum values invented --
`permit_risk_level` and `conflicts[].severity` enums copied verbatim from the JSON Schema's `enum`
arrays.

## One real conflict found and resolved (Phase 1 Rule: "if the existing contract sources conflict,
## STOP and report the exact conflict before proceeding" -- reported here, not silently patched)

`permit_analysis.schema.json` declares `payload.permit_id` and `payload.conflicts[].conflicting_permit_id`
as `{"type": "string", "format": "uuid"}`. But the field these values actually come from --
`PermitEvent.payload.permit_id` in the frozen, canonical `contracts/events/PermitEvent/v1/schema.avsc`
-- is declared as plain `string`, with no uuid constraint, and real permit identifiers observed in
this system (e.g. from PermitEventPayload construction in tests/production code) are business-style
strings, not UUIDs (example: `"P-1a5e1e3c"`). A literal translation of `format: uuid` into Avro's
`logicalType: uuid` (and therefore into a strict Pydantic `UUID` field) would make the resulting
contract permanently unable to hold a real permit_id from the very event this analysis is about --
confirmed by construction failure the first time a real (non-UUID) permit_id was validated against it.

**Resolution:** `permit_id` and `conflicting_permit_id` are encoded as plain `string` in
`PermitAnalysis.avsc`, matching the real upstream source of truth (`PermitEvent.payload.permit_id`)
rather than the JSON Schema's own internally-inconsistent `format: uuid` annotation. This is the only
technically coherent resolution -- the alternative (keeping `format: uuid`) is not a stricter-but-valid
interpretation, it's simply wrong given what permit_id actually is elsewhere in the same contract
family. No other field required this kind of resolution; everything else translated mechanically.

