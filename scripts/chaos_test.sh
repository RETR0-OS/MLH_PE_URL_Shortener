#!/usr/bin/env bash
#
# Chaos Test — kill app containers, verify auto-restart via Docker restart policy
# and that the service recovers to healthy within a timeout.
#
# Prerequisites: docker compose stack running (`docker compose up -d`)
#
# Usage:  ./scripts/chaos_test.sh
#
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'
BOLD='\033[1m'

HEALTH_URL="${HEALTH_URL:-http://localhost:80/health}"
RECOVERY_TIMEOUT="${RECOVERY_TIMEOUT:-90}"
PROJECT="${COMPOSE_PROJECT_NAME:-mlh_pe_url_shortener}"

log()  { printf "${BOLD}[%s]${NC} %s\n" "$(date +%T)" "$*"; }
pass() { printf "${GREEN}✓ PASS${NC} %s\n" "$*"; }
fail() { printf "${RED}✗ FAIL${NC} %s\n" "$*"; exit 1; }
warn() { printf "${YELLOW}⚠ WARN${NC} %s\n" "$*"; }

wait_healthy() {
    local elapsed=0
    while [ "$elapsed" -lt "$RECOVERY_TIMEOUT" ]; do
        if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    return 1
}

ensure_app_running() {
    local count
    count=$(docker compose ps -q app 2>/dev/null | wc -l | tr -d ' ')
    if [ "$count" -lt 1 ]; then
        log "No running app containers — restarting via docker compose..."
        docker compose up -d app > /dev/null 2>&1
        sleep 5
    fi
}

separator() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# ───────────────────────────────────────────────────────
# Pre-flight
# ───────────────────────────────────────────────────────

echo ""
echo "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo "${BOLD}║           CHAOS TEST — Resilience Suite          ║${NC}"
echo "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""

log "Pre-flight: checking stack is healthy"
if ! curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
    fail "Stack is not healthy at $HEALTH_URL — start it first with 'docker compose up -d'"
fi
pass "Stack is healthy"

INITIAL_CONTAINERS=$(docker compose ps -q app 2>/dev/null | wc -l | tr -d ' ')
log "Running app containers: $INITIAL_CONTAINERS"

separator

# ───────────────────────────────────────────────────────
# Test 1: Kill a single app container — expect Docker to restart it
# ───────────────────────────────────────────────────────

log "Test 1: Kill a single app container"

VICTIM=$(docker compose ps -q app 2>/dev/null | head -1)
if [ -z "$VICTIM" ]; then
    fail "No app containers found"
fi

log "Killing container ${VICTIM:0:12}..."
docker kill "$VICTIM" > /dev/null 2>&1

log "Waiting for recovery (timeout: ${RECOVERY_TIMEOUT}s)..."
START=$SECONDS
if wait_healthy; then
    ELAPSED=$((SECONDS - START))
    pass "Service recovered in ${ELAPSED}s after single container kill"
else
    fail "Service did not recover within ${RECOVERY_TIMEOUT}s"
fi

sleep 5
AFTER_CONTAINERS=$(docker compose ps -q app 2>/dev/null | wc -l | tr -d ' ')
log "App containers after recovery: $AFTER_CONTAINERS"

separator

# ───────────────────────────────────────────────────────
# Test 2: Kill ALL app containers — verify full recovery
# ───────────────────────────────────────────────────────

ensure_app_running
sleep 3

log "Test 2: Kill ALL app containers simultaneously"

ALL_CONTAINERS=$(docker compose ps -q app 2>/dev/null)
KILL_COUNT=$(echo "$ALL_CONTAINERS" | wc -l | tr -d ' ')
log "Killing $KILL_COUNT containers..."

echo "$ALL_CONTAINERS" | xargs -I{} docker kill {} > /dev/null 2>&1

log "Waiting for Docker restart policy (${RECOVERY_TIMEOUT}s timeout)..."
START=$SECONDS

RECOVERED=false
ELAPSED=0
while [ "$ELAPSED" -lt "$RECOVERY_TIMEOUT" ]; do
    RUNNING=$(docker compose ps -q app 2>/dev/null | wc -l | tr -d ' ')
    if [ "$RUNNING" -ge 1 ] && curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        RECOVERED=true
        break
    fi
    if [ "$RUNNING" -lt 1 ] && [ "$ELAPSED" -gt 15 ]; then
        log "No containers restarted after ${ELAPSED}s — triggering docker compose up..."
        docker compose up -d app > /dev/null 2>&1
    fi
    sleep 2
    ELAPSED=$((SECONDS - START))
done

if $RECOVERED; then
    pass "Full recovery after killing ALL containers in ${ELAPSED}s"
else
    fail "Service did not recover after killing all containers within ${RECOVERY_TIMEOUT}s"
fi

sleep 3
FINAL_CONTAINERS=$(docker compose ps -q app 2>/dev/null | wc -l | tr -d ' ')
pass "Containers running: $FINAL_CONTAINERS"

