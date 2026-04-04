# Service Level Objectives (SLOs)

## Availability

**Target**: 99.9% uptime (measured via `/health/ready`)

- **Measurement**: Percentage of successful `/health/ready` responses over a rolling 7-day window.
- **Error budget**: 0.1% = ~10 minutes of downtime per week.
- **Enforcement**: Docker Swarm auto-restarts failed containers. Nginx retries on failed replicas. Multiple app replicas prevent single-point failures.

## Latency

**Target**: p95 < 500ms for reads, p95 < 1s for writes

| Endpoint Type | p50 Target | p95 Target | p99 Target |
|--------------|-----------|-----------|-----------|
| Health checks | <10ms | <50ms | <100ms |
| GET (single resource) | <30ms | <200ms | <500ms |
| GET (list) | <100ms | <500ms | <1s |
| POST (create) | <50ms | <500ms | <1s |
| PUT (update) | <50ms | <500ms | <1s |
| POST (bulk import) | <5s | <10s | <30s |

- **Measurement**: `flask_http_request_duration_seconds` histogram in Prometheus.
- **Alert**: `HighLatency` fires when p95 > 3s for 2 minutes.

## Error Rate

**Target**: < 1% 5xx errors under normal load

- **Measurement**: `rate(flask_http_request_total{status=~"5.."}[5m]) / rate(flask_http_request_total[5m])`.
- **Alert**: `HighErrorRate` fires when 5xx rate > 10% for 2 minutes.
- **Normal load**: defined as <= 200 concurrent users on the 2 vCPU / 4 GB host.

## Saturation

**Target**: No resource exhaustion under normal load

- **CPU**: App containers stay below 75% CPU utilization.
- **Memory**: No OOM kills during normal operation.
- **DB connections**: Pool usage stays below 80% of `max_connections`.
- **Redis memory**: Stays below 128MB cap (LRU eviction handles overflow).
