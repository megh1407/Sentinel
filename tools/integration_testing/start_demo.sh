#!/usr/bin/env bash
# start_demo.sh -- thin wrapper around run_demo.py.
# All real logic lives in run_demo.py; this just fixes the working
# directory and forwards arguments, e.g.:
#   ./start_demo.sh --duration 120
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
exec python3 run_demo.py "$@"
