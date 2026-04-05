---
layout: default
title: Scalability Engineering
permalink: /scalability/
---

# Scalability Track Submission

## Application Overview

MLH PE URL Shortener is a production-grade URL shortener API built on Flask + Gunicorn, backed by PostgreSQL and Redis, fronted by Nginx, and orchestrated with Docker Compose. It supports user management, URL CRUD, redirect resolution, and full event logging — designed to scale horizontally under concurrent load with automated replica management, shared caching, and a complete observability stack.

## Architecture Diagram

![Architecture Diagram](assets/URL_Shortner_Architecture.svg)

### Component Descriptions

| Component | Role | Config Location |
|-----------|------|-----------------|
| **User/Client** | Sends HTTP/HTTPS requests to the Nginx entry point | — |
| **Nginx** | TLS termination, least-connections load balancing, rate limiting (2000 req/s/IP), gzip, proxy retries, security headers | [nginx/nginx.conf](../../nginx/nginx.conf) |
| **App replicas (Flask + Gunicorn)** | 2–5 auto-scaled containers, each running 2 Gunicorn workers × 4 threads (`gthread`) | [gunicorn.conf.py](../../gunicorn.conf.py) |
| **Auto-scaling monitor** | Python + Docker SDK daemon; polls CPU every 10 s; scales replicas between 2 and 5 based on sustained CPU load | [autoscaler/scaler.py](../../autoscaler/scaler.py) |
| **PostgreSQL 16** | Primary datastore; tuned with `shared_buffers=192MB`, `work_mem=8MB`, `synchronous_commit=off`; 20-connection Peewee pool per replica | [app/database.py](../../app/database.py), [app/__init__.py](../../app/__init__.py) |
| **Shared LFU Cache (Redis 7)** | Cache-aside layer with circuit breaker; `allkeys-lfu` eviction; no TTL; 128 MB cap; persistence disabled for pure speed | [app/utils/cache.py](../../app/utils/cache.py), [docker-compose.yml](../../docker-compose.yml) |
| **Observability stack** | Prometheus (15 s scrape), Grafana (8-panel dashboard), Loki + Promtail (log aggregation, 72 h retention), Jaeger (OTLP traces) | [docker-compose.yml](../../docker-compose.yml), [monitoring/](../../monitoring/) |
| **Alert destinations** | Alertmanager routes by severity to SMTP email and Discord webhooks | [monitoring/alertmanager/](../../monitoring/alertmanager/) |

All services share a single Docker Compose network; no port is exposed to the host except Nginx (80/443) and the monitoring UIs.

---

## Requirements Mapping

### Tier 1 (Bronze) — Baseline

**Concurrency handling — Nginx front door**

Nginx is configured with `worker_processes auto` (scales with CPU cores) and `keepalive_timeout 65`. Every inbound request passes through a rate-limit zone (`limit_req_zone` of 10 MB, 2000 req/s per IP, burst 200). Proxy buffers (`proxy_buffers 4 16k`) absorb spiky responses. On upstream errors (502, 503), Nginx retries the next healthy replica automatically.

Relevant config: [nginx/nginx.conf](../../nginx/nginx.conf)

**App throughput — Gunicorn gthread workers**

Each replica runs Gunicorn with:
- `workers = 2` processes
- `threads = 4` per worker → **8 concurrent request slots per replica**
- `worker_class = "gthread"` (I/O-friendly threaded model)
- `max_requests = 10000` with `max_requests_jitter = 1000` (gradual worker recycling to prevent memory leaks)
- `timeout = 30`, `graceful_timeout = 30` (clean in-flight shutdown)

`preload_app = True` shares app memory across workers before fork; each worker re-initialises its own DB pool connection in `post_fork()` to avoid shared-socket corruption.

Relevant config: [gunicorn.conf.py](../../gunicorn.conf.py)

**DB stability under load — Peewee connection pool**

`PooledPostgresqlDatabase` maintains up to **20 pooled connections** per app container, with `stale_timeout=300` (reconnects idle connections after 5 min) and a `timeout=10` for acquisition. Connections are claimed at the start of each request (skipped for `/health`) and returned to the pool in `teardown_appcontext`, keeping the pool fully utilised across the 4-thread workers.

Relevant config: [app/database.py](../../app/database.py)

**Early bottleneck visibility — per-request checkpoint timings**

