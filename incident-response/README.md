# Incident Response — Track 3 Deliverables

Complete incident response infrastructure for the URL Shortener service. This folder contains all Track 3 deliverables organized by tier.

---

## Architecture

```
  App (/metrics)          Prometheus            Alertmanager           Email
  ┌──────────┐     scrape  ┌──────────┐  alert   ┌──────────┐  notify  ┌─────────┐
  │  Flask +  │ ──────────>│  Metrics  │ ────────>│ Severity │ ────────>│  Inbox  │
  │ Gunicorn  │   15s      │  + Rules  │  eval    │ Routing  │  SMTP   │ (on-call)│
  └──────────┘             └──────────┘          └──────────┘         └─────────┘
       │                                               │
       │ JSON logs                                     │ critical: instant
       v                                               │ warning:  10s group
  ┌──────────┐             ┌──────────┐               │
  │  Docker   │ ──────────>│   Loki   │               │
  │  stdout   │   ingest   │  (3100)  │               │
  └──────────┘             └──────────┘               │
                                │                      │
                                v                      v
                           ┌──────────────────────────────┐
                           │     Grafana Dashboard         │
                           │  "URL Shortener - Golden      │
                           │         Signals"              │
                           │  8 panels + alert annotations │
                           │     http://localhost:3000     │
                           └──────────────────────────────┘
```

---

## Deliverables by Tier

### Bronze — The Watchtower

| Requirement | Implementation | Location |
|-------------|---------------|----------|
| Structured JSON logging | `pythonjsonlogger` with timestamp, level, message | [`app/logging_config.py`](../app/logging_config.py) |
| `/metrics` endpoint | Prometheus Flask Exporter (request count, latency histogram, memory) | [`app/__init__.py`](../app/__init__.py) |
| View logs without SSH | Docker JSON log driver + Loki + Grafana Logs panel | `docker compose logs app` |

**Verify:**
```bash
docker compose logs app --tail 5        # JSON structured logs
curl -s http://localhost:5000/metrics    # Prometheus metrics
```

---

### Silver — The Alarm

| Requirement | Implementation | Location |
|-------------|---------------|----------|
| Service Down alert | `up == 0` for 1m → fires in ~70s | [`monitoring/prometheus/alerts.yml`](../monitoring/prometheus/alerts.yml) |
| High Error Rate alert | 5xx rate > 10% for 2m → fires in ~130s | Same file |
| Email notification | Alertmanager SMTP with severity routing | [`monitoring/alertmanager/alertmanager.yml`](../monitoring/alertmanager/alertmanager.yml) |
| Fire within 5 minutes | `group_wait: 10s` (warnings), `0s` (critical) | Same file |
| Chaos testing script | Automated failure injection + alert verification | [`incident-response/chaos/chaos-test.sh`](chaos/chaos-test.sh) |

**Verify (live demo):**
```bash
# Dry run first
./incident-response/chaos/chaos-test.sh --service-down --dry-run

# Live demo — stops app, waits for alert, restores, verifies recovery
./incident-response/chaos/chaos-test.sh --service-down

# Run all scenarios
./incident-response/chaos/chaos-test.sh --all
```

**Alert routing:**
- **Critical** (ServiceDown): `group_wait: 0s` — instant email with subject `CRITICAL: ...`
- **Warning** (HighErrorRate, HighLatency, RedisDown): `group_wait: 10s` — batched email with subject `WARNING: ...`

---

### Gold — The Command Center

| Requirement | Implementation | Location |
|-------------|---------------|----------|
| Grafana dashboard (4+ metrics) | 8 panels: Uptime, Alerts, Request Rate, Error Rate, Latency, Memory, CPU, Logs | [`monitoring/grafana/dashboards/url-shortener.json`](../monitoring/grafana/dashboards/url-shortener.json) |
| Runbook | Per-alert mitigation + master incident playbook | [`docs/RUNBOOK.md`](../docs/RUNBOOK.md), [`INCIDENT-PLAYBOOK.md`](runbooks/INCIDENT-PLAYBOOK.md) |
| RCA exercise | Redis failure diagnosis using dashboard + logs | [`RCA-001-redis-failure.md`](rca/RCA-001-redis-failure.md) |
| Postmortem template | Google SRE format with 5 Whys | [`POSTMORTEM-TEMPLATE.md`](rca/POSTMORTEM-TEMPLATE.md) |

**Dashboard panels (Golden Signals):**

| Panel | Signal | PromQL |
|-------|--------|--------|
| Service Uptime | Availability | `up{job="app"}` |
| Active Alerts | Alerts | `count(ALERTS{alertstate="firing"})` |
| Request Rate | Traffic | `sum(rate(flask_http_request_total[1m])) by (method)` |
| Error Rate (5xx %) | Errors | `rate(5xx) / rate(total) * 100` |
| Latency p50/p95/p99 | Latency | `histogram_quantile(0.X, ...)` |
| Memory Usage | Saturation | `process_resident_memory_bytes` |
| CPU Usage | Saturation | `rate(process_cpu_seconds_total[1m]) * 100` |
| Application Logs | Investigation | Loki: `{job="app"}` |

---

## Monitoring Stack Access

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| Alertmanager | http://localhost:9093 | — |
| Jaeger | http://localhost:16686 | — |
| App Health | http://localhost/health | — |
| App Readiness | http://localhost/health/ready | — |
| Metrics | http://localhost/metrics | — |

---

## Folder Structure

```
incident-response/
├── README.md                        # This file
├── chaos/
│   └── chaos-test.sh               # Automated failure injection + alert verification
├── rca/
│   ├── RCA-001-redis-failure.md    # Root Cause Analysis narrative (Gold requirement)
│   └── POSTMORTEM-TEMPLATE.md      # Reusable incident postmortem template
├── runbooks/
│   └── INCIDENT-PLAYBOOK.md        # Master incident response playbook
└── screenshots/
    └── .gitkeep                     # Submission screenshots go here
```

---

## Related Documentation

- [Per-Alert Runbook](../docs/RUNBOOK.md) — Step-by-step mitigation for each alert
- [Failure Modes](../docs/FAILURE_MODES.md) — Expected behavior under failure
- [SLOs](../docs/SLO.md) — Service level objectives and error budgets
- [Troubleshooting](../docs/TROUBLESHOOTING.md) — Common issues and fixes
- [Capacity Plan](../docs/CAPACITY_PLAN.md) — Hardware limits and scaling formulas
- [Bottleneck Report](../docs/BOTTLENECK_REPORT.md) — Chaos test results and performance data
