---
layout: default
title: Decision Log
permalink: /decision-log
---

# Decision Log

Every significant technical choice made during the URL Shortener project, with alternatives considered, reasoning, and trade-offs accepted. This is a living document — decisions are recorded when made and never retroactively altered.

---

## How to Read This Log

Each entry follows this structure:

- **Choice**: What we selected
- **Alternatives considered**: What else we evaluated
- **Why this**: The deciding reason(s)
- **Trade-offs accepted**: What we gave up

---

## Application Layer

### ADR-001: Flask over FastAPI or Django

**Status**: Accepted
**Date**: 2026-04-01

**Choice**: Flask 3.0

**Alternatives considered**:
- FastAPI (Python async framework)
- Django REST Framework (batteries-included)
- Express.js (Node.js)

**Why this**:
- Flask's `test_client()` makes unit testing routes with a real app context trivial — no async test runner needed.
- The application is request/response with synchronous DB calls. Async does not provide a throughput benefit here; Gunicorn gthread handles concurrency at the WSGI layer.
- Flask has no opinion on ORM, validation, or project layout — this allowed us to pick best-in-class tools for each concern.

**Trade-offs accepted**:
- No built-in input validation (mitigated by custom validators in `app/utils/validation.py`).
- No async support (not needed for this workload; Gunicorn threads handle I/O concurrency).

---

### ADR-002: Gunicorn (gthread) over gevent, uvicorn, or async workers

**Status**: Accepted
**Date**: 2026-04-01

**Choice**: Gunicorn 22.0 with `worker_class = "gthread"`, 2 workers × 4 threads per replica.

**Alternatives considered**:
- `gevent` (greenlet-based async)
- `uvicorn` (ASGI, for FastAPI)
- `meinheld` (C-based high-performance WSGI)

**Why this**:
- `gthread` re-uses a single DB connection pool across threads in the same worker (connections are claimed/released per request, not per thread). `gevent` monkey-patching can cause subtle bugs with psycopg2.
- Threaded workers are easier to profile with standard Python tools (cProfile, py-spy) than greenlet-based workers.
- `max_requests = 10000` with jitter forces periodic worker recycling, preventing long-running memory growth without a restart.

**Trade-offs accepted**:
- Python GIL limits true CPU parallelism per worker. Mitigated by running 2 workers per replica and 2+ replicas.
- Slightly higher per-request overhead vs `gevent` for very high concurrency (thousands of simultaneous slow connections). Not applicable to this workload.

---

### ADR-003: Peewee ORM over SQLAlchemy or raw psycopg2

**Status**: Accepted
**Date**: 2026-04-01

**Choice**: Peewee 3.19 with `PooledPostgresqlDatabase`

**Alternatives considered**:
- SQLAlchemy (industry standard)
- psycopg2 directly (no ORM)
- Tortoise ORM (async)

**Why this**:
- `PooledPostgresqlDatabase` is a first-class feature, not a plugin. It handles `stale_timeout` (reconnect idle connections), `timeout` (acquisition wait), and thread-safe connection management out of the box.
- Peewee's `post_fork()` hook integrates cleanly with Gunicorn's pre-fork model: each worker re-initializes its own pool after forking, preventing shared-socket corruption.
- Much smaller API surface than SQLAlchemy; faster to onboard contributors.

**Trade-offs accepted**:
- Fewer community resources and third-party integrations than SQLAlchemy.
- No async support (not needed; see ADR-002).
- Migration tooling (`peewee-migrate`) is less mature than Alembic.

---

### ADR-004: uv as Python package manager over pip+venv, Poetry, or Pipenv

**Status**: Accepted
**Date**: 2026-04-01

**Choice**: `uv` (Astral)

**Alternatives considered**:
- pip + venv + requirements.txt
- Poetry
- Pipenv

**Why this**:
- `uv sync` installs the full dependency tree in < 5 seconds (vs 60+ for pip). This meaningfully shortens CI job runtime.
- Generates a `uv.lock` file with cryptographic hashes — reproducible installs across local, CI, and production.
- Native Python 3.13 support without workarounds.
- Single binary, no Rust or Node.js dependency chains to install.

