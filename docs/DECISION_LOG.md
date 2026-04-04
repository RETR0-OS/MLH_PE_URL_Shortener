# Architecture Decision Log

## ADR-001: Gunicorn gthread Worker Class

**Context**: The URL shortener is I/O-bound (database queries, Redis lookups). The default Gunicorn `sync` worker blocks on every I/O operation.

**Decision**: Use `gthread` worker class with 2 workers x 4 threads = 8 concurrent requests per container.

**Rationale**: `gthread` uses OS threads for concurrent I/O without the complexity of async frameworks. It's the best fit for a Flask + Peewee app that doesn't need async/await. Sized for 2 vCPU host — more workers would cause context-switch overhead.

**Alternatives rejected**: `gevent` (monkey-patching risks with Peewee/psycopg2), `uvicorn` (requires ASGI, not WSGI).

---

## ADR-002: Peewee PooledPostgresqlDatabase

**Context**: The starter template opened a new Postgres connection per request and closed it on teardown. Under load, this creates ~100 connections/second of churn.

**Decision**: Use `PooledPostgresqlDatabase` with `max_connections=20` per process.

**Rationale**: Connection pooling eliminates setup overhead (~5-10ms per connection). At 3 replicas x 2 workers = 6 processes, peak usage is ~60 connections — within Postgres `max_connections=100`. The `stale_timeout=300s` evicts idle connections.

**Alternatives rejected**: PgBouncer (external dependency, overkill for this scale), per-request connections (too expensive).

---

## ADR-003: Docker Swarm over Plain Compose

**Context**: The app needs horizontal scaling, rolling updates, self-healing, and secrets management — all PE fundamentals.

**Decision**: Use Docker Swarm as a single-node orchestrator.

**Rationale**: Swarm provides declarative replicas, restart policies, rolling updates (`start-first` for zero downtime), service discovery, and secrets — all in one `docker-compose.yml`. No external dependencies. Works on a single 2 vCPU / 4 GB machine.

**Alternatives rejected**: Kubernetes (too heavy for single node), plain Compose (no self-healing, no rolling updates, no secrets).

---

## ADR-004: Redis with Circuit Breaker

**Context**: Repeated database reads for popular URLs waste DB capacity. A cache layer is needed, but the cache itself must not become a single point of failure.

**Decision**: Redis cache-aside with a circuit-breaker pattern. On Redis failure, the app falls back to DB-only with no user-facing errors.

**Rationale**: Cache-aside is simple and correct (read-through on miss, invalidate on write). The circuit breaker prevents cascading failures — if Redis is down, the app doesn't waste time on failed connections. Recovery is automatic after `CIRCUIT_RESET_SECONDS`.

**Alternatives rejected**: In-process cache (doesn't share across replicas), write-through cache (more complex, not needed for this read pattern).

---

## ADR-005: Nginx as Reverse Proxy

**Context**: The app needs rate limiting, gzip compression, and protection from slow clients. Gunicorn should not handle these concerns.

**Decision**: Nginx in front of Gunicorn with rate limiting (100r/s per IP), gzip for JSON, keepalive to backend, and `proxy_next_upstream` for retry on failed replicas.

**Rationale**: Nginx is lightweight (~64MB), handles thousands of concurrent connections, and offloads non-application concerns. `proxy_next_upstream` provides transparent retry when a replica is unhealthy.

**Alternatives rejected**: Traefik (heavier, more features than needed), no proxy (exposes Gunicorn directly, no rate limiting).

---

## ADR-006: Loki over Plain Docker Logs

**Context**: `docker service logs` is ephemeral — logs disappear when containers restart. Incident response requires persistent, searchable, filterable logs.

**Decision**: Grafana Loki for log aggregation, correlated with Prometheus metrics in Grafana dashboards.

**Rationale**: Loki is lightweight, works with Docker's JSON log driver, and integrates natively with Grafana. Structured JSON logs from the app include `request_id`, `method`, `path`, `status`, and `latency_ms` — all queryable in Loki.

**Alternatives rejected**: ELK stack (too heavy for 4GB host), Fluentd (unnecessary middleware layer), stdout-only (not durable).

---

## ADR-007: Base62 Short Code Generation

**Context**: Each URL needs a unique `short_code`. The starter template had no generation logic.

**Decision**: Generate 6-character Base62 codes using cryptographically random selection with collision retry.

**Rationale**: 62^6 = 56.8 billion possible codes. At the scale of this application (<100K URLs), collision probability is negligible. Cryptographic randomness prevents enumeration. Retry loop (max 10 attempts) provides a safety net.

**Alternatives rejected**: Sequential Base62 encoding (predictable, allows enumeration), UUID truncation (higher collision risk), hash-based (unnecessary complexity).

---

## ADR-008: PostgreSQL Tuning

**Context**: Default Postgres configuration uses minimal memory, leading to excessive disk I/O.

**Decision**: Tune for the 2 vCPU / 4 GB host: `shared_buffers=192MB`, `work_mem=8MB`, `effective_cache_size=384MB`, `max_connections=100`.

**Rationale**: `shared_buffers` at ~25% of Postgres container memory (768MB) balances memory usage with cache hit ratio. `work_mem=8MB` handles sorts and joins without spilling to disk. `effective_cache_size` hints the query planner about available OS cache.

**Alternatives rejected**: Default config (wastes the database layer), aggressive tuning (starves other services on the 4GB host).
