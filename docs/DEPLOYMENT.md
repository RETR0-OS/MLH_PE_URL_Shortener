---
layout: default
title: Deployment Guide
permalink: /deployment
---

# Deployment Guide

How to get the URL Shortener service live, maintain it in production, and rollback on failure.

---

## Quick Links

- **Production Server**: http://64.225.10.147
- **Monitoring**: Grafana at http://64.225.10.147:3000
- **API Docs**: http://64.225.10.147/docs/
- **Health Check**: http://64.225.10.147/health

---

## Environment Comparison

| Configuration | Local Development | Production |
|---------------|------------------|-----------|
| **`FLASK_DEBUG`** | `true` | `false` |
| **`DATABASE_PASSWORD`** | `postgres` (default) | Strong random string (required) |
| **`DATABASE_HOST`** | `postgres` (Docker) or `localhost` | `postgres` (Docker service name) |
| **`GF_SECURITY_ADMIN_PASSWORD`** | `admin` | Changed from default (required) |
| **`API_KEY`** | Empty (disabled) | Recommended: set a random key |
| **`OTEL_EXPORTER_OTLP_ENDPOINT`** | Empty (tracing off) | `http://jaeger:4317` |
| **App replicas** | 1–2 | 2–5 (auto-scaled) |
| **Resource limits** | Relaxed | Enforced (0.75 CPU, 384 MB per replica) |
| **TLS** | Self-signed (cert-gen) | Self-signed (cert-gen) or bring your own |
| **Alerting** | Disabled (no RESEND_API_KEY) | Enabled (email + Discord) |
| **Backups** | Not needed | Manual pg_dump recommended daily |

---

## Local Development Setup

### Prerequisites

- Python 3.13+
- `uv` package manager: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- PostgreSQL 16 and Redis 7 (via Docker or native install)
- Docker & Docker Compose (for full stack)

### Step 1: Clone and Install

```bash
git clone https://github.com/RETR0-OS/MLH_PE_URL_Shortener.git
cd MLH_PE_URL_Shortener

# Install dependencies
uv sync

# Copy env template and customize
cp .env.example .env
# Edit .env with local database credentials if needed
```

### Step 2: Database Setup

**Option A: Docker Compose (recommended — spins up everything)**

```bash
docker compose up -d --build
# Waits for Postgres + Redis to be healthy, then starts the app

# Verify health
curl http://localhost/health
# → {"status": "ok"}

curl http://localhost/health/ready
# → {"status": "ok"}
```

**Option B: Local PostgreSQL**

```bash
# Create database
createdb hackathon_db

# Set DATABASE_HOST=localhost in .env

# Run migrations (automatic on app startup via app/__init__.py)
uv run flask --app run:app run --port 5000
```

### Step 3: Seed Data (Optional)

```bash
# If running Docker Compose
docker compose exec app python scripts/seed.py

# If running locally
uv run python scripts/seed.py
```

### Step 4: Run Tests

```bash
uv run pytest --cov=app --cov-fail-under=70
```

---

## Production Deployment

### Pre-Deployment Checklist

Run through these before every production deploy:

- [ ] All CI checks green on the branch being deployed (unit tests, load tests, lint)
- [ ] `.env` on the droplet has correct values (`DATABASE_PASSWORD`, `RESEND_API_KEY`, `GF_SECURITY_ADMIN_PASSWORD` all non-default)
- [ ] `.env` is NOT tracked by git (`git status` must not show it)
- [ ] Docker Compose file has correct resource limits for available hardware
- [ ] Grafana is accessible and shows no active firing alerts pre-deploy: `curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'`
- [ ] You have a rollback plan: know the previous commit SHA (`git log --oneline -5`)
- [ ] Disk space check: `df -h /` must show < 80% usage

### Prerequisites

- DigitalOcean Droplet (or equivalent Linux VM) with:
  - Ubuntu 22.04+
  - Docker & Docker Compose installed
  - SSH access from CI/CD runner
- GitHub Secrets configured:
  - `DROPLET_IP` — Production server public IP
  - `DROPLET_USER` — SSH user (e.g., `root`)
  - `DROPLET_PASS` — SSH password

### Deployment Process

**Automatic (Recommended):**

The CI/CD pipeline (`deploy.yml`) automatically deploys on every merge to `main`:

