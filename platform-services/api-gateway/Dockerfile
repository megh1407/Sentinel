# SENTINEL API Gateway
#
# Phase 3 remediation note (SENTINEL forensic audit): this file was
# previously empty (0 bytes). Added here as packaging for existing,
# already-implemented code (main.py + supporting modules) -- no new
# application functionality is introduced by this file.
#
# IMPORTANT -- build context must be the REPOSITORY ROOT, not this
# directory: `agents_runtime.py` resolves `_REPO_ROOT` as two directories
# above itself and dynamically imports agent source directly from
# `agents/<agent-dir>/...` at runtime (see that file's `_isolated_import`
# helper). This is an existing, unmodified architectural fact about how
# the gateway starts its in-process agents -- not something introduced by
# this Dockerfile -- so the image has to carry the relevant parts of the
# monorepo, not just this one directory.
#
# Build (from the repository root):
#   docker build -f platform-services/api-gateway/Dockerfile -t sentinel-api-gateway .
#
# Run (requires a reachable Redis; SENTINEL_TRANSPORT defaults to the
# real in-memory transport -- see README.md's "Current implementation
# status" for what is and isn't live-verified):
#   docker run -p 8000:8000 -e REDIS_HOST=<host> sentinel-api-gateway

FROM python:3.12-slim

WORKDIR /app

# Root requirements first (sentinel_eventbus, sentinel_agent_sdk,
# sentinel_state, sentinel_contracts, and everything the in-process
# agents need), then the gateway's own (fastapi/uvicorn) -- same order
# platform-services/api-gateway/requirements.txt's own header documents.
COPY requirements.txt ./requirements.txt
COPY platform-services/api-gateway/requirements.txt ./gateway-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r gateway-requirements.txt

# The monorepo subtrees agents_runtime.py's _isolated_import reaches into
# at runtime, plus the contracts/libs everything depends on.
COPY sentinel_contracts/ ./sentinel_contracts/
COPY libs/ ./libs/
COPY agents/ ./agents/
COPY platform-services/api-gateway/ ./platform-services/api-gateway/

# Phase 5 remediation note (SENTINEL forensic audit, Docker safety):
# don't run the app as root inside the container. /app is owned by the
# new user so uvicorn (which writes no files at runtime here) can run
# under it without needing broader permissions.
RUN useradd --create-home --shell /usr/sbin/nologin sentinel \
    && chown -R sentinel:sentinel /app
USER sentinel

WORKDIR /app/platform-services/api-gateway

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