**Trade-offs accepted**:
- Younger project than pip or Poetry; fewer Stack Overflow answers.
- Some niche plugins expect `pip` directly and require `uv run pip install` fallback.

---

## Data Layer

### ADR-005: PostgreSQL 16 over MySQL or SQLite

**Status**: Accepted
**Date**: 2026-04-01

**Choice**: PostgreSQL 16

**Alternatives considered**:
- MySQL 8.0
- SQLite (for local dev simplicity)
- CockroachDB (distributed SQL)

**Why this**:
- `pg_stat_statements` extension provides per-query execution statistics with zero application-level instrumentation — critical for diagnosing slow queries in production.
- `synchronous_commit = off` is a first-class PostgreSQL feature that lets us trade ~200ms of crash durability for lower write latency on event logging. MySQL equivalent requires more invasive configuration.
- JSONB column type on the `events.metadata` field allows flexible event payloads without schema migrations.
- `ON CONFLICT DO NOTHING` / `ON CONFLICT DO UPDATE` (upsert) syntax is cleaner than MySQL's `INSERT IGNORE` / `ON DUPLICATE KEY UPDATE`.

**Trade-offs accepted**:
- Slightly higher memory footprint than MySQL (mitigated by `shared_buffers=192MB` cap).
- `synchronous_commit=off` means up to ~200ms of committed writes could be lost on a hard crash. Acceptable because: (a) URL/user records can be re-created from user action, (b) event records are append-only analytics and loss is tolerable.

---

### ADR-006: Redis 7 with `allkeys-lfu` eviction and no TTL

**Status**: Accepted
**Date**: 2026-04-02

**Choice**: Redis 7, `allkeys-lfu`, no TTL on cache entries, 128 MB memory cap

**Alternatives considered**:
- Redis with `allkeys-lru` (least recently used)
- Redis with fixed TTL (e.g., 5 minutes)
- Memcached
- In-process dictionary cache

**Why this**:
- **LFU over LRU**: A one-off hit on a cold URL (e.g., from a link crawler) can displace an entry accessed 10,000 times under LRU. LFU tracks actual access frequency, so viral URLs accumulate score and stay cached. One-off hits decay and are evicted when Redis needs memory.
- **No TTL**: With a 5-minute TTL, even the hottest URL forces a DB read every 5 minutes, creating periodic load spikes (thundering herd). Without TTL, a hot URL is evicted only when Redis memory is full and something less popular must go. Cache utility per byte is maximized.
- **LFU vs Memcached**: Memcached has no LFU policy, no persistence option, and no circuit-breaker-friendly client semantics.
- **No in-process cache**: Not shared across replicas. Each replica would cache independently, wasting memory and causing inconsistency on PUT/DELETE.

**Trade-offs accepted**:
- Correctness without TTL requires explicit cache invalidation on every write (PUT, DELETE). Every write path must call `cache_delete_pattern` or the cache will serve stale data. This is enforced in `app/utils/cache.py`.
- Redis persistence disabled (`save ""`, `--appendonly no`) — all cached data is ephemeral. On Redis restart, cache is cold and DB absorbs the load until it refills.

---

### ADR-007: `synchronous_commit = off` on PostgreSQL

**Status**: Accepted
**Date**: 2026-04-02

**Choice**: PostgreSQL `synchronous_commit = off`

**Alternatives considered**:
- Default (`synchronous_commit = on`) — safe, slower
- Per-transaction override (set `off` only for event writes)

**Why this**:
- Every URL redirect logs an event to the `events` table. That is the highest-write-frequency operation in the system. With `synchronous_commit = on`, each INSERT waits for a disk fsync (1–10 ms), directly adding to event write latency and increasing DB CPU.
- With `off`, acknowledgement returns as soon as the write is in the WAL buffer. The disk flush happens asynchronously. P95 write latency drops significantly.
- Per-transaction override (option 2) adds code complexity and makes it easy to forget to apply on new write paths.

