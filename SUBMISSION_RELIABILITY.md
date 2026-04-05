# Reliability Track — Submission Evidence

> Copy each field into the hackathon submission form.
> Screenshots are in `docs/Reliability/screenshots/` — upload the listed file for each tier.

---

## Live URLs (for judges to test)

| Endpoint | URL |
|---|---|
| Dashboard | http://64.225.10.147/ |
| Health (liveness) | http://64.225.10.147/health |
| Health (readiness) | http://64.225.10.147/health/ready |
| Swagger API Docs | http://64.225.10.147/docs/ |
| GitHub Pages Docs | https://retr0-os.github.io/MLH_PE_URL_Shortener/ |

---

## BRONZE

### 1. A working GET /health endpoint is available

**URL:**
```
http://64.225.10.147/health
```

**Screenshot:** `pr12-unit-tests-174-passed-91pct-load-test-start.png`

**Description:**
```
GET /health returns 200 {"status":"ok"} as a liveness probe. GET /health/ready runs a live SELECT 1 against PostgreSQL — returns 200 when the DB is reachable, 503 when it is not. Both are live at http://64.225.10.147/health and http://64.225.10.147/health/ready. Tested explicitly in tests/test_coverage_gaps.py::TestHealthReadyFailure.
```

---

### 2. The repository includes unit tests and pytest collection succeeds

**URL:**
```
https://github.com/RETR0-OS/MLH_PE_URL_Shortener/tree/dev/tests
```

**Screenshot:** `pr12-overview-coverage-report-91pct.png`

**Description:**
```
174 tests across 9 files: test_health.py, test_unit.py, test_unit_modules.py, test_coverage_gaps.py, test_urls.py, test_users.py, test_events.py, test_integration_routes.py, test_performance.py. All pass on every PR with 91% coverage. Screenshot shows the bot-posted test results on PR #12.
```

---

### 3. CI workflow is configured to execute tests automatically

**URL:**
```
https://github.com/RETR0-OS/MLH_PE_URL_Shortener/actions/workflows/unit-tests.yml
```

**Screenshot:** `ci-all-workflows.png`

**Description:**
```
unit-tests.yml GitHub Actions workflow runs on every PR to dev or main. Spins up real Postgres + Redis service containers, runs the full pytest suite with --cov-fail-under=70, and posts coverage report + test summary as a bot comment directly on the PR. Merge is blocked if any test fails.
```

---

## SILVER

### 4. Automated test coverage reaches at least 50%

**URL:**
```
https://retr0-os.github.io/MLH_PE_URL_Shortener/Reliability/RELIABILITY_ENGINEERING#coverage--50-actual-91
```

**Screenshot:** `pr12-overview-coverage-report-91pct.png`

**Description:**
```
91% coverage — CI enforces --cov-fail-under=70. If coverage drops below 70%, pytest exits non-zero and the PR cannot merge. Screenshot shows the github-actions bot posting 91% coverage report on PR #12. Dedicated coverage-gap tests cover error handler branches (503, 405, 500) that happy-path tests miss.
```

---

### 5. Integration/API tests exist and are detectable

**URL:**
```
https://retr0-os.github.io/MLH_PE_URL_Shortener/Reliability/RELIABILITY_ENGINEERING#integration-tests
```

**Screenshot:** `pr12-unit-tests-174-passed-91pct-load-test-start.png`

**Description:**
```
Integration tests hit real API endpoints against a live PostgreSQL database: test_urls.py (POST /urls → DB write → GET → PUT → DELETE, short code uniqueness), test_users.py (full CRUD + pagination + bulk CSV import), test_events.py (event creation + field shapes match OpenAPI spec), test_integration_routes.py (redirect flow 302/410/404, delete cascades, cursor pagination, v1 prefix routes, full event CRUD).
```

---

### 6. Error handling behavior for failures is documented

**URL:**
```
https://retr0-os.github.io/MLH_PE_URL_Shortener/Reliability/RELIABILITY_ENGINEERING#error-handling-documentation
```

**Screenshot:** *(evidence is in the docs page — can skip or screenshot the table)*

**Description:**
```
Full error handling table: 400 (missing/bad JSON body, validation failure), 401 (unauthorized API key), 404 (resource/short code not found), 405 (method not allowed), 409 (duplicate username/email), 410 (deactivated URL redirect), 500 (unhandled exception), 503 (DB unreachable). Every error returns a structured JSON object — Python stack traces never reach the client.
```

---

## GOLD

### 7. Automated test coverage reaches at least 70%

**URL:**
```
https://retr0-os.github.io/MLH_PE_URL_Shortener/Reliability/RELIABILITY_ENGINEERING#coverage--70-actual-91
```

**Screenshot:** `pr12-overview-coverage-report-91pct.png`

**Description:**
```
91% coverage — 21 points above the Gold threshold. CI gate enforces --cov-fail-under=70 on every PR. 9 test files collectively cover 91% of application code lines. Dedicated coverage-gap tests (test_coverage_gaps.py) explicitly test the 503, 405, and 500 error branches.
```

---

### 8. Invalid input paths return clean structured errors

**URL:**
```
https://retr0-os.github.io/MLH_PE_URL_Shortener/Reliability/RELIABILITY_ENGINEERING#graceful-failure--bad-input-returns-clean-json
```

**Screenshot:** *(code examples in the docs page — can skip)*

**Description:**
```
Missing required field → 400 {"user_id":"required","original_url":"required","title":"required"}. Non-integer ID → 400 {"url_id":"must be an integer"}. Deactivated URL → 410 {"error":"URL is deactivated"}. DB down → 503 {"status":"unavailable"}. All return clean JSON — never raw stack traces. All paths covered by integration tests. Testable live at http://64.225.10.147/
```

---

### 9. Evidence shows service restart behavior after forced failure

**URL:**
```
https://retr0-os.github.io/MLH_PE_URL_Shortener/Reliability/RELIABILITY_ENGINEERING#chaos-mode--container-kill-and-auto-restart
```

**Screenshot:** `commit-chaos-tests.png`

**Description:**
```
Chaos test script (scripts/chaos-test.sh) automates kill-and-verify: kills all app replicas → waits for ServiceDown alert to fire (~70-90s) → restarts service → polls /health/ready until 200. Second scenario kills Redis → verifies circuit breaker (zero 5xx) → waits for RedisDown alert → restores. Docker restart policy (unless-stopped) + 2 replicas + start-first rolling deploys = automatic recovery with zero downtime. Script exits non-zero if any step times out.
```

---

### 10. Failure modes and recovery expectations are documented

**URL:**
```
https://retr0-os.github.io/MLH_PE_URL_Shortener/Reliability/RELIABILITY_ENGINEERING#failure-modes-documentation
```

**Screenshot:** `commit-chaos-incident-response.png`

**Description:**
```
Full failure modes table documenting 9 scenarios: app container crash (Docker restart in 5s, second replica absorbs traffic), OOM kill (restart + HighMemoryUsage alert), PostgreSQL down (503 + pool reconnect), Redis down (circuit breaker, zero 5xx, cache refills on recovery), bad client input (400/409/410, no state change), duplicate insert (IntegrityError → 409, no corruption), N+1 regression (caught by test_performance.py in CI), replica death under load (Nginx routes around it), broken PR code (merge blocked), deploy health check failure (old containers keep running, team notified via GitHub Actions).
```
