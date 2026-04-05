#!/usr/bin/env bash
# =============================================================================
# chaos-test.sh — MLH Production Engineering: Incident Response Demo
# =============================================================================
#
# PURPOSE:
#   Demonstrates the full incident-response loop for the URL Shortener stack:
#     1. Inject a controlled failure into a running service
#     2. Wait for Prometheus to detect it and fire an alert
#     3. Confirm Alertmanager received and routed the alert
#     4. Allow time for email delivery to be observed by judges
#     5. Restore the service and verify recovery
#
# ALERT TIMING EXPECTATIONS:
#   ServiceDown  — Prometheus scrapes every 15 s; alert requires up==0 for 1 m.
#                  Alertmanager group_wait is 0 s for critical alerts.
#                  Expect alert in ~70–90 s after service stops.
#   RedisDown    — redis_connection_errors_total must increase for 1 m.
#                  Alertmanager group_wait is 10 s for warnings.
#                  Expect alert in ~70–80 s after Redis stops.
#
# USAGE:
#   ./scripts/chaos-test.sh [--service-down | --redis-down | --all] [--dry-run]
#   ./scripts/chaos-test.sh --help
#
# REQUIREMENTS:
#   - Run from the project root directory (where docker-compose.yml lives)
#   - Docker Compose stack must be running before executing any scenario
#   - curl must be available on the host
#
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Color codes
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ALERTMANAGER_URL="http://localhost:9093"
HEALTH_URL_NGINX="http://localhost/health/ready"
HEALTH_URL_DIRECT="http://localhost:5000/health/ready"
ALERT_POLL_INTERVAL=5          # seconds between Alertmanager polls
ALERT_TIMEOUT=300              # 5-minute hard timeout for alert to appear
EMAIL_WAIT=10                  # seconds to wait after alert fires for email delivery
RECOVERY_TIMEOUT=120           # seconds to wait for service to recover after restore
RECOVERY_POLL_INTERVAL=5       # seconds between recovery health checks

# Docker Compose project name: Docker derives this from the directory name,
# lowercased with non-alphanumerics replaced by hyphens.
# The directory is "MLH_PE_URL_Shortener" → project = "mlh_pe_url_shortener"
# We detect it at runtime so the script works regardless of where the repo lives.
COMPOSE_PROJECT=""

# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------
DRY_RUN=false
SCENARIO=""
OVERALL_PASS=true

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

timestamp() {
  date '+%H:%M:%S'
}

log_info() {
  echo -e "${YELLOW}[$(timestamp)] INFO  ${RESET}$*"
}

log_success() {
  echo -e "${GREEN}[$(timestamp)] PASS  ${RESET}$*"
}

log_fail() {
  echo -e "${RED}[$(timestamp)] FAIL  ${RESET}$*"
}

log_cyan() {
  echo -e "${CYAN}[$(timestamp)] >>>   ${RESET}$*"
}

log_step() {
  echo -e "${BOLD}[$(timestamp)] STEP  ${RESET}$*"
}

elapsed_since() {
  local start=$1
  local now
  now=$(date +%s)
  echo $(( now - start ))
}

fmt_duration() {
  local secs=$1
  printf '%dm %02ds' $(( secs / 60 )) $(( secs % 60 ))
}

print_banner() {
  local scenario=$1
  echo ""
  echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${RESET}"
  echo -e "${BOLD}${CYAN}║   CHAOS SCENARIO: ${scenario}${RESET}"
  echo -e "${BOLD}${CYAN}║   Started at: $(timestamp)                                       ${RESET}"
  echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${RESET}"
  echo ""
}