**Trade-offs accepted**:
- Up to ~200ms of committed writes may be lost on a hard kernel crash or power loss. The WAL is never corrupted; only the last ~200ms window is at risk.
- For URL and user records: loss means the user retries creating the URL. Acceptable.
- For event records: loss means a few redirect/analytics events are not recorded. Acceptable (analytics, not billing).

---

## Infrastructure Layer

### ADR-008: Nginx over HAProxy, Traefik, or Caddy

**Status**: Accepted
**Date**: 2026-04-01

**Choice**: Nginx 1.25

**Alternatives considered**:
- HAProxy 2.8
- Traefik 3.0
- Caddy 2.0

**Why this**:
- `limit_req_zone` + `limit_req` provides rate limiting at the connection level, before requests reach the application — protecting against burst traffic and simple DDoS without application-level overhead.
- `proxy_next_upstream error timeout http_502 http_503` with `proxy_next_upstream_tries 2` gives automatic retry on unhealthy replicas without modifying application code.
- Nginx's `least_conn` upstream algorithm routes new connections to the replica with the fewest active connections. When the autoscaler adds a new replica, it starts with zero connections and Nginx immediately routes aggressively to it, naturally rebalancing load. Round-robin would not do this.
- Caddy's automatic HTTPS is not needed (self-signed cert via `cert-gen` service covers the requirement).

**Trade-offs accepted**:
- Nginx configuration is declarative and can be verbose for complex routing rules.
- No dynamic upstream reload without `SIGHUP` — mitigated by the autoscaler sending `SIGHUP` after every scaling action.

---

### ADR-009: Docker Compose over Kubernetes or Docker Swarm

**Status**: Accepted
**Date**: 2026-04-01

**Choice**: Docker Compose (with custom autoscaler sidecar)

**Alternatives considered**:
- Kubernetes (k3s on single node)
- Docker Swarm
- Nomad

**Why this**:
- A single `docker-compose.yml` defines the entire stack (app, DB, cache, monitoring, autoscaler). Any engineer can run the full production-equivalent stack locally with one command.
- Kubernetes adds ~500 MB of overhead per node and requires managing a control plane, etcd, and networking plugins — unjustified for a single-server deployment.
- Docker Swarm lacks pod-level health routing and has a smaller ecosystem.
- The custom autoscaler sidecar (`autoscaler/scaler.py`) gives us CPU-based horizontal scaling equivalent to Kubernetes HPA with 200 lines of Python instead of YAML manifests.

**Trade-offs accepted**:
- No cross-node scheduling. If the single droplet goes down, the service is down. Mitigated by: 2-replica redundancy, restart policies, zero-downtime deploy gates, and the 99.9% SLO target (43 min/month allowed downtime).
- Docker Compose rollback is manual (no built-in `rollback` command). Mitigated by `git revert` + redeploy procedure in `docs/DEPLOYMENT.md`.

---

### ADR-010: GitHub Actions for CI/CD over CircleCI, Jenkins, or GitLab CI

**Status**: Accepted
**Date**: 2026-04-01

**Choice**: GitHub Actions

**Alternatives considered**:
- CircleCI
- Jenkins (self-hosted)
- GitLab CI/CD

**Why this**:
- Native to GitHub repository — no OAuth integrations, no separate account, no per-minute billing for public repos.
- Service containers (`services:` in workflow YAML) spin up real PostgreSQL and Redis instances for integration tests with zero extra configuration.
- GitHub Secrets management is built-in and supports environment-scoped secrets (`DROPLET_IP`, `DROPLET_PASS`).
- `concurrency: deploy-production` prevents race conditions from back-to-back merges triggering simultaneous deploys.

**Trade-offs accepted**:
- GitHub Actions minutes are consumed on every push. For a free-tier public repo, this is $0, but private repos have a monthly cap.
- Build runners are ephemeral — no persistent Docker layer cache without explicit `cache:` action configuration.

---

### ADR-011: DigitalOcean over AWS, GCP, or Heroku

