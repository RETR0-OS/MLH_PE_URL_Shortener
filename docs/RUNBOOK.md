# Runbook

Operational runbook for the URL Shortener service. Each section corresponds to an alert from Alertmanager.

---

## ServiceDown

**Severity**: Critical
**Fires when**: `up == 0` for 1 minute

### What to check
1. Open Grafana > URL Shortener dashboard > check if traffic panel shows zero.
2. Run `docker service ps urlshort_app` to see replica status.
3. Check `docker service logs urlshort_app --tail 50` for crash logs.

### Mitigation
1. If a replica crashed, Swarm auto-restarts it. Wait 30 seconds and verify.
2. If all replicas are down, check if Postgres is reachable: `docker exec -it $(docker ps -q -f name=postgres) pg_isready`.
3. If Postgres is down, check `docker service logs urlshort_postgres`.
4. Force redeploy if stuck: `docker service update --force urlshort_app`.

### Escalation
If the service does not recover within 5 minutes, investigate OOM kills via `docker inspect` and adjust memory limits.

---

## HighErrorRate

**Severity**: Warning
**Fires when**: 5xx rate > 10% for 2 minutes

### What to check
1. Open Grafana > Error Rate panel. Identify which endpoints are failing.
2. Check Loki logs: `{job="app"} |= "ERROR"` or filter by `status=~"5.."`.
3. Look for database connection errors, Redis timeouts, or unhandled exceptions.

### Mitigation
1. If DB connection errors: check Postgres health, verify `max_connections` not exhausted.
2. If Redis errors: check Redis health. The circuit breaker should have engaged — verify in logs.
3. If a specific endpoint fails: check recent deployments for regressions.
4. Scale up if under load: `docker service scale urlshort_app=3`.

### Escalation
If error rate persists after scaling, rollback: `docker service update --rollback urlshort_app`.

---

## HighLatency

**Severity**: Warning
**Fires when**: p95 latency > 3 seconds for 2 minutes

### What to check
1. Open Grafana > Latency panel. Check p50/p95/p99 trends.
2. Check if traffic spiked (Traffic panel).
3. Check Redis cache hit ratio — a cold cache increases DB load.
4. Check Postgres slow queries via `pg_stat_statements`.

### Mitigation
1. Scale app replicas: `docker service scale urlshort_app=3`.
2. Warm the Redis cache by hitting popular URLs.
3. Check for long-running queries and add indexes if needed.
4. Verify Nginx keepalive is working (check upstream response times in Nginx logs).

### Escalation
If latency does not improve with 3 replicas, the bottleneck is likely Postgres on this hardware. Document in the capacity plan.

---

## RedisDown

**Severity**: Warning
**Fires when**: `redis_connection_errors_total` increasing for 1 minute

### What to check
1. Run `docker service ps urlshort_redis` to check Redis replica status.
2. Check Redis memory usage: `docker exec $(docker ps -q -f name=redis) redis-cli info memory`.
3. Check app logs for circuit breaker activation messages.

### Mitigation
1. The circuit breaker automatically falls back to DB-only mode. No user-facing errors expected.
2. If Redis is OOM killed, it will auto-restart. Wait 30 seconds.
3. If Redis is stuck, force restart: `docker service update --force urlshort_redis`.

### Escalation
If Redis repeatedly OOM-kills, increase the `maxmemory` setting or review cache TTLs.

---

## General Rollback Procedure

```bash
# View update history
docker service inspect urlshort_app --pretty

# Rollback to previous version
docker service update --rollback urlshort_app

# Verify rollback succeeded
docker service ps urlshort_app
curl http://localhost:5000/health/ready
```
