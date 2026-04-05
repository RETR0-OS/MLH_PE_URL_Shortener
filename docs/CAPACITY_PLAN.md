---
layout: default
title: Capacity Planning
permalink: /capacity-plan
---

# Capacity Planning & Performance Analysis

Current bottlenecks, scaling headroom, and growth roadmap for the URL Shortener.

---

## Current Hardware Specs

**Production Environment:**

| Resource | Spec | Notes |
|----------|------|-------|
| **Droplet** | DigitalOcean 2 vCPU, 2 GB RAM, 50 GB SSD | Single-server deployment |
| **CPU per App Replica** | 0.75 cores (750m) | Via Docker resource limits |
| **Memory per App Replica** | 384 MB | Via Docker resource limits |
| **PostgreSQL** | 768 MB | Tuned with `shared_buffers=192MB` |
| **Redis** | 160 MB | 128 MB max memory (eviction enabled) |
| **Nginx** | 64 MB | Minimal footprint |
| **Prometheus** | 512 MB | 72h retention |
| **Grafana** | 256 MB | Dashboards + log queries |
| **Loki** | 256 MB | 72h log retention |
| **Alertmanager** | 128 MB | Alert routing |
| **Jaeger** | 256 MB | Trace storage (limited retention) |
| **Promtail** | 128 MB | Log shipping agent |
| **Autoscaler** | 64 MB | Monitoring daemon |
| **Total** | ~4.6 GB | Current footprint |

---

## Measured Performance Baselines

### Load Test Results (500 VU k6)

**Test Setup**: 500 virtual users, 60-second ramp-up, sustained for 180 seconds

```
Total Requests: 63,001
Request Rate: 482 req/s
Error Rate: 0.00%
P50 Latency: 18 ms
P95 Latency: 42 ms
P99 Latency: 125 ms
```

**System State During Test:**
- App replicas: 2 (autoscaler did not scale up)
- CPU usage: 65% (under 70% threshold)
- Memory usage: 1.2 GB total
- Database connections: 28/40 (70% utilization)
- Redis memory: 38 MB (30% of 128 MB cap)
- 5xx errors: 0

**Conclusion**: System handled 482 req/s with low latency and zero errors.

### Per-Endpoint Performance

| Endpoint | P50 | P95 | P99 | Notes |
|----------|-----|-----|-----|-------|
| `GET /health` | 0.5ms | 1ms | 2ms | Lightweight, always cached |
| `GET /urls/{id}` | 12ms | 28ms | 85ms | Cache hit ~90%, DB hit with pool contention |
| `GET /{short_code}/redirect` | 8ms | 22ms | 65ms | Hot path, Redis cache-aside |
| `POST /urls` | 45ms | 120ms | 250ms | Event logging async, higher variance |
| `GET /users` (paginated) | 35ms | 95ms | 180ms | Multiple DB queries, user filtering |

### Checkpoint Timing Breakdown (Median Request)

From structured logs (`app/middleware.py`):

```json
{
  "path": "/urls/42",
  "timings": {
    "middleware": 0.5,      // Request setup, X-Request-ID
    "cache_get": 2.1,       // Redis lookup
    "db_read": 5.2,         // PostgreSQL query (if cache miss)
    "cache_set": 0.8,       // Redis cache write
    "serialize": 0.2,       // JSON serialization
    "after_request": 0.1    // Response headers, logging
  },
  "total_latency_ms": 8.9
}
```

---

## Current Bottleneck Analysis

### Tier 1: Request Handling (482 req/s max, measured)

**Bottleneck**: App concurrency

| Component | Current Capacity | Limiting Factor |
|-----------|------------------|-----------------|
| **Nginx workers** | ~4 (2 vCPU × auto) | CPU cores available |
| **Gunicorn workers** | 2 per replica × 2 replicas = 4 processes | Spawned at startup |
| **Gunicorn threads** | 4 threads per worker × 4 = 16 threads | Thread pool size |
| **Actual concurrent requests** | ~14-16 | Thread pool |
| **Throughput at current setup** | 482 req/s | Limited by # replicas × threads/replica |

**Scaling action**: If traffic > 482 req/s, autoscaler increases replicas.

With 3 replicas: 3 × 8 = 24 threads → ~720 req/s estimated
With 5 replicas (max): 5 × 8 = 40 threads → ~1200 req/s estimated

