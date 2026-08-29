# SENTINEL — Industrial Safety Intelligence Platform

Phase 2 remediation note (SENTINEL forensic audit): this file did not
previously exist, even though `ARCHITECTURE.md`, the root `Makefile`, and
`scripts/validate-contracts.sh` all cited a root `README.md`. This file
resolves that — see `ARCHITECTURE.md` for the full architecture writeup and
`AGENT_GUIDE.md` for how to build a new agent; this file is the entry point.

## What SENTINEL is

A contract-first, event-driven reference implementation of an industrial
safety intelligence platform: intelligence agents analyze zone/worker/
equipment/permit/environment/incident events, a Risk Orchestrator
correlates their findings into a risk score, and a Response Agent proposes
(never executes) actions. See `ARCHITECTURE.md` for the full pipeline
diagram and component descriptions.

## Repository structure (as built)

```
contracts/              Avro/.avsc + JSON Schema + registry YAMLs (source of truth)
sentinel_contracts/     Generated Pydantic models (DO NOT HAND-EDIT; see that file's own header)
libs/
  sentinel_common/      Logging/errors/metrics/tracing
  sentinel_eventbus/     Transport abstraction: real InMemoryTransport (default) + real KafkaTransport (opt-in)
  sentinel_state/        Redis/Postgres/Neo4j/Qdrant repositories
  sentinel_agent_sdk/    BaseAgent, AgentRunner, DI container, health checks
agents/                  One directory per agent -- see AGENT_GUIDE.md
platform-services/
  api-gateway/           The only substantially implemented platform service
  action-policy-gateway/, audit-service/, configuration-service/,
  ingestion-gateway/, notification-service/
                         Documented as missing -- each is an empty Dockerfile,
                         not a stub with partial logic. Not required for the
                         current agent pipeline or demo to run.
dashboard/               Next.js UI
scripts/                 Demo runners, contract validation
.github/workflows/       CI (see "CI" below)
```

## Prerequisites

- Python 3.12+
- Node.js (only if you're running `dashboard/`; not required for the
  agent/contract test workflow below)
- Docker (only if you want the full `docker-compose` stack with a real
  Kafka broker, Redis, Postgres, Neo4j; **not required** for the
  contract-validation or unit-test workflow below, both of which run
  entirely against local files and the in-memory transport)

## Configuration

Copy `.env.example` to `.env` and adjust if you need something other
than local defaults -- every variable already has a working local-dev
default baked into the code, so this step is optional unless you're
pointing at non-default infrastructure. See `.env.example` itself for
what each variable controls.

## Running the API gateway

```
docker build -f platform-services/api-gateway/Dockerfile -t sentinel-api-gateway .
docker run -p 8000:8000 -e REDIS_HOST=<your-redis-host> sentinel-api-gateway
```

Build context must be the repository root (not `platform-services/
api-gateway/`) -- the gateway dynamically imports agent source from
`agents/` at runtime, so the image needs that alongside its own code.
Requires a reachable Redis. Runs as a non-root user and excludes
caches/env files from the build context via `.dockerignore`. **This
Dockerfile has not been build-verified in this environment (no Docker
available)** -- it was written by directly tracing what the gateway's
own runtime code needs, but hasn't been run end-to-end; treat it as a
starting point and verify locally before relying on it.

By default the gateway allows all CORS origins (`SENTINEL_ENVIRONMENT`
unset or `development`) -- fine for local dev. Setting
`SENTINEL_ENVIRONMENT=production` requires `SENTINEL_ALLOWED_ORIGINS`
(comma-separated) to be set explicitly, or the service refuses to start
with a wildcard policy. This is not authentication -- see "Security /
deployment caveats" below.

## Installation

```
make install
```

Installs everything in `requirements.txt`, including test dependencies
(`pytest`, `pytest-asyncio`, `jsonschema`).

## Contract validation

```
make validate-contracts
```

Runs `schema_loader.py` (Avro schema syntax) and
`envelope_conformance_lint.py` (envelope-shape conformance) against every
schema and topic in `contracts/`. This is the same check
`.github/workflows/contract-validate.yml` runs in CI.

## Tests

```
make test
```

Runs the supported Python test suites: `environmental-intelligence-agent`,
`risk-orchestrator-agent` (`tests/unit` only -- see below), and
`worker-safety-agent`. No infrastructure (Docker, Redis, Kafka) is required
-- these suites use `InMemoryTransport` and in-memory fakes throughout.

Each agent's own `pyproject.toml` declares a `[tool.pytest.ini_options]`
`pythonpath` entry, so you do **not** need to manually export `PYTHONPATH`
-- just run `make test` from the repo root, or `cd` into an individual
agent directory and run `pytest` there directly.

Not currently run by `make test` (out of scope for this remediation pass,
not silently broken):
- `risk-orchestrator-agent/tests/{load,chaos,performance,production_validation}`
  -- require live infrastructure (Redis/Postgres/Neo4j/Kafka).
- `Sentinel_Data_Engine/tests` -- a separate sub-project with its own
  `requirements.txt`; not part of the agents/contracts workspace this
  Makefile targets.