`app/middleware.py` injects a `checkpoint(name)` helper into every request context. Named checkpoints (`middleware`, `cache_get`, `db_read`, `cache_set`, `serialize`, `after_request`) record elapsed milliseconds since the previous checkpoint. The full breakdown is emitted as structured JSON at the end of every request and attached to the `X-Request-ID` response header.

Example log line:
```json
{
  "request_id": "abc123",
  "method": "GET",
  "path": "/urls/42",
  "status": 200,
  "latency_ms": 12.45,
  "timings": { "middleware": 0.5, "cache_get": 2.1, "db_read": 8.5, "cache_set": 1.2, "serialize": 0.15 }
}
```

Relevant config: [app/middleware.py](../../app/middleware.py)

---

### Tier 2 (Silver) — Scale-Out

**2+ app instances**

Docker Compose starts **2 replicas** by default (`deploy.replicas: 2` in [docker-compose.yml](../../docker-compose.yml)). Each replica is CPU-capped at 0.75 cores and memory-limited to 384 MB. The `init-db` service runs a one-time migration before any replica starts, and replicas only become healthy once `/health/ready` (which checks DB connectivity) returns 200.

**Least-connections load balancing**

Nginx upstream block:
```nginx
upstream app {
    least_conn;
    server app:5000 max_fails=3 fail_timeout=5s;
    keepalive 64;
}
```
`least_conn` routes each new request to the replica with the fewest active connections, keeping load evenly distributed during bursts. `max_fails=3` with `fail_timeout=5s` temporarily marks an unhealthy replica out of rotation; Nginx automatically retries on the next available backend.

Relevant config: [nginx/nginx.conf](../../nginx/nginx.conf)

**Horizontal scale control — CPU-based autoscaler**

`autoscaler/scaler.py` runs as a sidecar container with access to the Docker socket. Every **10 seconds** it:

1. Enumerates all `app` containers using Compose labels.
2. Computes per-container CPU % relative to the container's CPU limit:
   ```
   cpu_pct = (cpu_delta / system_delta) × num_cpus / CPU_LIMIT_CORES × 100
   ```
3. Averages CPU across all replicas.
4. Applies streak logic:
   - **Scale-up**: avg CPU ≥ 70 % for **2 consecutive polls** (≈ 20 s) → add one replica (max 5)
   - **Scale-down**: avg CPU ≤ 30 % for **6 consecutive polls** (≈ 60 s) → remove one replica (min 2)
5. Enforces cooldown timers: **60 s** after a scale-up, **120 s** after a scale-down (prevents flapping).
6. After each scaling action, sends `SIGHUP` to the Nginx container to reload upstream configuration.

New replicas are created by cloning the reference container's full config (environment, volumes, network aliases), so they are indistinguishable from the original replicas.

Relevant config: [autoscaler/scaler.py](../../autoscaler/scaler.py)

---

### Tier 3 (Gold) — Caching and Optimisation

**Redis shared cache — cache-aside with circuit breaker**

All replicas share a single Redis 7 instance (`allkeys-lfu`, 128 MB cap, no TTL). Cache logic lives in [app/utils/cache.py](../../app/utils/cache.py) and is applied to the two hottest read paths:

| Cache key | TTL | Used in |
|-----------|-----|---------|
| `url:{id}` | 300 s | `GET /urls/{url_id}` |
| `redir:{short_code}` | 300 s | `GET /urls/{short_code}/redirect` |

Write/delete operations (PUT, DELETE) invalidate both keys atomically via `cache_delete_pattern`.

**Circuit breaker** — if any Redis call raises an exception, the breaker opens for **30 seconds**. During that window all cache calls return `None` immediately (no Redis I/O), and the app falls back transparently to PostgreSQL. After 30 s the breaker resets and retries. This prevents cascading latency when Redis is temporarily unavailable.

Redis is configured with `save ""` and `--appendonly no`, disabling all persistence to maximise throughput; data is purely ephemeral.

Relevant config: [app/utils/cache.py](../../app/utils/cache.py), [docker-compose.yml](../../docker-compose.yml)

**DB and query optimisations**

Runtime indexes are created in `app/__init__.py` using `safe=True` (no-op if already present):

