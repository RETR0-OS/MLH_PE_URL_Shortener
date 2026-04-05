---
layout: default
title: System Architecture
permalink: /architecture
---

# System Architecture

Complete overview of the URL Shortener system design, from load balancing through data persistence.

---

## Architecture Diagram

```
                            ┌─────────────────────┐
                            │   Client / User     │
                            └────────────┬────────┘
                                         │ HTTP/HTTPS
                                         ▼
                     ┌───────────────────────────────────┐
                     │       Nginx (Port 80/443)         │
                     │  - Rate limiting (2000 req/s)     │
                     │  - TLS termination                │
                     │  - Least-conn load balancing      │
                     │  - Gzip compression               │
                     │  - Proxy retry on 502/503         │
                     └────────────────┬────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
         ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
         │   App Replica   │ │   App Replica   │ │ App Replica...  │
         │  (Flask/Guni)   │ │  (Flask/Guni)   │ │  (auto-scaled)  │
         │  2-4 threads    │ │  2-4 threads    │ │  min 2, max 5   │
         └────┬────────┬───┘ └────┬────────┬───┘ └────┬────────┬───┘
              │        │          │        │          │        │
              ▼        ▼          ▼        ▼          ▼        ▼
         ┌──────────────────────────────────────────────────────┐
         │         Shared Cache Layer (Redis 7)                 │
         │  - LFU eviction (128 MB cap)                         │
         │  - No TTL (relies on explicit invalidation)          │
         │  - Circuit breaker (30s fallback to DB)              │
         │  - Persistence disabled (pure speed)                 │
         └──────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┴────────────────────┐
         ▼                                          ▼
    ┌─────────────────────┐              ┌─────────────────────┐
    │  PostgreSQL 16      │              │   Event Writer      │
    │  (Source of Truth)  │              │  (Async Thread Pool)│
    │  - 20-conn pool     │              │  - 2 worker threads │
    │  - Tuned settings   │              │  - Fire-and-forget  │
    │  - 9 indexes        │              │  - Doesn't block    │
    └─────────────────────┘              │    response path    │
                                         └─────────────────────┘

         Observability Layer (runs in parallel)
         ─────────────────────────────────────────

    ┌──────────────┐  ┌────────────────┐  ┌──────────────┐
    │ Prometheus   │  │ Promtail       │  │ Jaeger OTLP  │
    │ (Metrics)    │  │ (Log Shipper)  │  │ (Traces)     │
    │ 15s scrape   │  │ Docker socket  │  │ gRPC 4317    │
    │ 72h retention│  │ → Loki         │  │              │
    └──────────────┘  └────────────────┘  └──────────────┘
         │                    │                   │
         ▼                    ▼                   ▼
    ┌──────────────────────────────────────────────────────┐
    │              Loki (Log Aggregation)                   │
    │  - 72h retention                                      │
    │  - Full-text indexing by label + stream              │
    └──────────────────────────────────────────────────────┘
         │
         └─────────────────────┬──────────────────────┐
                               ▼                      ▼
                           ┌────────────┐       ┌──────────────┐
                           │  Grafana   │       │ Alertmanager │
                           │ Dashboards │       │ (Routing)    │
                           │ 4 GS + 8   │       │ → Email      │
                           │  panels    │       │ → Discord    │
                           └────────────┘       └──────────────┘
```

---

## Component Details

### Load Balancer — Nginx

**Role**: HTTP/HTTPS entry point, rate limiting, load distribution

| Aspect | Config |
|--------|--------|
| **Worker processes** | `auto` (scales with CPU cores) |
| **Load balancing** | Least connections (`least_conn`) |
| **Rate limiting** | 2000 req/s per IP, burst 200 |
| **TLS protocols** | TLSv1.2 + TLSv1.3 |
| **Compression** | Gzip (text payloads) |
| **Timeouts** | 5s connect, 30s read, 10s send |
| **Health check** | Max 3 failures in 5s before marking unhealthy |
| **Retry strategy** | Auto-retry on 502/503 to next healthy backend |
| **Keep-alive** | 64 upstream connections, 65s timeout |

**File**: [`nginx/nginx.conf`](../nginx/nginx.conf)

### App Replicas — Flask + Gunicorn