1. **PR to dev**: Unit tests + load tests run (177 tests, 91% coverage)
2. **Merge to main**: [`deploy.yml`](https://github.com/RETR0-OS/MLH_PE_URL_Shortener/blob/dev/.github/workflows/deploy.yml) triggers automatically
3. **On Droplet**:
   ```bash
   cd /root/MLH_PE_URL_Shortener
   git pull origin main
   docker compose up -d --build --remove-orphans
   # App is rebuilt, new replicas spin up, old ones stop (start-first rolling update)
   ```
4. **Health Check**: Workflow polls `/health` for 30s. If it fails, the workflow exits non-zero and alerts the team.

**Manual Deployment:**

```bash
# SSH into the droplet
ssh root@<DROPLET_IP>

# Navigate to project
cd /root/MLH_PE_URL_Shortener

# Pull latest code
git pull origin main

# Rebuild and restart
docker compose up -d --build --remove-orphans

# Verify health
curl http://localhost/health
curl http://localhost/health/ready

# Watch logs
docker compose logs -f app

# Verify specific services
docker compose ps
```

### Environment Variables

Set these on the droplet before deploying. See [`docs/config.md`](config.md) for full details:

```bash
# Critical (must change from defaults)
DATABASE_PASSWORD=<strong-random-password>
RESEND_API_KEY=re_xxxxxxx  # From resend.com
ALERT_EMAIL_TO=your-email@example.com

# Optional (good to set)
API_KEY=<random-key>  # For API authentication
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317  # For tracing
```

Create a `.env` file on the droplet at `/root/MLH_PE_URL_Shortener/.env`:

```bash
cat > /root/MLH_PE_URL_Shortener/.env << EOF
FLASK_DEBUG=false
DATABASE_NAME=hackathon_db
DATABASE_HOST=postgres
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=<change-me>

REDIS_HOST=redis
REDIS_PORT=6379

RESEND_API_KEY=<change-me>
ALERT_EMAIL_TO=<change-me>

GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=<change-me>
EOF
```

### Verify the Deployment Worked

Run these commands **immediately after every deploy** to confirm the new code is live and healthy:

```bash
# 1. Confirm the app responds (must return HTTP 200)
curl -s -o /dev/null -w "%{http_code}" http://localhost/health
# Expected: 200

# 2. Confirm DB is connected (readiness probe)
curl -s http://localhost/health/ready | jq .
# Expected: {"status": "ok"}

# 3. Confirm correct number of replicas are running
docker compose ps | grep app
# Expected: 2 (or more) "app" containers with "Up" status

# 4. Confirm no 5xx errors in last 60 seconds
curl -s "http://localhost:9090/api/v1/query?query=sum(increase(flask_http_request_total{status=~'5..'}[60s]))" | jq '.data.result[0].value[1]'
# Expected: "0" (or empty result)

# 5. Confirm p95 latency is below SLO
curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(flask_http_request_duration_seconds_bucket[5m]))by(le))*1000" | jq '.data.result[0].value[1]'
# Expected: a number below 500 (500ms SLO)

# 6. Spot-check the API
curl -s http://localhost/urls | jq '.count'
# Expected: a non-null integer

# 7. Watch logs for errors for 30 seconds
docker compose logs app --tail 0 -f &
sleep 30
kill %1
# Expected: no ERROR-level log lines
```

If any check fails, proceed to [Rollback Procedures](#rollback-procedures) immediately.

---

## Rolling Updates (Zero-Downtime Deploys)

Docker Compose is configured to deploy with **no downtime**:

```yaml
# docker-compose.yml
deploy:
  replicas: 2
  update_config:
    order: start-first   # ← New replica starts BEFORE old one stops
    parallelism: 1       # ← One at a time
    delay: 5s
```

**What happens during `docker compose up -d --build`:**

1. Docker builds the new app image
2. Spins up a **new** replica with the updated code
3. New replica reaches healthy state (`/health` → 200)
4. Docker stops the **old** replica
5. Repeats for the second replica

**Result**: At no point are zero replicas running. Users experience zero downtime.

If a new image fails to start or never becomes healthy, the deployment pauses and the old containers keep serving.

---

## Rollback Procedures

### Automatic Rollback (via Workflow Failure)

If the health check fails during deployment, the workflow exits non-zero and **the old containers keep running**. No action needed — the deploy failed and the old version is still live.

### Manual Rollback (Emergency)

If a deploy goes live but causes issues:

#### Option 1: Revert Commit and Redeploy

```bash
ssh root@<DROPLET_IP>
cd /root/MLH_PE_URL_Shortener

# Revert to the previous commit
git revert HEAD --no-edit
git push origin main

# The CI/CD workflow automatically triggers and redeploys the reverted code
# Alternatively, manually trigger the deploy:
docker compose up -d --build
```

#### Option 2: Manually Restart Previous Image

If you saved the image ID before deployment:

```bash
ssh root@<DROPLET_IP>

# Find the image ID of the old version
docker images | grep mlh_pe_url_shortener_app

# Tag the old image and use it
docker tag <old-image-id> app:rollback
docker compose -f docker-compose.yml \
  -e "IMAGE=app:rollback" \
  up -d --build

# Verify
curl http://localhost/health/ready
```

#### Option 3: Docker Swarm Rollback (if using Swarm)

If deployed to Docker Swarm instead of Compose:

```bash
docker service update --rollback <service-name>

# Example for the app service
docker service update --rollback urlshort_app
```

### Post-Rollback

1. **Verify health**: `curl http://localhost/health/ready`
2. **Check logs**: `docker compose logs app | tail -100`
3. **Monitor dashboard**: Open Grafana and watch error rate / latency return to baseline
4. **Notify team**: Post incident note in Slack / email with timeline and root cause
5. **Write RCA**: Use [`docs/Incident Response/rca/POSTMORTEM-TEMPLATE.md`](Incident%20Response/rca/POSTMORTEM-TEMPLATE.md) to document what happened

---

## Production Monitoring

### Access Monitoring Stack

All services are running in Docker Compose:

| Service | URL | Default Credentials |
|---------|-----|-------------------|
| **Grafana Dashboards** | http://64.225.10.147:3000 | admin / admin |
| **Prometheus Metrics** | http://64.225.10.147:9090 | — |
| **Alertmanager** | http://64.225.10.147:9093 | — |
| **Jaeger Tracing** | http://64.225.10.147:16686 | — |
| **App Metrics** | http://64.225.10.147/metrics | — |
| **Loki Logs** | http://64.225.10.147:3100 | — |

### Daily Operational Checks

Run these from the droplet every morning / after a deploy:

```bash
# Health endpoints
curl http://localhost/health
curl http://localhost/health/ready

# App container status
docker compose ps
# All services should be "Up"

# Log check (last 50 lines)
docker compose logs app | tail -50

# Metric check (request rate)
curl http://localhost/metrics | grep flask_http_request_total

# Database connectivity
docker compose exec app curl -s http://localhost/health/ready | jq .
# Should return 200 {"status": "ok"}
```

### Alert Response

See [`docs/Incident Response/runbooks/INCIDENT-PLAYBOOK.md`](Incident%20Response/runbooks/INCIDENT-PLAYBOOK.md) for detailed runbooks on responding to each alert:

- **ServiceDown** — App container crashed or Postgres unreachable
- **HighErrorRate** — 5xx errors > 5% (user-facing problem)
- **HighLatency** — p95 response time > 500ms (performance degradation)
- **RedisDown** — Redis unavailable (circuit breaker activated)

---

## Capacity Planning

### Current Hardware

**DigitalOcean Droplet:**
- CPU: 2 vCPU
- Memory: 2 GB
- Disk: 50 GB SSD

### Current Limits

From [`docs/Scalability/README.md`](Scalability/README.md):

| Metric | Limit | Reasoning |
|--------|-------|-----------|
| **Request Rate** | ~400 req/s (2 replicas × 200 req/s each) | Before hitting 70% CPU and triggering autoscaler |
| **App Replicas** | 2–5 (auto-scaled) | Min 2 for redundancy, max 5 due to memory |
| **Database Connections** | 20 per replica (40 total) | Peewee pool size × replica count |
| **Redis Memory** | 128 MB LFU cache | `maxmemory` config |
| **PostgreSQL Buffer** | 192 MB | `shared_buffers` config |

### Scaling Strategies

**If approaching 400 req/s:**

1. **Increase replica count**: Modify `MIN_REPLICAS` and `MAX_REPLICAS` env vars
   ```bash
   # In docker-compose.yml, autoscaler service section:
   environment:
     MIN_REPLICAS: 3      # Was 2
     MAX_REPLICAS: 8      # Was 5
   docker compose up -d --build
   ```

2. **Increase resource limits**: Edit docker-compose.yml:
   ```yaml
   services:
     app:
       deploy:
         resources:
           limits:
             cpus: '1.5'        # Was 0.75
             memory: 512M       # Was 384M
   ```

3. **Upgrade droplet**: Scale to a larger DigitalOcean VM (4 vCPU / 4 GB RAM)

---

## Troubleshooting Common Issues

### App keeps restarting (CrashLoopBackOff)

**Check logs:**
```bash
docker compose logs app | tail -100
```

**Common causes:**
- **Database unreachable**: Check `DATABASE_HOST` / `DATABASE_PASSWORD` in `.env`
- **Port already in use**: `docker ps` and kill conflicting container
- **Out of memory**: Check memory limits in docker-compose.yml

**Fix:**
```bash
# Restart the service
docker compose restart app

# Or full rebuild
docker compose down && docker compose up -d --build
```

### High error rate spike

**Check Grafana first**: Open http://64.225.10.147:3000, view **Error Rate** panel.

**Then check logs**:
```bash
docker compose logs app | grep -i error | tail -50
```

**Common causes:**
- **Database down**: Check `/health/ready` and `docker compose ps`
- **Validation failure**: Check log messages for `400` responses
- **Redis circuit breaker**: Check `app/utils/cache.py` circuit breaker logs

**Recovery:**
```bash
# Restart app
docker compose restart app

# Or restart specific service (e.g., Postgres)
docker compose restart postgres
```

### Latency spike (p95 > 500ms)

**Check Grafana**: View **Latency p50/p95/p99** panel.

**Check request volume**: Is traffic spiking simultaneously?

**Check database**: Run a slow query check:
```bash
docker compose exec postgres psql -U postgres -d hackathon_db \
  -c "SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 5;"
```

**Check cache hit rate**: Look at Prometheus metric `redis_evictions_total` (should be stable, not rapidly increasing).

---

## SLO & Maintenance Windows

### Availability Target

**99.9% uptime** (43 minutes of downtime per month allowed)

Monitor in Grafana: **Service Uptime** panel should always be > 99.8%.

### Planned Maintenance

If you need to take the service down:

1. **Announce 24 hours in advance** — Email affected users
2. **Schedule during low-traffic window** — Usually 2-4 AM UTC
3. **Deploy procedure**:
   ```bash
   # On the droplet
   docker compose down
   # Perform maintenance (DB migration, config change, etc.)
   docker compose up -d --build
   ```
4. **Health check**: Verify `curl http://localhost/health/ready` returns 200
5. **Post-maintenance announcement** — Confirm service is live

### Backup & Recovery

**Database backups** (manual):

```bash
# On the droplet
docker compose exec postgres pg_dump \
  -U postgres hackathon_db > backup-$(date +%Y%m%d).sql

# Restore from backup
docker compose exec postgres psql \
  -U postgres hackathon_db < backup-20260405.sql
```

---

## Security Checklist

Before going live, verify:

- [ ] `.env` is NOT committed to Git (check `.gitignore`)
- [ ] `DATABASE_PASSWORD` is a strong random string
- [ ] `RESEND_API_KEY` is from a valid Resend account
- [ ] `GF_SECURITY_ADMIN_PASSWORD` is changed from default `admin`
- [ ] API_KEY is set (optional but recommended)
- [ ] Nginx HTTPS is configured (TLS 1.2+)
- [ ] Security headers are set in Nginx (CSP, X-Frame-Options, etc.)
- [ ] Firewall only exposes ports 80, 443 (HTTP/HTTPS)
- [ ] SSH key auth is enforced (no password-based SSH)

---

## Related Documentation

- **Configuration**: [`docs/config.md`](config.md)
- **Incident Response**: [`docs/Incident Response/runbooks/INCIDENT-PLAYBOOK.md`](Incident%20Response/runbooks/INCIDENT-PLAYBOOK.md)
- **Reliability**: [`docs/Reliability/RELIABILITY_ENGINEERING.md`](Reliability/RELIABILITY_ENGINEERING.md)
- **Scalability**: [`docs/Scalability/README.md`](Scalability/README.md)
