# Load Test Results

> Tested on Apr 4, 2026 — Docker Compose stack with 3 Gunicorn replicas behind Nginx (`least_conn`), PostgreSQL 16

---

## Test Scripts

| Script | File | VUs | Duration | Description |
|---|---|---|---|---|
| k6 Test 1 | `loadtests/k6_test.js` | 50 / 200 / 500 (tiered) | 30s–2m | Read-heavy: health, list users, list urls, create user |
| k6 Test 2 — Smoke | `loadtests/k6_test2_smoke.js` | 50 | 30s | Full CRUD: health, list users, create url, get url |
| k6 Test 2 — Breakpoint | `loadtests/k6_test2_breakpoint.js` | 0→1000 | 3m10s | Ramp to 1000 VUs: create url, get url |

---

## Results

### 50 VU Smoke (30s)

| Metric | Value |
|---|---|
| **p95 Latency** | 17.18ms |
| **p90 Latency** | 15.09ms |
| **Avg Latency** | 9.09ms |
| **Median Latency** | 8.50ms |
| **Max Latency** | 38.85ms |
| **Error Rate** | 0.00% |
| **Total Requests** | 18,020 |
| **Throughput** | 593 req/s |
| **Iterations** | 4,500 |
| **Checks Passed** | 100.00% |
| **Data Received** | 11 MB (367 kB/s) |

**All thresholds passed.**

### 1000 VU Breakpoint (3m10s)

| Metric | Value |
|---|---|
| **p95 Latency** | 162.53ms |
| **p90 Latency** | 121.97ms |
| **Avg Latency** | 48.75ms |
| **Median Latency** | 31.88ms |
| **Max Latency** | 538.62ms |
| **Error Rate** | 0.00% |
| **Total Requests** | 1,050,659 |
| **Throughput** | 5,524 req/s |
| **Iterations** | 350,203 |
| **Checks Passed** | 100.00% |
| **Data Received** | 336 MB (1.8 MB/s) |

**All thresholds passed.**

---

## Key Optimizations

1. **Atomic short_code generation** — Each URL gets a unique UUID placeholder inside a `db.atomic()` transaction, eliminating race conditions under concurrent writes.

2. **Connection pooling** — `PooledPostgresqlDatabase` with `max_connections=8` per worker, plus `close_all()` after Gunicorn fork to prevent stale connections.

3. **Database indexes** — Indexes on `urls.user_id`, `urls.is_active`, `events.url_id`, `events.user_id`, `events.event_type` for faster filtered queries.

4. **Nginx `least_conn` load balancing** — Routes traffic to the replica with the fewest active connections instead of round-robin.

5. **Batch inserts for bulk operations** — `insert_many` with 100-row batches for CSV imports.

6. **Hybrid async/sync event logging** — Synchronous writes for create/update (immediate consistency), fire-and-forget via `ThreadPoolExecutor` for redirects (latency-sensitive path).

---

## Infrastructure

| Component | Config |
|---|---|
| App | Flask + Gunicorn (4 workers per replica) |
| Replicas | 3 (`docker-compose.yml` deploy.replicas) |
| Load Balancer | Nginx (`least_conn`) |
| Database | PostgreSQL 16 Alpine |
| Connection Pool | `PooledPostgresqlDatabase`, 8 max per worker |
