# Load Test Results

> Tested on Apr 4, 2026 — Docker Compose stack with Gunicorn replicas behind Nginx (`least_conn`), PostgreSQL 16

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

| Metric | Static (3 replicas) | Autoscale (2→5 replicas) |
|---|---|---|
| **p95 Latency** | 17.18ms | 13.65ms |
| **p90 Latency** | 15.09ms | 11.44ms |
| **Avg Latency** | 9.09ms | 6.60ms |
| **Median Latency** | 8.50ms | 5.90ms |
| **Max Latency** | 38.85ms | 89.65ms |
| **Error Rate** | 0.00% | 0.00% |
| **Total Requests** | 18,020 | 18,420 |
| **Throughput** | 593 req/s | 612 req/s |
| **Iterations** | 4,500 | 4,600 |
| **Checks Passed** | 100.00% | 100.00% |

**All thresholds passed.**

### 1000 VU Breakpoint (3m10s)

| Metric | Static (3 replicas) | Autoscale (2→5 replicas) |
|---|---|---|
| **p95 Latency** | 162.53ms | 122.74ms |
| **p90 Latency** | 121.97ms | 102.52ms |
| **Avg Latency** | 48.75ms | 52.60ms |
| **Median Latency** | 31.88ms | 49.22ms |
| **Max Latency** | 538.62ms | 395.19ms |
| **Error Rate** | 0.00% | 0.00% |
| **Total Requests** | 1,050,659 | 1,016,782 |
| **Throughput** | 5,524 req/s | 5,344 req/s |
| **Iterations** | 350,203 | 338,913 |
| **Checks Passed** | 100.00% | 99.99% (7 EOF during nginx reload) |

**All thresholds passed.**

### Autoscale Timeline (1000 VU Breakpoint)

| Time | Event | Replicas | Avg CPU |
|---|---|---|---|
| +0s | Test starts | 2 | 0% |
| +27s | Scale up triggered | 2 → 3 | 76% |
| +45s | Scale up triggered | 3 → 4 | 122% |
| +65s | Scale up triggered | 4 → 5 | 140% |
| +3m10s | Test ends, load drops | 5 | 1% |
| +3m28s | Scale down triggered | 5 → 4 | 1% |

---

## Key Optimizations

1. **Atomic short_code generation** — Each URL gets a unique UUID placeholder inside a `db.atomic()` transaction, eliminating race conditions under concurrent writes.

2. **Connection pooling** — `PooledPostgresqlDatabase` with `max_connections=5` per worker. PostgreSQL set to 103 max connections (100 usable + 3 superuser reserved). At max autoscale: 5 replicas × 4 workers × 5 pool = 100 connections, fully utilizing the available capacity.

3. **Database indexes** — Indexes on `urls.user_id`, `urls.is_active`, `events.url_id`, `events.user_id`, `events.event_type` for faster filtered queries.

4. **Nginx `least_conn` load balancing** — Routes traffic to the replica with the fewest active connections instead of round-robin.

5. **Batch inserts for bulk operations** — `insert_many` with 100-row batches for CSV imports.

6. **Hybrid async/sync event logging** — Synchronous writes for create/update (immediate consistency), fire-and-forget via `ThreadPoolExecutor` for redirects (latency-sensitive path).

7. **CPU-based autoscaling** — Custom autoscaler polls Docker stats, scales up immediately at >50% CPU (no cooldown), scales down at <30% CPU (60s cooldown to prevent flapping). Adaptive polling: 5s normal, 3s when CPU >50%.

---

## Infrastructure

| Component | Config |
|---|---|
| App | Flask + Gunicorn (4 workers per replica) |
| Replicas | 2 base, autoscales to 5 max |
| Load Balancer | Nginx (`least_conn`) |
| Database | PostgreSQL 16 Alpine (`max_connections=103`) |
| Connection Pool | `PooledPostgresqlDatabase`, 5 max per worker |
| Autoscaler | CPU-based, 5s/3s adaptive polling, 2–5 replicas |