print_summary() {
  local scenario=$1
  local result=$2        # "PASS" or "FAIL"
  local elapsed=$3
  echo ""
  if [[ "$result" == "PASS" ]]; then
    echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${GREEN}${BOLD}║   RESULT: PASS — ${scenario}${RESET}"
    echo -e "${GREEN}${BOLD}║   Total elapsed: $(fmt_duration "$elapsed")${RESET}"
    echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════════╝${RESET}"
  else
    echo -e "${RED}${BOLD}╔══════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${RED}${BOLD}║   RESULT: FAIL — ${scenario}${RESET}"
    echo -e "${RED}${BOLD}║   Total elapsed: $(fmt_duration "$elapsed")${RESET}"
    echo -e "${RED}${BOLD}╚══════════════════════════════════════════════════════════════╝${RESET}"
  fi
  echo ""
}

# ---------------------------------------------------------------------------
# Usage / Help
# ---------------------------------------------------------------------------

usage() {
  cat <<EOF

${BOLD}chaos-test.sh${RESET} — MLH PE Incident Response Chaos Tester

${BOLD}USAGE${RESET}
  ./docs/Incident\ Response/chaos/chaos-test.sh <scenario> [--dry-run]

${BOLD}SCENARIOS${RESET}
  --service-down   Stop the app container; wait for ServiceDown alert to fire
  --redis-down     Stop Redis; wait for RedisDown alert to fire
  --all            Run service-down then redis-down sequentially

${BOLD}OPTIONS${RESET}
  --dry-run        Print what would happen without executing any commands
  --help, -h       Show this help message

${BOLD}REQUIREMENTS${RESET}
  Run from the project root (directory containing docker-compose.yml).
  The full Docker Compose stack must be up before running.

${BOLD}EXPECTED ALERT TIMING${RESET}
  ServiceDown  ~70–90 s  (Prometheus 1m for: + scrape interval)
  RedisDown    ~70–80 s  (same timing, warning → 10 s group_wait)

${BOLD}EXAMPLES${RESET}
  # Run from project root
  bash scripts/chaos-test.sh --service-down
  bash scripts/chaos-test.sh --all --dry-run

EOF
}

# ---------------------------------------------------------------------------
# Environment validation
# ---------------------------------------------------------------------------

