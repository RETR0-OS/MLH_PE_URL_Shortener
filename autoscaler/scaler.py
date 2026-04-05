#!/usr/bin/env python3
"""
CPU-based autoscaler for Docker Compose services.

Monitors average CPU utilisation (relative to each container's CPU limit)
across all running replicas of the target service and scales up or down
within configured bounds.

Scale-up  : triggered when avg CPU >= SCALE_UP_THRESHOLD  for SCALE_UP_WINDOW  consecutive polls
Scale-down: triggered when avg CPU <= SCALE_DOWN_THRESHOLD for SCALE_DOWN_WINDOW consecutive polls

Separate cooldown timers for scale-up and scale-down prevent flapping.
"""

import os
import time
import logging
import docker
from docker.errors import DockerException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("autoscaler")

# ── Configuration (all overridable via environment variables) ─────────────────
SERVICE_NAME = os.environ.get("SERVICE_NAME", "app")
MIN_REPLICAS = int(os.environ.get("MIN_REPLICAS", "2"))
MAX_REPLICAS = int(os.environ.get("MAX_REPLICAS", "5"))
SCALE_UP_THRESHOLD = float(
    os.environ.get("SCALE_UP_THRESHOLD", "70.0")
)  # % of CPU limit
SCALE_DOWN_THRESHOLD = float(
    os.environ.get("SCALE_DOWN_THRESHOLD", "30.0")
)  # % of CPU limit
CPU_LIMIT_CORES = float(
    os.environ.get("CPU_LIMIT_CORES", "0.75")
)  # must match compose cpus
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "10"))  # seconds

# Consecutive polls above/below threshold before acting
SCALE_UP_WINDOW = int(
    os.environ.get("SCALE_UP_WINDOW", "2")
)  # 2 × 10s = 20 s sustained
SCALE_DOWN_WINDOW = int(
    os.environ.get("SCALE_DOWN_WINDOW", "6")
)  # 6 × 10s = 60 s sustained

# Minimum seconds between successive scale events (per direction)
SCALE_UP_COOLDOWN = int(os.environ.get("SCALE_UP_COOLDOWN", "60"))
SCALE_DOWN_COOLDOWN = int(os.environ.get("SCALE_DOWN_COOLDOWN", "120"))

# ── Docker client ─────────────────────────────────────────────────────────────
client = docker.from_env()


# ── Project name detection ────────────────────────────────────────────────────
def detect_project_name() -> str:
    """
    Read the Compose project name from a running app container's label.
    Falls back to the COMPOSE_PROJECT_NAME env var, then 'app'.
    """
    env_val = os.environ.get("COMPOSE_PROJECT_NAME", "")
    containers = client.containers.list(
        filters={"label": f"com.docker.compose.service={SERVICE_NAME}"}
    )
    if containers:
        return containers[0].labels.get("com.docker.compose.project", env_val or "app")
    return env_val or "app"


# ── Container helpers ─────────────────────────────────────────────────────────
def get_app_containers(project: str) -> list:
    """Return all *running* containers for the target service."""
    return client.containers.list(
        filters={
            "label": [
                f"com.docker.compose.project={project}",
                f"com.docker.compose.service={SERVICE_NAME}",
            ],
            "status": "running",
        }
    )


def container_cpu_percent(container) -> float:
    """
    Calculate CPU utilisation as a percentage of the container's CPU limit.

    Docker stats gives us nanoseconds of CPU time consumed (total_usage delta)
    vs nanoseconds available to the whole system (system_cpu_usage delta).
    We convert that fraction to cores used, then normalise against the limit.
    """
    stats = container.stats(stream=False)

    cpu_delta = (
        stats["cpu_stats"]["cpu_usage"]["total_usage"]
        - stats["precpu_stats"]["cpu_usage"]["total_usage"]
    )
    system_delta = (
        stats["cpu_stats"]["system_cpu_usage"]
        - stats["precpu_stats"]["system_cpu_usage"]
    )
    num_cpus = stats["cpu_stats"].get("online_cpus") or 1

    if system_delta <= 0 or cpu_delta < 0:
        return 0.0

    cores_used = (cpu_delta / system_delta) * num_cpus
    return (cores_used / CPU_LIMIT_CORES) * 100.0


def average_cpu(containers: list) -> float:
    percents = []
    for c in containers:
        try:
            pct = container_cpu_percent(c)
            log.debug("  %s → %.1f%%", c.name, pct)
            percents.append(pct)
        except Exception as exc:
            log.warning("Failed to read stats for %s: %s", c.name, exc)
    return sum(percents) / len(percents) if percents else 0.0


# ── Scaling actions ───────────────────────────────────────────────────────────
def _next_container_number(project: str) -> int:
    """Find the lowest positive integer not already used as a container number."""
    all_containers = client.containers.list(
        all=True,
        filters={
            "label": [
                f"com.docker.compose.project={project}",
                f"com.docker.compose.service={SERVICE_NAME}",
            ]
        },
    )
    used = set()
    for c in all_containers:
        num = c.labels.get("com.docker.compose.container-number", "")
        if num.isdigit():
            used.add(int(num))
    n = 1
    while n in used:
        n += 1
    return n