**Status**: Accepted
**Date**: 2026-04-01

**Choice**: DigitalOcean Droplet (2 vCPU, 2 GB RAM, $12/month)

**Alternatives considered**:
- AWS EC2 t3.small ($15–20/month) + EBS
- GCP e2-small (~$13/month)
- Heroku Eco Dyno ($5/month, no Docker Compose)
- Fly.io (Docker-native, $6/month)

**Why this**:
- Predictable flat pricing ($12/month) vs AWS/GCP pay-per-use that can surprise with egress charges.
- Simple SSH-based deployment: `git pull && docker compose up` with no cloud SDK or IAM role configuration.
- DigitalOcean's API is straightforward if we need to automate droplet upgrades (e.g., resize to 4 vCPU programmatically).
- Heroku does not support Docker Compose with multiple services — our monitoring stack (Prometheus, Grafana, Loki) would not deploy there.

**Trade-offs accepted**:
- No managed autoscaling across multiple nodes (mitigated by custom autoscaler within the single droplet).
- No managed PostgreSQL or Redis (reduces cost but requires manual backup procedures).
- If the droplet's host node has a hardware failure, DigitalOcean migrates it — this can cause 10–60 minutes of downtime. Mitigation: multi-droplet setup in Phase 3 (see `CAPACITY_PLAN.md`).

---

## Observability Stack

### ADR-012: Prometheus + Alertmanager over Grafana Alerting or Datadog

**Status**: Accepted
**Date**: 2026-04-03

**Choice**: Prometheus for metrics + Alertmanager for alert routing

**Alternatives considered**:
- Grafana Alerting (built-in)
- Datadog
- New Relic
- VictoriaMetrics

**Why this**:
- Prometheus evaluates alert rules independently of Grafana. If Grafana goes down, alerts still fire. Grafana Alerting stops if the Grafana container crashes.
- Alertmanager provides native severity routing, `repeat_interval`, inhibition (suppress child alerts when parent fires), and multi-channel fan-out (`continue: true`). Grafana Alerting's routing is less expressive.
- PromQL is the same query language used in dashboard panels — alert thresholds are consistent with what operators see, eliminating a class of "alert says X but dashboard shows Y" confusion.
- Free and self-hosted. Datadog pricing is ~$15–20/host/month at minimum.

**Trade-offs accepted**:
- Prometheus's 72-hour retention requires Grafana for any historical analysis beyond 3 days. Long-term retention requires Thanos, Cortex, or an external remote-write destination.
- Self-managed: we are responsible for Prometheus storage, scrape config, and alert rule maintenance.

---

### ADR-013: Loki + Promtail over ELK Stack or CloudWatch Logs

**Status**: Accepted
**Date**: 2026-04-03

**Choice**: Grafana Loki 3.4.2 + Promtail (Docker socket discovery)

**Alternatives considered**:
- ELK Stack (Elasticsearch + Logstash + Kibana)
- Fluentd + Elasticsearch
- AWS CloudWatch Logs
- Vector + S3

**Why this**:
- Loki uses a label-based index (not full-text index like Elasticsearch). On a 2 GB droplet, Elasticsearch alone requires 1–2 GB RAM minimum, which would leave no room for the application. Loki uses ~256 MB.
- Promtail's `docker_sd_configs` automatically discovers new app replicas when the autoscaler spins them up — no reconfiguration needed.
- Loki integrates natively as a Grafana datasource. Operators can correlate metrics and logs in one view without switching tools.

**Trade-offs accepted**:
- Loki's LogQL is less powerful than Elasticsearch's full-text search for complex log analytics.
- 72-hour retention means logs older than 3 days are not queryable. Acceptable for incident investigation (most incidents are diagnosed within hours).

---

### ADR-014: Jaeger + OpenTelemetry over Zipkin or Datadog APM

**Status**: Accepted
**Date**: 2026-04-03

**Choice**: Jaeger (self-hosted) with OpenTelemetry SDK