| Index | Columns | Purpose |
|-------|---------|---------|
| `urls_user_id` | `urls(user_id)` | Filter URLs by owner |
| `urls_short_code` | `urls(short_code)` | Redirect lookups |
| `urls_is_active` | `urls(is_active)` | Active-URL filters |
| `urls_user_id_is_active` | `urls(user_id, is_active)` | Compound owner + active filter |
| `events_url_id` | `events(url_id)` | Event history per URL |
| `events_user_id` | `events(user_id)` | Event history per user |
| `events_event_type` | `events(event_type)` | Filter by event type |
| `events_timestamp` | `events(timestamp DESC)` | Recency sort |
| `events_url_event` | `events(url_id, event_type)` | Compound event queries |

PostgreSQL itself is tuned with:
- `shared_buffers=192MB` — ~40 % of allocated memory in shared cache
- `work_mem=8MB` — per-sort/hash memory for complex queries
- `effective_cache_size=384MB` — planner hint for index vs seq-scan decisions
- `synchronous_commit=off` — async WAL flush (safe for non-critical event writes; durability risk only on hard crash)

Relevant config: [app/__init__.py](../../app/__init__.py), [app/database.py](../../app/database.py)

**Bottleneck analysis tooling**

Prometheus metrics are exported at `/metrics` (via `prometheus_flask_exporter`) and scraped every 15 seconds. Latency distributions (`flask_http_request_duration_seconds`) feed directly into the Grafana dashboard and the `HighLatency` alert rule (p95 > 500 ms for 30 s fires a warning). Per-checkpoint timings in middleware logs are shipped to Loki via Promtail and are queryable in Grafana alongside the metrics panels.

Relevant config: [app/__init__.py](../../app/__init__.py), [app/middleware.py](../../app/middleware.py), [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)

---

## Architectural Decisions

### Load Balancing — Least Connections over Round Robin

> **Config:** `least_conn` in [nginx/nginx.conf](../../nginx/nginx.conf)

| Strategy | Behaviour | Effect at scale |
|----------|-----------|-----------------|
| Round Robin | Distributes requests evenly by count | Ignores actual load per replica |
| **Least Connections** | Routes to the replica with fewest active connections | Naturally adapts to imbalanced load |

When the autoscaler adds a new replica mid-traffic, that replica starts with **zero active connections** while existing replicas are already handling live requests. Round robin would distribute new requests evenly by count, still sending a proportional share to overloaded replicas. Least connections routes aggressively to the new replica until it catches up, then naturally rebalances — no manual weight adjustment needed.

---

### Caching — LFU Eviction Without TTL

> **Config:** `allkeys-lfu`, `--lfu-decay-time 1`, `--lfu-log-factor 10` in [docker-compose.yml](../../docker-compose.yml) · TTL removed from [app/utils/cache.py](../../app/utils/cache.py)

The goal is to keep the **hottest URLs in cache at all times** and let Redis decide what to evict — not a fixed expiry clock.

| Approach | What stays in cache | Problem |
|----------|-------------------|---------|
| TTL-based | Everything, for a fixed window | Hot URLs expire and cause thundering herd problem, stressing the DB. |
| LRU eviction | Most recently accessed | A one-off hit on a cold URL can displace a URL accessed 1000× |
| **LFU eviction** | Most frequently accessed over time | One-off hits decay and are evicted; viral URLs stay cached indefinitely |

Two parameters control the behaviour:

| Parameter | Value | Effect |
|-----------|-------|--------|
| `lfu-log-factor` | `10` | Counter saturates at ~1 M hits — gives good resolution across the full URL popularity range |
| `lfu-decay-time` | `1` min | Counter decays every minute for keys that stop being accessed, so yesterday's viral URL eventually becomes evictable |

**Why no TTL?** With a TTL, even the most-accessed URLs expire on a fixed clock and force a DB read every 5 minutes regardless of traffic, thus causing a thundering herd problem, and spiking DB CPU usage. Without a TTL, a URL accumulates frequency score continuously and is only displaced when Redis hits its 128 MB memory cap and something less popular must go. Cache utility is maximised per byte.

**Correctness without TTL relies entirely on explicit invalidation.** Since stale entries no longer self-expire, every write path must evict the relevant keys immediately:

| Operation | Keys invalidated |
|-----------|-----------------|
| `PUT /urls/{url_id}` | `url:{id}` + `redir:{short_code}` |
| `DELETE /urls/{url_id}` | `url:{id}` + `redir:{short_code}` |
| `POST /urls` | None — new key, no prior entry |

---

### Database Indexes — Columns, Rationale, and Write Trade-offs

> **Config:** [app/__init__.py](../../app/__init__.py)