def scale_up(containers: list, project: str) -> None:
    """Spin up one additional replica by cloning a reference container's config."""
    ref = containers[0]
    attrs = ref.attrs
    network_name = f"{project}_default"
    next_num = _next_container_number(project)
    new_name = f"{project}-{SERVICE_NAME}-{next_num}"

    log.info("Scaling up → creating %s on network %s", new_name, network_name)

    host_config = client.api.create_host_config(
        nano_cpus=attrs["HostConfig"]["NanoCpus"],
        mem_limit=attrs["HostConfig"]["Memory"],
        restart_policy={"Name": "unless-stopped", "MaximumRetryCount": 0},
        log_config={
            "Type": "json-file",
            "Config": {"max-size": "10m", "max-file": "3"},
        },
    )

    networking_config = client.api.create_networking_config(
        {network_name: client.api.create_endpoint_config(aliases=[SERVICE_NAME])}
    )

    labels = {
        "com.docker.compose.project": project,
        "com.docker.compose.service": SERVICE_NAME,
        "com.docker.compose.container-number": str(next_num),
        "com.docker.compose.oneoff": "False",
    }

    cid = client.api.create_container(
        image=attrs["Config"]["Image"],
        name=new_name,
        environment=attrs["Config"]["Env"],
        labels=labels,
        host_config=host_config,
        networking_config=networking_config,
    )
    client.api.start(cid)
    log.info("Started %s", new_name)
    _reload_nginx(project)


def scale_down(containers: list, project: str) -> None:
    """Gracefully stop and remove the highest-numbered replica."""

    def container_number(c):
        num = c.labels.get("com.docker.compose.container-number", "0")
        return int(num) if num.isdigit() else 0

    victim = max(containers, key=container_number)
    log.info("Scaling down → stopping %s", victim.name)
    victim.stop(timeout=30)
    victim.remove()
    log.info("Removed %s", victim.name)
    _reload_nginx(project)


def _reload_nginx(project: str) -> None:
    """Signal Nginx to reload config so it re-resolves upstream IPs."""
    try:
        nginx_containers = client.containers.list(
            filters={
                "label": [
                    f"com.docker.compose.project={project}",
                    "com.docker.compose.service=nginx",
                ]
            }
        )
        for c in nginx_containers:
            c.exec_run("nginx -s reload")
            log.info("Reloaded Nginx (%s)", c.name)
    except Exception as exc:
        log.warning("Nginx reload failed: %s", exc)


# ── Main loop ─────────────────────────────────────────────────────────────────
def main() -> None:
    log.info(
        "Autoscaler starting — service=%s  min=%d  max=%d  "
        "scale_up≥%.0f%%  scale_down≤%.0f%%  poll=%ds",
        SERVICE_NAME,
        MIN_REPLICAS,
        MAX_REPLICAS,
        SCALE_UP_THRESHOLD,
        SCALE_DOWN_THRESHOLD,
        POLL_INTERVAL,
    )

    # Detect project name from running containers (retried until found)
    project = ""
    while not project:
        project = detect_project_name()
        if not project:
            log.warning(
                "Could not detect project name yet, retrying in %ds…", POLL_INTERVAL
            )
            time.sleep(POLL_INTERVAL)

    log.info("Detected Compose project: %s", project)

    scale_up_streak = 0
    scale_down_streak = 0
    last_scale_up_at = 0.0
    last_scale_down_at = 0.0

    while True:
        try:
            containers = get_app_containers(project)
            current = len(containers)

            if current == 0:
                log.warning("No running %s containers found, waiting…", SERVICE_NAME)
                time.sleep(POLL_INTERVAL)
                continue

            avg_cpu = average_cpu(containers)
            now = time.monotonic()

            log.info(
                "replicas=%-2d  avg_cpu=%5.1f%%  streak_up=%d/%d  streak_down=%d/%d",
                current,
                avg_cpu,
                scale_up_streak,
                SCALE_UP_WINDOW,
                scale_down_streak,
                SCALE_DOWN_WINDOW,
            )

            # ── Scale-up path ─────────────────────────────────────────────────
            if avg_cpu >= SCALE_UP_THRESHOLD:
                scale_up_streak += 1
                scale_down_streak = 0

                if scale_up_streak >= SCALE_UP_WINDOW:
                    if current >= MAX_REPLICAS:
                        log.info(
                            "Already at max replicas (%d), cannot scale up",
                            MAX_REPLICAS,
                        )
                    elif (now - last_scale_up_at) < SCALE_UP_COOLDOWN:
                        remaining = SCALE_UP_COOLDOWN - (now - last_scale_up_at)
                        log.info("Scale-up cooldown: %.0fs remaining", remaining)
                    else:
                        log.info(
                            "SCALE UP  %d → %d  (avg_cpu=%.1f%%)",
                            current,
                            current + 1,
                            avg_cpu,
                        )
                        scale_up(containers, project)
                        scale_up_streak = 0
                        last_scale_up_at = now

            # ── Scale-down path ───────────────────────────────────────────────
            elif avg_cpu <= SCALE_DOWN_THRESHOLD:
                scale_down_streak += 1
                scale_up_streak = 0

                if scale_down_streak >= SCALE_DOWN_WINDOW:
                    if current <= MIN_REPLICAS:
                        log.info(
                            "Already at min replicas (%d), cannot scale down",
                            MIN_REPLICAS,
                        )
                    elif (now - last_scale_down_at) < SCALE_DOWN_COOLDOWN:
                        remaining = SCALE_DOWN_COOLDOWN - (now - last_scale_down_at)
                        log.info("Scale-down cooldown: %.0fs remaining", remaining)
                    else:
                        log.info(
                            "SCALE DOWN %d → %d  (avg_cpu=%.1f%%)",
                            current,
                            current - 1,
                            avg_cpu,
                        )
                        scale_down(containers, project)
                        scale_down_streak = 0
                        last_scale_down_at = now

            # ── Neutral band ──────────────────────────────────────────────────
            else:
                scale_up_streak = 0
                scale_down_streak = 0

        except DockerException as exc:
            log.error("Docker error: %s", exc)
        except Exception as exc:
            log.exception("Unexpected error: %s", exc)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
