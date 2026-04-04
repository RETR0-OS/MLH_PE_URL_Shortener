import logging
import os
import subprocess
import time

import docker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# --- Configuration ---
PROJECT_NAME = os.environ["COMPOSE_PROJECT_NAME"]
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 10))
COOLDOWN = int(os.environ.get("COOLDOWN", 60))
SCALE_UP_CPU = float(os.environ.get("SCALE_UP_CPU", 70))
SCALE_DOWN_CPU = float(os.environ.get("SCALE_DOWN_CPU", 30))
MIN_REPLICAS = int(os.environ.get("MIN_REPLICAS", 2))
MAX_REPLICAS = int(os.environ.get("MAX_REPLICAS", 5))


def get_cpu_percent(stats: dict) -> float | None:
    """
    Compute CPU usage percentage from a single container stats snapshot.

    Returns None when precpu_stats contains zero values (first-poll cold start),
    which Docker signals by setting all counters to 0.
    """
    cpu_stats = stats.get("cpu_stats", {})
    precpu_stats = stats.get("precpu_stats", {})

    current_total = cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
    previous_total = precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
    current_system = cpu_stats.get("system_cpu_usage", 0)
    previous_system = precpu_stats.get("system_cpu_usage", 0)

    # Skip containers where precpu_stats hasn't been populated yet
    if previous_total == 0 or previous_system == 0:
        return None

    cpu_delta = current_total - previous_total
    system_cpu_delta = current_system - previous_system

    if system_cpu_delta <= 0:
        return None

    # Prefer online_cpus when available; fall back to len(percpu_usage)
    percpu = cpu_stats.get("cpu_usage", {}).get("percpu_usage")
    num_cpus = cpu_stats.get("online_cpus") or (len(percpu) if percpu else 1)

    return (cpu_delta / system_cpu_delta) * num_cpus * 100.0


def scale_app(client: docker.DockerClient, replicas: int) -> None:
    """Invoke docker compose to scale the app service to the given replica count."""
    cmd = [
        "docker", "compose",
        "-p", PROJECT_NAME,
        "up", "-d",
        "--scale", f"app={replicas}",
        "--no-recreate",
    ]
    logger.info("Running scale command: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        logger.error("Scale command failed (exit %d): %s", result.returncode, result.stderr.strip())
    else:
        logger.info("Scale command succeeded.")


def reload_nginx(client: docker.DockerClient) -> None:
    """Find the nginx container for this project and reload its config."""
    nginx_containers = client.containers.list(filters={
        "label": [
            "com.docker.compose.service=nginx",
            f"com.docker.compose.project={PROJECT_NAME}",
        ]
    })

    if not nginx_containers:
        logger.warning("No nginx container found for project '%s'; skipping reload.", PROJECT_NAME)
        return

    nginx = nginx_containers[0]
    logger.info("Reloading nginx (container: %s).", nginx.name)
    exit_code, output = nginx.exec_run("nginx -s reload")
    if exit_code != 0:
        logger.error("nginx reload failed (exit %d): %s", exit_code, output.decode().strip())
    else:
        logger.info("nginx reloaded successfully.")


def poll(client: docker.DockerClient, last_scale_time: float) -> float:
    """
    Single poll cycle. Returns the (possibly updated) last_scale_time.
    All exceptions are caught so the caller's main loop stays alive.
    """
    try:
        app_containers = client.containers.list(filters={
            "label": [
                "com.docker.compose.service=app",
                f"com.docker.compose.project={PROJECT_NAME}",
            ]
        })

        current_replicas = len(app_containers)

        if current_replicas == 0:
            logger.warning("No app containers found; skipping cycle.")
            return last_scale_time

        # Collect per-container CPU percentages
        cpu_samples: list[float] = []
        for container in app_containers:
            try:
                stats = container.stats(stream=False)
                pct = get_cpu_percent(stats)
                if pct is not None:
                    cpu_samples.append(pct)
            except Exception as exc:
                logger.warning("Could not read stats for container %s: %s", container.name, exc)

        now = time.time()
        in_cooldown = (now - last_scale_time) < COOLDOWN
        cooldown_remaining = max(0, COOLDOWN - (now - last_scale_time))

        if not cpu_samples:
            logger.info(
                "status | replicas=%d  avg_cpu=n/a (warming up)  cooldown=%s",
                current_replicas,
                f"{cooldown_remaining:.0f}s remaining" if in_cooldown else "ready",
            )
            return last_scale_time

        avg_cpu = sum(cpu_samples) / len(cpu_samples)

        logger.info(
            "status | replicas=%d  avg_cpu=%.1f%%  cooldown=%s",
            current_replicas,
            avg_cpu,
            f"{cooldown_remaining:.0f}s remaining" if in_cooldown else "ready",
        )

        if avg_cpu > SCALE_UP_CPU and current_replicas < MAX_REPLICAS and not in_cooldown:
            new_replicas = current_replicas + 1
            logger.info(
                "SCALE UP: %.1f%% > %.1f%% threshold — %d -> %d replicas",
                avg_cpu, SCALE_UP_CPU, current_replicas, new_replicas,
            )
            scale_app(client, new_replicas)
            time.sleep(2)
            reload_nginx(client)
            return now

        if avg_cpu < SCALE_DOWN_CPU and current_replicas > MIN_REPLICAS and not in_cooldown:
            new_replicas = current_replicas - 1
            logger.info(
                "SCALE DOWN: %.1f%% < %.1f%% threshold — %d -> %d replicas",
                avg_cpu, SCALE_DOWN_CPU, current_replicas, new_replicas,
            )
            scale_app(client, new_replicas)
            time.sleep(2)
            reload_nginx(client)
            return now

    except Exception as exc:
        logger.error("Unhandled exception in poll cycle: %s", exc, exc_info=True)

    return last_scale_time


def main() -> None:
    logger.info(
        "Autoscaler starting — project=%s  interval=%ds  cooldown=%ds  "
        "scale_up=%.0f%%  scale_down=%.0f%%  min=%d  max=%d",
        PROJECT_NAME, POLL_INTERVAL, COOLDOWN,
        SCALE_UP_CPU, SCALE_DOWN_CPU, MIN_REPLICAS, MAX_REPLICAS,
    )

    client = None
    for attempt in range(1, 6):
        try:
            client = docker.from_env()
            client.ping()
            logger.info("Connected to Docker daemon.")
            break
        except Exception as exc:
            logger.warning("Docker connection attempt %d/5 failed: %s", attempt, exc)
            time.sleep(5)
    if client is None:
        logger.critical("Could not connect to Docker daemon after 5 attempts. Exiting.")
        raise SystemExit(1)

    last_scale_time: float = 0.0

    while True:
        last_scale_time = poll(client, last_scale_time)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
