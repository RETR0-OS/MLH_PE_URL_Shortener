# Failure Modes & Chaos Testing

> Last tested: Apr 4, 2026 — Docker Compose stack on macOS

---

## Chaos Test Script

Run the chaos test suite:

```bash
./scripts/chaos_test.sh
```

The script requires a running Docker Compose stack (`docker compose up -d`).

---

## Test Results

### Test 1: Kill a Single App Container

| Detail | Result |
|---|---|
| **Action** | `docker kill <app-container-1>` |
| **Expected** | Remaining containers serve traffic; killed container restarts |
| **Recovery** | **2 seconds** |
| **Outcome** | PASS — Nginx routes to surviving replica(s), Docker restarts the killed container |

### Test 2: Kill ALL App Containers

| Detail | Result |
|---|---|
| **Action** | Kill every app container simultaneously |
| **Expected** | Docker restart policy + autoscaler restores containers |
| **Recovery** | **~20 seconds** (Docker restart policy + container healthcheck) |
| **Outcome** | PASS — Full recovery, requests resume after containers pass healthcheck |

### Test 3: Kill the Database (PostgreSQL)

| Detail | Result |
|---|---|
| **Action** | `docker kill <postgres-container>` |
| **Expected** | PostgreSQL restarts via `restart: unless-stopped`; app reconnects via connection pool |
| **Recovery** | **< 1 second** (DB restart) + connection pool re-establishes |
| **Outcome** | PASS — Service recovered after DB kill |

### Test 4: Kill the Nginx Load Balancer

| Detail | Result |
|---|---|
| **Action** | `docker kill <nginx-container>` |
| **Expected** | Nginx restarts via Docker restart policy |
| **Recovery** | Nginx restarts automatically |
| **Outcome** | PASS — Load balancer restored, traffic resumes |

### Test 5: Graceful Failure on Bad Input

| Request | Expected | Actual | Outcome |
|---|---|---|---|
| `GET /users/not-an-integer` | 404 | 404 | PASS |
| `POST /users {"username": 12345}` | 400 | 400 | PASS |
| `POST /urls {}` | 400 | 400 | PASS |
| `GET /urls/NONEXISTENT/redirect` | 404 | 404 | PASS |
| `POST /events {"garbage": true}` | 400 | 400 | PASS |
| `GET /nonexistent-path` | 404 + JSON | 404 + JSON | PASS |

All error responses are JSON with an `"error"` key — no stack traces or HTML error pages are exposed to clients.

---

## Failure Modes Reference

### 1. App Container Crash

| Aspect | Behavior |
|---|---|
| **Cause** | OOM, unhandled exception, SIGKILL |
| **Detection** | Docker healthcheck fails (`/health` endpoint) |
| **Auto-recovery** | `restart: unless-stopped` policy restarts the container |
| **Impact** | Other replicas continue serving; Nginx's `least_conn` routes around the dead container |
| **Recovery time** | 2-10 seconds |

### 2. All App Containers Down

| Aspect | Behavior |
|---|---|
| **Cause** | Simultaneous crash, host resource exhaustion |
| **Detection** | Nginx returns 502 Bad Gateway |
| **Auto-recovery** | Docker restart policy + autoscaler brings replicas back |
| **Impact** | Complete service outage until at least one container restarts and passes healthcheck |
| **Recovery time** | 15-30 seconds |

### 3. Database (PostgreSQL) Down

| Aspect | Behavior |
|---|---|
| **Cause** | Container crash, disk full, OOM |
| **Detection** | Peewee raises `OperationalError` on queries |
| **Auto-recovery** | `restart: unless-stopped` restarts PostgreSQL; `PooledPostgresqlDatabase` reconnects automatically |
| **Impact** | All write operations fail; reads fail; `/health` still returns 200 (app is alive, DB is not) |
| **Recovery time** | 5-15 seconds (depends on PostgreSQL WAL recovery) |

### 4. Nginx Load Balancer Down

| Aspect | Behavior |
|---|---|
| **Cause** | Container crash, config error |
| **Detection** | Port 80 stops responding |
| **Auto-recovery** | `restart: unless-stopped` restarts the container |
| **Impact** | Complete inbound traffic loss (Nginx is the single entry point) |
| **Recovery time** | 2-5 seconds |

### 5. Bad User Input

| Aspect | Behavior |
|---|---|
| **Cause** | Invalid JSON, missing required fields, wrong types |
| **Detection** | Input validation in route handlers |
| **Response** | `400 Bad Request` or `422 Unprocessable Entity` with `{"error": "..."}` |
| **Impact** | None — bad requests are rejected cleanly, valid requests unaffected |

### 6. Duplicate Data (Uniqueness Violation)

| Aspect | Behavior |
|---|---|
| **Cause** | Duplicate username, email, or short_code |
| **Detection** | Peewee `IntegrityError` from PostgreSQL unique constraint |
| **Response** | `409 Conflict` with descriptive error message |
| **Impact** | None — transaction is rolled back, no data corruption |

### 7. Resource Not Found

| Aspect | Behavior |
|---|---|
| **Cause** | Invalid ID, deleted resource, nonexistent short code |
| **Detection** | `Model.DoesNotExist` exception |
| **Response** | `404 Not Found` with `{"error": "..."}` |
| **Impact** | None |

### 8. Connection Pool Exhaustion

| Aspect | Behavior |
|---|---|
| **Cause** | Spike in concurrent requests exceeding pool size (5 per worker) |
| **Detection** | Peewee raises connection timeout error |
| **Response** | `500 Internal Server Error` |
| **Mitigation** | `stale_timeout=300` clears idle connections; autoscaler adds replicas under load |

### 9. Inactive URL Redirect

| Aspect | Behavior |
|---|---|
| **Cause** | URL's `is_active` set to `false` |
| **Detection** | Route handler checks `url.is_active` before redirecting |
| **Response** | `410 Gone` with `{"error": "URL is inactive"}` |
| **Impact** | None — active URLs continue to redirect normally |

---

## Resilience Mechanisms

| Mechanism | Config |
|---|---|
| **Docker restart policy** | `restart: unless-stopped` on all services |
| **Healthcheck** | `HEALTHCHECK` in Dockerfile polls `/health` every 10s |
| **Connection pooling** | `PooledPostgresqlDatabase` with auto-reconnect (`reuse_if_open=True`) |
| **Autoscaler** | CPU-based, scales 2→5 replicas, no cooldown on scale-up |
| **Load balancing** | Nginx `least_conn` routes around unhealthy upstreams |
| **Atomic transactions** | `db.atomic()` for short_code generation prevents race conditions |
| **Cascade deletes** | `on_delete="CASCADE"` ensures referential integrity on user/URL deletion |
| **JSON error handlers** | Flask `@errorhandler(404)` and `@errorhandler(500)` return JSON, never HTML |
