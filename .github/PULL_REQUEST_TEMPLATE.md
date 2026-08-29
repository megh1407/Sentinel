## What this changes and why


## Evidence

- [ ] `make validate-contracts` passes (if contracts touched)
- [ ] `make test` passes
- [ ] `npm run build` passes (if `dashboard/` touched)
- [ ] If a test's expected behavior changed, the PR description explains
      why the old expectation was wrong — not just that the new one is
      green (see `CONTRIBUTING.md`)

## Scope check

- [ ] This PR doesn't bundle unrelated formatting/refactoring
- [ ] This PR doesn't modify `agents/hello_agent/` (unless the PR is
      specifically about that reference implementation)
- [ ] This PR doesn't implement one of the documented-as-intentionally-
      empty platform services merely for completeness (see `README.md`)
