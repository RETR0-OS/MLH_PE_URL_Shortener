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
Update the status channel (Slack, team chat, email):
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
| 0-5 min | Alert received, acknowledge in Slack | On-call engineer |
| 5-15 min | Diagnose using runbook | On-call engineer |
| 15-30 min | If not resolved, loop in team lead | On-call + team lead |
| 30+ min | Page backup on-call, consider rollback or code change | Team |
| 1+ hour | Post incident update, coordinate postmortem | Team lead |

**On-Call Contact**:
- Primary: [Defined in team rotation]
- Backup: [Defined in team rotation]
- Team Lead: [Defined in team rotation]

**Notification channels**:
- Slack: #incidents
- Email: oncall@urlshortener.local (configured in `ALERT_EMAIL_TO`)

---

## 8. Runbook Summaries

These are brief summaries of each alert. Full details are below.

### ServiceDown

**Alert fires**: App instance unreachable for >1 minute.

**Immediate checks**:
1. `docker compose ps` — Are containers running?
2. `docker compose logs app --tail 50` — Any crash logs?
3. `curl http://localhost/health` — Does the service respond?

**Common causes**:
- Postgres is down → app can't start
- Port 5000 is already in use
- Out of memory (OOM kill)
- Container crash in startup

**Mitigation**:
1. Check Postgres: `docker compose ps postgres` and `docker compose logs postgres`
2. If Postgres is down, restart it: `docker compose restart postgres`
3. If app still won't start, check dependencies: `docker compose up app` (not detached) to see the error
4. If OOM: scale down replicas (`docker compose up -d --scale app=1`) and investigate memory leak

**Expected recovery time**: 5-15 seconds (after Postgres or dependencies recover).

### HighErrorRate

**Alert fires**: 5xx error rate exceeds 5% for >30 seconds.

**Immediate checks**:
1. Grafana "Error Rate" panel — which endpoints are failing?
2. Grafana "Traffic" panel — did traffic spike?
3. `docker compose logs app | grep ERROR` — any application errors?
4. `docker compose ps` — all replicas healthy?

**Common causes**:
- Database connection pool exhausted
- Unhandled exception in code
- Cascading failure from dependency (Postgres, Redis)
- Traffic spike overwhelming the app

**Mitigation**:
1. If DB connection errors, check Postgres: `docker compose exec postgres psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"` (should be <80% of max_connections=100)
2. If Redis errors, Redis is likely down (expected behavior — circuit breaker engages). Not user-facing.
3. If specific endpoint is broken, check app logs for stack traces.
4. Scale up: `docker compose up -d --scale app=3`
5. If still high after scaling, consider rollback: `git revert HEAD && docker compose up -d --build app`

**Expected recovery time**: 2-5 minutes (after app restart or scale-up).

### HighLatency

**Alert fires**: p95 latency exceeds 500ms for >30 seconds.

**Immediate checks**:
1. Grafana "Request Duration" panel — is p95 consistently high?
2. Grafana "Traffic" panel — did traffic spike?
3. Grafana "CPU" and "Memory" panels — are resources maxed out?
4. `docker stats` — individual container memory/CPU?

**Common causes**:
- Traffic spike (legitimate or attack)
- Redis down → cache misses → slower DB reads
- Postgres under heavy load (cold cache, slow query)
- Insufficient app replicas

**Mitigation**:
1. Scale up app replicas: `docker compose up -d --scale app=3` (practical ceiling on this hardware is 3 replicas)
2. Check Redis: `docker compose logs redis | tail 20`. If down, it will auto-restart.
3. Warm the cache by accessing popular URLs.
4. If latency doesn't improve with 3 replicas, the bottleneck is Postgres. Document in CAPACITY_PLAN and consider infrastructure upgrade.

**Expected recovery time**: 1-3 minutes (after scaling).

### RedisDown

**Alert fires**: Redis connection errors detected for >1 minute.

**Immediate checks**:
1. `docker compose ps redis` — is Redis container running?
2. `docker compose exec redis redis-cli ping` — does it respond?
3. `docker compose logs redis | tail 50` — any error messages?
4. `docker compose exec redis redis-cli info memory` — memory usage?

**Immediate impact**: NONE. The app has a circuit breaker that falls back to direct database reads. Latency will increase, but no user-facing errors.

**Common causes**:
- Redis OOM killed (memory limit exceeded)
- Redis crash or hang
- Network connectivity issue

**Mitigation**:
1. If Redis is down, it will auto-restart due to `restart: unless-stopped` in docker-compose.yml.
2. Wait 30 seconds for Redis to restart and reconnect.
3. If Redis keeps crashing, check logs: `docker compose logs redis`
4. If OOM kill, consider reducing cache TTL or checking for memory leak. Or increase `maxmemory` from 128MB to 256MB if hardware allows.

**Expected recovery time**: 30 seconds (auto-restart), no manual intervention needed.

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

Your hardware has **4 GB RAM** total; ~3.3 GB available for services.

### Service Memory Budget

| Service | Limit | Current Config |
|---------|-------|-----------------|
| App (per replica) | 384 MB | 2-3 replicas |
| Postgres | 768 MB | Fixed 1 instance |
| Redis | 160 MB | Fixed 1 instance |
| Nginx | 64 MB | Fixed 1 instance |
| Prometheus | 256 MB | Fixed 1 instance |
| Loki | 256 MB | Fixed 1 instance |
| Grafana | 256 MB | Fixed 1 instance |
| Alertmanager | 128 MB | Fixed 1 instance |

**Formula**: `Total = (app_replicas * 384MB) + 1920MB (fixed services)`

- **2 replicas**: ~2.66 GB (safe, 36% headroom)
- **3 replicas**: ~3.04 GB (safe, 8% headroom)
- **4 replicas**: ~3.4 GB (OUT OF MEMORY, don't do this)

**Action**: If memory usage >3 GB, scale app down to 1 replica or restart services.

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
- [ ] You have a way to be notified (email, Slack, phone)
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
- Alert channel: #incidents Slack
- Escalation: [phone number or contact]

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
| On-Call Engineer | [Phone / Slack] | [Backup number] |
| Team Lead | [Phone / Slack] | [Backup number] |
| SRE Lead | [Phone / Slack] | [Backup number] |

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
