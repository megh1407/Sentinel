# SENTINEL — root Makefile
#
# Exposes the workflow that already exists in this repository (README.md
# "Verification Checklist" + .github/workflows/contract-validate.yml).
# Introduces no new build system or tooling choices of its own.

.PHONY: install validate-contracts test

install:
	pip install -r requirements.txt

validate-contracts:
	./scripts/validate-contracts.sh

test:
	python -m pytest tests/ -v
