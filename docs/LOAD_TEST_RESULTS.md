# Load Test Results

## Setup

- **Stack**: Flask + Gunicorn (4 workers) x 3 replicas behind Nginx
- **Database**: PostgreSQL 16
- **Infrastructure**: Docker Compose on local machine

## How to Run

```bash
# Start the full stack
docker compose up --build -d

# Verify containers are running
docker ps

# Tier 1: 50 concurrent users for 30 seconds
k6 run --env SCENARIO=tier1 loadtests/k6_test.js

# Tier 2: Ramp to 200 concurrent users over 1m45s
k6 run --env SCENARIO=tier2 loadtests/k6_test.js
```

## Tier 1 — 50 Concurrent Users (Bronze)

| Metric | Value |
|---|---|
| Virtual Users | 50 |
| Duration | 30s |
| p95 Response Time | *TBD — paste from k6 output* |
| Error Rate | *TBD* |
| Total Requests | *TBD* |

## Tier 2 — 200 Concurrent Users (Silver)

| Metric | Value |
|---|---|
| Peak Virtual Users | 200 |
| Duration | 1m45s (ramp up + sustain + ramp down) |
| p95 Response Time | *TBD — must be < 3s* |
| Error Rate | *TBD — must be < 5%* |
| Total Requests | *TBD* |

## Architecture

```
k6 --> Nginx (:80) --> Flask app-1 (:5000)
                   --> Flask app-2 (:5000)
                   --> Flask app-3 (:5000)
                           |
                       PostgreSQL (:5432)
```

## Observations

*Fill in after running tests — note any bottlenecks, latency spikes, or error patterns.*
