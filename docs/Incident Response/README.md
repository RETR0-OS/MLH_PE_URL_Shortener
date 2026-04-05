---
layout: default
title: Incident Response — Track 3
permalink: /incident-response/
---

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
| Structured JSON logging | `pythonjsonlogger` with timestamp, level, message | [`app/logging_config.py`](../../app/logging_config.py) |
| `/metrics` endpoint | Prometheus Flask Exporter (request count, latency histogram, memory) | [`app/__init__.py`](../../app/__init__.py) |
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
| Service Down alert | `up == 0` for 1m → fires in ~70s | [`monitoring/prometheus/alerts.yml`](../../monitoring/prometheus/alerts.yml) |
| High Error Rate alert | 5xx rate > 5% for 30s → fires in ~45s | Same file |
| Email notification | Alertmanager SMTP with severity routing | [`monitoring/alertmanager/alertmanager.yml`](../../monitoring/alertmanager/alertmanager.yml) |
| Fire within 5 minutes | `group_wait: 10s` (warnings), `0s` (critical) | Same file |
| Chaos testing script | Automated failure injection + alert verification | [`chaos-test.sh`](../../scripts/chaos-test.sh) |

**Verify (live demo):**
```bash
# Dry run first
./scripts/chaos-test.sh --service-down --dry-run

# Live demo — stops app, waits for alert, restores, verifies recovery
./scripts/chaos-test.sh --service-down

# Run all scenarios
./scripts/chaos-test.sh --all
```

**Alert routing:**
- **Critical** (ServiceDown): `group_wait: 0s` — instant email with subject `CRITICAL: ...`
- **Warning** (HighErrorRate, HighLatency, RedisDown): `group_wait: 10s` — batched email with subject `WARNING: ...`

---

### Gold — The Command Center

| Requirement | Implementation | Location |
|-------------|---------------|----------|
| Grafana dashboard (4+ metrics) | 8 panels: Uptime, Alerts, Request Rate, Error Rate, Latency, Memory, CPU, Logs | [`monitoring/grafana/dashboards/url-shortener.json`](../../monitoring/grafana/dashboards/url-shortener.json) |
| Runbook | Per-alert mitigation + master incident playbook | [`INCIDENT-PLAYBOOK.md`]({{ site.baseurl }}/incident-response/playbook) |
| RCA exercise | Redis failure diagnosis using dashboard + logs | [`RCA-001-redis-failure.md`]({{ site.baseurl }}/incident-response/rca/redis-failure) |
| Postmortem template | Google SRE format with 5 Whys | [`POSTMORTEM-TEMPLATE.md`]({{ site.baseurl }}/incident-response/postmortem-template) |

**Dashboard panels (Golden Signals):**

| Panel | Signal | PromQL |
|-------|--------|--------|
| Service Uptime | Availability | `up{job="app"}` |
| Active Alerts | Alerts | `count(ALERTS{alertstate="firing"})` |
| Request Rate | Traffic | `sum(rate(flask_http_request_total[5m])) by (method)` |
| Error Rate (5xx %) | Errors | `sum(rate(flask_http_request_total{status=~"5.."}[5m])) / sum(rate(flask_http_request_total[5m])) * 100` |
| Latency p50/p95/p99 | Latency | `histogram_quantile(0.X, sum(rate(flask_http_request_duration_seconds_bucket[5m])) by (le))` |
| Memory Usage | Saturation | `process_resident_memory_bytes` |
| CPU Usage | Saturation | `rate(process_cpu_seconds_total{job="app"}[5m]) * 100` |
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
docs/Incident Response/
├── README.md                        # This file
├── rca/
│   ├── RCA-001-redis-failure.md    # Root Cause Analysis narrative (Gold requirement)
│   └── POSTMORTEM-TEMPLATE.md      # Reusable incident postmortem template
├── runbooks/
│   └── INCIDENT-PLAYBOOK.md        # Master incident response playbook
└── screenshots/
    ├── metrics-endpoint.png            # /metrics endpoint output
    ├── prometheus-alert-rules.png      # Prometheus alert rules page
    ├── alertmanager-ui.png             # Alertmanager UI
    ├── alertmanager-config.png         # Alertmanager configuration/status
    ├── grafana-golden-signals-dashboard.png  # Grafana Golden Signals dashboard
    ├── grafana-loki-logs.png           # Grafana Loki log exploration
    └── jaeger-tracing.png              # Jaeger distributed tracing UI

scripts/
└── chaos-test.sh                    # Automated failure injection + alert verification
```

---

## Related Documentation

- [Incident Playbook]({{ site.baseurl }}/incident-response/playbook) — Per-alert runbooks, SLO targets, remediation commands, escalation paths
- [RCA: Redis Failure]({{ site.baseurl }}/incident-response/rca/redis-failure) — Root cause analysis using dashboard and logs
- [Postmortem Template]({{ site.baseurl }}/incident-response/postmortem-template) — Google SRE-style postmortem format
- [Track 3 Design Decisions]({{ site.baseurl }}/incident-response/design-decisions) — All design decisions with rationale and evidence
- [Track 3 Requirements]({{ site.baseurl }}/TRACK3_INCIDENT_RESPONSE) — Original quest specification
