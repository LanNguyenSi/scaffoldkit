## Summary

<!-- One or two sentences. What changed? -->

## Motivation

<!-- Why this change? Link the issue if applicable. -->

## Test plan

- [ ] `pytest tests/ --cov=src/scaffoldkit --cov-fail-under=83` (the coverage floor CI enforces in `.github/workflows/ci.yml`)
- [ ] `shellcheck scripts/*.sh`
- [ ] `ruff check src/ tests/`
- [ ] `ruff format --check src/ tests/` (CI also enforces this)
- [ ] For blueprint changes: generated a sample project and verified output
- [ ] Manual smoke check: <!-- command or scenario -->

## Notes for reviewer

<!-- Anything non-obvious. -->