#### Index decisions

| Index | Table | Columns | Query it serves |
|-------|-------|---------|-----------------|
| `urls_short_code` | urls | `short_code` | Redirect lookup — hottest read path |
| `urls_user_id` | urls | `user_id` | List all URLs for a user |
| `urls_is_active` | urls | `is_active` | Filter active-only URLs |
| `urls_user_id_is_active` | urls | `(user_id, is_active)` | List active URLs for a user (compound avoids two index scans) |
| `events_url_id` | events | `url_id` | Fetch event history for a URL |
| `events_user_id` | events | `user_id` | Fetch event history for a user |
| `events_event_type` | events | `event_type` | Filter by action type (e.g. all redirects) |
| `events_timestamp` | events | `timestamp DESC` | Recency-sorted event queries |
| `events_url_event` | events | `(url_id, event_type)` | History for a URL filtered by type |

#### The write trade-off

Every index improves reads but adds overhead to **every INSERT and UPDATE** on that table — PostgreSQL must update the index structure in addition to the heap row. For the `urls` table (low write volume — users create/update URLs infrequently) this overhead is negligible. For the `events` table the picture is different: every redirect logs an event, so `events` is the highest write-volume table in the system.

The decision to index `events` was made deliberately:

- **Redirect events** are written via the async fire-and-forget `event_writer.py` (see below), so the index update cost does not appear on the request's critical path.
- The queries they serve (audit history, analytics) are infrequent but expensive without an index on a large table.
- `synchronous_commit=off` (see below) further amortises the WAL cost of these index updates.

This means we accepted a moderate background write amplification in exchange for fast analytical reads, with the async writer and async commit ensuring that amplification is invisible to end-users.

---

### PostgreSQL — `synchronous_commit = off`

> **Config:** `command` flags in [docker-compose.yml](../../docker-compose.yml)

By default, PostgreSQL holds a write acknowledgement until the WAL (Write-Ahead Log) has been **flushed to disk**. This guarantees no data loss on crash but adds disk-sync latency (~1–10 ms per write) to every INSERT and UPDATE.

With `synchronous_commit=off`, PostgreSQL acknowledges the write to the client as soon as it is written to the **in-memory WAL buffer** — the actual disk flush happens asynchronously a few milliseconds later.

| | `synchronous_commit=on` | `synchronous_commit=off` |
|---|---|---|
| **Write latency** | Higher (waits for disk fsync) | Lower (returns on buffer write) |
| **Crash risk** | Zero data loss | Up to ~200 ms of committed writes may be lost |
| **Data corruption** | Never | Never (WAL ensures consistency; only the last ~200 ms window is at risk) |

For this application the trade-off is acceptable:
- **URL records** (create/update) — losing a creation in a crash means the user retries; no corruption or inconsistency.
- **Event records** (redirect logs, analytics) — these are append-only analytics. Losing a handful of redirect events in a crash has no impact on correctness.

---

### Non-Blocking Event Logging — Async Fire-and-Forget

> **Config:** [app/event_writer.py](../../app/event_writer.py)

Every redirect and URL mutation logs an event to the `events` table. A naive synchronous implementation would add the full DB INSERT latency to every request's response time.

`event_writer.py` avoids this with a **`ThreadPoolExecutor(max_workers=2)`**:

```
Request handler
  │
  ├─ cache/DB lookup   ← on critical path
  ├─ build response    ← on critical path
  ├─ _executor.submit(write_event)   ← queued, returns immediately
  └─ return HTTP response
         │
         └─ background thread: Event.create(...)   ← off critical path
```

`log_event()` returns as soon as the task is submitted to the pool. The actual `Event.create()` INSERT runs in a background thread with its own DB connection, completely decoupled from the response. If the write fails, it is logged but the response is unaffected — event logging is explicitly not a reliability boundary.

The pool size of 2 workers is intentional: event writes are fast (single INSERT), so 2 threads are sufficient to drain the queue without over-provisioning threads that compete for DB connections.

---

### Autoscaler — Asymmetric Cooldowns (60 s up / 120 s down)

> **Config:** [autoscaler/scaler.py](../../autoscaler/scaler.py)

After any scaling action the autoscaler enters a cooldown period before it is allowed to scale in the same direction again. Scale-up and scale-down use **different cooldown durations deliberately**:

