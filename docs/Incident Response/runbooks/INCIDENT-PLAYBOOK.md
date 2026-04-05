---
layout: default
title: Incident Response Playbook
permalink: /incident-response/playbook
---

# URL Shortener — Incident Response Playbook

**In Case of Emergency, open this document.**

This is the master operational reference for on-call engineers responding to production incidents on the URL Shortener service. It ties together monitoring, alert rules, runbooks, and failure modes into a single process document.

**Important**: All commands in this playbook should be run from the project root directory.

---

## 1. Quick Access

**Monitoring URLs** (all running locally):

| Service | URL | Purpose |
|---------|-----|---------|
| **Grafana Dashboards** | http://localhost:3000 | Primary monitoring dashboard (user: admin, password: admin) |
| **Prometheus Alerts** | http://localhost:9090/alerts | View active alerts, alert rules, and history |
| **Alertmanager** | http://localhost:9093 | Alert routing, silencing, and grouping |
| **Jaeger Traces** | http://localhost:16686 | Distributed tracing for request diagnostics |
| **App Health Check** | http://localhost/health | Liveness check (200 = running) |
| **App Readiness** | http://localhost/health/ready | Readiness check (200 = DB connected) |
| **Prometheus Metrics** | http://localhost/metrics | Raw metrics endpoint (for queries) |
| **Loki Logs** | http://localhost:3100 | Log aggregation (queried via Grafana) |

**Remember**: Grafana is your primary dashboard. Open it first.

---

## 2. Incident Severity Definitions

| Severity | Definition | Examples | Response Time | SLO Impact |
|----------|-----------|----------|----------------|-----------|
| **P1 - Critical** | Service completely down or user-facing data loss risk | All replicas down, Postgres unreachable, disk full | Immediate (page on-call) | Violates 99.9% availability target |
| **P2 - Major** | Service degraded but functioning; increased errors/latency | High error rate (>5%), p95 latency >500ms, single replica crash | < 15 minutes | May violate SLO if sustained |
| **P3 - Minor** | Warning condition; service operating below targets | Redis down (circuit breaker active), CPU warning, elevated memory | < 1 hour | Doesn't violate SLO |

**Severity assignment decision tree:**
- Is the app returning 5xx for all requests? → P1
- Is `/health/ready` failing? → P1 (or P2 if single replica)
- Is error rate >5%? → P2
- Is latency consistently >500ms p95? → P2
- Is a non-critical service (Redis, Jaeger) down? → P3
- Is there a capacity warning (CPU/memory high)? → P3

---

## 3. Incident Response Flow

Follow this sequence for every incident:

### 1. **Detect** (0 min)
Alert fires. Notification sent via email (Alertmanager configured in `alertmanager.yml`).

### 2. **Acknowledge** (1 min)
Open **Grafana** → **URL Shortener - Golden Signals** dashboard.
- View: Request rate (traffic), error rate (5xx %), latency (p95), and saturation (CPU/memory/connections).
- Confirm the alert is real and not a false positive.

### 3. **Assess** (2-3 min)
Determine severity based on **golden signals**:
- **Error rate**: % of 5xx responses
- **Latency**: p95 response time
- **Traffic**: requests per second
- **Saturation**: CPU, memory, DB connections

Assign severity using the table in section 2.

### 4. **Diagnose** (5-10 min)
Consult the **Alert Quick Reference** (section 4) for the specific alert. Jump to the per-alert runbook in section 8 of this playbook.

