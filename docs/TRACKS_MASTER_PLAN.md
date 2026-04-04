# All tracks — master plan

This file ties **Reliability (Track 1)**, **Scalability (Track 2)**, **Incident Response (Track 3)**, and **Documentation (Track 4 / bonus)** together with the **submission API** (`docs/SUBMISSION_TESTS.md`, `docs/openapi.yaml`). Use it as the single checklist for “we are doing every track.”

---

## How the tracks depend on each other

| Foundation | Builds on | Why |
|------------|-----------|-----|
| **Core API + DB** | Everything | Nothing to test, load, or observe without working endpoints. |
| **Track 1 — Reliability** | Core API | Tests + CI + `/health` are prerequisites for confident changes. |
| **Track 2 — Scalability** | Core API + (ideally) Track 1 | Load tests and Docker/Nginx/Redis need something stable to stress. |
| **Track 3 — Incident Response** | Deployed or runnable stack | Logs/metrics/alerts need a process to instrument and break safely. |
| **Track 4 — Documentation** | All of the above | Runbooks and capacity plans only make sense once architecture is real. |

**Practical order:** implement **submission/OpenAPI contract** → **Track 1 Bronze** (pytest + CI + `/health`) → parallelize **Track 1 Silver/Gold** with **Track 2 Bronze** (baseline k6) → **Track 2 Silver** (Compose + Nginx) → **Track 2 Gold** (Redis + heavy load) → **Track 3** (JSON logs, `/metrics`, Prometheus/Grafana, alerts) → **Track 4** (README, diagrams, deploy/troubleshooting, decision log, runbooks).

---

## Cross-cutting requirements (do once, satisfy many tracks)

- **`GET /health`** — Track 1 (pulse), Track 2 (LB health), Track 3 (uptime checks).
- **CI (GitHub Actions)** — Track 1; keeps all tracks from shipping broken code.
- **Docker Compose** — Track 2 Silver; reuse same compose for Track 1 chaos (restart policies) and Track 3 (logs from containers).
- **Redis** — Track 2 Gold; document the choice in Track 4 Gold decision log.
- **Runbooks** — Track 3 Gold and Track 4 Gold overlap; write **one** runbook repo, link from both.

---

## Track 1 — Reliability Engineering

| Tier | Must deliver | Evidence to keep |
|------|----------------|-------------------|
| Bronze | `pytest`, CI on every commit, `GET /health` | Green CI logs |
| Silver | `pytest-cov` **≥50%**, integration API tests, CI blocks deploy on failure, doc 404/500 behavior | Coverage report, screenshot of failed deploy blocking |
| Gold | **≥70%** coverage, bad input → JSON errors (no crash), chaos: kill container → auto-restart, failure-modes doc | Demo clips or notes, link to failure doc |

**Note:** Track 1 Silver mentions `POST /shorten` as an example; your contract uses **`POST /urls`** — integration tests should follow `docs/SUBMISSION_TESTS.md`.

**Hidden reliability bonus:** edge cases, validation, uniqueness, inactive resources — align with tests + product behavior.

---

## Track 2 — Scalability Engineering

| Tier | Must deliver | Evidence to keep |
|------|----------------|-------------------|
| Bronze | k6 or Locust, **50** concurrent users, document latency + error rate | Screenshot, baseline **p95** |
| Silver | **200** concurrent users, **2+** app containers, **Nginx** LB, responses **&lt;3s** | `docker ps`, load test output |
| Gold | **500+** users or **100 req/s**, **Redis** caching, bottleneck write-up (**2–3 sentences**), **&lt;5%** errors | Cache proof, load output, short report |

---

## Track 3 — Incident Response

| Tier | Must deliver | Evidence to keep |
|------|----------------|-------------------|
| Bronze | **JSON** structured logs (level, timestamp), **`/metrics`** (CPU/RAM or Prometheus-friendly), view logs without SSH | Screenshots |
| Silver | Alerts: service down + high error rate, notify **Slack/Discord/Email**, fire **within 5 minutes** | Demo recording, alert config snippet |
| Gold | **Grafana** (or similar) with **4+** metrics (latency, traffic, errors, saturation), **runbook**, RCA exercise using dashboard + logs | Dashboard screenshot, runbook link, short RCA narrative |

**Tooling suggested in doc:** Prometheus, Grafana, Alertmanager, Discord webhooks.

---

## Track 4 — Documentation (bonus, parallel-friendly)

| Tier | Must deliver |
|------|----------------|
| Bronze | README setup, architecture diagram (App → DB, add LB/Redis when you have them), API list (OpenAPI or equivalent) |
| Silver | Deploy + rollback guide, troubleshooting section, **env var** table |
| Gold | Per-alert runbooks (ties to Track 3 Gold), **decision log** (e.g. why Redis/Nginx), **capacity plan** (users/limit — use Track 2 numbers) |

---

## Submission API (non-negotiable for judging)

Work from `docs/SUBMISSION_TESTS.md` and `docs/openapi.yaml`:

- Health, users (CRUD + bulk CSV), URLs (CRUD + `short_code`), events list.

Load tests and integration tests should hit these routes once implemented.

---

## One-page team checklist

- [ ] API matches submission tests + OpenAPI
- [ ] Track 1: CI + pytest + coverage targets + integration tests + failure docs + chaos demo
- [ ] Track 2: k6 baselines → Compose + Nginx → Redis + tsunami test + bottleneck note
- [ ] Track 3: JSON logs + `/metrics` → alerts → Grafana + runbook + RCA story
- [ ] Track 4: README + diagram + deploy/troubleshooting + env vars + decision log + capacity plan

---

## Source docs (full detail)

- [TRACK1_RELIABILITY_ENGINEERING.md](./TRACK1_RELIABILITY_ENGINEERING.md)
- [TRACK2_SCALABILITY_ENGINEERING.md](./TRACK2_SCALABILITY_ENGINEERING.md)
- [TRACK3_INCIDENT_RESPONSE.md](./TRACK3_INCIDENT_RESPONSE.md)
- [TRACK4_DOCUMENTATION.md](./TRACK4_DOCUMENTATION.md)
- [SUBMISSION_TESTS.md](./SUBMISSION_TESTS.md)