Note: Each replica has 2 workers × 4 threads = 8 concurrent request slots per replica.

### Tier 2: Database Connections (40 max, tested)

**Bottleneck**: Connection pool saturation

| Resource | Current | Max | Usage at 482 req/s |
|----------|---------|-----|-----------------|
| **Peewee pool per replica** | 20 connections | 20 | ~14/20 (70%) |
| **Total replicas × pool** | 40 connections | 40 | ~28/40 (70%) |
| **PostgreSQL max_connections** | Default 100 | 100 | 28/100 (28%) |

**Scaling action**: If > 90% pool utilization, add replicas (shares same DB, not direct scaling).

At 5 replicas: 5 × 20 = 100 connections → approaches PostgreSQL default max.

**Mitigation**: Increase `max_connections` in PostgreSQL or increase `stale_timeout` to recycle idle connections faster.

### Tier 3: Redis Cache (128 MB, LFU)

**Bottleneck**: Memory limit

| Metric | Value | Notes |
|--------|-------|-------|
| **Max memory** | 128 MB | Hardcoded in docker-compose.yml |
| **Eviction policy** | allkeys-lfu | Least frequently used keys evicted first |
| **Typical memory at 482 req/s** | ~38 MB (30%) | Leaves headroom |
| **Full cache scenario** | 128 MB | Occurs when > 1 M unique URLs cached |

**Scaling action**: Redis rarely bottlenecks; if needed:
1. Increase `maxmemory` to 256 MB (more overhead)
2. Use `--save-db-frequency` to tune eviction aggressiveness

**When to worry**: If eviction counter (`redis_evictions_total`) rapidly increases, cache thrashing is occurring.

### Tier 4: Disk I/O (50 GB, SSD)

**Bottleneck**: Unlikely at current scale

| Resource | Usage | Capacity | Headroom |
|----------|-------|----------|----------|
| **Database** | ~200 MB (typical) | 50 GB | 49.8 GB |
| **Logs (Loki 72h)** | ~500 MB/day | 50 GB | Can store ~100 days |
| **Trace data (Jaeger)** | ~100 MB/day | 50 GB | Can store ~500 days |

**Scaling action**: Upgrade droplet SSD if disk usage > 70%.

---

## Break Point Analysis — What Fails First

This section answers: "if traffic keeps growing, what is the first thing that breaks, and at what load?"

### Current Break Point Order (measured + estimated)

| # | Component | Breaks At | Failure Mode | Leading Indicator |
|---|-----------|-----------|--------------|-------------------|
| 1 | **App replica count cap** | ~800 req/s (5 replicas × 160 req/s) | Latency climbs, autoscaler hits `MAX_REPLICAS=5` ceiling | `HighReplicaCount` alert fires |
| 2 | **PostgreSQL max_connections** | ~100 connections (5 replicas × 20 pool) | App crashes: "FATAL: too many connections" | `pg_stat_activity` count approaching 90+ |
| 3 | **Droplet CPU** | ~1,200 req/s (estimated, 5 replicas × 2 cores) | Response time degrades, autoscaler can't add more replicas | CPU > 90% for sustained period |
| 4 | **Droplet RAM** | 3 replicas on 2GB droplet (services use ~2.9 GB at 3 replicas) | OOMKill of one or more containers | `free -m` shows < 200 MB free |
| 5 | **Redis memory** | ~1 million unique cached URLs (128 MB / ~120 bytes per key) | Eviction thrashing — cache hit rate drops sharply | `redis_evictions_total` increasing rapidly |
| 6 | **Disk (Loki/Prometheus)** | ~100 days at current log volume | Log queries fail, metrics retention exceeded | `df -h /` > 80% |

### The First Thing That Actually Breaks

At current hardware (2 vCPU, 2 GB RAM, `MAX_REPLICAS=5`):

**The replica cap (800 req/s) will be hit before PostgreSQL connection exhaustion or RAM exhaustion.** Here's why:

- At 5 replicas, the RAM consumption is ~3.7 GB which exceeds the 2 GB droplet. The autoscaler will be constrained to 3 replicas max on a 2 GB droplet before hitting 5.
- With 3 replicas max: break point is ~480 req/s before latency exceeds SLO.
- PostgreSQL connection exhaustion at 3 replicas: 3 × 20 = 60 connections (well below 100 limit).

**Practical ceiling on 2 GB droplet: ~480 req/s with SLO-compliant latency.**

