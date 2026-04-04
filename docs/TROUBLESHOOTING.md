# Troubleshooting

## App won't start

**Symptom**: Container exits immediately or health check fails.

1. Check logs: `docker compose logs app`
2. Common causes:
   - Postgres not ready: ensure `depends_on` with `service_healthy` is set
   - Wrong database credentials: check `DATABASE_*` environment variables
   - Port conflict: another process on port 5000

## Database connection errors

**Symptom**: `peewee.OperationalError: could not connect to server`

1. Verify Postgres is running: `docker compose ps postgres`
2. Check connectivity: `docker compose exec postgres pg_isready`
3. Verify `DATABASE_HOST` matches the service name (`postgres`)
4. Check `max_connections` isn't exhausted: `docker compose exec postgres psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"`

## Bulk import fails

**Symptom**: `POST /users/bulk` returns 500

1. Check the CSV format: must have headers `id,username,email,created_at`
2. Timestamp format must be `YYYY-MM-DD HH:MM:SS`
3. IDs must be unique integers
4. If re-importing, existing IDs are skipped (`ON CONFLICT IGNORE`)

## Redis connection warnings

**Symptom**: Log lines with `"Redis unavailable, falling back to DB-only"`

1. This is expected behavior — the circuit breaker is working
2. Check Redis: `docker compose exec redis redis-cli ping`
3. If Redis is down, the app continues working with higher latency

## Tests fail locally

1. Ensure test database exists: `createdb hackathon_db_test`
2. Set environment: `DATABASE_NAME=hackathon_db_test DATABASE_USER=$(whoami) DATABASE_PASSWORD=""`
3. Run: `uv run pytest -x -v`

## High memory usage

1. Check per-service memory: `docker stats`
2. Postgres is the largest consumer — tuned for ~768MB
3. If OOM, reduce replicas: `docker compose up -d --scale app=1`
4. Check for connection pool leaks: ensure requests close connections

## Nginx 502 Bad Gateway

1. App containers might not be ready. Check: `docker compose ps app`
2. Nginx upstream might be stale. Restart Nginx: `docker compose restart nginx`
3. Check Nginx logs: `docker compose logs nginx`