check_dependencies() {
  local missing=()
  for cmd in curl docker; do
    if ! command -v "$cmd" &>/dev/null; then
      missing+=("$cmd")
    fi
  done
  if (( ${#missing[@]} > 0 )); then
    log_fail "Missing required commands: ${missing[*]}"
    exit 1
  fi

  # Verify docker compose (v2 plugin or v1 standalone)
  if docker compose version &>/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
  elif command -v docker-compose &>/dev/null; then
    DOCKER_COMPOSE="docker-compose"
  else
    log_fail "Neither 'docker compose' (v2) nor 'docker-compose' (v1) is available."
    exit 1
  fi
}

detect_compose_project() {
  # Docker derives the project name from the directory name of the compose file,
  # converting to lowercase and replacing non-alphanumeric characters with hyphens.
  local dir_name
  dir_name=$(basename "$(pwd)")
  # Lowercase, replace anything not [a-z0-9] with a hyphen, strip leading/trailing hyphens
  COMPOSE_PROJECT=$(echo "$dir_name" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//')

  # Validate the project name by checking for running containers
  if ! $DOCKER_COMPOSE ps --quiet 2>/dev/null | head -1 | grep -q .; then
    log_warn "No running containers found for project '${COMPOSE_PROJECT}'."
    log_warn "Make sure the stack is running: $DOCKER_COMPOSE up -d"
  fi
  log_info "Detected Compose project name: ${BOLD}${COMPOSE_PROJECT}${RESET}"
}

assert_compose_file_present() {
  if [[ ! -f "docker-compose.yml" && ! -f "docker-compose.yaml" ]]; then
    log_fail "No docker-compose.yml found in current directory: $(pwd)"
    log_fail "Please run this script from the project root."
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

check_stack_health() {
  log_step "Pre-check: verifying stack is healthy..."

  # First try nginx (port 80), fall back to direct app (port 5000)
  local health_status
  health_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$HEALTH_URL_NGINX" 2>/dev/null || echo "000")

  if [[ "$health_status" == "200" ]]; then
    log_success "Health check via nginx: HTTP $health_status — stack is healthy."
    return 0
  fi

  log_info "nginx health check returned HTTP $health_status, trying direct app endpoint..."
  health_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$HEALTH_URL_DIRECT" 2>/dev/null || echo "000")

  if [[ "$health_status" == "200" ]]; then
    log_success "Health check via direct app: HTTP $health_status — stack is healthy."
    return 0
  fi

  log_fail "Stack does not appear healthy (HTTP $health_status on both endpoints)."
  log_fail "Ensure the Docker Compose stack is fully running before starting chaos tests."
  return 1
}

check_alertmanager_reachable() {
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${ALERTMANAGER_URL}/-/healthy" 2>/dev/null || echo "000")
  if [[ "$status" == "200" ]]; then
    log_success "Alertmanager is reachable at ${ALERTMANAGER_URL}"
    return 0
  else
    log_fail "Alertmanager not reachable at ${ALERTMANAGER_URL} (HTTP $status)."
    log_fail "Is the monitoring stack running?"
    return 1
  fi
}

# ---------------------------------------------------------------------------
# Alert polling
# ---------------------------------------------------------------------------

# Poll Alertmanager API until the named alert appears or we time out.
# Returns 0 if alert found, 1 if timed out.
wait_for_alert() {
  local alert_name=$1
  local start_time
  start_time=$(date +%s)
  local deadline=$(( start_time + ALERT_TIMEOUT ))

  log_step "Polling Alertmanager every ${ALERT_POLL_INTERVAL}s for alert: ${BOLD}${alert_name}${RESET}"
  log_info "Timeout: ${ALERT_TIMEOUT}s ($(fmt_duration $ALERT_TIMEOUT))"

  while true; do
    local now
    now=$(date +%s)

    if (( now >= deadline )); then
      log_fail "Timeout: alert '${alert_name}' did not appear within ${ALERT_TIMEOUT}s."
      return 1
    fi

    local alerts_json
    alerts_json=$(curl -s --max-time 5 "${ALERTMANAGER_URL}/api/v2/alerts" 2>/dev/null || echo "[]")

    if echo "$alerts_json" | grep -q "\"alertname\":\"${alert_name}\""; then
      local elapsed
      elapsed=$(elapsed_since "$start_time")
      log_success "Alert '${BOLD}${alert_name}${RESET}${GREEN}' is FIRING!"
      log_success "Time to alert: ${BOLD}$(fmt_duration "$elapsed")${RESET}${GREEN} (${elapsed}s) — well within the 5-minute requirement."
      return 0
    fi

    local remaining=$(( deadline - now ))
    log_cyan "Alert not yet firing... elapsed: $(fmt_duration "$(elapsed_since "$start_time")"), remaining: $(fmt_duration "$remaining")"
    sleep "$ALERT_POLL_INTERVAL"
  done
}

# ---------------------------------------------------------------------------
# Recovery verification
# ---------------------------------------------------------------------------

wait_for_recovery() {
  local start_time
  start_time=$(date +%s)
  local deadline=$(( start_time + RECOVERY_TIMEOUT ))

  log_step "Waiting for service to recover and health checks to pass..."

  while true; do
    local now
    now=$(date +%s)

    if (( now >= deadline )); then
      log_fail "Service did not recover within ${RECOVERY_TIMEOUT}s."
      return 1
    fi

    local health_status
    health_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$HEALTH_URL_NGINX" 2>/dev/null || echo "000")

    if [[ "$health_status" == "200" ]]; then
      local elapsed
      elapsed=$(elapsed_since "$start_time")
      log_success "Service recovered! Health check returned HTTP 200 after $(fmt_duration "$elapsed")."
      return 0
    fi

    # Also try direct on fallback
    health_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$HEALTH_URL_DIRECT" 2>/dev/null || echo "000")
    if [[ "$health_status" == "200" ]]; then
      local elapsed
      elapsed=$(elapsed_since "$start_time")
      log_success "Service recovered (via direct endpoint)! Health check HTTP 200 after $(fmt_duration "$elapsed")."
      return 0
    fi

    log_cyan "Still recovering... elapsed: $(fmt_duration "$(elapsed_since "$start_time")")"
    sleep "$RECOVERY_POLL_INTERVAL"
  done
}

# ---------------------------------------------------------------------------
# Docker Compose helpers
# ---------------------------------------------------------------------------

compose_stop() {
  local service=$1
  if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} Would execute: ${BOLD}${DOCKER_COMPOSE} stop ${service}${RESET}"
    return 0
  fi
  log_info "Stopping service: ${BOLD}${service}${RESET}"
  ${DOCKER_COMPOSE} stop "$service"
}

compose_start() {
  local service=$1
  if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} Would execute: ${BOLD}${DOCKER_COMPOSE} start ${service}${RESET}"
    return 0
  fi
  log_info "Starting service: ${BOLD}${service}${RESET}"
  ${DOCKER_COMPOSE} start "$service"
}

# ---------------------------------------------------------------------------
# SCENARIO: Service Down
# ---------------------------------------------------------------------------

scenario_service_down() {
  local scenario_start
  scenario_start=$(date +%s)
  print_banner "SERVICE DOWN (app container)"

  # Pre-check
  check_stack_health || { OVERALL_PASS=false; return 1; }
  check_alertmanager_reachable || { OVERALL_PASS=false; return 1; }

  # Inject failure
  log_step "Injecting failure: stopping the 'app' service..."
  log_info "NOTE: The app runs with 2 replicas. Stopping the service stops all replicas."
  log_info "Prometheus scrapes every 15s; alert fires after up==0 for 1m. Expect ~70–90s."
  echo ""

  if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} Would stop: app"
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} Would poll Alertmanager for 'ServiceDown' alert"
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} Would wait ${EMAIL_WAIT}s for email delivery"
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} Would restart: app"
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} Would verify health endpoint returns 200"
    print_summary "SERVICE DOWN" "PASS" "$(elapsed_since "$scenario_start")"
    return 0
  fi

  compose_stop "app"
  log_success "app service stopped at $(timestamp)"
  echo ""

  # Poll for alert
  local alert_fired=true
  wait_for_alert "ServiceDown" || alert_fired=false

  if [[ "$alert_fired" == "true" ]]; then
    # Wait for email delivery
    log_step "Alert confirmed. Waiting ${EMAIL_WAIT}s for email notification delivery..."
    sleep "$EMAIL_WAIT"
    log_success "Email delivery window passed. Check oncall@urlshortener.local inbox."
  else
    log_fail "ServiceDown alert did not fire within the timeout window."
    OVERALL_PASS=false
  fi

  # Restore service
  echo ""
  log_step "Restoring service: starting 'app'..."
  compose_start "app"
  log_info "Service started. Waiting for replicas to become healthy..."

  wait_for_recovery || {
    log_fail "Recovery verification failed."
    OVERALL_PASS=false
  }

  local total_elapsed
  total_elapsed=$(elapsed_since "$scenario_start")

  if [[ "$alert_fired" == "true" ]]; then
    print_summary "SERVICE DOWN" "PASS" "$total_elapsed"
  else
    print_summary "SERVICE DOWN" "FAIL" "$total_elapsed"
    OVERALL_PASS=false
  fi
}

