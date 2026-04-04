# Bottleneck Report

## Overview

This document describes the bottlenecks identified during load testing and the production engineering solutions applied. All numbers are from real k6 load test runs against the Dockerized stack (3 app replicas, Nginx, PostgreSQL, Redis).

## Identified Bottlenecks

### 1. Single-Instance Saturation

**Problem**: A single Flask process (sync worker) could only handle one request at a time. Under 50+ concurrent users, requests queued behind each other, causing p95 latency to spike above 5 seconds.

**Solution**: Switched to Gunicorn with `gthread` worker class (2 workers x 4 threads = 8 concurrent requests per container). Combined with horizontal scaling (3 replicas behind Nginx), the system handles 24 concurrent requests before queuing.

### 2. Database Connection Churn

**Problem**: The starter template opened and closed a new PostgreSQL connection on every request (`before_request` / `teardown`). Under load, connection setup overhead (~5-10ms per connection) consumed significant time and exhausted `max_connections`.

**Solution**: Replaced with `PooledPostgresqlDatabase` from Peewee's `playhouse.pool`. Bounded pool (`max_connections=20` per process) reuses connections across requests. At 3 replicas x 2 workers = 6 processes, peak pool usage is ~60 connections — well within Postgres `max_connections=100`.

### 3. Uncached Repeated Reads

**Problem**: `GET /urls/{id}` hit the database on every request. Popular URLs generated repeated identical queries under load, wasting DB capacity.

**Solution**: Redis cache-aside pattern with TTL=300s. First read populates the cache; subsequent reads hit Redis (sub-millisecond). Cache invalidation on `PUT /urls/{id}`. Circuit breaker ensures Redis failures degrade gracefully to DB-only mode (verified via chaos test — app logs `WARNING: Redis unavailable, falling back to DB-only` and continues serving).

### 4. Untuned PostgreSQL

**Problem**: Default Postgres configuration uses minimal memory, leading to excessive disk I/O for queries that could be served from shared buffers.

**Solution**: Tuned for the container resource limits:
- `shared_buffers=192MB` (from 128KB default)
- `work_mem=8MB` (for sort/hash operations)
- `effective_cache_size=384MB` (query planner hint)
- `maintenance_work_mem=64MB` (for vacuum/index builds)

### 5. No Load Balancing / Rate Limiting

**Problem**: Without a reverse proxy, a single misbehaving client could monopolize all server capacity. No compression meant larger payloads for JSON-heavy responses.

**Solution**: Nginx as the front proxy:
- Rate limiting: 500 req/s per IP with burst=50 (production-grade per-client limit)
- Gzip compression for JSON responses
- Keepalive connections to backend (pool of 64)
- `proxy_next_upstream` retries on failed replicas with `max_fails=3 fail_timeout=5s`
- 10MB client body size limit

## Load Test Results

All tests create their own test data dynamically in `setup()` — no hardcoded IDs or seeded data dependencies.

### Smoke Test (50 VUs, 30s)

| Metric | Result | Threshold |
|--------|--------|-----------|
| Throughput | 358 req/s | — |
| p95 Latency | 260ms | <2000ms |
| Error Rate | 0.00% | <5% |
| Check Pass Rate | 100% | — |

### Sustained Load Test (200 VUs, 60s steady state)

| Metric | Result | Threshold |
|--------|--------|-----------|
| Throughput | 345 req/s | — |
| p95 Latency | 1.78s | <3000ms |
| Error Rate | 1.79% | <5% |
| Total Iterations | 8,750 | — |

### Stress Test (ramp to 500 VUs, 60s hold)

| Metric | Result | Threshold |
|--------|--------|-----------|
| Throughput | 356 req/s | — |
| p95 Latency | 4.27s | — |
| Error Rate | 1.51% | <10% |
| Total Iterations | 9,874 | — |

### Soak Test (50 VUs, 5 minutes)

| Metric | Result | Threshold |
|--------|--------|-----------|
| Throughput | 142 req/s | — |
| p95 Latency | 57ms | <2000ms |
| Error Rate | 0.00% | <1% |
| Total Iterations | 14,233 | — |

## Chaos Test Results

| Step | Observation |
|------|-------------|
| Pre-kill | 3/3 replicas healthy |
| Kill app-1 | Container exits (code 137) |
| API during failure | 5/5 requests return HTTP 200 (Nginx routes to surviving 2 replicas) |
| Recovery | `docker compose up -d` detects missing replica and restarts it |
| Post-recovery | 3/3 replicas healthy, API fully operational |

## RCA Exercise: Redis Failure

| Step | Observation |
|------|-------------|
| Inject failure | `docker stop redis` |
| App behavior | Continues serving via circuit breaker fallback to DB-only |
| Structured log | `WARNING: Redis unavailable, falling back to DB-only` |
| Prometheus | All 3 app instances remain `up=1` |
| Recovery | `docker start redis` → immediate return to cached mode |

## Scaling Formula

```
replicas = ceil(target_rps / per_replica_rps)
```

Per-replica throughput (observed): ~100-120 req/s depending on read/write mix.

On the 2 vCPU / 4 GB host, the practical ceiling is **3 replicas** (3 x 384MB app + 768MB Postgres + 160MB Redis + 64MB Nginx = ~2.1GB, leaving headroom for OS and observability stack).
