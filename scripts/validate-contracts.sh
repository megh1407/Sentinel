#!/usr/bin/env bash
# validate-contracts.sh
#
# Exposes, as a local script, exactly the two checks
# .github/workflows/contract-validate.yml already runs in CI:
#   1. Avro syntax check (schema_loader.py)
#   2. Envelope-conformance check (envelope_conformance_lint.py)
#
# No new checks are introduced here. When contract-validate.yml gains more
# steps (naming lint, cross-reference check, lineage check -- see that
# workflow's comments for status), add the same steps here in the same order.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Avro syntax check (schema_loader.py)"
python schema_loader.py

echo "==> Envelope-conformance check (envelope_conformance_lint.py)"
python envelope_conformance_lint.py

echo "==> Contract validation passed."