### How to Extend the Break Point

1. **Immediate (no cost)**: Increase `work_mem` to 16 MB and `max_connections` to 200 in PostgreSQL to give more headroom.
2. **$12 → $24/month**: Upgrade to 2 vCPU / 4 GB RAM droplet. This allows 5 replicas safely → ~800 req/s.
3. **$24 → $48/month**: Upgrade to 4 vCPU / 8 GB RAM. Up to 10 replicas → ~1,600 req/s.
4. **> $48/month**: Multi-droplet setup with managed PostgreSQL and Redis (see Phase 3 below).

---

## Cost Projections

### Current Costs

| Resource | Monthly Cost | Notes |
|----------|-------------|-------|
| DigitalOcean Droplet (2 vCPU, 2 GB) | $12 | All services on single droplet |
| Resend email (alerts) | $0 | Free tier: 3,000 emails/month |
| Domain / TLS | $0 | Self-signed cert, no paid domain |
| **Total** | **$12/month** | |

### Cost at Scale

| Traffic Level | Recommended Setup | Monthly Cost |
|--------------|-----------------|-------------|
| < 480 req/s | Current 2 vCPU / 2 GB droplet | $12 |
| 480–800 req/s | Upgrade to 2 vCPU / 4 GB droplet | $24 |
| 800–1,600 req/s | Upgrade to 4 vCPU / 8 GB droplet | $48 |
| 1,600–5,000 req/s | 2× 4 vCPU droplets + DigitalOcean Managed PostgreSQL | ~$120–$160 |
| 5,000+ req/s | 4+ app droplets + Managed DB + Managed Redis + CDN | $300+ |

### Cost Per Request (at 482 req/s baseline)

- 482 req/s × 86,400 s/day = ~41.6 million requests/day
- $12/month / 30 days = $0.40/day
- **Cost per million requests: ~$0.01** (sub-cent, well within typical URL shortener economics)

---

## Scaling Scenarios

### Scenario 1: Light Load → Heavy Load (Gradual)

**Trigger**: Traffic grows from 100 req/s to 600 req/s over 1 week

```
Day 1: 100 req/s
  ↓ (2 replicas, CPU 20%, latency p95 = 15ms)

Day 3: 300 req/s
  ↓ (2 replicas, CPU 55%, latency p95 = 28ms)
  ↓ Autoscaler detects CPU ≥ 70% for 2 polls (20s)
  ↓ Scales to 3 replicas, waits 60s cooldown

Day 5: 500 req/s
  ↓ (3 replicas, CPU 60%, latency p95 = 20ms)
  ↓ Autoscaler scales to 4 replicas

Day 7: 600 req/s
  ↓ (4 replicas, CPU 62%, latency p95 = 18ms)
  ↓ System stable, no further scaling needed
```

**Outcome**: Auto-scaling handles gradual growth with zero manual intervention.

### Scenario 2: Traffic Spike (Sudden)

**Trigger**: Viral URL shared on social media, traffic jumps from 100 → 800 req/s instantly

```
T=0s: Traffic spike detected
     ↓ Latency jumps from 15ms → 120ms (p95)
     ↓ Error rate jumps to 2% (connection pool exhaustion)
     ↓ CPU hits 85%

T=20s: Autoscaler 1st poll detects CPU 85% ≥ 70%
     ↓ (Need 2 consecutive polls before scaling)

T=30s: Autoscaler 2nd poll confirms CPU still 85%
     ↓ Scales to 3 replicas (starts new container)

T=40s: New replica initializes, connections pool warm
     ↓ Nginx adds it to upstream (least-conn)

T=60s: Cooldown expires, autoscaler can scale again
     ↓ CPU still 75%, scales to 4 replicas

T=120s: All 4 replicas healthy
     ↓ CPU 68%, latency p95 = 22ms
     ↓ Error rate back to 0%
```

**Outcome**:
- **Initial impact**: 20-40s of elevated latency/errors during scale-up
- **Recovery time**: ~2 minutes to stable state
- **Max replicas**: 5 (hardcoded limit)
- **If 800 req/s exceeds 5 replica capacity**: Latency stays high, SLO violated

**Mitigation**:
1. Increase `MAX_REPLICAS` to 8 (requires more memory: ~8 × 384 MB = 3 GB)
2. Pre-scale to 3 replicas during known traffic peaks (Black Friday, etc.)
3. Vertical scale: Upgrade droplet to 4 vCPU / 4 GB RAM

