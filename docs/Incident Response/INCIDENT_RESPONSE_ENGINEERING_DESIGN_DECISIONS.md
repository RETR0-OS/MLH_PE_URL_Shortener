# Track 3: Incident Response — Design Decisions & Evidence Map

**Project:** MLH Production Engineering URL Shortener
**Date:** April 5, 2026

This document records every design decision made for Track 3 (Incident Response), grounded in the actual codebase. Each decision includes the rationale, the alternatives considered, and the files that implement it.

---

## Table of Contents

1. [Evidence Summary by Submission Field](#evidence-summary-by-submission-field)
2. [Bronze Tier Decisions](#bronze-tier-decisions)
3. [Silver Tier Decisions](#silver-tier-decisions)
4. [Gold Tier Decisions](#gold-tier-decisions)
5. [Architecture Overview](#architecture-overview)
6. [Known Gaps](#known-gaps)

---

## Evidence Summary by Submission Field

### Bronze

| Submission Requirement | Verifiable Evidence | Key Files |
|---|---|---|
| JSON structured logging includes timestamp and log level fields | `pythonjsonlogger.json.JsonFormatter` configured with `rename_fields={"asctime": "timestamp", "levelname": "level"}` and ISO-8601 `datefmt`. Gunicorn mirrors the same formatter in `logconfig_dict`. Nginx uses a `json_combined` log format. Every request emits structured JSON with `request_id`, `method`, `path`, `status`, `latency_ms`. | `app/logging_config.py` (lines 10-13), `gunicorn.conf.py` (lines 21-26), `nginx/nginx.conf` (lines 12-24), `app/middleware.py` (lines 41-51) |
| A `/metrics`-style endpoint is available and returns monitoring data | `prometheus-flask-exporter` auto-registers a `/metrics` endpoint on the Flask app. Prometheus scrapes it every 15s via DNS service discovery. Exposed metrics include `flask_http_request_total`, `flask_http_request_duration_seconds_bucket`, `process_resident_memory_bytes`, `process_cpu_seconds_total`. | `app/__init__.py` (lines 5, 12, 43), `monitoring/prometheus/prometheus.yml` (lines 13-20), `pyproject.toml` (line 16) |
| Logs can be inspected through tooling without direct server SSH | Three methods available: (1) `docker compose logs app` reads Docker's `json-file` log driver output, (2) Promtail ships container logs to Loki via Docker socket discovery, (3) Grafana's "Application Logs" panel queries Loki with `{job="app"}`. All three avoid SSH. | `docker-compose.yml` (lines 26-30: json-file driver; lines 242-256: promtail; lines 258-279: grafana), `monitoring/promtail/promtail-config.yml`, `monitoring/grafana/dashboards/url-shortener.json` (lines 162-177) |

### Silver

| Submission Requirement | Verifiable Evidence | Key Files |
|---|---|---|
| Alerting rules are configured for service down and high error rate | Seven Prometheus alert rules in two groups. `ServiceDown`: `up == 0` for 1m (severity: critical). `HighErrorRate`: 5xx rate / total rate > 0.05 for 30s (severity: warning). Additional rules: `HighLatency`, `RedisDown`, `HighReplicaCount`, `HighRequestRate`, `HighMemoryUsage`. | `monitoring/prometheus/alerts.yml` (lines 1-71), `monitoring/prometheus/prometheus.yml` (lines 4-5: `rule_files`) |
| Alerts are routed to an operator channel such as Slack or email | Alertmanager routes to email via Resend SMTP (`smtp.resend.com:587`). Two receivers: `email-critical` (instant, `group_wait: 0s`) and `email-warnings` (`group_wait: 10s`). Both use rich HTML templates. Discord webhook receivers are defined in `discord-receivers.yml` and dynamically merged by `entrypoint.sh` when `DISCORD_WEBHOOK_URL` is set. | `monitoring/alertmanager/alertmanager.yml` (lines 1-92), `monitoring/alertmanager/discord-receivers.yml` (lines 1-34), `monitoring/alertmanager/entrypoint.sh` (lines 13-28), `docker-compose.yml` (lines 212-215) |
| Alerting latency is documented and meets five-minute response objective | `ServiceDown` (critical): 1m `for` duration + 0s `group_wait` = ~60-70s. `HighErrorRate` (warning): 30s `for` duration + 10s `group_wait` = ~40-50s. `HighLatency`: 30s + 10s = ~40-50s. `RedisDown`: 1m + 10s = ~70s. All are well within the 5-minute target. Prometheus evaluation interval is 15s (`monitoring/prometheus/prometheus.yml` line 3). | `monitoring/prometheus/alerts.yml` (per-rule `for` values), `monitoring/alertmanager/alertmanager.yml` (lines 11, 19: `group_wait`), `monitoring/prometheus/prometheus.yml` (line 3: `evaluation_interval: 15s`) |

### Gold

| Submission Requirement | Verifiable Evidence | Key Files |
|---|---|---|
| Dashboard evidence covers latency, traffic, errors, and saturation | Grafana dashboard "URL Shortener - Golden Signals" (UID: `url-shortener-golden`) has 8 panels: Service Uptime (availability), Active Alerts, Request Rate (traffic by HTTP method), Error Rate 5xx % (errors), Latency p50/p95/p99 (latency), Memory Usage RSS (saturation), CPU Usage % (saturation), Application Logs (Loki). Auto-refresh every 10s, alert annotations overlay. | `monitoring/grafana/dashboards/url-shortener.json` (189 lines), `monitoring/grafana/provisioning/datasources/datasources.yml`, `monitoring/grafana/provisioning/dashboards/dashboards.yml` |
| Runbook includes actionable alert-response procedures | `INCIDENT-PLAYBOOK.md` is a 640-line, 20-section operational playbook covering severity definitions, per-alert remediation commands (ServiceDown, HighErrorRate, HighLatency, RedisDown), SLO targets, escalation paths, communication templates, on-call handoff procedures, and troubleshooting decision trees. | `docs/Incident Response/runbooks/INCIDENT-PLAYBOOK.md`, `docs/Incident Response/README.md` |
| Root-cause analysis of a simulated incident is documented | `RCA-001-redis-failure.md` documents a Redis OOMKill incident using the Grafana dashboard. Walks through 5 specific dashboard panels, includes Loki log queries (`{job="app"} |= "Redis unavailable"`), traces the circuit breaker activation in `app/utils/cache.py`, and records timeline, impact, and resolution. A reusable `POSTMORTEM-TEMPLATE.md` (Google SRE 5-Whys format) is also provided. | `docs/Incident Response/rca/RCA-001-redis-failure.md` (356 lines), `docs/Incident Response/rca/POSTMORTEM-TEMPLATE.md` (271 lines) |

---

## Bronze Tier Decisions

### Decision B1: `python-json-logger` over stdlib or structlog

**Choice:** `pythonjsonlogger.json.JsonFormatter` (from `python-json-logger>=3.0`)

**Rationale:**
- Wraps Python's stdlib `logging` module — zero changes to existing `logger.info()` / `logger.warning()` calls across the codebase.
- The `rename_fields` parameter directly maps `asctime` to `timestamp` and `levelname` to `level`, which matches the Track 3 requirement verbatim without post-processing.
- Minimal dependency footprint (single package) compared to `structlog` which would require restructuring all logging callsites.

**Alternatives considered:**
- `structlog`: More powerful (contextual binding, processors) but would require rewriting every logging callsite. Overkill for the submission scope.
- stdlib `logging.Formatter` with a custom `format()`: Would work, but hand-rolled JSON serialization is error-prone (escaping, nested fields).

**Implementation:**
- `app/logging_config.py` — Central `setup_logging()` function called at app startup (`app/__init__.py`, line 37).
- `gunicorn.conf.py` (lines 17-51) — Mirrors the same formatter via `logconfig_dict` so Gunicorn's own access/error logs are also JSON.
- Fields emitted per log line: `timestamp` (ISO-8601), `level`, `name`, `message`, plus any `extra={}` dict from the call site.

### Decision B2: Per-request structured fields via middleware

**Choice:** Custom Flask middleware in `app/middleware.py` that injects `request_id`, `method`, `path`, `status`, `latency_ms`, and timing checkpoints into every request log.

**Rationale:**
- A single `after_request` hook ensures 100% of requests are logged with the same schema, avoiding inconsistent ad-hoc logging.
- `X-Request-ID` propagation (from header or auto-generated UUID) enables tracing a request across Nginx access logs, application logs, and Grafana Loki.
- Timing checkpoints (`g.timings`) allow diagnosing which phase of a request (middleware, DB, cache, serialization) is slow.

**Implementation:** `app/middleware.py` (lines 23-52)

### Decision B3: Nginx JSON access logs

**Choice:** Custom `log_format json_combined` in `nginx/nginx.conf` producing JSON-structured access logs.

**Rationale:**
- Nginx sits in front of Gunicorn. Its access logs capture upstream response time, upstream address (which replica served the request), and client-facing metrics that the application itself cannot see (e.g., network latency between Nginx and Gunicorn).
- JSON format ensures Promtail/Loki can parse Nginx logs with the same tooling as application logs.

**Implementation:** `nginx/nginx.conf` (lines 12-24)

### Decision B4: `prometheus-flask-exporter` for `/metrics`

**Choice:** `PrometheusMetrics.for_app_factory()` from `prometheus-flask-exporter>=0.23`

**Rationale:**
- Auto-instruments every Flask route with `flask_http_request_total` (counter by method, status, path) and `flask_http_request_duration_seconds` (histogram) with zero per-route annotation.
- Exposes standard process metrics (`process_resident_memory_bytes`, `process_cpu_seconds_total`) that map directly to golden signals (Saturation).
- `for_app_factory()` supports Flask's application factory pattern (used in `create_app()`).
- Health and utility endpoints are excluded via `@metrics.do_not_track()` to avoid polluting dashboards with noise.

**Implementation:** `app/__init__.py` (lines 5, 12, 43, 84, 90, 95)

### Decision B5: Loki + Promtail for SSH-free log inspection

**Choice:** Grafana Loki for log aggregation, Promtail for log shipping, Grafana for the viewing UI.

**Rationale:**
- Loki is purpose-built for Grafana and integrates natively as a datasource — no additional adapters needed.
- Promtail uses Docker service discovery (`docker_sd_configs`) to automatically discover and ship logs from all containers matching `.*app.*`, meaning new replicas are automatically picked up when the autoscaler creates them.
- Compared to the ELK stack (Elasticsearch + Logstash + Kibana), Loki+Promtail has dramatically lower memory and storage requirements (index-free design, only labels are indexed).
- 72-hour retention (`monitoring/loki/loki-config.yml`, line 28) is sufficient for incident investigation without excessive storage.

**Alternatives considered:**
- ELK (Elasticsearch + Logstash + Kibana): Much heavier on resources (Elasticsearch alone requires 1-2GB RAM minimum). Inappropriate for a hackathon project running on a single machine.
- `docker compose logs app`: Works, but is ephemeral (no search, no time range filtering, no correlation with metrics).

**Implementation:**
- `monitoring/loki/loki-config.yml` — TSDB storage, v13 schema, filesystem backend.
- `monitoring/promtail/promtail-config.yml` — Docker SD, filters to `app` containers, pushes to Loki.
- `monitoring/grafana/dashboards/url-shortener.json` (lines 162-177) — "Application Logs" panel querying `{job="app"}`.
- `monitoring/grafana/provisioning/datasources/datasources.yml` (lines 11-15) — Loki datasource.

---

## Silver Tier Decisions

### Decision S1: Prometheus + Alertmanager over Grafana Alerting

**Choice:** Alert rules evaluated by Prometheus, routed by Alertmanager.

**Rationale:**
- Prometheus evaluates rules at `evaluation_interval: 15s` using the same PromQL that powers the dashboard panels. This guarantees alert thresholds are consistent with what operators see on the dashboard.
- Alertmanager provides native severity-based routing, `group_wait`/`group_interval`/`repeat_interval` controls, and multi-receiver fan-out (email + Discord simultaneously via `continue: true`).
- Grafana Alerting (the built-in alternative) would couple alert definitions to the visualization layer. If Grafana goes down, alerting would stop. With Prometheus + Alertmanager, alerts fire independently of the dashboard.

**Implementation:**
- `monitoring/prometheus/prometheus.yml` (lines 5-11) — `rule_files` + `alertmanagers` config.
- `monitoring/prometheus/alerts.yml` — 7 rules across 2 groups.
- `monitoring/alertmanager/alertmanager.yml` — Routing tree with severity-based receiver selection.

### Decision S2: Email (via Resend SMTP) as primary notification channel

**Choice:** Alertmanager sends email via `smtp.resend.com:587` using a Resend API key.

**Rationale:**
- Email is a native Alertmanager receiver type — no external webhook adapter, sidecar container, or custom code required.
- Resend provides a developer-friendly transactional email API with SMTP compatibility. The account is already provisioned (API key in `.env`).
- Email creates a permanent, searchable audit trail — important for postmortems.
- HTML-formatted alert emails include severity, instance, summary, description, timestamps, and direct links to Alertmanager/Grafana/Prometheus.

**Alternatives considered:**
- Discord only: Discord webhooks are also configured (`discord-receivers.yml`) but are opt-in via `DISCORD_WEBHOOK_URL` env var. Discord messages are ephemeral and harder to audit than email.
- Slack: Not implemented. Would require a Slack workspace and app configuration overhead.
- PagerDuty/OpsGenie: Enterprise on-call tools. Out of scope for a hackathon.

**Implementation:**
- `monitoring/alertmanager/alertmanager.yml` (lines 3-6) — SMTP global config.
- Two receivers: `email-critical` (lines 22-56), `email-warnings` (lines 58-91).
- Critical alerts: `group_wait: 0s`, `repeat_interval: 15m`. Warnings: `group_wait: 10s`, `repeat_interval: 1h`.

### Decision S3: Discord as opt-in secondary channel

**Choice:** Discord receivers defined in a separate file, dynamically merged at container startup only if `DISCORD_WEBHOOK_URL` is set.

**Rationale:**
- Not every deployment has a Discord server. Making Discord opt-in via an environment variable means the alerting stack works out of the box with just email.
- The `entrypoint.sh` script (lines 13-28) uses `sed` and `cat` to merge `discord-receivers.yml` into the Alertmanager config at runtime. This avoids maintaining two separate Alertmanager config files.
- When enabled, Discord routes use `continue: true` so both email AND Discord fire for the same alert.

**Implementation:**
- `monitoring/alertmanager/discord-receivers.yml` — Two receivers: `discord-critical` (red formatting), `discord-warnings` (orange formatting).
- `monitoring/alertmanager/entrypoint.sh` — Conditional merge logic.
- `docker-compose.yml` (line 215) — `DISCORD_WEBHOOK_URL: "${DISCORD_WEBHOOK_URL:-}"`.

### Decision S4: Alert timing tuned for sub-5-minute delivery

**Choice:** Reduced `group_wait` to 0s (critical) and 10s (warnings) to ensure all alerts are delivered well within the 5-minute Track requirement.

**Rationale:**
- The total alert delivery time is: `for` duration (time the condition must hold) + `evaluation_interval` (polling delay, worst case 15s) + `group_wait` (batching delay) + SMTP delivery latency.
- For `ServiceDown` (critical): 1m `for` + 15s eval + 0s group_wait = ~75s worst case.
- For `HighErrorRate` (warning): 30s `for` + 15s eval + 10s group_wait = ~55s worst case.
- All seven alerts fire well under 5 minutes.

**Implementation:**
- `monitoring/prometheus/alerts.yml` — Individual `for` values per rule.
- `monitoring/alertmanager/alertmanager.yml` — `group_wait: 0s` (line 19) for critical, `group_wait: 10s` (line 11) default.

### Decision S5: Chaos testing script for live demonstration

**Choice:** A bash script (`chaos-test.sh`, 611 lines) that automates failure injection, alert verification, and recovery.

**Rationale:**
- Judges need a live demo showing "app breaks → alert fires → notification received". Manually stopping containers and checking Alertmanager is error-prone and slow.
- The script supports `--service-down`, `--redis-down`, `--all`, and `--dry-run` modes.
- It polls the Alertmanager API (`/api/v2/alerts`) to programmatically verify that the expected alert fires.
- It auto-detects Docker Compose v1 vs v2 syntax and validates the project is running before injecting failures.

**Implementation:** `scripts/chaos-test.sh`

---

## Gold Tier Decisions

### Decision G1: Single "Golden Signals" dashboard with 8 panels

**Choice:** One pre-provisioned Grafana dashboard covering all four golden signals in a single view.

**Rationale:**
- The Track requirement is "4+ metrics covering Latency, Traffic, Errors, Saturation." A single dashboard with 8 panels exceeds this. Splitting into multiple dashboards would make the judge's evaluation harder and fragment the operational view.
- The dashboard uses two datasources (Prometheus for metrics, Loki for logs) so an operator can correlate metrics with log events without switching views.
- Auto-refresh at 10s ensures the dashboard shows near-real-time data during a demo.
- Alert annotations (firing alerts shown as red vertical lines) allow operators to see exactly when alerts fired overlaid on the metric graphs.

**Panel mapping to golden signals:**

| Golden Signal | Panel(s) | PromQL / Query |
|---|---|---|
| Latency | Latency p50/p95/p99 | `histogram_quantile(0.X, sum(rate(flask_http_request_duration_seconds_bucket[5m])) by (le))` |
| Traffic | Request Rate (req/s) | `sum(rate(flask_http_request_total[1m])) by (method)` |
| Errors | Error Rate (5xx %) | `sum(rate(flask_http_request_total{status=~"5.."}[2m])) / sum(rate(flask_http_request_total[2m])) * 100` |
| Saturation | Memory Usage (RSS), CPU Usage (%) | `process_resident_memory_bytes`, `rate(process_cpu_seconds_total{job="app"}[1m]) * 100` |
| Availability | Service Uptime | `up{job="app"}` |
| Operational | Active Alerts | `count(ALERTS{alertstate="firing"}) OR vector(0)` |
| Investigation | Application Logs | Loki: `{job="app"}` |

**Implementation:** `monitoring/grafana/dashboards/url-shortener.json`

### Decision G2: Grafana auto-provisioning via file-based providers

**Choice:** Dashboard JSON and datasource YAML are mounted into Grafana at startup via provisioning directories.

**Rationale:**
- Grafana's provisioning feature (`/etc/grafana/provisioning/`) ensures the dashboard, Prometheus datasource, and Loki datasource are available immediately after `docker compose up` — no manual import or configuration required.
- The `updateIntervalSeconds: 30` setting means changes to the dashboard JSON on disk are picked up automatically.
- `disableDeletion: false` allows judges to modify or experiment with the dashboard without it being recreated.

**Implementation:**
- `monitoring/grafana/provisioning/datasources/datasources.yml` — Prometheus (default) + Loki.
- `monitoring/grafana/provisioning/dashboards/dashboards.yml` — File-based provider pointing to `/var/lib/grafana/dashboards`.
- `docker-compose.yml` (lines 265-267) — Volume mounts for provisioning and dashboard directories.

### Decision G3: Incident Playbook structured as a 20-section operational reference

**Choice:** A single comprehensive playbook (`INCIDENT-PLAYBOOK.md`) rather than multiple scattered runbook files.

**Rationale:**
- At 3 AM during an incident, operators need one place to go — not a directory of loosely linked documents.
- The playbook includes: quick-access URLs, severity definitions, alert-specific runbooks (ServiceDown, HighErrorRate, HighLatency, RedisDown), SLO targets, remediation commands (copy-pasteable), escalation paths, communication templates, and on-call handoff procedures.
- Each alert section follows a consistent structure: Description → Likely Causes → Diagnosis Steps → Remediation → Escalation.

**Implementation:** `docs/Incident Response/runbooks/INCIDENT-PLAYBOOK.md` (640 lines, 20 sections)

### Decision G4: RCA documented against actual Grafana panels

**Choice:** The RCA (`RCA-001-redis-failure.md`) references specific Grafana dashboard panels and actual PromQL queries, rather than abstract descriptions.

**Rationale:**
- The Track requires "Diagnose a fake issue using only your dashboard and logs." The RCA demonstrates this by walking through each panel of the Golden Signals dashboard during a Redis failure.
- Referencing specific panels ("Latency panel shows p95 spiked from ~30ms to ~195ms") proves the dashboard is actionable, not just decorative.
- Loki log queries (`{job="app"} |= "Redis unavailable"`) show how log aggregation supports root cause identification.
- The incident ties back to actual application code: the circuit breaker in `app/utils/cache.py` (lines 17-51) that prevented cascading failures.

**Implementation:** `docs/Incident Response/rca/RCA-001-redis-failure.md` (356 lines)

### Decision G5: Google SRE postmortem template

**Choice:** A reusable `POSTMORTEM-TEMPLATE.md` following Google's SRE postmortem format.

**Rationale:**
- Provides a blameless, structured format for future incidents: Summary, Impact, Timeline, Root Cause (5 Whys), Action Items (with owners and due dates), Communication Log.
- Demonstrates operational maturity beyond the immediate track requirements.

**Implementation:** `docs/Incident Response/rca/POSTMORTEM-TEMPLATE.md` (271 lines)

---

## Architecture Overview

```
                                    ┌──────────────────────┐
                                    │       Grafana         │
                                    │    :3000              │
                                    │  Dashboard + Logs UI  │
                                    └─────┬──────┬─────────┘
                                          │      │
                              ┌───────────┘      └────────────┐
                              v                                v
                   ┌──────────────────┐            ┌──────────────────┐
                   │   Prometheus     │            │      Loki        │
                   │   :9090          │            │    :3100          │
                   │  Metrics + Rules │            │  Log Aggregation  │
                   └──────┬───────────┘            └──────┬───────────┘
                          │                                │
              ┌───────────┤                                │
              │           │                                │
   ┌──────────v───┐  ┌────v──────────┐           ┌────────v──────────┐
   │ Alertmanager │  │   App :5000   │           │     Promtail      │
   │   :9093      │  │  /metrics     │           │  Docker SD        │
   │  Email +     │  │  JSON logs    │           │  → Loki ingest    │
   │  Discord     │  │  OTEL traces  │           └───────────────────┘
   └──────────────┘  └──────┬────────┘
                            │
                   ┌────────v─────────┐
                   │     Jaeger       │
                   │   :16686         │
                   │  Distributed     │
                   │  Tracing         │
                   └──────────────────┘
```

**Data flows:**
1. App → Prometheus: `/metrics` scraped every 15s via DNS service discovery.
2. Prometheus → Alertmanager: Alert rules evaluated every 15s; firing alerts forwarded to Alertmanager.
3. Alertmanager → Email/Discord: Severity-based routing; critical = instant, warning = 10s batched.
4. App (stdout) → Docker json-file driver → Promtail → Loki: Container logs ingested with 5s refresh.
5. Grafana → Prometheus + Loki: Dashboards query both datasources. Logs panel uses Loki, all other panels use Prometheus.
6. App → Jaeger: OpenTelemetry traces exported via OTLP/gRPC.

---

## Known Gaps

These are factual observations about what is not implemented. They are documented here for transparency.

| Gap | Description | Impact |
|---|---|---|
| Autoscaler logging format | `autoscaler/scaler.py` uses `logging.basicConfig` with plain-text format, not JSON. All other components use JSON logging. | Autoscaler logs are not parseable by the same JSON pipeline. Minor — autoscaler is a sidecar, not the main app. |
| Discord not active by default | `DISCORD_WEBHOOK_URL` is not set in `.env`. Discord receivers exist in code but are dormant. | Email is the active channel. Discord works if the env var is populated. |
| `docs/ARCHITECTURE.md` is empty | The file exists but has 0 bytes. | No impact on Track 3, but a dangling reference. |
| No infrastructure-specific dashboards | Only one Grafana dashboard exists (`url-shortener-golden`). No separate dashboards for PostgreSQL, Redis, or Nginx. | Application golden signals are covered. Infrastructure monitoring relies on alert rules (RedisDown, etc.) rather than dedicated dashboards. |
| Alertmanager HTML links use localhost | Email templates link to `http://localhost:9093`, `http://localhost:3000`, `http://localhost:9090`. These only work when the operator is on the same machine. | Acceptable for hackathon/demo. Would need DNS/IP updates for remote deployment. |

---

## File Index

All files contributing to Track 3, organized by function:

### Logging
| File | Role |
|---|---|
| `app/logging_config.py` | JSON formatter setup (pythonjsonlogger) |
| `app/middleware.py` | Per-request structured log emission |
| `gunicorn.conf.py` | Gunicorn JSON log config |
| `nginx/nginx.conf` | Nginx JSON access log format |

### Metrics
| File | Role |
|---|---|
| `app/__init__.py` | Prometheus Flask Exporter integration, `/metrics` endpoint |
| `monitoring/prometheus/prometheus.yml` | Scrape config (DNS SD, 15s interval) |

### Alerting
| File | Role |
|---|---|
| `monitoring/prometheus/alerts.yml` | 7 alert rules (2 groups) |
| `monitoring/alertmanager/alertmanager.yml` | Email routing (Resend SMTP) |
| `monitoring/alertmanager/discord-receivers.yml` | Discord webhook receivers |
| `monitoring/alertmanager/entrypoint.sh` | Dynamic config merge at startup |

### Log Aggregation
| File | Role |
|---|---|
| `monitoring/loki/loki-config.yml` | Loki storage and retention (72h, TSDB) |
| `monitoring/promtail/promtail-config.yml` | Docker SD log shipping to Loki |

### Dashboards
| File | Role |
|---|---|
| `monitoring/grafana/dashboards/url-shortener.json` | Golden Signals dashboard (8 panels) |
| `monitoring/grafana/provisioning/datasources/datasources.yml` | Prometheus + Loki datasources |
| `monitoring/grafana/provisioning/dashboards/dashboards.yml` | File-based dashboard provider |

### Incident Response Documentation
| File | Role |
|---|---|
| `docs/Incident Response/README.md` | Index of all Track 3 deliverables |
| `docs/Incident Response/runbooks/INCIDENT-PLAYBOOK.md` | Master operational playbook (640 lines) |
| `docs/Incident Response/rca/RCA-001-redis-failure.md` | Root cause analysis narrative |
| `docs/Incident Response/rca/POSTMORTEM-TEMPLATE.md` | Reusable postmortem template |
| `scripts/chaos-test.sh` | Automated chaos testing script |

### Tracing (supplementary to Track 3)
| File | Role |
|---|---|
| `app/tracing.py` | OpenTelemetry SDK initialization, OTLP export to Jaeger |

### Infrastructure
| File | Role |
|---|---|
| `docker-compose.yml` | All monitoring services (Prometheus, Alertmanager, Loki, Promtail, Grafana, Jaeger) |
