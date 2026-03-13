#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_DIR="${REPO_ROOT}/output/dev_stack"
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
FRONTEND_DIR="${REPO_ROOT}/frontend"
COMPOSE_FILE="${REPO_ROOT}/compose.yaml"

BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8000"
FRONTEND_HOST="127.0.0.1"
FRONTEND_PORT="8173"
POSTGRES_HOST="127.0.0.1"
POSTGRES_PORT="8132"
POSTGRES_USER="rpg_local"
POSTGRES_PASSWORD="rpg_local"
POSTGRES_DEV_DB="rpg_dev"

TAIL_LINES="${DEV_STACK_TAIL_LINES:-80}"

log() { printf '[dev_stack] %s\n' "$*"; }
warn() { printf '[dev_stack] WARN: %s\n' "$*" >&2; }
fail() { printf '[dev_stack] ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<USAGE
usage: ./scripts/dev_stack.sh <command> [args]

Commands:
  up                 Start postgres, migrate head, then start backend/frontend
  down [--all]       Stop frontend/backend; use --all to also stop postgres
  restart            Restart frontend/backend and ensure postgres is running
  status             Show postgres + service state and health
  resetdb            Recreate local PostgreSQL rpg_dev and migrate
  logs [service]     Show recent logs for one of: postgres backend frontend (or all)
  ready              Check postgres, backend /ready, and frontend /
USAGE
}

ensure_run_dir() { mkdir -p "${RUN_DIR}"; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || fail "missing required command '$1'"; }
require_python_env() {
  [[ -x "${PYTHON_BIN}" ]] || fail "missing ${PYTHON_BIN}; create venv and install deps first"
}
require_frontend_deps() {
  [[ -f "${FRONTEND_DIR}/package.json" ]] || fail "missing frontend/package.json"
  [[ -d "${FRONTEND_DIR}/node_modules" ]] || fail "missing frontend/node_modules; run: cd frontend && npm install"
  require_cmd npm
}
require_compose() {
  require_cmd docker
  docker compose version >/dev/null 2>&1 || fail "docker compose is required"
  [[ -f "${COMPOSE_FILE}" ]] || fail "missing ${COMPOSE_FILE}"
}
compose_cmd() { docker compose -f "${COMPOSE_FILE}" "$@"; }

pid_file() { printf '%s/%s.pid' "${RUN_DIR}" "$1"; }
log_file() { printf '%s/%s.log' "${RUN_DIR}" "$1"; }

pid_alive() { [[ -n "${1}" ]] && kill -0 "${1}" 2>/dev/null; }

service_port() {
  case "$1" in
    backend) printf '%s' "${BACKEND_PORT}" ;;
    frontend) printf '%s' "${FRONTEND_PORT}" ;;
    postgres) printf '%s' "${POSTGRES_PORT}" ;;
    *) fail "unknown service '$1'" ;;
  esac
}

service_host() {
  case "$1" in
    backend) printf '%s' "${BACKEND_HOST}" ;;
    frontend) printf '%s' "${FRONTEND_HOST}" ;;
    postgres) printf '%s' "${POSTGRES_HOST}" ;;
    *) fail "unknown service '$1'" ;;
  esac
}

service_health_url() {
  case "$1" in
    backend) printf 'http://%s:%s/ready' "${BACKEND_HOST}" "${BACKEND_PORT}" ;;
    frontend) printf 'http://%s:%s/' "${FRONTEND_HOST}" "${FRONTEND_PORT}" ;;
    *) fail "unknown service '$1'" ;;
  esac
}

list_port_pids() {
  local host="$1" port="$2"
  lsof -t -nP -iTCP@"${host}":"${port}" -sTCP:LISTEN 2>/dev/null | sort -u || true
}

service_pid() {
  local name="$1" file pid
  file="$(pid_file "${name}")"
  if [[ -f "${file}" ]]; then
    pid="$(tr -d '[:space:]' < "${file}")"
    if pid_alive "${pid}"; then
      printf '%s' "${pid}"
      return 0
    fi
  fi
  return 1
}

http_code() {
  local url="$1"
  curl -s -o /dev/null -w '%{http_code}' --max-time 5 "${url}" 2>/dev/null || printf '000'
}

