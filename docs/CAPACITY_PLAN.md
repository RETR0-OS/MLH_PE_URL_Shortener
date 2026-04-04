# Capacity Plan

## Hardware Envelope

- **Machine**: 2 vCPUs, 4 GB RAM
- **OS overhead**: ~500 MB reserved
- **Docker overhead**: ~200 MB reserved
- **Available for services**: ~3.3 GB

## Service Memory Budget

| Service | Instances | Per-Instance | Total |
|---------|-----------|-------------|-------|
| App (Gunicorn) | 2-3 | 384 MB | 768-1152 MB |
| PostgreSQL | 1 | 768 MB | 768 MB |
| Redis | 1 | 160 MB | 160 MB |
| Nginx | 1 | 64 MB | 64 MB |
| Prometheus | 1 | 256 MB | 256 MB |
| Loki | 1 | 256 MB | 256 MB |
| Grafana | 1 | 256 MB | 256 MB |
| Alertmanager | 1 | 128 MB | 128 MB |
| **Total (2 app replicas)** | | | **~2.66 GB** |
| **Total (3 app replicas)** | | | **~3.04 GB** |

3 app replicas is the practical ceiling on this hardware.

## Observed Performance (per replica)

| Metric | Value |
|--------|-------|
| Throughput | ~100-150 req/s |
| p50 latency | <50 ms |
| p95 latency | <200 ms (cached reads) |
| p95 latency | <500 ms (DB reads) |
| Max concurrent | 8 (2 workers x 4 threads) |

## Scaling Formula

```
replicas = ceil(target_rps / per_replica_rps)
```

Example: For 300 req/s sustained, need `ceil(300/125) = 3` replicas.

## Load Test Reference Points

| Test | VUs | Duration | Expected p95 | Expected Error Rate |
|------|-----|----------|--------------|-------------------|
| Smoke | 50 | 30s | <2s | <5% |
| Sustained | 200 | 90s | <3s | <5% |
| Stress | 500 | 130s | — | <5% |
| Soak | 50 | 5m | <2s | <1% |

## Scaling Limits on This Hardware

- **Horizontal**: Max 3 app replicas (limited by RAM)
- **Vertical**: Gunicorn already at 2 workers (limited by 2 vCPU)
- **Database**: Single Postgres instance; read replicas not feasible on single node
- **Cache**: Redis at 128 MB; increase requires reducing other services

## Growth Recommendations

To scale beyond this hardware:
1. Move to a 4 vCPU / 8 GB machine: supports 5+ replicas and larger DB cache
2. Add a read replica for Postgres on a second node
3. Consider PgBouncer for centralized connection pooling
4. Move observability stack to a separate node
