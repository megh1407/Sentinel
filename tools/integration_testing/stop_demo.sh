#!/usr/bin/env bash
# stop_demo.sh -- stops the Kafka/Redis/Postgres containers started for the
# demo. Does NOT touch .state/trace_events.db or integration_report.md by
# default, so you can still inspect the last run's results after stopping
# infra. Pass --wipe-state to also clear the trace store.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

REPO_ROOT="$(cd ../.. && pwd)"
DEV_ENV_COMPOSE="$REPO_ROOT/scripts/dev-env/docker-compose.yml"

if command -v docker >/dev/null 2>&1; then
    docker compose -f "$DEV_ENV_COMPOSE" -f docker-compose.yml down
else
    echo "docker not found on PATH -- nothing to stop."
fi

if [[ "${1:-}" == "--wipe-state" ]]; then
    echo "Wiping trace store and report..."
    rm -f .state/trace_events.db .state/trace_events.db-wal .state/trace_events.db-shm integration_report.md
fi
