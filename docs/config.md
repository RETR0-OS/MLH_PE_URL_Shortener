---
layout: default
title: Configuration & Environment Variables
permalink: /config
---

# Configuration & Environment Variables

All environment variables and configuration required to run the URL Shortener stack.

## Application

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FLASK_DEBUG` | No | false | Enable Flask debug mode. Set to `true` for local development only. |
| `API_KEY` | No | (empty) | Optional API key for request authentication. When set, all requests (except health checks) must include matching `X-API-Key` header. Leave blank to disable API-key auth. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | (empty) | OpenTelemetry OTLP gRPC endpoint for distributed tracing (e.g., `http://jaeger:4317`). Leave blank to disable tracing. |
| `OTEL_SERVICE_NAME` | No | url-shortener | Service name reported to the tracing backend in OpenTelemetry spans. |

## Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_NAME` | Yes | hackathon_db | PostgreSQL database name. |
| `DATABASE_HOST` | Yes | localhost | PostgreSQL hostname or IP address. In Docker Compose, use `postgres` (service name). |
| `DATABASE_PORT` | Yes | 5432 | PostgreSQL port. |
| `DATABASE_USER` | Yes | postgres | PostgreSQL user account for authentication. |
| `DATABASE_PASSWORD` | Yes | postgres | PostgreSQL password. **Change in production.** Supports Docker secrets `/run/secrets/database_password`. |

### Database Configuration Notes

- All database variables are read via `app.utils.secrets.read_secret()`, which supports Docker secrets as override.
- Connection pool: 20 max connections, 300s stale timeout, 10s socket timeout.
- Automatic indexes created at startup (user_id, short_code, is_active, event_type, timestamp).

## Redis

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_HOST` | Yes | redis | Redis hostname or IP. In Docker Compose, use `redis` (service name). |
| `REDIS_PORT` | Yes | 6379 | Redis port. |
| `REDIS_PASSWORD` | No | (empty) | Redis password. Leave blank if Redis has no password authentication. |

### Redis Configuration Notes

- Connection timeout: 0.5s, socket timeout: 0.5s (fail-fast design).
- Health check interval: 30s.
- Eviction policy: `maxmemory-policy allkeys-lfu` (128 MB max, LFU eviction).
- Circuit breaker: 30s reset window when Redis becomes unavailable. App continues with DB-only fallback.
- Cache stores: URL metadata, user info (no TTL, relies on LFU eviction).

## Alertmanager & Email Notifications

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RESEND_API_KEY` | No | (empty) | Resend API key for transactional email delivery. Get from https://resend.com. Free tier: 3,000 emails/month, 100/day. |
| `ALERT_EMAIL_TO` | No | contact.sahajpreetsingh@gmail.com | Destination email for critical and warning alerts. |
| `DISCORD_WEBHOOK_URL` | No | (empty) | Discord webhook URL for alert notifications (optional alternative to email). |

### Alertmanager Configuration Notes

- SMTP server: `smtp.resend.com:587` with TLS required.
- SMTP username: `resend` (hardcoded, password is API key).
- Sender: `alerts@hackathon.forgeopus.org` (must be verified domain in Resend).
- Alert routing:
  - Critical alerts: 0s group wait, 15m repeat interval.
  - Warnings: 10s group wait, 1h repeat interval.

## Monitoring (Prometheus / Alertmanager)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| (none) | - | - | Prometheus and Alertmanager configurations are read from YAML files, not environment variables. See below. |

### Prometheus Configuration

- Location: `monitoring/prometheus/prometheus.yml`
- Scrape interval: 15s
- Evaluation interval: 15s
- Alert rules: `monitoring/prometheus/alerts.yml`
- Data retention: 72 hours
- Scrapes from: `app:5000/metrics` (Prometheus Flask exporter)

### Alertmanager Configuration

- Location: `monitoring/alertmanager/alertmanager.yml`
- SMTP auth password: Uses `${RESEND_API_KEY}` environment variable (template substitution via entrypoint script).
- Alert email receiver: Uses `${ALERT_EMAIL_TO}` environment variable.

## Loki & Log Aggregation

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| (none) | - | - | Loki configuration is file-based. See `monitoring/loki/loki-config.yml`. |

### Loki Configuration Notes

- Config file: `monitoring/loki/loki-config.yml`
- Log ingestion port: 3100 (HTTP)
- Promtail ships logs from Docker containers via socket mount.