**Example paths:**
- `ServiceDown` firing? → [Runbook: ServiceDown](#servicedown)
- `HighErrorRate` firing? → [Runbook: HighErrorRate](#higherrorrate)
- `HighLatency` firing? → [Runbook: HighLatency](#highlatency)
- `RedisDown` firing? → [Runbook: RedisDown](#redisdown)

### 5. **Mitigate** (10-20 min)
Apply the fix from the runbook. Verify by:
- Checking health endpoints: `curl http://localhost/health/ready`
- Monitoring Grafana for metrics returning to baseline
- Watching Prometheus for the alert to clear (may take 1-3 min)

### 6. **Communicate** (during mitigation)
Update the team via GitHub issue or email:
- **At detection**: "URL Shortener P2 alert: HighErrorRate. Investigating."
- **During mitigation**: "Root cause found: Redis OOM kill. Restarting Redis."
- **At resolution**: "Resolved. Error rate back to <1%. Redis recovered. No data loss."

### 7. **Postmortem** (after resolution)
Create a postmortem document in `docs/Incident Response/rca/` using the template below.

**When to write postmortem:**
- All P1 incidents (mandatory)
- P2 incidents lasting >1 hour (mandatory)
- P3 incidents (optional, but recommended)

**Postmortem template:**
```markdown
# Incident Report: [Title]

**Date**: YYYY-MM-DD HH:MM UTC
**Severity**: P1 / P2 / P3
**Duration**: X minutes
**Timeline**:
  - HH:MM: Alert fired
  - HH:MM: Root cause identified
  - HH:MM: Mitigation applied
  - HH:MM: Service recovered

**Root cause**: [1-2 sentence explanation]

**Impact**:
  - Downtime: X minutes
  - Users affected: ~Y
  - Data loss: Yes/No

**Remediation**:
  1. Immediate (within 24 hours): [fix applied]
  2. Follow-up (within 1 week): [prevent recurrence]

**Action items**:
  - [ ] PR for config change / code fix
  - [ ] Update docs / runbook
  - [ ] Discuss in team standup
```

---

## 4. Alert Quick Reference

| Alert | Severity | Condition | Fires After | Expected Time to Fire | Runbook |
|-------|----------|-----------|-------------|----------------------|---------|
| **ServiceDown** | Critical | `up == 0` | 1 minute | ~70 seconds | [Runbook](#servicedown) |
| **HighErrorRate** | Warning | 5xx rate > 5% | 30 seconds | ~45 seconds | [Runbook](#higherrorrate) |
| **HighLatency** | Warning | p95 > 500ms | 30 seconds | ~45 seconds | [Runbook](#highlatency) |
| **RedisDown** | Warning | Redis connection errors > 0 | 1 minute | ~70 seconds | [Runbook](#redisdown) |

**Key insight**: Alerts have a "wait period" (the `for: Xm` duration in `monitoring/prometheus/alerts.yml`). This prevents noise from brief blips. If you see a spike in Grafana but the alert didn't fire, it may have already recovered.

---

## 5. SLO Targets (at a glance)

These are your targets. Sustained violations trigger postmortems.

| Signal | Target | Measurement Window | Where to Check |
|--------|--------|-------------------|-----------------|
| **Availability** | 99.9% uptime | Rolling 7 days | Grafana: "Availability" panel (via `/health/ready` checks) |
| **Read Latency (p95)** | < 500 ms | 5-minute rolling window | Grafana: "Request Duration" panel |
| **Write Latency (p95)** | < 1 s | 5-minute rolling window | Grafana: "Request Duration" panel (POST/PUT) |
| **Error Rate (5xx)** | < 1% | 5-minute rolling window | Grafana: "Error Rate" panel |

**Error budget for 99.9% availability**: ~10 minutes of downtime per week.

---

## 6. Common Remediation Commands

Quick reference for the most common fixes. Run these from the machine hosting the Docker services.

### Service Status & Logs
```bash
# Check all service status
docker compose ps

# View app logs (last 50 lines, follow in real-time)
docker compose logs app --tail 50 -f

# View Postgres logs
docker compose logs postgres --tail 50

# View Redis logs
docker compose logs redis --tail 50

# View Nginx logs
docker compose logs nginx --tail 50
```

### Scaling & Restarting
```bash
# Scale app replicas up (for high latency/error rate under load)
docker compose up -d --scale app=3

# Scale app replicas down (to reduce memory pressure)
docker compose up -d --scale app=1

# Restart a specific service (use after fixing config)
docker compose restart app        # Restart app
docker compose restart postgres   # Restart Postgres
docker compose restart redis      # Restart Redis

# Rebuild and restart (if code was updated)
docker compose up -d --build app

# Force hard restart (kills container immediately, no graceful shutdown)
docker compose kill app && docker compose up -d app
```

### Health Checks
```bash
# Check app readiness (must return HTTP 200)
curl -s http://localhost/health/ready | jq .

# Check Postgres connectivity
docker compose exec postgres pg_isready -U postgres

# Check Redis connectivity
docker compose exec redis redis-cli ping

# Check Postgres connection pool
docker compose exec postgres psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Check Redis memory usage
docker compose exec redis redis-cli info memory
```

### Diagnostics
```bash
# Check system memory pressure
docker stats

# Check Prometheus for active alerts
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts'

# Check recent Docker restarts
docker compose logs --timestamps | grep "Restarting\|Started"

# View container resource usage over time
docker compose stats --no-stream
```

### Rollback (if the latest deployment is bad)
```bash
# View update history
docker compose inspect app | grep -A20 "UpdateStatus"

# Note: docker-compose doesn't have built-in rollback, so either:
# Option 1: Revert the code, rebuild, and redeploy
git revert HEAD && docker compose up -d --build app

# Option 2: Restart with the previous image (requires tagging)
docker compose up -d app  # Uses previous image if still available
```

---

## 7. Escalation Path

| Time Elapsed | Action | Who |
|--------------|--------|-----|
| 0-5 min | Alert received, acknowledge via GitHub issue or email | On-call engineer |
| 5-15 min | Diagnose using runbook | On-call engineer |
| 15-30 min | If not resolved, loop in team lead | On-call + team lead |
| 30+ min | Contact backup engineer, consider rollback or code change | Team |
| 1+ hour | Post incident update, coordinate postmortem | Team lead |

**On-Call Contacts**:
| Role | GitHub | Email |
|------|--------|-------|
| Primary On-Call | [@devgunnu](https://github.com/devgunnu) | gunbirsingh2006@gmail.com |
| Backup On-Call | [@RETR0-OS](https://github.com/RETR0-OS) | ajinda17@asu.edu |
| Team | [@aryankhanna2004](https://github.com/aryankhanna2004), [@SinghOPS](https://github.com/SinghOPS) | — |

**Notification channels**:
- GitHub: Open an issue at https://github.com/RETR0-OS/MLH_PE_URL_Shortener/issues
- Email: gunbirsingh2006@gmail.com / ajinda17@asu.edu (configured in `ALERT_EMAIL_TO`)

---

## 8. Runbook Summaries

These are brief summaries of each alert. Full details are below.

### ServiceDown

**Alert fires**: App instance unreachable for >1 minute.
**Severity**: P1 — Service completely down.
**Escalate if not resolved in**: 15 minutes → page team lead.

**Step 1 — Confirm the alert is real** (0–2 min):
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost/health
# If 200: alert is stale (already recovered). Monitor for 2 min, then silence if stable.
# If non-200 or connection refused: proceed to Step 2.
```

**Step 2 — Identify the failed component** (2–5 min):
```bash
# Check all service states
docker compose ps

# Check app crash logs
docker compose logs app --tail 50

# Check if Postgres is the blocker
docker compose ps postgres
docker compose exec postgres pg_isready -U postgres
```

**Step 3 — Mitigation by root cause** (5–10 min):

If Postgres is down:
```bash
docker compose restart postgres
# Wait 15s for health check, then:
docker compose restart app
curl -s http://localhost/health/ready | jq .
```

If app is OOM-killed:
```bash
docker stats --no-stream | grep app
# If memory > 384MB per replica, scale down:
docker compose up -d --scale app=1
docker compose logs app --tail 30
```

If port conflict or startup crash:
```bash
# Run attached to see startup error:
docker compose stop app
docker compose up app   # NOT -d, so you see the error
# Ctrl-C once you see the cause, fix it, then:
docker compose up -d app
```

**Step 4 — Verify recovery**:
```bash
curl -s http://localhost/health/ready | jq .
# Must return: {"status": "ok"}
docker compose ps | grep app
# Must show 2+ "Up" entries
```

**Expected recovery time**: 5–15 seconds after Postgres or dependencies recover.
**Escalate if not resolved in 15 minutes**: page team lead with current `docker compose ps` output and last 100 lines of `docker compose logs app`.

### HighErrorRate

**Alert fires**: 5xx error rate exceeds 5% for >30 seconds.
**Severity**: P2 — User-facing errors.
**Escalate if not resolved in**: 20 minutes → page team lead + consider rollback.

**Step 1 — Identify which endpoint is failing** (0–3 min):
```bash
# Check error logs with context
docker compose logs app --tail 100 | grep -E '"status": 5'

# Check active DB connections (should be < 80 out of 100 max)
docker compose exec postgres psql -U postgres -c \
  "SELECT count(*) FROM pg_stat_activity WHERE state != 'idle';"

# Check container health
docker compose ps
```

**Step 2 — Match to root cause**:

If DB connection errors in logs:
```bash
# Check connection pool saturation
docker compose exec postgres psql -U postgres -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
# If > 80 active: connection pool is exhausted
docker compose restart app   # Forces pool reconnection
```

If unhandled exception / code bug:
```bash
# Get full stack traces
docker compose logs app --tail 200 | grep -A 10 "Traceback\|ERROR"
# If from a recent deploy → rollback:
cd /root/MLH_PE_URL_Shortener
git log --oneline -5   # Note the previous commit SHA
git revert HEAD --no-edit
docker compose up -d --build
```

If traffic spike:
```bash
# Scale up replicas
docker compose up -d --scale app=3
# Wait 30s for new replicas to warm up, then re-check error rate in Grafana
```

**Step 3 — Verify recovery**:
```bash
# Poll error rate for 60 seconds
for i in $(seq 1 6); do
  curl -s "http://localhost:9090/api/v1/query?query=sum(rate(flask_http_request_total{status=~'5..'}[30s]))/sum(rate(flask_http_request_total[30s]))*100" \
    | jq '.data.result[0].value[1]' 2>/dev/null || echo "0"
  sleep 10
done
# All values should be below 1.0 (1%)
```

**Expected recovery time**: 2–5 minutes after restart or scale-up.
**Escalate if not resolved in 20 minutes**: share current error rate (from Prometheus query above) and last 200 log lines with team lead.

### HighLatency

**Alert fires**: p95 latency exceeds 500ms for >30 seconds.
**Severity**: P2 — Performance degradation, SLO at risk.
**Escalate if not resolved in**: 20 minutes → review capacity plan, consider droplet upgrade.

**Step 1 — Confirm and characterise** (0–3 min):
```bash
# Check current p95 latency
curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(flask_http_request_duration_seconds_bucket[5m]))by(le))*1000" \
  | jq '.data.result[0].value[1]'
# If < 500: alert is clearing. Monitor for 2 min.

# Check if it's traffic-driven
curl -s "http://localhost:9090/api/v1/query?query=sum(rate(flask_http_request_total[5m]))" \
  | jq '.data.result[0].value[1]'
# Compare to baseline: ~100 req/s is normal, > 400 req/s may require scaling

# Check container CPU and memory
docker stats --no-stream
```

**Step 2 — Match to root cause**:

If traffic spike (request rate > 400 req/s):
```bash
# Scale up replicas (max 3 on 2 GB droplet)
docker compose up -d --scale app=3
# Wait 30s for new replica to warm up
```

If Redis is down (cache misses causing DB load):
```bash
docker compose ps redis
docker compose exec redis redis-cli ping
# If Redis is down, it will auto-restart. Wait 30s for recovery.
# Latency will be elevated (~200ms p95) until Redis is back and cache refills.
```

If Postgres is slow (high DB latency):
```bash
# Find slow queries
docker compose exec postgres psql -U postgres -d hackathon_db \
  -c "SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 5;"
# If a specific query is slow, check EXPLAIN ANALYZE
```

**Step 3 — Verify recovery**:
```bash
# Watch p95 latency trend over 2 minutes
for i in $(seq 1 6); do
  echo -n "$(date +%H:%M:%S) p95: "
  curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(flask_http_request_duration_seconds_bucket[2m]))by(le))*1000" \
    | jq -r '.data.result[0].value[1]' 2>/dev/null || echo "no data"
  sleep 20
done
# Should trend downward toward < 100ms
```

**Expected recovery time**: 1–3 minutes after scaling or Redis recovery.
**Escalate if not resolved in 20 minutes**: the bottleneck is hardware (see `docs/CAPACITY_PLAN.md` Phase 2 — droplet upgrade required).

### RedisDown

**Alert fires**: Redis connection errors detected for >1 minute.
**Severity**: P3 — No user-facing errors (circuit breaker active), but latency is elevated.
**Escalate if not resolved in**: 30 minutes → investigate OOM kill or hardware issue.

**IMPORTANT**: The circuit breaker is active. Reads fall back to PostgreSQL automatically. Users see higher latency (~200ms p95) but zero errors. This is NOT an emergency.

**Step 1 — Assess Redis state** (0–2 min):
```bash
# Check Redis container status
docker compose ps redis

# Try to ping Redis
docker compose exec redis redis-cli ping
# Expected: PONG (if running), or connection refused (if down)

# Check Redis logs for crash reason
docker compose logs redis --tail 50

# Check if it was OOM-killed (look for exit code 137)
docker inspect $(docker compose ps -q redis) | jq '.[0].State.ExitCode'
# 137 = OOM kill, 1 = crash, 0 = clean exit
```

**Step 2 — Mitigation**:

If Redis is down and NOT auto-restarting:
```bash
# Force restart
docker compose restart redis
# Wait 15s then verify:
docker compose exec redis redis-cli ping
# Expected: PONG
```

If Redis keeps OOM-killing (memory leak):
```bash
# Check memory usage before it crashes again
docker compose exec redis redis-cli info memory | grep used_memory_human
# If > 120MB out of 128MB limit, it's about to OOM again

# Immediate: flush cache to buy time (safe — app will refill from DB)
docker compose exec redis redis-cli flushall
# This causes a temporary spike in DB load as cache is cold

# Permanent: increase Redis memory limit (requires docker-compose.yml edit)
# Change: command: --maxmemory 128mb   →   --maxmemory 256mb
# Then: docker compose up -d redis
```

**Step 3 — Verify recovery**:
```bash
docker compose exec redis redis-cli ping
# Must return: PONG

# Verify circuit breaker has closed (app reconnected to Redis)
docker compose logs app --tail 20 | grep -i redis
# Should see no "Redis unavailable" messages after recovery

# Check latency returned to baseline (< 50ms p95)
curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(flask_http_request_duration_seconds_bucket[5m]))by(le))*1000" \
  | jq '.data.result[0].value[1]'
```

**Expected recovery time**: 30 seconds (auto-restart). No manual intervention needed unless crash-looping.
**Escalate if not resolved in 30 minutes**: Redis is crash-looping. Share `docker compose logs redis --tail 100` output with team lead.

---

## 9. Golden Signals Dashboard Reference

Grafana "URL Shortener - Golden Signals" dashboard shows four key metrics:

| Metric | What It Means | Baseline | Warning | Critical |
|--------|---------------|----------|---------|----------|
| **Request Rate (RPS)** | Requests per second | 50-150 rps | >250 rps | >500 rps |
| **Error Rate (%)** | % of 5xx responses | <1% | >5% | >10% |
| **Latency (p95 ms)** | 95th percentile response time | <200 ms | >500 ms | >3000 ms |
| **Saturation (%)** | Highest of (CPU%, Mem%, DB connections%) | <50% | >70% | >85% |

**Usage**:
1. Open http://localhost:3000 (Grafana)
2. Click "URL Shortener - Golden Signals" dashboard
3. Scan the four panels
4. Compare current values to baselines above
5. Use trends (hovering over time series) to spot degradation

---

## 10. Detailed Failure Mode Reference

These describe expected behavior under failure:

### Database Down
- **Symptom**: `/health/ready` returns 503, all CRUD operations fail
- **Recovery**: Postgres auto-restarts and connection pool reconnects. App doesn't need restart.
- **Docker behavior**: Healthcheck fails, Docker restarts container per `restart: unless-stopped` policy

### Redis Down
- **Symptom**: Connection errors in logs, cache circuit breaker activates
- **Impact**: Cache bypassed, reads go direct to DB. No user-facing errors (latency increases)
- **Recovery**: Redis auto-restarts, cache refills organically

### Container Crash / OOM Kill
- **Symptom**: `docker compose ps` shows task in Failed/Shutdown state
- **Impact**: Docker Compose routing removes dead replica. In-flight requests timeout; Nginx retries on other replicas
- **Recovery**: Docker `restart: unless-stopped` auto-restarts the container. Recovery time: 5-15s

### Bulk Import Failure
- **Symptom**: `POST /users/bulk` returns 500
- **Impact**: Entire import rolls back. No partial data committed
- **Recovery**: Fix CSV, re-upload. Existing IDs skipped via `ON CONFLICT IGNORE`

### Network Partition (Postgres unreachable)
- **Symptom**: Connection pool timeout errors
- **Impact**: All read/write ops fail (same as Database Down)
- **Recovery**: When network heals, pool reconnects. Stale connections evicted after 300s

### Disk Full (Postgres volume)
- **Symptom**: Write operations fail
- **Impact**: Reads still work; new data creation fails
- **Recovery**: Free disk space or expand volume. Postgres resumes automatically

---

## 11. Memory & Capacity Limits

Your hardware has **2 GB RAM** total; ~1.8 GB available for services.

### Service Memory Budget

| Service | Limit | Current Config |
|---------|-------|-----------------|
| App (per replica) | 384 MB | 2-5 replicas |
| Postgres | 768 MB | Fixed 1 instance |
| Redis | 160 MB | Fixed 1 instance |
| Nginx | 64 MB | Fixed 1 instance |
| Prometheus | 512 MB | Fixed 1 instance |
| Loki | 256 MB | Fixed 1 instance |
| Grafana | 256 MB | Fixed 1 instance |
| Alertmanager | 128 MB | Fixed 1 instance |
| Jaeger | 256 MB | Fixed 1 instance |
| Promtail | 128 MB | Fixed 1 instance |
| Autoscaler | 64 MB | Fixed 1 instance |

**Formula**: `Total = (app_replicas * 384MB) + 2592MB (fixed services)`

Note: The combined Docker memory limits exceed the 2 GB droplet RAM. Docker limits are upper bounds; actual RSS usage is lower. The system runs on the 2 GB droplet because limits are rarely hit simultaneously, and Linux overcommits memory. Monitor with `docker stats` to see actual usage.

- **2 replicas**: ~3.36 GB limits (~1.8–2.2 GB actual RSS typical)
- **3 replicas**: ~3.74 GB limits (tight — watch actual RSS closely)
- **4 replicas**: ~4.13 GB limits (high risk of OOMKill)

**Action**: If actual RSS usage (from `docker stats`) exceeds 1.8 GB, scale app down to 1 replica or restart services.

---

## 12. Troubleshooting Decision Tree

**Start here if you're not sure which runbook to use.**

```
Alert received?
├─ ServiceDown (up == 0)
│  └─ Go to: Runbook "ServiceDown"
│
├─ HighErrorRate (5xx > 5%)
│  └─ Go to: Runbook "HighErrorRate"
│
├─ HighLatency (p95 > 500ms)
│  └─ Go to: Runbook "HighLatency"
│
├─ RedisDown (redis_connection_errors > 0)
│  └─ Go to: Runbook "RedisDown"
│
└─ No alert, but service is slow/broken?
   ├─ Can you curl http://localhost/health?
   │  ├─ Yes (200) → Check Runbook "HighLatency" or "HighErrorRate"
   │  └─ No → Check Runbook "ServiceDown"
   │
   └─ Are there error messages in logs?
      ├─ "database connection" → Restart Postgres: `docker compose restart postgres`
      ├─ "Redis unavailable" → Wait 30s for auto-restart (expected behavior)
      ├─ OutOfMemory → Scale down replicas: `docker compose up -d --scale app=1`
      └─ Application error → Check git log, consider rollback
```

---

## 13. Related Documentation

Keep these docs handy:

| Document | Purpose | Location |
|----------|---------|----------|
| **Incident Playbook** | This document — master operational guide | `docs/Incident Response/runbooks/INCIDENT-PLAYBOOK.md` |
| **RCA: Redis Failure** | Past incident analysis | `docs/Incident Response/rca/RCA-001-redis-failure.md` |
| **Postmortem Template** | Incident report structure | `docs/Incident Response/rca/POSTMORTEM-TEMPLATE.md` |
| **Alert Rules** | Prometheus alert definitions | `monitoring/prometheus/alerts.yml` |
| **Alertmanager Config** | Email routing and grouping | `monitoring/alertmanager/alertmanager.yml` |
| **Design Decisions** | Track 3 rationale and evidence | `docs/Incident Response/INCIDENT_RESPONSE_ENGINEERING_DESIGN_DECISIONS.md` |

---

## 14. Pre-Incident Checklist

**Before going on-call, verify:**

- [ ] You can access Grafana (http://localhost:3000, user: admin, password: admin)
- [ ] You can access Prometheus (http://localhost:9090)
- [ ] You can access Alertmanager (http://localhost:9093)
- [ ] You can SSH/access the server hosting Docker
- [ ] You have docker-compose commands aliased or in your PATH
- [ ] You've read the runbook summaries in section 8 and the failure modes in section 10
- [ ] You have a way to be notified (email or GitHub)
- [ ] You know how to reach the backup on-call engineer
- [ ] You have the postmortem template URL bookmarked

---

## 15. After-Incident Checklist

**When an incident is resolved:**

1. [ ] **Stabilize**: Confirm metrics returned to baseline. Alert cleared in Prometheus.
2. [ ] **Communicate**: Post final status update. "Resolved at HH:MM UTC. Error rate back to <1%. No data loss."
3. [ ] **Document**: Create postmortem in `docs/Incident Response/rca/` with timeline, root cause, and action items.
4. [ ] **Review**: Share postmortem in team channel within 24 hours.
5. [ ] **Follow up**: Ensure action items are tracked in your issue tracker (GitHub, Jira, etc.).
6. [ ] **Prevent**: Close any related PRs that prevent recurrence.

---

## 16. Quick Reference: Critical Thresholds

Keep these numbers in your head:

| Metric | Alert Threshold | SLO Target | Your Hardware Ceiling |
|--------|-----------------|------------|----------------------|
| **Error Rate (5xx)** | >5% for 30s | <1% | 20% (saturation) |
| **Latency p95** | >500ms for 30s | <500ms (reads), <1s (writes) | ~3s with 3 replicas |
| **Availability** | N/A | 99.9% (10m downtime/week) | ~99.5% if Postgres frequently restarts |
| **Memory** | N/A | N/A | ~3.3 GB (3 app replicas max) |
| **CPU** | N/A | <75% | ~180% per vCPU (2 total) with 3 replicas |

---

## 17. Incident Response Communication Template

Copy-paste these messages to keep communication consistent:

**Initial Alert**:
```
P[1/2/3] Alert: [AlertName]
- Service: URL Shortener
- Status: INVESTIGATING
- Grafana: http://localhost:3000
- Last update: [timestamp]
```

**Root Cause Found**:
```
Root cause identified: [brief description]
Mitigation: [what we're doing]
ETA to resolution: [estimate]
```

**Resolved**:
```
RESOLVED - URL Shortener [AlertName]
- Duration: X minutes
- Root cause: [brief description]
- Impact: [what was affected]
- Postmortem: [link to RCA]
- Next steps: [action items for follow-up]
```

---

## 18. On-Call Handoff Template

**When passing on-call to the next engineer:**

```markdown
# On-Call Handoff: [Date]

## Current Status
- [ ] All services healthy (check Grafana)
- [ ] No active alerts in Prometheus
- [ ] Recent incident? If yes, postmortem status: [pending/in-progress/completed]

## Recent Changes
- Code deployed: [commit hash, time]
- Infrastructure changes: [if any]
- Known issues: [if any]

## Monitoring
- Primary dashboard: http://localhost:3000 (URL Shortener - Golden Signals)
- Alert channel: gunbirsingh2006@gmail.com / ajinda17@asu.edu
- Escalation: [@devgunnu](https://github.com/devgunnu) → [@RETR0-OS](https://github.com/RETR0-OS)

## Key Docs
- Incident playbook: `docs/Incident Response/runbooks/INCIDENT-PLAYBOOK.md`
- RCA archive: `docs/Incident Response/rca/`
- Design decisions: `docs/Incident Response/INCIDENT_RESPONSE_ENGINEERING_DESIGN_DECISIONS.md`

Questions for the outgoing engineer: [ask here]
```

---

## 19. Critical Emergency Numbers

**If this is a production incident affecting real users:**

| Role | Contact | Backup |
|------|---------|--------|
| @devgunnu (Gunbir Singh) | gunbirsingh2006@gmail.com | [@devgunnu](https://github.com/devgunnu) |
| @RETR0-OS (Aaditya Jindal) | ajinda17@asu.edu | [@RETR0-OS](https://github.com/RETR0-OS) |
| @aryankhanna2004 (Aryan Khanna) | — | [@aryankhanna2004](https://github.com/aryankhanna2004) |
| @SinghOPS (Sahajpreet Singh) | — | [@SinghOPS](https://github.com/SinghOPS) |

---

## 20. Final Reminders

1. **Stay calm.** Incidents happen. You're trained for this.
2. **Document as you go.** Start the postmortem timeline immediately.
3. **Don't guess.** Check logs, check dashboards, verify with curl/psql/redis-cli before acting.
4. **Escalate early.** If unsure after 15 minutes, loop in the team lead.
5. **Test your fix.** After mitigation, wait 2-3 minutes and verify metrics are back to baseline.
6. **Communicate status every 5-10 minutes.** Updates prevent panic and align the team.
7. **Automate the fix.** After the postmortem, write code or config that prevents recurrence.

---

**Last Updated**: 2026-04-04
**Maintained By**: [Team Name]
**Review Cycle**: Quarterly or after any P1 incident
