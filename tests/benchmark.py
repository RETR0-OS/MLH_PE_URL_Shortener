"""
Performance benchmark suite for the URL Shortener.

Measures latency (avg, p50, p95, p99, min, max) and throughput (req/s)
across all major endpoints. Outputs a JSON report for comparison.

Usage:
    uv run python tests/benchmark.py [--output results.json]
"""
import json
import math
import os
import statistics
import sys
import time

os.environ.setdefault("DATABASE_NAME", "hackathon_db_test")
os.environ.setdefault("DATABASE_HOST", "localhost")
os.environ.setdefault("DATABASE_PORT", "5432")
os.environ.setdefault("DATABASE_USER", os.environ.get("USER", "postgres"))
os.environ.setdefault("DATABASE_PASSWORD", "")

from app import create_app
from app.database import db
from app.models.event import Event
from app.models.url import Url
from app.models.user import User

MODELS = [User, Url, Event]

SEED_USERS = 50
SEED_URLS_PER_USER = 4
ITERATIONS = 200
WARMUP = 10


def percentile(data, p):
    """Return the p-th percentile of sorted data."""
    if not data:
        return 0.0
    k = (len(data) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return data[int(k)]
    return data[f] * (c - k) + data[c] * (k - f)


def measure(client, method, path, **kwargs):
    """Execute a single request and return elapsed ms."""
    fn = getattr(client, method)
    start = time.perf_counter()
    resp = fn(path, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return resp, elapsed_ms


def run_benchmark(client, name, method, path, iterations=ITERATIONS, **kwargs):
    """Run a benchmark for a single endpoint and return stats dict."""
    for _ in range(WARMUP):
        measure(client, method, path, **kwargs)

    latencies = []
    status_counts = {}
    wall_start = time.perf_counter()

    for _ in range(iterations):
        resp, ms = measure(client, method, path, **kwargs)
        latencies.append(ms)
        code = resp.status_code
        status_counts[code] = status_counts.get(code, 0) + 1

    wall_elapsed = time.perf_counter() - wall_start
    latencies.sort()

    return {
        "name": name,
        "method": method.upper(),
        "path": path,
        "iterations": iterations,
        "wall_time_s": round(wall_elapsed, 4),
        "throughput_rps": round(iterations / wall_elapsed, 2) if wall_elapsed > 0 else 0,
        "latency_ms": {
            "avg": round(statistics.mean(latencies), 3),
            "p50": round(percentile(latencies, 50), 3),
            "p95": round(percentile(latencies, 95), 3),
            "p99": round(percentile(latencies, 99), 3),
            "min": round(min(latencies), 3),
            "max": round(max(latencies), 3),
            "stdev": round(statistics.stdev(latencies), 3) if len(latencies) > 1 else 0,
        },
        "status_codes": status_counts,
    }


def seed_data(client):
    """Populate test data and return references for benchmarks."""
    user_ids = []
    url_ids = []

    for i in range(SEED_USERS):
        resp = client.post(
            "/users",
            data=json.dumps({"username": f"bench_u{i}", "email": f"bench{i}@test.com"}),
            content_type="application/json",
        )
        user = resp.get_json()
        user_ids.append(user["id"])

    for uid in user_ids:
        for j in range(SEED_URLS_PER_USER):
            resp = client.post(
                "/urls",
                data=json.dumps({
                    "user_id": uid,
                    "original_url": f"https://example.com/{uid}/{j}",
                    "title": f"Bench URL {uid}-{j}",
                }),
                content_type="application/json",
            )
            url_data = resp.get_json()
            url_ids.append(url_data["id"])

    return user_ids, url_ids


def truncate_tables():
    with db.connection_context():
        db.execute_sql(
            'TRUNCATE TABLE "events", "urls", "users" RESTART IDENTITY CASCADE'
        )


def main():
    output_file = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    truncate_tables()

    print(f"Seeding {SEED_USERS} users, {SEED_USERS * SEED_URLS_PER_USER} URLs...")
    user_ids, url_ids = seed_data(client)
    print(f"Seeded. Running benchmarks ({ITERATIONS} iterations, {WARMUP} warmup)...\n")

    results = []

    # 1. GET /health
    results.append(run_benchmark(client, "health", "get", "/health"))

    # 2. GET /health/ready
    results.append(run_benchmark(client, "health_ready", "get", "/health/ready"))

    # 3. GET /users (list)
    results.append(run_benchmark(client, "list_users", "get", "/users"))

    # 4. GET /users/:id (single)
    target_user = user_ids[0]
    results.append(run_benchmark(client, "get_user", "get", f"/users/{target_user}"))

    # 5. POST /users (create)
    create_user_counter = [0]
    def bench_create_user():
        i = create_user_counter[0]
        create_user_counter[0] += 1
        return client.post(
            "/users",
            data=json.dumps({"username": f"newu_{i}", "email": f"newu_{i}@test.com"}),
            content_type="application/json",
        )

    latencies = []
    status_counts = {}
    for _ in range(WARMUP):
        bench_create_user()
    wall_start = time.perf_counter()
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        resp = bench_create_user()
        ms = (time.perf_counter() - start) * 1000
        latencies.append(ms)
        code = resp.status_code
        status_counts[code] = status_counts.get(code, 0) + 1
    wall_elapsed = time.perf_counter() - wall_start
    latencies.sort()
    results.append({
        "name": "create_user",
        "method": "POST",
        "path": "/users",
        "iterations": ITERATIONS,
        "wall_time_s": round(wall_elapsed, 4),
        "throughput_rps": round(ITERATIONS / wall_elapsed, 2),
        "latency_ms": {
            "avg": round(statistics.mean(latencies), 3),
            "p50": round(percentile(latencies, 50), 3),
            "p95": round(percentile(latencies, 95), 3),
            "p99": round(percentile(latencies, 99), 3),
            "min": round(min(latencies), 3),
            "max": round(max(latencies), 3),
            "stdev": round(statistics.stdev(latencies), 3) if len(latencies) > 1 else 0,
        },
        "status_codes": status_counts,
    })

    # 6. GET /urls (list)
    results.append(run_benchmark(client, "list_urls", "get", "/urls"))

    # 7. GET /urls?user_id=X (filtered list)
    results.append(run_benchmark(client, "list_urls_filtered", "get", f"/urls?user_id={user_ids[0]}"))

    # 8. GET /urls/:id (single, tests cache path)
    target_url = url_ids[0]
    results.append(run_benchmark(client, "get_url", "get", f"/urls/{target_url}"))

    # 9. POST /urls (create)
    create_url_counter = [0]
    def bench_create_url():
        i = create_url_counter[0]
        create_url_counter[0] += 1
        uid = user_ids[i % len(user_ids)]
        return client.post(
            "/urls",
            data=json.dumps({
                "user_id": uid,
                "original_url": f"https://bench.com/{i}",
                "title": f"Bench {i}",
            }),
            content_type="application/json",
        )

    latencies = []
    status_counts = {}
    for _ in range(WARMUP):
        bench_create_url()
    wall_start = time.perf_counter()
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        resp = bench_create_url()
        ms = (time.perf_counter() - start) * 1000
        latencies.append(ms)
        code = resp.status_code
        status_counts[code] = status_counts.get(code, 0) + 1
    wall_elapsed = time.perf_counter() - wall_start
    latencies.sort()
    results.append({
        "name": "create_url",
        "method": "POST",
        "path": "/urls",
        "iterations": ITERATIONS,
        "wall_time_s": round(wall_elapsed, 4),
        "throughput_rps": round(ITERATIONS / wall_elapsed, 2),
        "latency_ms": {
            "avg": round(statistics.mean(latencies), 3),
            "p50": round(percentile(latencies, 50), 3),
            "p95": round(percentile(latencies, 95), 3),
            "p99": round(percentile(latencies, 99), 3),
            "min": round(min(latencies), 3),
            "max": round(max(latencies), 3),
            "stdev": round(statistics.stdev(latencies), 3) if len(latencies) > 1 else 0,
        },
        "status_codes": status_counts,
    })

    # 10. PUT /urls/:id (update)
    results.append(run_benchmark(
        client, "update_url", "put", f"/urls/{target_url}",
        data=json.dumps({"title": "Updated Title"}),
        content_type="application/json",
    ))

    # 11. GET /events (list)
    results.append(run_benchmark(client, "list_events", "get", "/events"))

    # 12. PUT /users/:id (update)
    results.append(run_benchmark(
        client, "update_user", "put", f"/users/{target_user}",
        data=json.dumps({"username": f"updated_bench_u0"}),
        content_type="application/json",
    ))

    # 13. Bulk import
    import io
    csv_rows = "id,username,email,created_at\n"
    base_id = 90000
    for i in range(100):
        csv_rows += f"{base_id + i},bulk_{i},bulk_{i}@t.com,2025-01-01 00:00:00\n"
    bulk_latencies = []
    for trial in range(20):
        with db.connection_context():
            db.execute_sql(f"DELETE FROM users WHERE id >= {base_id}")
        csv_file = (io.BytesIO(csv_rows.encode()), "data.csv")
        start = time.perf_counter()
        resp = client.post(
            "/users/bulk",
            data={"file": csv_file},
            content_type="multipart/form-data",
        )
        ms = (time.perf_counter() - start) * 1000
        bulk_latencies.append(ms)
    bulk_latencies.sort()
    results.append({
        "name": "bulk_import_100rows",
        "method": "POST",
        "path": "/users/bulk",
        "iterations": 20,
        "wall_time_s": round(sum(bulk_latencies) / 1000, 4),
        "throughput_rps": round(20 / (sum(bulk_latencies) / 1000), 2),
        "latency_ms": {
            "avg": round(statistics.mean(bulk_latencies), 3),
            "p50": round(percentile(bulk_latencies, 50), 3),
            "p95": round(percentile(bulk_latencies, 95), 3),
            "p99": round(percentile(bulk_latencies, 99), 3),
            "min": round(min(bulk_latencies), 3),
            "max": round(max(bulk_latencies), 3),
            "stdev": round(statistics.stdev(bulk_latencies), 3) if len(bulk_latencies) > 1 else 0,
        },
        "status_codes": {200: 20},
    })

    # Print report
    print(f"{'Endpoint':<28} {'Method':<7} {'Avg ms':>8} {'p50 ms':>8} {'p95 ms':>8} {'p99 ms':>8} {'Min ms':>8} {'Max ms':>8} {'RPS':>10}")
    print("-" * 110)
    for r in results:
        lat = r["latency_ms"]
        print(
            f"{r['name']:<28} {r['method']:<7} {lat['avg']:>8.2f} {lat['p50']:>8.2f} "
            f"{lat['p95']:>8.2f} {lat['p99']:>8.2f} {lat['min']:>8.2f} {lat['max']:>8.2f} "
            f"{r['throughput_rps']:>10.1f}"
        )
    print()

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "seed_users": SEED_USERS,
            "seed_urls_per_user": SEED_URLS_PER_USER,
            "iterations": ITERATIONS,
            "warmup": WARMUP,
        },
        "results": results,
    }

    if output_file:
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Results written to {output_file}")

    return report


if __name__ == "__main__":
    main()
