#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Docker Compose Autoscaler
# Monitors app container CPU & health latency, scales replicas accordingly.
# Run from the project root: ./scripts/autoscaler.sh
# ---------------------------------------------------------------------------

SERVICE="app"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

MIN_REPLICAS="${MIN_REPLICAS:-2}"
MAX_REPLICAS="${MAX_REPLICAS:-8}"

CPU_SCALE_UP="${CPU_SCALE_UP_THRESHOLD:-70}"
CPU_SCALE_DOWN="${CPU_SCALE_DOWN_THRESHOLD:-25}"

LATENCY_UP="${LATENCY_SCALE_UP_MS:-500}"

POLL="${POLL_INTERVAL:-10}"
COOLDOWN="${COOLDOWN:-30}"

last_scale=0

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }

running_replicas() {
    docker compose -f "${PROJECT_DIR}/docker-compose.yml" \
        ps --status running --format '{{.Name}}' 2>/dev/null |
        grep -c "${SERVICE}" || echo 0
}

avg_cpu() {
    docker stats --no-stream --format '{{.Name}} {{.CPUPerc}}' 2>/dev/null |
        awk -v svc="${SERVICE}" '
            $1 ~ svc {
                gsub(/%/, "", $2)
                sum += $2; n++
            }
            END { if (n>0) printf "%.0f", sum/n; else print "0" }
        '
}

health_latency_ms() {
    local ms
    ms=$(curl -sf -o /dev/null -w '%{time_total}' http://localhost/health 2>/dev/null || echo "1")
    python3 -c "print(int(float('${ms}') * 1000))"
}

scale_to() {
    local target=$1
    local now
    now=$(date +%s)

    if (( now - last_scale < COOLDOWN )); then
        log "  cooldown active ($(( COOLDOWN - now + last_scale ))s left), skipping"
        return
    fi

    local cur
    cur=$(running_replicas)
    if (( target == cur )); then return; fi

    log "SCALING ${SERVICE}: ${cur} -> ${target} replicas"
    docker compose -f "${PROJECT_DIR}/docker-compose.yml" \
        up -d --scale "${SERVICE}=${target}" --no-recreate 2>&1 | tail -3

    sleep 2
    docker compose -f "${PROJECT_DIR}/docker-compose.yml" \
        exec -T nginx nginx -s reload 2>/dev/null && \
        log "  nginx reloaded (new upstreams)" || \
        log "  nginx reload skipped"

    last_scale=$(date +%s)
}

decide() {
    local cpu=$1 latency=$2 cur=$3

    if (( cpu > CPU_SCALE_UP )) || (( latency > LATENCY_UP )); then
        local up=$(( cur + 1 ))
        (( up > MAX_REPLICAS )) && up=$MAX_REPLICAS
        if (( up != cur )); then
            log "SCALE UP  cpu=${cpu}%  latency=${latency}ms  -> ${up} replicas"
            scale_to "$up"
        fi
    elif (( cpu < CPU_SCALE_DOWN )) && (( latency < LATENCY_UP / 2 )); then
        local down=$(( cur - 1 ))
        (( down < MIN_REPLICAS )) && down=$MIN_REPLICAS
        if (( down != cur )); then
            log "SCALE DOWN  cpu=${cpu}%  latency=${latency}ms  -> ${down} replicas"
            scale_to "$down"
        fi
    fi
}

# ---------------------------------------------------------------------------
log "=== Autoscaler started ==="
log "  replicas: min=${MIN_REPLICAS}  max=${MAX_REPLICAS}"
log "  CPU:      up>${CPU_SCALE_UP}%  down<${CPU_SCALE_DOWN}%"
log "  Latency:  up>${LATENCY_UP}ms"
log "  poll=${POLL}s  cooldown=${COOLDOWN}s"
log ""

while true; do
    cpu=$(avg_cpu)
    latency=$(health_latency_ms)
    replicas=$(running_replicas)

    log "TICK  replicas=${replicas}  avg_cpu=${cpu}%  latency=${latency}ms"
    decide "$cpu" "$latency" "$replicas"

    sleep "$POLL"
done
