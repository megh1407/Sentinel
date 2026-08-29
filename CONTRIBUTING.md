# Contributing to SENTINEL

Thanks for taking a look at this project. This is a reference
implementation / portfolio project, not a large open-source community yet,
so this guide is intentionally short — it documents what actually works
today, not an aspirational process.

## Prerequisites

- Python 3.12+
- Node.js (only for `dashboard/` work)
- Docker (only if you want the local infrastructure stack — see
  `scripts/dev-env/docker-compose.yml`; not required for the Python
  test/contract workflow below)

## Setup

```
make install
```

Installs everything in `requirements.txt`, including test dependencies.

## Before opening a PR

Run these two commands — both are exactly what CI runs
(`.github/workflows/contract-validate.yml` and `contract-test.yml`), so a
green result here means CI will be green too:

```
make validate-contracts
make test
```

`make test` covers the three agents with a supported, infrastructure-free
test suite (`environmental-intelligence-agent`, `risk-orchestrator-agent`,
`worker-safety-agent`). See `README.md`'s "Tests" section for what's out
of scope and why.

## Dashboard changes

```
cd dashboard
npm ci
npm run build
npm run lint
```

`npm run lint` currently reports 19 pre-existing `@typescript-eslint/
no-explicit-any` errors (see `README.md`'s known-limitations note) — a PR
that doesn't touch the affected files isn't expected to fix those, but
please don't add new ones.

## Agent development

See `AGENT_GUIDE.md` for the reference pattern (`zone_intelligence_agent`,
`hello_agent`) and `contracts/agent-registry/agents.yaml` for what an
agent is expected to consume/produce. `agents/hello_agent/` is a
documented minimal reference — please don't repurpose it into a real
agent; copy the pattern instead.

## Commit expectations

- Keep changes scoped to what the PR describes — no unrelated formatting
  or refactors bundled in.
- If a change touches a contract (`contracts/`, `sentinel_contracts/`),
  run `make validate-contracts` and mention the result in the PR.
- If a change affects test behavior, explain why in the commit message —
  see this repository's own git history for examples of that discipline
  (e.g. commits `f858ca5`, `df82d43`) where a test was corrected only
  after tracing why it was stale, not just to get to green.

## Security

See `SECURITY.md` for how to report a vulnerability. Please don't open a
public issue for a security-sensitive finding.

## Known limitations you don't need to "fix" in an unrelated PR

See `README.md`'s "Current implementation status" and "Known
non-blocking limitations" sections — the five empty platform services,
one-hop-only risk correlation, and the unresolved LICENSE status are
documented, known, and not silently missing; they're just not this
project's current scope unless a PR is specifically about them.