### Scenario 3: Database Connection Pool Exhaustion

**Trigger**: 5 replicas × 20 connections each = 100 connections, PostgreSQL `max_connections` = 100

```
New replica spins up
   ↓ Tries to initialize 20-connection pool
   ↓ PostgreSQL rejects: max_connections reached
   ↓ App crashes with "FATAL: too many connections"
   ↓ Docker restarts app (crash loop)
```

**Prevention**:
1. Monitor `docker compose ps` during scale-ups
2. If 4th or 5th replica fails to start, increase PostgreSQL `max_connections`:
   ```bash
   docker compose exec postgres psql -U postgres \
     -c "ALTER SYSTEM SET max_connections = 200; SELECT pg_reload_conf();"
   ```
3. Or increase pool `stale_timeout` to recycle idle connections faster

### Scenario 4: Redis Circuit Breaker Activation

**Trigger**: Redis OOMKill or network partition

```
T=0s: Redis becomes unavailable
     ↓ App calls `cache.get(key)` → timeout
     ↓ Circuit breaker opens (30s window)

T=1s: All cache calls return None immediately
     ↓ App falls back to DB for every read
     ↓ DB latency increases from ~10ms to ~40ms (no cache)
     ↓ Latency p95 jumps from 20ms → 60ms

T=30s: Circuit breaker resets
     ↓ Retries Redis
     ↓ If Redis still down, opens again
     ↓ If Redis recovered, cache refills

T=60s+: Cache warm again
     ↓ Latency p95 back to 20ms
```

**Outcome**:
- **Impact**: +30-40ms latency for 30s, zero 5xx errors
- **No data loss**: All reads fall through to DB
- **Automatic recovery**: No manual intervention needed

---

## Growth Roadmap

### Phase 1: Current (2-5 replicas, 482 req/s baseline)

**Targets**:
- Max throughput: ~800 req/s (5 replicas × 160 req/s each)
- Max latency p95: < 100ms
- Availability: 99.9%

**Action items**:
- Monitor autoscaler scaling patterns
- Watch database connection pool utilization
- Set up capacity alerts (CPU > 85% for 10+ minutes)

### Phase 2: Scaling to 1000+ req/s (Droplet Upgrade)

**When to trigger**: Traffic consistently at 800+ req/s

**Changes needed**:
```bash
# 1. Upgrade droplet: DigitalOcean 4 vCPU / 4 GB RAM
# 2. Increase resource limits in docker-compose.yml:
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '1.5'          # Was 0.75
          memory: 768M         # Was 384M
  postgres:
    deploy:
      resources:
        limits:
          memory: 2G           # Was 768M
  redis:
    deploy:
      resources:
        limits:
          memory: 512M         # Was 160M

# 3. Increase autoscaler limits:
autoscaler:
  environment:
    MIN_REPLICAS: 3            # Was 2
    MAX_REPLICAS: 10           # Was 5

# 4. Increase PostgreSQL settings:
postgres:
  command:
    - "-c"
    - "max_connections=300"    # Was 100
    - "-c"
    - "shared_buffers=512MB"   # Was 192MB
```

**Expected performance**:
- Max throughput: ~2000 req/s (10 replicas × 200 req/s)
- Max latency p95: < 50ms
- Memory headroom: 2 GB

### Phase 3: Multi-Server Setup (1000+ req/s, high availability)

**When to trigger**: Single droplet limits reached or HA required

**Architecture change**:
```
Load Balancer (Managed)
   ↓
  ┌─ DigitalOcean Droplet 1 (4 vCPU, 4 GB)
  │  └─ Docker Compose stack (app + monitoring)
  │
  └─ DigitalOcean Droplet 2 (4 vCPU, 4 GB)
     └─ Docker Compose stack (app + monitoring)

Shared:
  - PostgreSQL (managed database or dedicated VM)
  - Redis (managed or dedicated VM)
  - Prometheus (aggregate metrics)
```

**Benefits**:
- No single point of failure (if one droplet dies, traffic routes to other)
- Each droplet handles ~5 replicas × 8 threads = 1000 req/s
- Total capacity: 2000+ req/s across both droplets

**Downside**: Operational complexity increases, requires load balancer setup

---

## Performance Tuning Checklist

### Quick Wins (No Code Changes)