## Grafana

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GF_SECURITY_ADMIN_USER` | No | admin | Grafana admin username. |
| `GF_SECURITY_ADMIN_PASSWORD` | No | admin | Grafana admin password. **Change in production.** |
| `GF_USERS_ALLOW_SIGN_UP` | No | false | Disable self-service user registration. |

## Nginx

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| (none) | - | - | Nginx is configured via `nginx/nginx.conf` (no environment variables). |

### Nginx Configuration Notes

- HTTP server: Port 80
- HTTPS server: Port 443 (with auto-generated self-signed certs from `cert-gen` service)
- TLS protocols: TLSv1.2 and TLSv1.3
- Rate limiting: 2000 req/s per zone, burst of 200 requests
- Upstream: Load-balanced to `app:5000` with least-conn strategy
- Proxy timeouts: 5s connect, 30s read, 10s send
- Max body size: 10 MB
- Security headers: CSP, X-Frame-Options, X-Content-Type-Options, HSTS, Referrer-Policy

## Docker / Deployment

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SERVICE_NAME` | No | app | Service name for Docker autoscaler to manage (must match docker-compose service name). |
| `MIN_REPLICAS` | No | 2 | Minimum number of app container replicas. |
| `MAX_REPLICAS` | No | 5 | Maximum number of app container replicas. |
| `SCALE_UP_THRESHOLD` | No | 70.0 | CPU usage percentage to trigger scale-up. |
| `SCALE_DOWN_THRESHOLD` | No | 30.0 | CPU usage percentage to trigger scale-down. |
| `CPU_LIMIT_CORES` | No | 0.75 | CPU limit per container (cores). |
| `POLL_INTERVAL` | No | 10 | Autoscaler polling interval (seconds). |
| `SCALE_UP_WINDOW` | No | 2 | Number of polls required above threshold to scale up. |
| `SCALE_DOWN_WINDOW` | No | 6 | Number of polls required below threshold to scale down. |
| `SCALE_UP_COOLDOWN` | No | 60 | Cooldown after scale-up (seconds). |
| `SCALE_DOWN_COOLDOWN` | No | 120 | Cooldown after scale-down (seconds). |

### Docker Resource Limits

- **App container**: 2 replicas (default), 0.75 CPU, 384 MB memory
- **PostgreSQL**: 768 MB memory
- **Redis**: 160 MB memory
- **Prometheus**: 512 MB memory
- **Grafana**: 256 MB memory
- **Loki**: 256 MB memory
- **Alertmanager**: 128 MB memory
- **Nginx**: 64 MB memory
- **Jaeger**: 256 MB memory
- **Promtail**: 128 MB memory
- **Autoscaler**: 64 MB memory

### Gunicorn Configuration

- Location: `gunicorn.conf.py`
- Workers: 2 (configurable via `gunicorn -w`)
- Threads per worker: 4
- Worker class: gthread (threaded)
- Max requests per worker: 10,000 (jitter: 1,000) — forces periodic reload
- Timeout: 30s
- Graceful shutdown: 30s
- Keep-alive: 30s
- Log format: JSON (via python-json-logger)

## Quick Start

### Local Development

```bash
# Copy example and customize
cp .env.example .env

# Fill in any required values:
# - DATABASE_* (unless using Docker Compose defaults)
# - REDIS_* (unless using Docker Compose defaults)
# - RESEND_API_KEY (for email alerts)
# - ALERT_EMAIL_TO (for alert recipient)

# Start all services
docker-compose up

# Verify health
curl http://localhost/health
curl http://localhost/health/ready
curl http://localhost:3000  # Grafana
curl http://localhost:9090  # Prometheus
curl http://localhost:16686 # Jaeger
```

### Production Deployment

1. **Create `.env` from `.env.example`** and fill in all required variables:
   - `DATABASE_PASSWORD` — Strong, random password
   - `RESEND_API_KEY` — From https://resend.com
   - `ALERT_EMAIL_TO` — Valid email address
   - `API_KEY` — (optional) strong random key for API auth
   - `OTEL_EXPORTER_OTLP_ENDPOINT` — Point to your Jaeger instance

2. **Use Docker secrets** (optional, recommended):
   ```bash
   echo "your-strong-password" | docker secret create database_password -
   ```
   The app will prefer `/run/secrets/database_password` over `DATABASE_PASSWORD` env var.

3. **Configure resource limits** in `docker-compose.yml` based on your infrastructure.

4. **Scale replicas**:
   - Modify `MIN_REPLICAS` and `MAX_REPLICAS` in the `autoscaler` service environment.
   - Autoscaler monitors CPU and scales up/down automatically.

5. **Enable monitoring**:
   - Prometheus scrapes metrics from `app:5000/metrics`
   - Alertmanager requires valid SMTP credentials (via `RESEND_API_KEY`)
   - Loki aggregates logs from all containers via Promtail

### Monitoring & Alerts

**Accessing the monitoring stack** (all require docker-compose running):

- **Prometheus** (metrics): http://localhost:9090
- **Alertmanager** (alert routing): http://localhost:9093
- **Grafana** (dashboards): http://localhost:3000 (admin / admin)
- **Jaeger** (traces): http://localhost:16686
- **Loki** (logs): http://localhost:3100

**Alert email configuration**:

1. Create a Resend account: https://resend.com
2. Get an API key from the dashboard
3. Verify the sender domain (`alerts@hackathon.forgeopus.org` in alertmanager.yml)
4. Set `RESEND_API_KEY` and `ALERT_EMAIL_TO` in `.env`
5. Restart Alertmanager: `docker-compose restart alertmanager`

---

## Related Documentation

- **Architecture**: [/ARCHITECTURE.md](ARCHITECTURE.md)
- **Deployment**: [/DEPLOYMENT.md](DEPLOYMENT.md)
- **Reliability**: [/Reliability/RELIABILITY_ENGINEERING]({{ site.baseurl }}/Reliability/RELIABILITY_ENGINEERING)
- **Scalability**: [/scalability/]({{ site.baseurl }}/scalability/)
- **Incident Response**: [/incident-response/playbook]({{ site.baseurl }}/incident-response/playbook)