**Alternatives considered**:
- Zipkin
- Datadog APM
- Honeycomb

**Why this**:
- OpenTelemetry is the CNCF-standard vendor-neutral instrumentation SDK. Using it means we can switch trace backends (Jaeger → Tempo → Honeycomb) by changing one environment variable (`OTEL_EXPORTER_OTLP_ENDPOINT`), with zero application code changes.
- The `FlaskInstrumentor` auto-instruments all Flask routes with zero per-route annotation.
- Jaeger is free and self-hosted. Datadog APM is ~$23/host/month.

**Trade-offs accepted**:
- Jaeger's in-memory store is ephemeral — traces are lost on container restart. Acceptable for debugging (traces are diagnostic, not auditable).
- Self-managed: we are responsible for Jaeger storage and retention configuration.

---

### ADR-015: python-json-logger over structlog or stdlib logging.Formatter

**Status**: Accepted
**Date**: 2026-04-03

**Choice**: `pythonjsonlogger.json.JsonFormatter` from `python-json-logger >= 3.0`

**Alternatives considered**:
- `structlog` (full contextual logging library)
- stdlib `logging.Formatter` with custom `format()` method

**Why this**:
- Wraps Python's stdlib `logging` module with no changes to existing `logger.info()` / `logger.warning()` call sites. Drop-in replacement.
- `rename_fields={"asctime": "timestamp", "levelname": "level"}` maps field names to match the Track 3 submission requirement verbatim.
- Promtail parses JSON logs natively, enabling structured queries in Loki/Grafana without a parsing pipeline.

**Trade-offs accepted**:
- Less powerful than `structlog`'s contextual binding and processor pipeline. Acceptable for this project's logging needs.

---

## Testing Strategy

### ADR-016: k6 for load testing over Locust or JMeter

**Status**: Accepted
**Date**: 2026-04-02

**Choice**: k6 (Grafana)

**Alternatives considered**:
- Locust (Python-based)
- JMeter (Java-based, XML config)
- Artillery (Node.js-based)
- wrk (low-level HTTP benchmarking)

**Why this**:
- k6 scripts are JavaScript — readable, version-controlled alongside the codebase, and testable. JMeter requires XML configuration that is difficult to diff and review.
- `k6 run --out json=results.json` produces structured output that the CI workflow parses and posts as a PR comment (load test results visible in the PR without clicking through to the Actions tab).
- Built-in VU (virtual user) ramp profiles match real traffic patterns better than wrk's flat concurrency model.
- k6 is a single binary, no JVM or Python virtualenv needed in CI.

**Trade-offs accepted**:
- JavaScript is not the team's primary language. Mitigated by k6's simple API (`http.get()`, `http.post()`, `check()`).
- k6 cloud requires a paid account for distributed load generation. For CI, we run k6 locally (single runner, 500 VUs) which is sufficient.

---

### ADR-017: 70% coverage floor over 100% or no coverage gate

**Status**: Accepted
**Date**: 2026-04-02

**Choice**: `--cov-fail-under=70` in CI (actual coverage: 91%)

**Alternatives considered**:
- No coverage gate (trust engineers)
- 100% coverage gate
- 80% gate

**Why this**:
- A 70% floor blocks obvious regressions (e.g., someone adds a large uncovered feature) while not forcing coverage of every edge case and error branch.
- The actual coverage is 91% — the floor is a safety net, not the target.
- Chasing 100% coverage has diminishing returns: the last 10% typically covers error handler branches and OS-level failure paths that are hard to test without complex mocking.

**Trade-offs accepted**:
- Coverage percentage measures lines executed, not assertion quality. A test that calls a function without asserting its output contributes to coverage but provides no safety. Mitigated by code review and integration tests.

---

## Alert Routing

### ADR-018: Resend (SMTP) for email alerts over SendGrid, Mailgun, or SES

**Status**: Accepted
**Date**: 2026-04-03

**Choice**: Resend transactional email (`smtp.resend.com:587`)

**Alternatives considered**:
- SendGrid SMTP
- AWS SES
- Postmark
- Gmail SMTP

