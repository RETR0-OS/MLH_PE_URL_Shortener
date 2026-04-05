## What does this PR do?

<!-- Brief description of the change — what and why, not how. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor / tech debt
- [ ] Documentation
- [ ] CI/CD / infra
- [ ] Other: <!-- describe -->

---

## Pre-merge checklist

### Code quality
- [ ] No new linter warnings (`ruff check` passes)
- [ ] No hardcoded secrets, API keys, or credentials
- [ ] Code follows existing patterns and conventions

### Testing
- [ ] New/changed code is covered by tests
- [ ] All existing tests still pass locally (`uv run pytest`)
- [ ] Coverage has not dropped below 70%

### CI gates (must be green before merge)
- [ ] Unit Tests workflow passed (174+ tests, ≥70% coverage)
- [ ] Load Tests workflow passed (500 VU k6, 37 infra checks)
- [ ] CI/CD lint check passed (ruff)

### For production-impacting changes
- [ ] Tested against a running `docker compose up` stack locally
- [ ] Health endpoints still return 200 (`/health`, `/health/ready`)
- [ ] No breaking API changes (or documented in PR body)
- [ ] Database migrations are backward-compatible (if applicable)

### Documentation
- [ ] Updated relevant docs if behavior changed
- [ ] API changes reflected in `openapi.json`

---

## Screenshots / logs (if applicable)

<!-- Paste screenshots, test output, or curl responses that demonstrate the change works. -->
