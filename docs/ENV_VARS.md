# Environment Variables

## Application

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_NAME` | PostgreSQL database name | `hackathon_db` | No |
| `DATABASE_HOST` | PostgreSQL host | `localhost` | No |
| `DATABASE_PORT` | PostgreSQL port | `5432` | No |
| `DATABASE_USER` | PostgreSQL user | `postgres` | No |
| `DATABASE_PASSWORD` | PostgreSQL password | `postgres` | No |
| `REDIS_HOST` | Redis host | `redis` | No |
| `REDIS_PORT` | Redis port | `6379` | No |
| `REDIS_PASSWORD` | Redis password | (none) | No |
| `FLASK_DEBUG` | Enable Flask debug mode | `false` | No |

## Docker Secrets (Swarm mode)

When running in Docker Swarm, credentials can be provided via secrets instead of environment variables. The app reads from `/run/secrets/{name}` first, falling back to environment variables.

| Secret Name | Overrides |
|-------------|-----------|
| `database_name` | `DATABASE_NAME` |
| `database_host` | `DATABASE_HOST` |
| `database_port` | `DATABASE_PORT` |
| `database_user` | `DATABASE_USER` |
| `database_password` | `DATABASE_PASSWORD` |
| `redis_host` | `REDIS_HOST` |
| `redis_port` | `REDIS_PORT` |
| `redis_password` | `REDIS_PASSWORD` |

## PostgreSQL

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_DB` | Database to create on startup | `hackathon_db` |
| `POSTGRES_USER` | Superuser name | `postgres` |
| `POSTGRES_PASSWORD` | Superuser password | `postgres` |

## Monitoring

| Variable | Description | Default |
|----------|-------------|---------|
| `GF_SECURITY_ADMIN_USER` | Grafana admin username | `admin` |
| `GF_SECURITY_ADMIN_PASSWORD` | Grafana admin password | `admin` |
| `DISCORD_WEBHOOK_URL` | Alertmanager Discord webhook | (none) |