# ---------------------------------------------------------------------------
# SCENARIO: Redis Down
# ---------------------------------------------------------------------------

scenario_redis_down() {
  local scenario_start
  scenario_start=$(date +%s)
  print_banner "REDIS DOWN"

  # Pre-check
  check_stack_health || { OVERALL_PASS=false; return 1; }
  check_alertmanager_reachable || { OVERALL_PASS=false; return 1; }

  # Inject failure
  log_step "Injecting failure: stopping the 'redis' service..."
  log_info "The app will detect Redis connection failures and increment redis_connection_errors_total."
  log_info "Alert fires after metric increases for 1m + 10s group_wait. Expect ~70–80s."
  echo ""

  if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} Would stop: redis"
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} Would poll Alertmanager for 'RedisDown' alert"
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} Would wait ${EMAIL_WAIT}s for email delivery"
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} Would restart: redis"
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} Would verify health endpoint returns 200"
    print_summary "REDIS DOWN" "PASS" "$(elapsed_since "$scenario_start")"
    return 0
  fi

  compose_stop "redis"
  log_success "redis service stopped at $(timestamp)"
  echo ""

  # Poll for alert
  local alert_fired=true
  wait_for_alert "RedisDown" || alert_fired=false

  if [[ "$alert_fired" == "true" ]]; then
    log_step "Alert confirmed. Waiting ${EMAIL_WAIT}s for email notification delivery..."
    sleep "$EMAIL_WAIT"
    log_success "Email delivery window passed. Check oncall@urlshortener.local inbox."
  else
    log_fail "RedisDown alert did not fire within the timeout window."
    OVERALL_PASS=false
  fi

  # Restore service
  echo ""
  log_step "Restoring service: starting 'redis'..."
  compose_start "redis"
  log_info "Redis restarted. Waiting for app to reconnect and health checks to pass..."

  wait_for_recovery || {
    log_fail "Recovery verification failed."
    OVERALL_PASS=false
  }

  local total_elapsed
  total_elapsed=$(elapsed_since "$scenario_start")

  if [[ "$alert_fired" == "true" ]]; then
    print_summary "REDIS DOWN" "PASS" "$total_elapsed"
  else
    print_summary "REDIS DOWN" "FAIL" "$total_elapsed"
    OVERALL_PASS=false
  fi
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

