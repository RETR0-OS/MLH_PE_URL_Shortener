# Failure Modes

This document describes how the URL shortener behaves under various failure conditions and what operators should expect.

## Database Down

- **Symptom**: `GET /health/ready` returns `503 {"status": "unavailable"}`.
- **Impact**: All CRUD operations fail with `500 Internal Server Error` (JSON, never a stack trace).
- **Recovery**: When Postgres comes back, the connection pool automatically reconnects. No restart required.
- **Swarm behavior**: The healthcheck on `/health/ready` fails, so Swarm marks the task as unhealthy and restarts it after the configured retry policy.

## Redis Down (future, with cache layer)

- **Symptom**: `redis_connection_errors_total` Prometheus counter increments; structured log warnings with `"component": "cache"`.
- **Impact**: The circuit-breaker falls back to direct DB reads. **No user-facing errors.** Latency increases for previously-cached reads.
- **Recovery**: When Redis returns, the cache refills organically via cache-aside on subsequent reads.

## Container Crash / OOM Kill

- **Symptom**: `docker service ps urlshort_app` shows a task in `Failed` or `Shutdown` state.
- **Impact**: Swarm routing mesh removes the dead replica from the load-balancer pool. Remaining replicas handle traffic. In-flight requests on the crashed replica receive a TCP reset; Nginx retries via `proxy_next_upstream`.
- **Recovery**: Swarm `restart_policy` (`condition: on-failure`, `max_attempts: 5`, `delay: 5s`) re-creates the container automatically. Typical recovery time: 5-15 seconds including healthcheck start period.

## Bulk Import Mid-Failure

- **Symptom**: `POST /users/bulk` returns `500` if the CSV is malformed or a constraint violation occurs mid-batch.
- **Impact**: The entire import runs inside `db.atomic()`, so a failure rolls back the entire transaction. No partial data is committed.
- **Recovery**: Fix the CSV and re-upload. The `on_conflict_ignore` clause allows safe re-imports of previously loaded data.

## Network Partition (Postgres unreachable)

- **Symptom**: Connection pool timeout errors. Health readiness fails.
- **Impact**: Same as "Database Down" — all write and read operations fail.
- **Recovery**: Pool automatically re-establishes connections when the network heals. Stale connections are evicted after `stale_timeout` (300s).

## Disk Full (Postgres volume)

- **Symptom**: Write operations fail with disk-full errors. Reads may still work.
- **Impact**: New user/URL/event creation fails. Reads from existing data continue.
- **Recovery**: Free disk space or expand the volume. Postgres resumes accepting writes automatically.