wait_for_http_ok() {
  local name="$1" url="$2" attempts="$3"
  local try=1 code='000'
  while (( try <= attempts )); do
    code="$(http_code "${url}")"
    if [[ "${code}" == "200" ]]; then
      return 0
    fi
    sleep 1
    try=$(( try + 1 ))
  done
  warn "${name} not ready; last http=${code} url=${url}"
  return 1
}

postgres_sql_ok() {
  require_python_env
  POSTGRES_HOST="${POSTGRES_HOST}" POSTGRES_PORT="${POSTGRES_PORT}" POSTGRES_USER="${POSTGRES_USER}" POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import os, sys
import psycopg
try:
    with psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname="postgres",
        connect_timeout=2,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
except Exception:
    sys.exit(1)
PY
}

wait_for_postgres_ready() {
  local try=1
  while (( try <= 60 )); do
    if postgres_sql_ok; then
      return 0
    fi
    sleep 1
    try=$(( try + 1 ))
  done
  return 1
}

start_postgres() {
  require_compose
  log "starting postgres"
  (cd "${REPO_ROOT}" && compose_cmd up -d postgres >/dev/null)
}

stop_postgres() {
  require_compose
  log "stopping postgres"
  (cd "${REPO_ROOT}" && compose_cmd stop postgres >/dev/null || true)
}

run_migrate_head() {
  require_python_env
  log "running migrations to head"
  (cd "${REPO_ROOT}" && PYTHONPATH="${REPO_ROOT}" "${PYTHON_BIN}" scripts/db_migrate.py upgrade head)
}

start_service() {
  local name="$1" workdir cmd
  local file_pid file_log
  ensure_run_dir

  if service_pid "${name}" >/dev/null 2>&1; then
    log "${name} already running"
    return 0
  fi

  case "${name}" in
    backend)
      require_python_env
      workdir="${REPO_ROOT}"
      cmd="env PYTHONPATH=${REPO_ROOT} ${PYTHON_BIN} -m uvicorn rpg_backend.main:app --reload --host ${BACKEND_HOST} --port ${BACKEND_PORT}"
      ;;
    frontend)
      require_frontend_deps
      workdir="${FRONTEND_DIR}"
      if [[ -x "${FRONTEND_DIR}/node_modules/.bin/vite" ]]; then
        cmd="${FRONTEND_DIR}/node_modules/.bin/vite --host ${FRONTEND_HOST} --port ${FRONTEND_PORT}"
      else
        cmd="npm run dev -- --host ${FRONTEND_HOST} --port ${FRONTEND_PORT}"
      fi
      ;;
    *)
      fail "unknown service '${name}'"
      ;;
  esac

  file_pid="$(pid_file "${name}")"
  file_log="$(log_file "${name}")"
  : > "${file_log}"
  log "starting ${name}"
  (
    cd "${workdir}"
    nohup sh -c "${cmd}" < /dev/null >> "${file_log}" 2>&1 &
    echo $! > "${file_pid}"
  )
  sleep 1
  local pid
  pid="$(tr -d '[:space:]' < "${file_pid}")"
  if ! pid_alive "${pid}"; then
    tail -n 80 "${file_log}" || true
    fail "${name} failed to stay running"
  fi
}

stop_service() {
  local name="$1" pid port host extra_pids
  if pid="$(service_pid "${name}" 2>/dev/null || true)"; then
    log "stopping ${name} pid=${pid}"
    kill "${pid}" 2>/dev/null || true
    sleep 1
    if pid_alive "${pid}"; then
      kill -9 "${pid}" 2>/dev/null || true
    fi
  fi
  rm -f "$(pid_file "${name}")"
  host="$(service_host "${name}")"
  port="$(service_port "${name}")"
  extra_pids="$(list_port_pids "${host}" "${port}" | paste -sd' ' -)"
  if [[ -n "${extra_pids}" ]]; then
    warn "cleaning stale listeners for ${name} on ${host}:${port}: ${extra_pids}"
    kill ${extra_pids} 2>/dev/null || true
  fi
}

stack_up() {
  require_cmd curl
  require_cmd lsof
  start_postgres
  wait_for_postgres_ready || fail "postgres not ready"
  run_migrate_head
  start_service backend
  start_service frontend
  wait_for_http_ok "backend /ready" "$(service_health_url backend)" 90 || fail "backend not ready"
  wait_for_http_ok "frontend /" "$(service_health_url frontend)" 90 || fail "frontend not ready"
  status
}

