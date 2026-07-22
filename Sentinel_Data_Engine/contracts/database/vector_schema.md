# SENTINEL Vector Database Schema

Backend: Pgvector (Postgres extension) or Weaviate, depending on deployment scale.
Embedding model: text-embedding-3-large (3072-dim) or domain-tuned alternative.

---

## Collection: incident_memory

Stores embedded representations of past safety incidents for similarity retrieval by the Incident Intelligence Agent.

**Embedded text** = concatenation of: `description + root_cause + contributing_factors + remediation_taken`

| Field | Type | Description |
|---|---|---|
| incident_id | uuid | FK to Postgres `incidents` table |
| embedding | vector(3072) | Dense embedding of incident narrative |
| site_id | uuid | Filter dimension |
| zone_type | string | Filter dimension — match similar zone types across sites |
| incident_type | string | gas_leak, fire, equipment_failure, etc. |
| severity | string | Filter / boost dimension |
| occurred_at | timestamp | Recency boost factor |
| metadata | jsonb | Full incident record for retrieval display |

**Index:** HNSW, cosine distance, m=16, ef_construction=200
**Query pattern:** Given current risk context embedding, return top-K (default 5) most similar incidents above similarity threshold 0.75, optionally filtered by `zone_type` or `incident_type`.

---

## Collection: safety_documents

Safety Data Sheets (SDS), OSHA/COSHH regulatory text, SOPs, and equipment manuals — chunked for RAG retrieval by Incident Agent and Safety Copilot.

| Field | Type | Description |
|---|---|---|
| chunk_id | uuid | Unique chunk identifier |
| document_id | uuid | Parent document |
| document_type | string | sds, regulation, sop, manual |
| embedding | vector(3072) | Chunk embedding |
| chunk_text | text | Raw chunk content (max 512 tokens) |
| chunk_index | int | Position within document |
| hazard_tags | string[] | Extracted hazard classifications |
| applicable_equipment | string[] | Equipment types this chunk applies to |
| source_url | string | Original document reference |

**Index:** HNSW, cosine distance
**Chunking strategy:** Semantic chunking with 50-token overlap, max 512 tokens per chunk.

---

## Collection: shift_logs

Operator shift handover notes and observations — provides soft context the structured event stream may miss.

| Field | Type | Description |
|---|---|---|
| log_id | uuid | Unique log entry |
| embedding | vector(3072) | Log text embedding |
| site_id | uuid | Filter dimension |
| zone_id | uuid | Filter dimension (nullable — some logs are site-wide) |
| shift_date | date | Filter dimension |
| author_id | uuid | Operator who logged the entry |
| log_text | text | Raw shift note |
| flagged_concern | boolean | Operator-flagged as safety concern |

**Index:** HNSW, cosine distance
**Retention:** 2 years, then archived to cold storage (not deleted — regulatory requirement)