for arg in "$@"; do
  case "$arg" in
    --service-down)
      SCENARIO="service-down"
      ;;
    --redis-down)
      SCENARIO="redis-down"
      ;;
    --all)
      SCENARIO="all"
      ;;
    --dry-run)
      DRY_RUN=true
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown argument: $arg${RESET}"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$SCENARIO" ]]; then
  echo -e "${RED}No scenario specified.${RESET}"
  usage
  exit 1
fi

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

main() {
  echo ""
  echo -e "${BOLD}${CYAN}================================================================${RESET}"
  echo -e "${BOLD}${CYAN}   MLH PE URL Shortener — Chaos & Incident Response Tester${RESET}"
  echo -e "${BOLD}${CYAN}   Run started: $(date '+%Y-%m-%d %H:%M:%S')${RESET}"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${BOLD}${YELLOW}   MODE: DRY-RUN (no actual changes will be made)${RESET}"
  fi
  echo -e "${BOLD}${CYAN}================================================================${RESET}"
  echo ""

  assert_compose_file_present
  check_dependencies
  detect_compose_project

  case "$SCENARIO" in
    service-down)
      scenario_service_down
      ;;
    redis-down)
      scenario_redis_down
      ;;
    all)
      log_info "Running ALL scenarios sequentially."
      echo ""
      scenario_service_down
      log_info "Pausing 15s between scenarios to let alerting settle..."
      sleep 15
      scenario_redis_down
      ;;
  esac

  echo ""
  if [[ "$OVERALL_PASS" == "true" ]]; then
    echo -e "${GREEN}${BOLD}================================================================${RESET}"
    echo -e "${GREEN}${BOLD}   ALL SCENARIOS PASSED${RESET}"
    echo -e "${GREEN}${BOLD}   Incident response loop: break → alert → notify → recover${RESET}"
    echo -e "${GREEN}${BOLD}   Finished: $(date '+%Y-%m-%d %H:%M:%S')${RESET}"
    echo -e "${GREEN}${BOLD}================================================================${RESET}"
    exit 0
  else
    echo -e "${RED}${BOLD}================================================================${RESET}"
    echo -e "${RED}${BOLD}   ONE OR MORE SCENARIOS FAILED${RESET}"
    echo -e "${RED}${BOLD}   Review output above for details.${RESET}"
    echo -e "${RED}${BOLD}   Finished: $(date '+%Y-%m-%d %H:%M:%S')${RESET}"
    echo -e "${RED}${BOLD}================================================================${RESET}"
    exit 1
  fi
}

main