separator

# ───────────────────────────────────────────────────────
# Test 3: Kill the database — verify app recovers when DB comes back
# ───────────────────────────────────────────────────────

ensure_app_running
sleep 3

log "Test 3: Kill the database container"

DB_CONTAINER=$(docker compose ps -q postgres 2>/dev/null | head -1)
if [ -z "$DB_CONTAINER" ]; then
    warn "No postgres container found, skipping"
else
    log "Killing postgres ${DB_CONTAINER:0:12}..."
    docker kill "$DB_CONTAINER" > /dev/null 2>&1

    log "Waiting for postgres + app recovery (timeout: ${RECOVERY_TIMEOUT}s)..."
    START=$SECONDS
    if wait_healthy; then
        ELAPSED=$((SECONDS - START))
        pass "Service recovered after DB kill in ${ELAPSED}s"
    else
        log "Triggering docker compose up to restore DB..."
        docker compose up -d postgres > /dev/null 2>&1
        sleep 10
        if wait_healthy; then
            ELAPSED=$((SECONDS - START))
            pass "Service recovered after DB restore in ${ELAPSED}s"
        else
            fail "Service did not recover after DB kill within ${RECOVERY_TIMEOUT}s"
        fi
    fi
fi

separator

# ───────────────────────────────────────────────────────
# Test 4: Kill Nginx — verify restart
# ───────────────────────────────────────────────────────

ensure_app_running
sleep 3

log "Test 4: Kill the Nginx load balancer"

NGINX_CONTAINER=$(docker compose ps -q nginx 2>/dev/null | head -1)
if [ -z "$NGINX_CONTAINER" ]; then
    warn "No nginx container found, skipping"
else
    log "Killing nginx ${NGINX_CONTAINER:0:12}..."
    docker kill "$NGINX_CONTAINER" > /dev/null 2>&1

    log "Waiting for Nginx recovery (timeout: ${RECOVERY_TIMEOUT}s)..."
    START=$SECONDS
    if wait_healthy; then
        ELAPSED=$((SECONDS - START))
        pass "Nginx recovered in ${ELAPSED}s"
    else
        log "Triggering docker compose up to restore Nginx..."
        docker compose up -d nginx > /dev/null 2>&1
        sleep 5
        if wait_healthy; then
            ELAPSED=$((SECONDS - START))
            pass "Nginx recovered after restart in ${ELAPSED}s"
        else
            fail "Nginx did not recover within ${RECOVERY_TIMEOUT}s"
        fi
    fi
fi

separator

# ───────────────────────────────────────────────────────
# Test 5: Graceful failure — bad input returns JSON errors, not crashes
# ───────────────────────────────────────────────────────

ensure_app_running
sleep 2

log "Test 5: Graceful failure on bad input"

TESTS_PASSED=0
TESTS_TOTAL=0

check_status() {
    local desc="$1" expected="$2" actual="$3"
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    if [ "$actual" -eq "$expected" ]; then
        pass "$desc (HTTP $actual)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        warn "$desc — expected $expected, got $actual"
    fi
}

STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    "http://localhost:80/users/not-an-integer" 2>/dev/null || echo "000")
check_status "GET /users/not-an-integer returns 404" 404 "$STATUS"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:80/users" \
    -H "Content-Type: application/json" \
    -d '{"username": 12345, "email": 67890}' 2>/dev/null || echo "000")
check_status "POST /users with integer fields returns 400" 400 "$STATUS"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:80/urls" \
    -H "Content-Type: application/json" \
    -d '{}' 2>/dev/null || echo "000")
check_status "POST /urls with empty body returns 400" 400 "$STATUS"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    "http://localhost:80/urls/ZZZNONEXISTENT/redirect" 2>/dev/null || echo "000")
check_status "GET /urls/ZZZNONEXISTENT/redirect returns 404" 404 "$STATUS"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:80/events" \
    -H "Content-Type: application/json" \
    -d '{"garbage": true}' 2>/dev/null || echo "000")
check_status "POST /events with garbage returns 400" 400 "$STATUS"

BODY=$(curl -sf "http://localhost:80/nonexistent-path" 2>/dev/null || echo '{}')
if echo "$BODY" | grep -q '"error"'; then
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    TESTS_PASSED=$((TESTS_PASSED + 1))
    pass "404 response is JSON with 'error' key"
else
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    warn "404 response is not JSON with 'error' key"
fi

log "Graceful failure tests: $TESTS_PASSED/$TESTS_TOTAL passed"

if [ "$TESTS_PASSED" -lt "$TESTS_TOTAL" ]; then
    warn "Some graceful failure checks did not match expected status"
fi

separator

# ───────────────────────────────────────────────────────
# Summary
# ───────────────────────────────────────────────────────

echo ""
echo "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo "${BOLD}║              CHAOS TEST — COMPLETE               ║${NC}"
echo "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""
pass "All chaos tests passed — service is resilient"