stack_down() {
  local stop_pg="${1:-false}"
  stop_service frontend
  stop_service backend
  if [[ "${stop_pg}" == "true" ]]; then
    stop_postgres
  fi
}

resetdb() {
  require_python_env
  start_postgres
  wait_for_postgres_ready || fail "postgres not ready"
  log "recreating ${POSTGRES_DEV_DB}"
  POSTGRES_HOST="${POSTGRES_HOST}" POSTGRES_PORT="${POSTGRES_PORT}" POSTGRES_USER="${POSTGRES_USER}" POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" POSTGRES_DEV_DB="${POSTGRES_DEV_DB}" \
  "${PYTHON_BIN}" - <<'PY'
import os
import psycopg

with psycopg.connect(
    host=os.environ["POSTGRES_HOST"],
    port=int(os.environ["POSTGRES_PORT"]),
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    dbname="postgres",
    autocommit=True,
) as conn:
    db_name = os.environ["POSTGRES_DEV_DB"]
    with conn.cursor() as cur:
        cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s", (db_name,))
        cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        cur.execute(f'CREATE DATABASE "{db_name}"')
PY
  run_migrate_head
}

status() {
  local backend_pid frontend_pid backend_code frontend_code postgres_health
  backend_pid="$(service_pid backend 2>/dev/null || true)"
  frontend_pid="$(service_pid frontend 2>/dev/null || true)"
  backend_code="$(http_code "$(service_health_url backend)")"
  frontend_code="$(http_code "$(service_health_url frontend)")"
  if postgres_sql_ok; then postgres_health="ok"; else postgres_health="down"; fi
  printf 'postgres state=%s port=%s\n' "${postgres_health}" "${POSTGRES_PORT}"
  printf 'backend  pid=%s port=%s http=%s log=%s\n' "${backend_pid:--}" "${BACKEND_PORT}" "${backend_code}" "$(log_file backend)"
  printf 'frontend pid=%s port=%s http=%s log=%s\n' "${frontend_pid:--}" "${FRONTEND_PORT}" "${frontend_code}" "$(log_file frontend)"
}

ready() {
  local failed=0
  if postgres_sql_ok; then
    printf '%-15s ok\n' "postgres sql"
  else
    printf '%-15s down\n' "postgres sql"
    failed=1
  fi
  for service in backend frontend; do
    local url code
    url="$(service_health_url "${service}")"
    code="$(http_code "${url}")"
    printf '%-15s http=%s url=%s\n' "${service}" "${code}" "${url}"
    if [[ "${code}" != "200" ]]; then
      failed=1
    fi
  done
  return "${failed}"
}

logs() {
  local target="${1:-all}"
  case "${target}" in
    postgres)
      (cd "${REPO_ROOT}" && compose_cmd logs --tail="${TAIL_LINES}" postgres)
      ;;
    backend|frontend)
      tail -n "${TAIL_LINES}" "$(log_file "${target}")" 2>/dev/null || warn "no logs for ${target}"
      ;;
    all)
      printf '=== postgres ===\n'
      (cd "${REPO_ROOT}" && compose_cmd logs --tail="${TAIL_LINES}" postgres || true)
      printf '\n=== backend ===\n'
      tail -n "${TAIL_LINES}" "$(log_file backend)" 2>/dev/null || true
      printf '\n=== frontend ===\n'
      tail -n "${TAIL_LINES}" "$(log_file frontend)" 2>/dev/null || true
      ;;
    *)
      fail "unknown service '${target}'"
      ;;
  esac
}

cmd="${1:-}"
case "${cmd}" in
  up)
    stack_up
    ;;
  down)
    if [[ "${2:-}" == "--all" ]]; then
      stack_down true
    else
      stack_down false
    fi
    ;;
  restart)
    stack_down false
    stack_up
    ;;
  status)
    status
    ;;
  resetdb)
    stack_down false
    resetdb
    ;;
  logs)
    logs "${2:-all}"
    ;;
  ready)
    ready
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    usage
    fail "unknown command '${cmd}'"
    ;;
esac