**Why this**:
- Resend's free tier is 3,000 emails/month, 100/day — more than sufficient for alert notifications.
- Resend provides an SMTP-compatible interface, which Alertmanager natively supports with no webhook adapter.
- Domain verification is straightforward (`alerts@hackathon.forgeopus.org`).
- Email creates a permanent, searchable audit trail for postmortems.

**Trade-offs accepted**:
- Email has higher delivery latency (~5–30s) than Discord webhooks. Mitigated by Discord as the secondary channel for real-time awareness.
- Sender domain (`hackathon.forgeopus.org`) must remain verified in Resend. If the domain lapses, alerts stop being delivered.

---

### ADR-019: Discord as opt-in secondary alert channel

**Status**: Accepted
**Date**: 2026-04-03

**Choice**: Discord webhook, opt-in via `DISCORD_WEBHOOK_URL` environment variable

**Alternatives considered**:
- Slack (more common in industry)
- PagerDuty (enterprise on-call)
- OpsGenie

**Why this**:
- Discord is free with no per-seat cost. A webhook URL is created in seconds. PagerDuty starts at $19/user/month.
- Making Discord opt-in via env var means the stack works with just email out of the box — operators without a Discord server are not blocked.
- `entrypoint.sh` merges `discord-receivers.yml` into the Alertmanager config at container startup only when `DISCORD_WEBHOOK_URL` is set. No separate Alertmanager config file to maintain.

**Trade-offs accepted**:
- Discord messages are ephemeral — no searchable history for postmortems (mitigated by email as the permanent record).
- No on-call rotation or escalation policies. Acceptable for a hackathon project without a formal on-call team.

---

## Summary Table

| ADR | Decision | Key Trade-off |
|-----|----------|---------------|
| ADR-001 | Flask over FastAPI/Django | No async, no built-in validation |
| ADR-002 | Gunicorn gthread over gevent | GIL limits CPU parallelism per worker |
| ADR-003 | Peewee over SQLAlchemy | Smaller ecosystem, less mature migrations |
| ADR-004 | uv over pip/Poetry | Younger project, fewer resources |
| ADR-005 | PostgreSQL over MySQL/SQLite | Slightly higher memory footprint |
| ADR-006 | Redis LFU, no TTL | Must explicitly invalidate on every write |
| ADR-007 | `synchronous_commit=off` | ~200ms crash window on event writes |
| ADR-008 | Nginx over HAProxy/Traefik | Verbose config, manual SIGHUP for upstream changes |
| ADR-009 | Docker Compose over Kubernetes | No cross-node scheduling |
| ADR-010 | GitHub Actions over CircleCI | Minute limits on private repos |
| ADR-011 | DigitalOcean over AWS/GCP | No managed autoscaling across nodes |
| ADR-012 | Prometheus+Alertmanager over Grafana Alerting | Self-managed retention |
| ADR-013 | Loki+Promtail over ELK | Less powerful full-text search |
| ADR-014 | Jaeger+OpenTelemetry over Zipkin | Ephemeral trace storage |
| ADR-015 | python-json-logger over structlog | Less powerful contextual binding |
| ADR-016 | k6 over Locust/JMeter | JS not primary team language |
| ADR-017 | 70% coverage floor | Coverage ≠ assertion quality |
| ADR-018 | Resend SMTP over SendGrid/SES | Domain must stay verified |
| ADR-019 | Discord opt-in over Slack/PagerDuty | No on-call rotation |

---

## Related Documentation

- **Architecture Overview**: [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — System design and component configs
- **Scalability Decisions**: [`docs/Scalability/README.md`](Scalability/README.md) — Load balancing, caching, autoscaler decisions
- **Incident Response Decisions**: [`docs/Incident Response/INCIDENT_RESPONSE_ENGINEERING_DESIGN_DECISIONS.md`](Incident%20Response/INCIDENT_RESPONSE_ENGINEERING_DESIGN_DECISIONS.md) — Monitoring, alerting, observability decisions