**Role**: Handle business logic, validate input, fetch/cache data

| Aspect | Config |
|--------|--------|
| **Framework** | Flask 3.0 |
| **WSGI Server** | Gunicorn (gthread) |
| **Worker processes** | 2 per replica |
| **Threads per worker** | 4 |
| **Total concurrency** | 8 concurrent request slots per replica |
| **Worker recycling** | Max 10,000 requests (+ jitter) before restart |
| **Graceful shutdown** | 30s timeout for in-flight requests |
| **Health check** | `/health` (liveness), `/health/ready` (DB connectivity) |
| **Request instrumentation** | UUID `X-Request-ID`, JSON structured logs, checkpoint timings |

**Files**: [`gunicorn.conf.py`](../gunicorn.conf.py), [`app/__init__.py`](../app/__init__.py)

### Auto-Scaler — Docker Compose Sidecar

**Role**: Monitor CPU, scale replicas up/down based on load

| Aspect | Config |
|--------|--------|
| **Poll interval** | 10 seconds |
| **Scale-up trigger** | CPU ≥ 70% for 2 consecutive polls (≈20s) |
| **Scale-down trigger** | CPU ≤ 30% for 6 consecutive polls (≈60s) |
| **Scale-up cooldown** | 60 seconds (act fast on overload) |
| **Scale-down cooldown** | 120 seconds (prevent flapping) |
| **Min replicas** | 2 (redundancy) |
| **Max replicas** | 5 (memory constraint) |
| **New replica strategy** | Clone reference container config (env, volumes, network) |
| **Nginx reload** | Send SIGHUP to Nginx after scaling to pick up new replicas |

**File**: [`autoscaler/scaler.py`](../autoscaler/scaler.py)

### Shared Cache — Redis 7

**Role**: Cache-aside layer for hot URL reads, user metadata

| Aspect | Config |
|--------|--------|
| **Memory limit** | 128 MB |
| **Eviction policy** | `allkeys-lfu` (keep most-frequently-accessed) |
| **LFU log factor** | 10 (counter resolution across popularity range) |
| **LFU decay time** | 1 minute (old accesses fade) |
| **Persistence** | Disabled (`save ""`, `--appendonly no`) |
| **Connection timeout** | 0.5s (fail-fast) |
| **Socket timeout** | 0.5s |
| **Health check interval** | 30 seconds |
| **Circuit breaker** | 30s reset window when unavailable |
| **Cache keys** | `url:{id}` (no TTL — relies on LFU eviction), `redir:{short_code}` (no TTL) |
| **Invalidation** | Explicit on PUT/DELETE via `cache_delete_pattern` |

**Files**: [`app/utils/cache.py`](../app/utils/cache.py), [`docker-compose.yml`](../docker-compose.yml)

### Database — PostgreSQL 16

**Role**: Authoritative data store for users, URLs, events

| Aspect | Config |
|--------|--------|
| **Connection pool** | 20 max per replica (40 total with 2 replicas) |
| **Stale timeout** | 300s (reconnect idle connections) |
| **Acquisition timeout** | 10s |
| **Shared buffers** | 192 MB (~40% of allocated RAM) |
| **Work memory** | 8 MB per sort/hash operation |
| **Effective cache size** | 384 MB (planner hint) |
| **Synchronous commit** | Off (faster WAL writes, ~200ms crash window) |
| **Indexes** | 9 indexes covering hot query paths |
| **Table statistics** | Auto-analyzed on size changes |

**Files**: [`app/database.py`](../app/database.py), [`app/__init__.py`](../app/__init__.py)

### Event Writer — Async Background Thread

**Role**: Log URL mutations and redirects without blocking the request path

| Aspect | Config |
|--------|--------|
| **Executor type** | ThreadPoolExecutor |
| **Worker threads** | 2 |
| **Task queuing** | Bounded queue (no limit specified, unbounded) |
| **Error handling** | Logged but doesn't fail the response |
| **Reliability boundary** | Non-critical — loss is acceptable |
| **Database connection** | Separate pool entry per thread |

**File**: [`app/event_writer.py`](../app/event_writer.py)

---

## Data Flow Examples

### User Creates a Shortened URL

