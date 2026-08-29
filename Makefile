# SENTINEL — root Makefile
#
# Exposes the workflow documented in README.md's "Verification Checklist"
# and .github/workflows/contract-validate.yml / contract-test.yml.

.PHONY: install validate-contracts test

install:
	pip install -r requirements.txt

validate-contracts:
	./scripts/validate-contracts.sh

# Phase 2 remediation note (SENTINEL forensic audit, P0-4): this used to
# read `python -m pytest tests/ -v`, but no root `tests/` directory
# exists -- every real test suite lives under an individual agent's own
# `tests/` (or Sentinel_Data_Engine/tests, which has its own separate
# requirements.txt and is not part of this target). Each of the three
# agents below now has a `[tool.pytest.ini_options]` pythonpath entry in
# its own pyproject.toml, so no manually-exported PYTHONPATH is needed --
# just `cd` into the agent directory and run pytest from there. Looping
# with a subshell per agent (rather than one pytest invocation across all
# of them) is deliberate: several agents' tests do bare `from config
# import ...`-style imports that would collide if every agent's src/ were
# on sys.path at once.
test:
	@set -e; \
	for agent in environmental-intelligence-agent risk-orchestrator-agent worker-safety-agent; do \
		echo "=== agents/$$agent ==="; \
		(cd agents/$$agent && python -m pytest -v) || exit 1; \
	done
