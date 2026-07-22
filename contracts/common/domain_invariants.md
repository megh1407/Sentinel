# Domain Invariants

Numbered, citable business-domain rules referenced by doc string or comment
elsewhere in the contract tree (e.g. `(Domain Invariant #3)`). A citation to
a number not listed here, or a rule stated here that no longer matches its
citing site, is a defect to be fixed at the citing site or here — never
silently ignored.

This registry exists because `ActionRequest`'s and `RiskScore`'s existing
doc-string citations to "Domain Invariant #3" / "#4" pointed at a registry
that did not yet exist anywhere in the repository (Artifact 6, Open Item
Carried Forward). It lists only the invariants already cited elsewhere in
the codebase today — no additional numbers are reserved or implied.

---

## Domain Invariant #3

**Every Action references exactly one RiskScore.**

An `ActionRequest`'s `payload.risk_id` is required and must identify the
single `RiskScore` that justified the proposed action. An action is never
proposed independent of a risk determination.

**Cited at:** `contracts/events/ActionRequest/v1/schema.avsc` (`payload.risk_id`).

## Domain Invariant #4

**No finding may be published without a populated explanation.**

Every decision-bearing event or agent result — a `RiskScore`, an
`AgentResult`, or any other Intelligence/Action-category output — must
carry a non-null, populated `ExplanationObject`, including for a
`NO_FINDING` result. Explanation is never omitted or deferred, and an
empty/absent `evidence` list is never acceptable for a non-`NO_FINDING`
result.

**Cited at:**
- `contracts/events/RiskScore/v1/schema.avsc` (`explanation` field doc)
- `agents/hello_agent/hello_agent.py` (module doc string)
- `tests/test_hello_agent_e2e.py` (`result.explanation.evidence` assertion)

---

## Closing Note

Only invariants #3 and #4 are cited anywhere in the repository as of this
writing. No other numbered invariant exists; none is reserved in advance.
