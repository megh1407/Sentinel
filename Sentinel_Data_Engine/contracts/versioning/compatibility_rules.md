# SENTINEL Schema Versioning & Compatibility Rules

## Principle

All schemas in this contract system follow **BACKWARD compatibility** by default,
enforced by Schema Registry on every produce call. This means: a new schema
version can read data written with an older schema version, so consumers can
upgrade independently of producers.

---

## Non-breaking changes (same version, e.g. v1 → v1)

These changes are safe to deploy without coordinating with consumers:

- Adding a new **optional** field
- Adding a new enum value (consumers must implement a default/unknown-value branch)
- Widening a numeric type (int → float)
- Adding new items to an array's allowed object shape (additive only)
- Adding new topics (doesn't affect existing topic consumers)
- Relaxing a constraint (e.g. removing a maximum on a previously bounded field)

## Breaking changes (require new version, e.g. v1 → v2)

These require a new schema version AND typically a new Kafka topic:

- Removing or renaming a required field
- Changing a field's type incompatibly (string → object)
- Removing an enum value a consumer depends on
- Changing the meaning of an existing field without changing its name
- Changing the partition key semantics
- Restructuring nested payload shape
- Changing a field from optional to required

---

## Migration procedure (v1 → v2)

1. New schema registered as `io.sentinel.events.v2.{SchemaName}` in Schema Registry.
2. New Kafka topic created: `sentinel.{domain}.{type}.v2`.
3. Producer updated to **dual-write**: publishes to both v1 and v2 topics for the migration window (minimum 30 days, or until all consumers confirm migration).
4. Each consumer migrates independently:
   a. Deploy consumer code that can read v2.
   b. Switch consumer group to v2 topic.
   c. Confirm no errors for 48 hours.
5. Once `agent-registry/agents.yaml` shows zero consumers still on v1 for this schema, producer stops dual-write.
6. v1 topic retained for the configured retention period (replay safety net), then decommissioned.
7. Update `agent-registry/agents.yaml` and `topics/kafka_topics.yaml` to remove the v1 references.

## Versioning the agent-registry itself

`agent-registry/agents.yaml` and `topics/kafka_topics.yaml` are themselves versioned
artifacts under git. Any change to either file requires:
- A pull request reviewed by the owning team (see `owner` field per agent)
- CI validation that every referenced topic/schema exists
- CI validation that no consumer references a topic version not yet GA

## Deprecation policy

- A schema/topic marked deprecated must remain functional for **minimum 90 days**.
- Deprecation must be announced in `#sentinel-platform-changes` with a migration guide.
- `agents.yaml` entries for deprecated dependencies are flagged with `deprecated: true` and a `sunset_date`.

## Compatibility testing in CI

Every schema change triggers automated compatibility checks against:
1. The last 3 GA versions of that schema (registry compatibility check)
2. Replay of the last 24 hours of production traffic for that topic against the new schema (canary validation)
3. Consumer contract tests defined per-agent in their respective repos