- [ ] **Redis maxmemory**: Increase from 128 MB to 256 MB (if eviction thrashing)
- [ ] **PostgreSQL shared_buffers**: Increase from 192 MB to 384 MB (if high DB latency)
- [ ] **Gunicorn worker count**: Increase from 2 to 3 per replica (test in staging first)
- [ ] **App replica count**: Pre-scale to 3 during known peaks (Black Friday)
- [ ] **Nginx worker_connections**: Increase from default to handle more concurrent clients

### Medium-Effort Improvements

- [ ] **Query optimization**: Run `EXPLAIN ANALYZE` on slow queries, add missing indexes
- [ ] **Connection pool tuning**: Increase `stale_timeout` to 600s if many idle connections
- [ ] **Cache invalidation**: Batch invalidations if cache.delete_pattern is called frequently
- [ ] **Event logging**: Consider batching event writes (currently 1 INSERT per redirect)

### High-Impact Changes

- [ ] **Read replicas**: Set up PostgreSQL read replicas for analytics queries (GET /events)
- [ ] **CDN**: Add CloudFlare or similar for static content + DDoS protection
- [ ] **Database sharding**: If URL table > 10 million rows, shard by user_id or short_code
- [ ] **Asynchronous workers**: Use Celery for heavy tasks (email notifications, bulk imports)

---

## Monitoring & Alerting

### Key Metrics to Watch

**Resource Utilization:**

```
CPU Usage:
  - Baseline (100 req/s): 15-20%
  - Heavy load (500 req/s): 65-75%
  - Critical (≥ 85%): Page on-call

Memory Usage (per replica):
  - Baseline: 180 MB
  - Heavy load: 350 MB
  - OOMKill risk (> 384 MB): Automatic restart by Docker

Database Connections:
  - Baseline: 8/40
  - Heavy load: 28-35/40
  - Pool exhaustion risk (≥ 38/40): Scale up or increase pool size

Redis Memory:
  - Baseline: 15 MB
  - Heavy load: 38-40 MB
  - Eviction thrashing (rapid evictions_total increase): Increase maxmemory
```

**Application Metrics:**

```
Request Latency (p95):
  - Target: < 50ms
  - Warning: 50-100ms
  - Critical: > 100ms

Error Rate:
  - Target: < 0.1%
  - Warning: 0.1-1%
  - Critical: > 1%

Cache Hit Rate:
  - Target: > 80% for redirect lookups
  - Low hit rate (< 50%): Check if URLs are diverse or stale data
```

### Recommended Alerts

All configured in [`monitoring/prometheus/alerts.yml`](../monitoring/prometheus/alerts.yml):

| Alert | Condition | Action |
|-------|-----------|--------|
| `ServiceDown` | `up == 0` for 1m | Page on-call, check if app crashed |
| `HighErrorRate` | 5xx rate > 5% for 30s | Check error logs, rollback if recent deploy |
| `HighLatency` | p95 > 500ms for 30s | Check CPU/memory, scale if needed |
| `HighReplicaCount` | replicas > 3 for 10s | Investigate traffic spike, possible DDoS |
| `HighMemoryUsage` | RSS > 350 MB for 5m | Check for memory leak, restart app |
| `RedisDown` | Redis connection errors | Check Redis health, check circuit breaker logs |

---

## SLO & Budget

### Service Level Objectives

| Objective | Target | Tolerance |
|-----------|--------|-----------|
| **Availability** | 99.9% | 43 minutes downtime/month |
| **Latency p95** | 50ms | Sustained > 100ms = SLO violation |
| **Error rate** | < 0.1% | Sustained > 1% = SLO violation |

### Error Budget

At 99.9% availability (43 minutes/month):

- If a major incident causes 10 minutes of downtime, 33 minutes remain for the month
- If another outage happens, SLO is violated
- Better to do planned maintenance during low-traffic windows

---

## Related Documentation

- **Scaling**: [`docs/Scalability/README.md`](Scalability/README.md)
- **Deployment**: [`docs/DEPLOYMENT.md`](DEPLOYMENT.md)
- **Architecture**: [`docs/ARCHITECTURE.md`](ARCHITECTURE.md)
- **Incident Response**: [`docs/Incident Response/runbooks/INCIDENT-PLAYBOOK.md`](Incident%20Response/runbooks/INCIDENT-PLAYBOOK.md)