```
1. POST /urls {original_url, user_id, title}
   ↓ [Nginx load balancer]
2. Flask app validates input (schema, business rules)
   ↓
3. Check cache for user → Redis hit/miss
   ↓
4. INSERT new URL record → PostgreSQL
   ↓ [Synchronous, on request path]
5. Invalidate cache keys (user:{id}, urls)
   ↓ [Redis cache.delete_pattern]
6. Respond with {id, short_code, ...} → 201 Created
   ↓ [Response sent to client]
7. Log event asynchronously → ThreadPoolExecutor
   ↓ [Off critical path, INSERT events table]
```

**Critical path**: Input validation → DB insert → Response (no cache hit for new data)
**Off-critical path**: Event logging (happens in background thread)

### User Redirects via Short Code

```
1. GET /{short_code}
   ↓ [Nginx load balancer]
2. Check cache for redir:{short_code} → Redis
   ↓ [Cache hit → 302 redirect, < 5ms]
   or [Cache miss → continue]
3. SELECT from urls WHERE short_code = ?
   ↓ PostgreSQL [via pooled connection]
4. Check is_active flag
   ↓
5. Cache result → Redis (set redir:{short_code})
   ↓
6. Respond 302 Location: <target_url>
   or 410 Gone (if deactivated)
   or 404 Not Found (if deleted)
   ↓ [Response sent to client]
7. Log redirect event asynchronously
```

**Critical path**: Cache lookup (or DB lookup) → Response (< 100ms typical)
**Off-critical path**: Event logging

---

## Request Lifecycle with Observability

Every request through the system is instrumented:

```
1. Request enters Nginx
   ↓ Rate limit check, TLS termination
   ↓ Access log emitted (JSON)

2. Nginx routes to Flask app
   ↓ X-Request-ID header propagated

3. Flask middleware intercepts
   ↓ Checkpoint: "middleware" (0.5ms elapsed)
   ↓ Structured log: {request_id, method, path}

4. App handler executes
   ├─ Checkpoint: "cache_get" (2.1ms)
   ├─ Checkpoint: "db_read" (8.5ms)
   ├─ Checkpoint: "cache_set" (1.2ms)
   └─ Checkpoint: "serialize" (0.15ms)

5. Response sent
   ├─ Total latency_ms: 12.45ms
   ├─ X-Request-ID response header
   ├─ Prometheus metric emitted:
   │  flask_http_request_duration_seconds_bucket{...}
   └─ JSON log emitted:
      {request_id, status, latency_ms, timings{}}

6. Loki collects the log
   ↓ Queryable in Grafana by job, level, request_id

7. Prometheus scrapes /metrics
   ↓ 15s interval, updates latency percentiles

8. If latency > 500ms (p95), alert rule triggers
   ├─ Grafana dashboard updates
   └─ Alertmanager notifies on-call
```

---

## Scaling Model

### Horizontal Scaling (More Replicas)

When CPU usage exceeds 70% for 20 seconds:

```
                    Autoscaler detects high CPU
                           ↓
                  Spins up a new replica
                           ↓
                  Clone config from reference
                    (env, volumes, network)
                           ↓
                    New replica pulls code
                           ↓
                    New replica warms up pool
                    (DB connections, caches)
                           ↓
                    New replica health checks
                           ↓
                    Nginx SIGHUP to reload
                           ↓
              New replica added to upstream
                           ↓
              Least-conn load balancer routes
              new connections to new replica
```

**Effect**: Request latency drops as load spreads across more workers.

### Vertical Scaling (Bigger Droplet)

If CPU limit is reached and more replicas don't help:

1. Upgrade droplet to more CPU cores
2. Increase `MAX_REPLICAS` threshold
3. Redeploy

---

## Caching Strategy

### LFU Eviction (No TTL)

**Why no TTL?**

With a fixed TTL (e.g., 5 minutes), even the most-accessed URL expires and forces a DB read every 5 minutes regardless of traffic. This causes a thundering herd and spikes DB CPU.

**Our approach**: Keep the hottest URLs indefinitely until Redis runs out of memory. When memory is full, evict the **least frequently used** keys. This maximizes cache utility per byte.