| Direction | Cooldown | Reasoning |
|-----------|----------|-----------|
| **Scale-up** | 60 s | Under-provisioning has immediate, user-visible consequences (latency spikes, 503s). Act fast. |
| **Scale-down** | 120 s | Premature scale-down during a brief traffic lull forces an immediate scale-up, wasting a cold-start cycle. |

The asymmetry reflects the **cost asymmetry of errors**:
- An extra idle replica costs a fixed amount of memory/CPU.
- A missing replica under load costs user-facing latency and potentially dropped requests.

The longer scale-down cooldown also accounts for the fact that a new replica added 60 seconds ago is still warming up its connection pool and hasn't yet appeared in Prometheus metrics with stable CPU readings. Scaling it down immediately would waste the cold-start cost entirely.

---

## Beyond the Rubric

### Full Observability Stack

Five additional services provisioned in [docker-compose.yml](../../docker-compose.yml):

| Service | Port | Purpose |
|---------|------|---------|
| **Prometheus** | 9090 | Metrics scraping, 15 s interval, 72 h retention |
| **Grafana** | 3000 | 8-panel dashboard: uptime, active alerts, request rate, error rate, p95 latency, memory, CPU, live logs |
| **Loki** | 3100 | Log aggregation backend, 72 h retention |
| **Promtail** | — | Docker log scraper; ships container stdout/stderr to Loki |
| **Jaeger** | 16686 | Distributed trace UI (OTLP gRPC receiver on 4317) |

**Grafana dashboard panels (4 golden signals + extras):**
1. Service uptime (availability %)
2. Active firing alerts
3. Request rate (req/s)
4. Error rate (5xx %)
5. p95 latency (ms)
6. Memory usage (RSS MB)
7. CPU utilisation (%)
8. Live log stream (Loki)

Datasources are auto-provisioned from [monitoring/grafana/provisioning/datasources/](../../monitoring/grafana/provisioning/datasources/); dashboards are auto-imported from [monitoring/grafana/dashboards/](../../monitoring/grafana/dashboards/).

### Prometheus Alert Rules

Six alert rules in [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml):

| Alert | Condition | Severity | Fire Time |
|-------|-----------|----------|-----------|
| `ServiceDown` | `up == 0` for 1 m | critical | ~70 s |
| `HighErrorRate` | 5xx rate > 5 % for 30 s | warning | ~45 s |
| `HighLatency` | p95 > 500 ms for 30 s | warning | ~45 s |
| `RedisDown` | redis connection errors > 0 for 1 m | warning | ~70 s |
| `HighReplicaCount` | replica count > 3 for 10 s | warning | ~10 s |
| `HighRequestRate` | total rate > 400 req/s for 30 s | warning | ~45 s |

### Alertmanager Routing

Critical alerts (e.g. `ServiceDown`) are dispatched with **0 s group wait** and repeat every 15 minutes until resolved. Warning alerts batch with a 10 s group wait and repeat every 1 hour. Both severity tiers can route to SMTP email (Resend) and Discord webhooks, configured in [monitoring/alertmanager/alertmanager.yml](../../monitoring/alertmanager/alertmanager.yml) and [monitoring/alertmanager/discord-receivers.yml](../../monitoring/alertmanager/discord-receivers.yml).

### OpenTelemetry Distributed Tracing

[app/tracing.py](../../app/tracing.py) instruments Flask with `FlaskInstrumentor` and exports spans via OTLP gRPC to Jaeger. If the Jaeger endpoint is unreachable (e.g. `OTEL_EXPORTER_OTLP_ENDPOINT` unset), the app starts normally without tracing — no startup failures.

### TLS Termination

A `cert-gen` init container generates a self-signed certificate (`server.crt` / `server.key`) at startup. Nginx serves HTTPS on port 443 with TLS 1.2 + 1.3, a curated cipher suite (`HIGH:!aNULL:!MD5`), HTTP/2, HSTS (`max-age=31536000`), and a 10-minute session cache. HTTP on port 80 is served in parallel for local development.

### Structured Request Logging

Every request is tagged with a UUID `X-Request-ID` (honoured if provided by the client) and logged as a single JSON line with full checkpoint timing breakdown. Logs are collected by Promtail and queryable in Grafana/Loki without SSH access to any container.

### Nginx Security Hardening

Beyond load balancing, Nginx enforces:
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy` denying geolocation, camera, and microphone
- `/nginx-status` restricted to Docker private subnets only (`172.16.0.0/12`)

---