- The remaining ~9 agents under `agents/` either have no `tests/`
  directory yet or were out of scope for this audit/remediation pass --
  see `AGENT_GUIDE.md` and each agent's own README for status.

## Development workflow

1. `make install`
2. `make validate-contracts` before touching any contract-related code
3. `make test` before opening a PR
4. See `AGENT_GUIDE.md` before building a new agent -- it documents the
   working reference pattern (`zone_intelligence_agent`, `hello_agent`)
   and the agent registry (`contracts/agent-registry/agents.yaml`) that's
   authoritative for what your agent consumes/produces.

## Current implementation status (honest summary)

This section exists so the repository doesn't claim more than it
currently does. See the linked forensic-audit reports for the full
evidence trail behind each line.

**Working, verified by running the code (not just reading it):**
- Contract validation (`make validate-contracts`).
- `environmental-intelligence-agent`, `risk-orchestrator-agent` (unit
  tests), and `worker-safety-agent` unit/integration/contract test
  suites, all green, all runnable with zero manual setup.
- The in-memory event transport (`InMemoryTransport`) -- a real, complete
  local transport, not a mock.
- `worker-safety-agent` publishing a real `WorkerAnalysisV1` end-to-end
  through the real producer/schema-provider/transport/consumer stack.

**Implemented but not exercised end-to-end in this pass:**
- Kafka-mode transport (code-complete, requires a live broker to verify).
- Redis/Postgres state repositories (code-complete; live-tested in prior
  work per in-repo agent documentation, not independently re-verified
  here).
- Neo4j and Qdrant repositories (code-complete; Neo4j has never been
  live-tested against a running instance anywhere in this repository's
  history; Qdrant's vector embeddings are a documented deterministic-hash
  placeholder, not real semantic embeddings).
- The Risk Orchestrator's local/global risk scoring math (deterministic,
  manually verified per `agents/risk-orchestrator-agent/docs/
  RECONCILIATION_REPORT.md`'s cited scenario runs) and its one-hop
  cross-zone correlation.

**Explicitly not implemented (documented, not silently missing):**
- `action-policy-gateway`, `audit-service`, `configuration-service`,
  `ingestion-gateway`, `notification-service` -- no code, only a
  Dockerfile placeholder each.
- Multi-hop / site-wide cascade risk detection (only one-hop neighbor
  correlation exists) -- see `RECONCILIATION_REPORT.md`.
- `compliance-intelligence-agent` -- an unresolved architecture decision,
  documented in its own `OWNERSHIP.md`, not a bug.

## Security / deployment caveats

This is a local-development / reference-implementation configuration, not
a production security posture:
- The API gateway's CORS policy defaults to permissive (all origins) in
  development, and refuses to start with a wildcard policy if
  `SENTINEL_ENVIRONMENT=production` is set without an explicit
  `SENTINEL_ALLOWED_ORIGINS` -- see "Running the API gateway" above. This
  is an origin-restriction boundary, **not authentication** -- no route
  requires a caller to prove who they are, in either mode. Add real
  authentication before deploying anywhere reachable beyond localhost.
- Local-dev default values (e.g. a default Postgres password) are read
  from environment variables with a local-dev default when unset
  (`SENTINEL_DB_PASSWORD`, `SENTINEL_DEMO_POSTGRES_DSN` -- see
  `.env.example`) -- never used as the credential for any shared or
  reachable database.
- There is no deployment automation in this repository, and none is
  assumed. Running the demo locally (`InMemoryTransport`, no Docker
  required) is the supported and verified path.

## Contributing

See `CONTRIBUTING.md` for setup, the exact commands CI runs (so you can
run them yourself before opening a PR), and scope expectations.
`CODE_OF_CONDUCT.md` covers interaction standards.

## License

**No LICENSE file exists in this repository yet.** This is a real,
outstanding decision, not an oversight this document is papering over --
choosing a license (MIT, Apache-2.0, "all rights reserved," etc.) is the
repository owner's call, not something to default silently. Until one is
added, default copyright applies and no reuse rights are granted.

## Owner decisions

A few things need the repository owner's action, not a code change:
- **LICENSE** (above).
- **Dependabot**: `.github/dependabot.yml` configures pip/npm/GitHub-
  Actions update PRs, but Dependabot itself must be enabled in the
  GitHub repository settings (Settings -> Code security and analysis) --
  this file alone does not turn it on.
- **Secret scanning / CodeQL**: also GitHub repository settings, not
  something a file in this repository can enable on your behalf.

## Known non-blocking limitations

- The dashboard's `lib/api.ts` and two components use `any` in 19 places
  (flagged by `npm run lint`) -- functional, but not fully typed. Left
  as-is rather than guessing at the intended response shapes for each.
- `sync_files.py` (a ~176KB base64-encoded file-delivery script) and two
  demo `.mp4` files (~2.1MB combined) remain tracked at their existing
  sizes/locations -- neither breaks anything, and removing or relocating
  either is a repository-hygiene call for the owner, not something this
  pass changed unilaterally.