| Scenario | With TTL | Without TTL (LFU) |
|----------|----------|------------------|
| **Popular URL** (1000 hits/min) | Expires every 5 min, forces DB hit | Accumulates frequency score, stays cached |
| **One-off URL** (1 hit ever) | Takes up space, expires in 5 min | Decays and evicted when memory needed |
| **DB load at scale** | Periodic spikes every 5 min per URL | Smooth, only on cache misses |

**Implementation**: Every write (PUT, DELETE) explicitly invalidates both `url:{id}` and `redir:{short_code}` to maintain correctness.

---

## Failure Scenarios & Recovery

### Replica Crash

```
Docker container OOMKill or segfault
            ↓
Docker restart policy: unless-stopped
            ↓
Container restarts within 5 seconds
            ↓
New container re-initializes:
  - Connects to shared Redis
  - Initializes DB connection pool
  - Runs health checks
            ↓
Once healthy, Nginx marks it ready
            ↓
Least-conn load balancer routes traffic
```

**User impact**: Zero (second replica absorbs traffic)

### PostgreSQL Unavailable

```
App startup: depends_on {postgres: condition: service_healthy}
            ↓
Container waits for DB health check
            ↓
Once DB is reachable, app initializes
            ↓
/health/ready checks SELECT 1 on every poll
            ↓
If DB becomes unavailable:
  - /health → 200 (liveness still ok)
  - /health/ready → 503 (readiness fails)
  - Nginx marks replica unhealthy
  - Kubernetes/Docker can restart if desired
```

**User impact**: Request routes to healthy replica

### Redis Unavailable

```
Circuit breaker detects Redis timeout
            ↓
Opens circuit (blocks all Redis calls for 30s)
            ↓
App falls back to direct DB reads
            ↓
Response time increases (no cache hit)
            ↓
No 5xx errors (DB has answers)
            ↓
After 30s, circuit resets and retries
            ↓
Once Redis is back, cache refills on next read
```

**User impact**: Increased latency, zero errors

---

## Data Model

Three tables. All relationships are explicit foreign keys. Events are append-only (never updated or deleted).

```
users
  id          SERIAL PK
  username    TEXT UNIQUE NOT NULL
  email       TEXT UNIQUE NOT NULL
  created_at  TIMESTAMP DEFAULT NOW()

urls
  id          SERIAL PK
  user_id     INT FK → users.id
  short_code  TEXT UNIQUE NOT NULL    ← 6-char random alphanumeric
  original_url TEXT NOT NULL
  title       TEXT
  is_active   BOOLEAN DEFAULT TRUE
  created_at  TIMESTAMP DEFAULT NOW()
  updated_at  TIMESTAMP DEFAULT NOW()

events
  id          SERIAL PK
  url_id      INT FK → urls.id (nullable — user-level events have no URL)
  user_id     INT FK → users.id (nullable)
  event_type  TEXT NOT NULL    ← 'redirect' | 'created' | 'updated'
  timestamp   TIMESTAMP DEFAULT NOW()
  details     JSONB
```

**Indexes** (9 total, created at startup via `app/__init__.py`):

| Index | Table | Columns | Serves |
|-------|-------|---------|--------|
| `urls_short_code` | urls | `short_code` | Redirect lookups (hottest path) |
| `urls_user_id` | urls | `user_id` | List URLs by user |
| `urls_is_active` | urls | `is_active` | Active-only filter |
| `urls_user_id_is_active` | urls | `(user_id, is_active)` | Compound owner + active |
| `events_url_id` | events | `url_id` | Events per URL |
| `events_user_id` | events | `user_id` | Events per user |
| `events_event_type` | events | `event_type` | Filter by action type |
| `events_timestamp` | events | `timestamp DESC` | Recency sort |
| `events_url_event` | events | `(url_id, event_type)` | Compound event queries |

---

## Tech Stack Summary

