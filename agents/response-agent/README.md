# Response Agent

Action planner (`contracts/agent-registry/agents.yaml`: *"Action planner.
Proposes actions, never executes them directly."*). Converts an
authoritative `RiskScore` into one or more `ActionRequest` events, and
reacts to `ActionResult` failures with escalation. Never executes a
physical action itself — that authority belongs solely to the Action
Policy Gateway (`action_gateway`).

## Boundary (verified against `agents.yaml` **and** `kafka_topics.yaml`)

| | Topic | Schema |
|---|---|---|
| consumes | `sentinel.risk.score.v1` | `RiskScoreV1` |
| consumes | `sentinel.action.result.v1` | `ActionResultV1` |
| produces | `sentinel.action.request.v1` | `ActionRequestV1` |

`sentinel.action.result.v1` was already listed as a `response_agent`
consumer in `kafka_topics.yaml` before this task, but missing from
`agents.yaml`'s `consumes` list — a pre-existing registry drift, fixed as
part of this task (both files now agree), not a new dependency invented
unilaterally.

## Contract changes made for this task

The master prompt this agent was built from describes a much richer
emergency-decision model (cascade paths, propagation paths, affected
zones/personnel, acknowledgement workflows, escalation chains) than the
real `RiskScoreV1`/`ActionRequestV1` schemas carried. Rather than invent a
second, competing shape alongside the real contracts (which the master
prompt itself forbids — *"do not create a second incompatible action
model"*), the real contracts were extended with **additive, optional,
non-breaking fields**, per `contracts/versioning/compatibility_rules.md`
(adding an optional field / a new enum value are both listed there as
non-breaking, same-version changes — no `v2` topic or dual-write needed):

- **`RiskScore` v1** gained: `affected_zones`, `affected_assets`,
  `human_exposure_confirmed`, `critical_controls_unavailable`,
  `propagation_paths`, `cascade_paths`. All default to empty/false. **An
  empty/false value means "the producer did not populate this," never
  "confirmed absent."** Risk Orchestrator (the real producer) is a
  separate agent, out of scope here, and does not populate these fields
  yet — see PLATFORM_GAP below.
- **`ActionRequest` v1** gained 9 new `ActionType` enum values
  (`ISOLATE_ZONE`, `RESTRICT_ACCESS`, `STOP_WORK`, `SHELTER_IN_PLACE`,
  `SHUTDOWN_REQUEST`, `DISPATCH_RESPONSE_TEAM`, `REQUEST_HUMAN_REVIEW`,
  `CREATE_INCIDENT`, `INCREASE_MONITORING`) plus `priority`,
  `lifecycle_state`, `emergency_triggered`, `trigger_reason`,
  `acknowledgement_required`, `acknowledgement_deadline`, `deadline`.
- `contracts/agent-registry/agents.yaml`: added `action_result` to
  `response_agent.consumes` (drift fix, see above) and `action_gateway` to
  `dependencies`.
- `libs/sentinel_state/redis_repositories.py`: added
  `ResponseTrackingRepository` (idempotency dedupe, previous-risk-per-zone
  cache for escalation-velocity detection, active-response state, and
  action-id → originating-risk provenance for `ActionResult` handling),
  wired into `StateContainer` as `self.state.response`. This is this
  agent's own private working memory — never wire format, never read by
  another agent.

All edits are hand-synced with `contracts/events/*/v1/schema.avsc` (the
source of truth); the codegen tool (`tools/codegen/avro_to_pydantic.py`)
was not re-run because its `OUT_ROOT` still points at the deprecated
`libs/sentinel_contracts/generated/` location (see
`libs/sentinel_contracts/DEPRECATED.md`) and its `render_module` emits
relative imports (`from ..common.X import Y`), which doesn't match this
package's actual absolute-import style — running it as-is would not
reproduce the canonical files even before this task's edits. Pre-existing
gap, not introduced here.

## PLATFORM_GAP notes

- **`ActionRequest` v2 is not dual-written.** `kafka_topics.yaml`
  registers `sentinel.action.request.v2` ahead of any real producer, with
  a note that dual-write should begin "once a real producer exists." This
  agent is that producer, but publishes only to v1, for two independent
  reasons: (1) v2's only difference from v1 is an unrelated field rename
  (`justification` → `explanation`) from a prior, already-decided
  migration this task did not start — the new emergency-model fields went
  into v1 directly, so v1 already says everything this agent needs to say;
  (2) `AgentRunner`'s output-topic routing dispatches by a result's
  `event_type` string, and `ActionRequestV1`/`V2` both default `event_type`
  to the literal string `"ActionRequest"` — there's no way to route the
  "same" event to two topics through `output_topics` today. A real
  dual-write needs either a runner-level change or a second `publish()`
  call the SDK doesn't expose to agent authors by design. Flagged rather
  than faked.
- **The "multiple simultaneous hazards" emergency trigger (master prompt
  §4.E) is approximated**, not solved: `RiskScoreV1` has no typed list of
  distinct hazard categories, only `compound_rules_fired` (rule IDs).
  `domain/emergency_evaluator.py`'s `_multiple_hazards()` treats ≥2 fired
  compound rules as a proxy signal. It is not a semantic guarantee the
  rules concern genuinely different hazards. A real fix needs a typed
  `hazard_categories` field on `RiskScorePayload`.
- **Acknowledgement-timeout escalation (master prompt §14, test scenario
  8) is not implemented.** Every action that requires acknowledgement
  carries a populated `acknowledgement_deadline`, so the *data* a
  timeout-sweeper would need already exists on the wire — but detecting
  "no ack arrived by the deadline" needs a scheduler/polling component
  external to a purely Kafka-event-reactive agent, which is out of scope
  here.
- **Notification-channel failure escalation (test scenario 7) has no
  event to react to.** A `NotificationEvent` schema exists in
  `contracts/events/`, but no Kafka topic for it is registered in
  `kafka_topics.yaml` and nothing produces it — there's nothing for this
  agent to consume yet.
- Risk Orchestrator does not yet populate the new optional `RiskScore`
  fields (`affected_zones`, `cascade_paths`, etc.) — every emergency
  trigger that depends on them degrades to "not detected" until it does,
  per `compatibility_rules.md`'s semantics for an unpopulated optional
  field. This agent's tests exercise both the populated and unpopulated
  paths explicitly (see `tests/unit/test_emergency_evaluator.py`).

## Code layout

- `domain/` — pure decision logic, no I/O, fully unit-testable:
  `emergency_evaluator.py` (§4-§6), `response_classifier.py` (§3),
  `action_planner.py` (§7-§18).
- `models/action_plan.py` — internal (non-wire) representation of one
  planned action, before `services/response_service.py` converts it to a
  real `ActionRequestV1`.
- `services/response_service.py` — the seam to the wire/state world:
  idempotency, escalation-velocity, active-response tracking, and
  `ActionRequestV1`/envelope construction.
- `agent.py` — the `BaseAgent` subclass (`process()` only, per
  `sentinel_agent_sdk`'s design).
- `main.py` — `AgentRunner` wiring only, no business logic.
- `handlers/`, `memory/` — unused; superseded by the above, matching the
  established pattern in every other built agent in this repo (e.g.
  `permit_intelligence_agent`).

## Running the tests

```
PYTHONPATH=libs:agents/response-agent/src pytest agents/response-agent/tests/unit
```

These are plain unit tests (no Kafka, no Redis — `tests/unit/conftest.py`
supplies a `FakeResponseTrackingRepository` in-memory stand-in). They
could not be executed inside the environment this task was authored in
(no network access, `pydantic` not installed and not fetchable) — verified
instead by `python3 -m py_compile` on every file plus careful manual
trace-through of each test against the implementation. Please run them for
real before merging.
