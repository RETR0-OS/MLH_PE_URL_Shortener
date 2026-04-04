# MLH PE URL Shortener

A production-grade URL shortener API built for the MLH Production Engineering hackathon. Covers all 4 tracks: Reliability, Scalability, Incident Response, and Documentation.

## Architecture

```mermaid
graph TD
  Client --> Nginx["Nginx (rate limit + gzip)"]
  Nginx -->|"proxy_pass + retry"| AppR1["App Replica 1 (Gunicorn gthread)"]
  Nginx -->|"proxy_pass + retry"| AppR2["App Replica 2"]
  AppR1 -->|"circuit breaker"| Redis["Redis (LRU, 128MB)"]
  AppR2 -->|"circuit breaker"| Redis
  AppR1 -->|"pooled conn"| PostgreSQL["PostgreSQL (tuned)"]
  AppR2 -->|"pooled conn"| PostgreSQL
  Prometheus -->|"scrape /metrics"| AppR1
  Prometheus -->|"scrape /metrics"| AppR2
  Prometheus --> Alertmanager --> Discord
  Grafana --> Prometheus
  Grafana --> Loki
```

## Quick Start (Local Development)

```bash
# Install dependencies
uv sync

# Set up Postgres (create database)
createdb hackathon_db

# Run the dev server
uv run flask --app run:app run --port 5000

# Seed data (optional)
uv run python scripts/seed.py

# Run tests
uv run pytest --cov=app
```

## Docker Compose (Production)

```bash
# Start the full stack
docker compose up -d --build

# Seed the database
docker compose exec app python scripts/seed.py

# Scale app replicas
docker compose up -d --scale app=3

# View logs
docker compose logs -f app
```

## Docker Swarm Deployment

```bash
docker swarm init
docker stack deploy -c docker-compose.yml urlshort

# Scale
docker service scale urlshort_app=3

# Rolling update
docker service update --image app:v2 urlshort_app

# Rollback
docker service update --rollback urlshort_app
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/health/ready` | Readiness probe (DB check) |
| GET | `/users` | List users (paginated) |
| POST | `/users` | Create user |
| POST | `/users/bulk` | Bulk import users (CSV) |
| GET | `/users/{id}` | Get user by ID |
| PUT | `/users/{id}` | Update user |
| GET | `/urls` | List URLs (filter by `?user_id=`) |
| POST | `/urls` | Create shortened URL |
| GET | `/urls/{id}` | Get URL by ID |
| PUT | `/urls/{id}` | Update URL |
| GET | `/events` | List events |
| GET | `/metrics` | Prometheus metrics |

Full API specification: [docs/openapi.yaml](docs/openapi.yaml)

## Service Ports

| Service | Port |
|---------|------|
| App (Gunicorn) | 5000 |
| Nginx | 80 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Prometheus | 9090 |
| Alertmanager | 9093 |
| Grafana | 3000 |
| Loki | 3100 |

## Documentation

- [API Specification](docs/openapi.yaml)
- [Deploy Guide](docs/DEPLOY_GUIDE.md)
- [Environment Variables](docs/ENV_VARS.md)
- [Error Handling](docs/ERROR_HANDLING.md)
- [Failure Modes](docs/FAILURE_MODES.md)
- [Bottleneck Report](docs/BOTTLENECK_REPORT.md)
- [Runbook](docs/RUNBOOK.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Decision Log (ADRs)](docs/DECISION_LOG.md)
- [Capacity Plan](docs/CAPACITY_PLAN.md)
- [SLOs](docs/SLO.md)
- [Tracks Master Plan](docs/TRACKS_MASTER_PLAN.md)

## Tech Stack

- **Runtime**: Python 3.13, Flask, Gunicorn (gthread)
- **Database**: PostgreSQL 16 (tuned), Peewee ORM (pooled connections)
- **Cache**: Redis 7 (LRU, circuit-breaker fallback)
- **Proxy**: Nginx (rate limiting, gzip, keepalive, proxy retries)
- **Observability**: Prometheus, Alertmanager, Grafana, Loki
- **CI/CD**: GitHub Actions (pytest + coverage gate)
- **Orchestration**: Docker Swarm (rolling updates, self-healing, secrets)