| Layer | Technology | Why This Choice |
|-------|-----------|----------------|
| **Reverse Proxy** | Nginx 1.25 | Industry-standard; `least_conn` load balancing; proven rate limiting via `limit_req_zone`; zero-config upstream health checks. Chosen over HAProxy (less familiar) and Traefik (heavier, Kubernetes-oriented). |
| **Runtime** | Python 3.13 | Latest stable Python; `uv` makes dependency management fast and reproducible. Chosen over Node.js (team familiarity) and Go (faster startup but steeper learning curve for the team). |
| **Web Framework** | Flask 3.0 | Lightweight, no ORM baked in, easy to unit-test with `test_client()`. Chosen over FastAPI (async not needed for sync DB calls) and Django (too much convention for a simple API). |
| **WSGI Server** | Gunicorn 22.0 (gthread) | Threaded workers reuse DB connections; `gthread` avoids GIL contention on I/O-heavy paths. Chosen over `gevent` (greenlet complexity) and `uvicorn` (ASGI, not needed). |
| **ORM** | Peewee 3.19 | Thin abstraction with first-class connection pooling (`PooledPostgresqlDatabase`). Chosen over SQLAlchemy (heavier, more setup) and raw psycopg2 (more boilerplate). |
| **Database** | PostgreSQL 16 | ACID compliance, JSON support, `pg_stat_statements` for query analysis. Chosen over MySQL (fewer analytics features) and SQLite (no concurrent writes). |
| **Cache** | Redis 7 | Native `allkeys-lfu` eviction policy; sub-millisecond reads; single-threaded model avoids cache stampedes. Chosen over Memcached (no LFU, no persistence option) and in-process cache (not shared across replicas). |
| **Metrics** | Prometheus | Pull-based scraping works with Docker service discovery; PromQL is expressive for alert rules; native Grafana integration. Chosen over Datadog (cost) and InfluxDB (push model adds complexity). |
| **Dashboards** | Grafana 10 | Native Prometheus + Loki datasources; auto-provisioning via YAML files; free and self-hosted. Chosen over Kibana (Elasticsearch dependency) and Datadog (cost). |
| **Logs** | Loki + Promtail | Index-free design uses 10x less storage than Elasticsearch; Promtail Docker SD auto-discovers new replicas; native Grafana integration for side-by-side metrics + logs. |
| **Tracing** | Jaeger + OpenTelemetry | OpenTelemetry SDK is vendor-neutral; Jaeger is free and self-hosted; OTLP gRPC transport. Chosen over Zipkin (less feature-rich UI) and Datadog APM (cost). |
| **Alerting** | Alertmanager | Decoupled from Grafana (alerts fire even if Grafana is down); severity-based routing; built-in inhibition and grouping. Chosen over Grafana Alerting (couples alerting to visualization layer). |
| **Container** | Docker + Docker Compose | Single `docker-compose.yml` defines the entire stack; `start-first` rolling deploys; health check gates. Chosen over Kubernetes (operational overhead unjustified for single-server deployment). |
| **Package Manager** | uv | 10–100x faster than pip; lockfile-based reproducible installs; native Python 3.13 support. Chosen over Poetry (slower) and pip+venv (no lockfile). |
| **Testing** | pytest | Industry standard; rich fixture system; `pytest-cov` for coverage gates. |
| **Load Testing** | k6 | JavaScript scripting; native CI integration via GitHub Actions; built-in VU ramp profiles. Chosen over Locust (Python, but slower) and JMeter (XML config, no CI-native output). |
| **Linting** | ruff | Single tool replaces flake8 + isort + pyupgrade; 10–100x faster than pylint. |
| **CI/CD Platform** | GitHub Actions | Native to the repository; free for public repos; matrix builds, service containers, and secrets management built in. Chosen over CircleCI (cost) and Jenkins (self-hosted overhead). |
| **Hosting** | DigitalOcean Droplet | $12/month for 2 vCPU / 2 GB RAM; predictable pricing; fast SSH-based deploys. Chosen over AWS (complex pricing) and Heroku (no Docker Compose support). |

---

## Related Documentation

- **Decision Log**: [`docs/DECISION_LOG.md`](DECISION_LOG.md) — Full ADR log for all 19 technology choices with alternatives and trade-offs
- **Deployment**: [`docs/DEPLOYMENT.md`](DEPLOYMENT.md)
- **Configuration**: [`docs/config.md`](config.md)
- **Scalability**: [`docs/Scalability/README.md`](Scalability/README.md)
- **Reliability**: [`docs/Reliability/RELIABILITY_ENGINEERING.md`](Reliability/RELIABILITY_ENGINEERING.md)
- **Incident Response**: [`docs/Incident Response/`](Incident%20Response/)
