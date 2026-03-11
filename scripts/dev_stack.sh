#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_DIR="${REPO_ROOT}/output/dev_stack"
STATUS_FILE="${RUN_DIR}/status.json"
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
FRONTEND_DIR="${REPO_ROOT}/frontend"
COMPOSE_FILE="${REPO_ROOT}/compose.yaml"
BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8000"
WORKER_HOST="127.0.0.1"
WORKER_PORT="8100"
FRONTEND_HOST="127.0.0.1"
FRONTEND_PORT="8173"
POSTGRES_HOST="127.0.0.1"
POSTGRES_PORT="8132"
POSTGRES_USER="rpg_local"
POSTGRES_PASSWORD="rpg_local"
POSTGRES_DEV_DB="rpg_dev"
POSTGRES_TEST_DB="rpg_test"
TAIL_LINES="${DEV_STACK_TAIL_LINES:-80}"

log() { printf '[dev_stack] %s\n' "$*"; }
warn() { printf '[dev_stack] WARN: %s\n' "$*" >&2; }
fail() { printf '[dev_stack] ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<USAGE
usage: ./scripts/dev_stack.sh <command> [args]

Commands:
  up                 Start postgres, migrate head, then start worker/backend/frontend
  down [--all]       Stop frontend/backend/worker; use --all to also stop postgres
  restart            Restart frontend/backend/worker and ensure postgres is running
  status             Show postgres + service state, ports, logs, and health
  resetdb            Recreate local PostgreSQL rpg_dev, migrate, then start stack
  logs [service]     Show recent logs for one of: postgres backend worker frontend (or all)
  ready              Check postgres, backend /ready, worker /ready, and frontend /
USAGE
}

ensure_run_dir() { mkdir -p "${RUN_DIR}"; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || fail "missing required command '$1'"; }
require_python_env() { [[ -x "${PYTHON_BIN}" ]] || fail "missing ${PYTHON_BIN}; create the virtualenv first: python -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"; }
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

service_port() {
  case "$1" in
    postgres) printf '%s' "${POSTGRES_PORT}" ;;
    backend) printf '%s' "${BACKEND_PORT}" ;;
    worker) printf '%s' "${WORKER_PORT}" ;;
    frontend) printf '%s' "${FRONTEND_PORT}" ;;
    *) fail "unknown service '$1'" ;;
  esac
}

service_host() {
  case "$1" in
    postgres) printf '%s' "${POSTGRES_HOST}" ;;
    backend) printf '%s' "${BACKEND_HOST}" ;;
    worker) printf '%s' "${WORKER_HOST}" ;;
    frontend) printf '%s' "${FRONTEND_HOST}" ;;
    *) fail "unknown service '$1'" ;;
  esac
}

service_pid_file() { printf '%s/%s.pid' "${RUN_DIR}" "$1"; }
service_log_file() { printf '%s/%s.log' "${RUN_DIR}" "$1"; }

service_health_url() {
  case "$1" in
    backend) printf 'http://%s:%s/ready' "${BACKEND_HOST}" "${BACKEND_PORT}" ;;
    worker) printf 'http://%s:%s/ready' "${WORKER_HOST}" "${WORKER_PORT}" ;;
    frontend) printf 'http://%s:%s/' "${FRONTEND_HOST}" "${FRONTEND_PORT}" ;;
    *) fail "unknown health-url service '$1'" ;;
  esac
}

service_health_name() {
  case "$1" in
    postgres) printf 'postgres sql' ;;
    backend) printf 'backend /ready' ;;
    worker) printf 'worker /ready' ;;
    frontend) printf 'frontend /' ;;
    *) fail "unknown service '$1'" ;;
  esac
}

pid_alive() { [[ -n "${1}" ]] && kill -0 "${1}" 2>/dev/null; }

service_pid() {
  local name="$1" pid_file pid
  pid_file="$(service_pid_file "${name}")"
  if [[ -f "${pid_file}" ]]; then
    pid="$(tr -d '[:space:]' < "${pid_file}")"
    if pid_alive "${pid}"; then
      printf '%s' "${pid}"
      return 0
    fi
  fi
  return 1
}

list_pids_for_port() {
  local host="$1"
  local port="$2"
  lsof -t -nP -iTCP@"${host}":"${port}" -sTCP:LISTEN 2>/dev/null | sort -u || true
}

postgres_state() {
  require_compose
  local running
  running="$(compose_cmd ps --services --status running 2>/dev/null | grep -x 'postgres' || true)"
  if [[ -n "${running}" ]]; then
    printf 'running'
  elif [[ -n "$(list_pids_for_port "${POSTGRES_HOST}" "${POSTGRES_PORT}")" ]]; then
    printf 'port_busy'
  else
    printf 'stopped'
  fi
}

service_state() {
  local name="$1"
  if [[ "${name}" == 'postgres' ]]; then
    postgres_state
    return 0
  fi
  if service_pid "${name}" >/dev/null 2>&1; then
    printf 'running'
    return 0
  fi
  local port="$(service_port "${name}")"
  if [[ -n "$(list_pids_for_port "$(service_host "${name}")" "${port}")" ]]; then
    printf 'port_busy'
  else
    printf 'stopped'
  fi
}

service_any_pid() {
  local name="$1"
  if [[ "${name}" == 'postgres' ]]; then
    compose_cmd ps -q postgres 2>/dev/null || true
    return 0
  fi
  if service_pid "${name}" >/dev/null 2>&1; then
    service_pid "${name}"
    return 0
  fi
  local port="$(service_port "${name}")"
  local pids
  pids="$(list_pids_for_port "$(service_host "${name}")" "${port}" | paste -sd, -)"
  [[ -n "${pids}" ]] && printf '%s' "${pids}"
}

http_code() {
  local url="$1"
  curl -s -o /dev/null -w '%{http_code}' --max-time 5 "${url}" 2>/dev/null || printf '000'
}

wait_for_http_ok() {
  local name="$1" url="$2" attempts="$3" sleep_seconds="$4" code='000' try=1
  while (( try <= attempts )); do
    code="$(http_code "${url}")"
    if [[ "${code}" == '200' ]]; then return 0; fi
    sleep "${sleep_seconds}"
    try=$(( try + 1 ))
  done
  warn "${name} did not become ready; last http=${code} url=${url}"
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
        host=os.environ['POSTGRES_HOST'],
        port=int(os.environ['POSTGRES_PORT']),
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'],
        dbname='postgres',
        connect_timeout=2,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
            cur.fetchone()
except Exception:
    sys.exit(1)
PY
}

wait_for_postgres_ready() {
  local try=1
  while (( try <= 60 )); do
    if postgres_sql_ok; then return 0; fi
    sleep 1
    try=$(( try + 1 ))
  done
  warn "postgres did not become ready on ${POSTGRES_HOST}:${POSTGRES_PORT}"
  return 1
}

write_status_file() {
  ensure_run_dir
  local postgres_state backend_state worker_state frontend_state
  local postgres_pid_json backend_pid_json worker_pid_json frontend_pid_json
  local postgres_ready backend_ready worker_ready frontend_ready
  local backend_code worker_code frontend_code now

  postgres_state="$(service_state postgres)"
  backend_state="$(service_state backend)"
  worker_state="$(service_state worker)"
  frontend_state="$(service_state frontend)"

  postgres_pid_json="$(service_any_pid postgres || true)"
  backend_pid_json="$(service_any_pid backend || true)"
  worker_pid_json="$(service_any_pid worker || true)"
  frontend_pid_json="$(service_any_pid frontend || true)"

  postgres_sql_ok && postgres_ready=true || postgres_ready=false
  backend_code="$(http_code "$(service_health_url backend)")"
  worker_code="$(http_code "$(service_health_url worker)")"
  frontend_code="$(http_code "$(service_health_url frontend)")"
  [[ "${backend_code}" == '200' ]] && backend_ready=true || backend_ready=false
  [[ "${worker_code}" == '200' ]] && worker_ready=true || worker_ready=false
  [[ "${frontend_code}" == '200' ]] && frontend_ready=true || frontend_ready=false

  [[ -n "${postgres_pid_json}" ]] || postgres_pid_json='null'
  [[ -n "${backend_pid_json}" ]] || backend_pid_json='null'
  [[ -n "${worker_pid_json}" ]] || worker_pid_json='null'
  [[ -n "${frontend_pid_json}" ]] || frontend_pid_json='null'

  now="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  cat > "${STATUS_FILE}" <<JSON
{
  "generated_at": "${now}",
  "services": {
    "postgres": {
      "state": "${postgres_state}",
      "pid": ${postgres_pid_json},
      "port": ${POSTGRES_PORT},
      "log": "docker compose logs postgres",
      "ready": ${postgres_ready}
    },
    "backend": {
      "state": "${backend_state}",
      "pid": ${backend_pid_json},
      "port": ${BACKEND_PORT},
      "log": "$(service_log_file backend)",
      "http_code": "${backend_code}",
      "ready": ${backend_ready}
    },
    "worker": {
      "state": "${worker_state}",
      "pid": ${worker_pid_json},
      "port": ${WORKER_PORT},
      "log": "$(service_log_file worker)",
      "http_code": "${worker_code}",
      "ready": ${worker_ready}
    },
    "frontend": {
      "state": "${frontend_state}",
      "pid": ${frontend_pid_json},
      "port": ${FRONTEND_PORT},
      "log": "$(service_log_file frontend)",
      "http_code": "${frontend_code}",
      "ready": ${frontend_ready}
    }
  }
}
JSON
}

show_status() {
  write_status_file
  for name in postgres worker backend frontend; do
    local state pid port log_file health
    state="$(service_state "${name}")"
    pid="$(service_any_pid "${name}" || true)"
    [[ -n "${pid}" ]] || pid='-'
    port="$(service_port "${name}")"
    if [[ "${name}" == 'postgres' ]]; then
      log_file='docker compose logs postgres'
      postgres_sql_ok && health='ok' || health='down'
    else
      log_file="$(service_log_file "${name}")"
      code="$(http_code "$(service_health_url "${name}")")"
      [[ "${code}" == '200' ]] && health='ok' || health='down'
    fi
    printf '%-8s state=%-9s pid=%-12s port=%-5s health=%-4s log=%s\n' "${name}" "${state}" "${pid}" "${port}" "${health}" "${log_file}"
  done
  printf 'status_file=%s\n' "${STATUS_FILE}"
}

show_ready() {
  write_status_file
  local failed=0
  if postgres_sql_ok; then
    printf '%-15s ok   host=%s port=%s db=%s\n' "postgres sql" "${POSTGRES_HOST}" "${POSTGRES_PORT}" "${POSTGRES_DEV_DB}"
  else
    printf '%-15s down host=%s port=%s db=%s\n' "postgres sql" "${POSTGRES_HOST}" "${POSTGRES_PORT}" "${POSTGRES_DEV_DB}"
    failed=1
  fi
  for name in backend worker frontend; do
    local url code
    url="$(service_health_url "${name}")"
    code="$(http_code "${url}")"
    printf '%-15s http=%s url=%s\n' "$(service_health_name "${name}")" "${code}" "${url}"
    if [[ "${code}" != '200' ]]; then failed=1; fi
  done
  return "${failed}"
}

run_migrate_head() {
  require_python_env
  log 'running migrations to head'
  (cd "${REPO_ROOT}" && PYTHONPATH="${REPO_ROOT}" "${PYTHON_BIN}" scripts/db_migrate.py upgrade head)
}

start_service() {
  local name="$1" state workdir pid_file log_file
  local -a cmd
  state="$(service_state "${name}")"
  if [[ "${state}" == 'running' ]]; then
    log "${name} already running"
    return 0
  fi
  if [[ "${state}" == 'port_busy' ]]; then
    fail "${name} port $(service_port "${name}") is already in use without a valid pid file; run ./scripts/dev_stack.sh down or inspect the port"
  fi
  case "${name}" in
    worker)
      require_python_env
      workdir="${REPO_ROOT}"
      cmd=(env "PYTHONPATH=${REPO_ROOT}" "${PYTHON_BIN}" -m uvicorn rpg_backend.llm_worker.main:app --reload --host "${WORKER_HOST}" --port "${WORKER_PORT}")
      ;;
    backend)
      require_python_env
      workdir="${REPO_ROOT}"
      cmd=(env "PYTHONPATH=${REPO_ROOT}" "${PYTHON_BIN}" -m uvicorn rpg_backend.main:app --reload --host "${BACKEND_HOST}" --port "${BACKEND_PORT}")
      ;;
    frontend)
      require_frontend_deps
      workdir="${FRONTEND_DIR}"
      if [[ -x "${FRONTEND_DIR}/node_modules/.bin/vite" ]]; then
        cmd=("${FRONTEND_DIR}/node_modules/.bin/vite" --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}")
      else
        cmd=(npm run dev -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}")
      fi
      ;;
    *) fail "unknown service '${name}'" ;;
  esac
  ensure_run_dir
  pid_file="$(service_pid_file "${name}")"
  log_file="$(service_log_file "${name}")"
  : > "${log_file}"
  log "starting ${name}"
  (
    cd "${workdir}"
    if command -v setsid >/dev/null 2>&1; then
      setsid nohup "${cmd[@]}" < /dev/null >> "${log_file}" 2>&1 &
    else
      nohup "${cmd[@]}" < /dev/null >> "${log_file}" 2>&1 &
    fi
    echo $! > "${pid_file}"
  )
  sleep 1
  local pid
  pid="$(tr -d '[:space:]' < "${pid_file}")"
  if ! pid_alive "${pid}"; then
    tail -n 60 "${log_file}" || true
    fail "${name} failed to stay running; see ${log_file}"
  fi
}

stop_service() {
  local name="$1" pid_file pid port port_pids
  pid_file="$(service_pid_file "${name}")"
  pid="$(service_pid "${name}" || true)"
  if [[ -n "${pid}" ]]; then
    log "stopping ${name} pid=${pid}"
    kill "${pid}" 2>/dev/null || true
    local try=1
    while pid_alive "${pid}" && (( try <= 15 )); do sleep 1; try=$(( try + 1 )); done
    if pid_alive "${pid}"; then warn "${name} did not stop after SIGTERM; sending SIGKILL"; kill -9 "${pid}" 2>/dev/null || true; fi
  fi
  rm -f "${pid_file}"
  port="$(service_port "${name}")"
  port_pids="$(list_pids_for_port "$(service_host "${name}")" "${port}" | paste -sd' ' -)"
  if [[ -n "${port_pids}" ]]; then
    warn "cleaning stale listeners for ${name} on port ${port}: ${port_pids}"
    kill ${port_pids} 2>/dev/null || true
    sleep 1
    port_pids="$(list_pids_for_port "$(service_host "${name}")" "${port}" | paste -sd' ' -)"
    if [[ -n "${port_pids}" ]]; then
      warn "forcing stale listeners for ${name} on port ${port}: ${port_pids}"
      kill -9 ${port_pids} 2>/dev/null || true
    fi
  fi
}

postgres_up() {
  require_compose
  log 'starting postgres'
  (cd "${REPO_ROOT}" && compose_cmd up -d postgres >/dev/null)
}

postgres_down() {
  require_compose
  log 'stopping postgres'
  (cd "${REPO_ROOT}" && compose_cmd stop postgres >/dev/null || true)
}

wait_for_stack_ready() {
  wait_for_postgres_ready || return 1
  wait_for_http_ok 'worker /ready' "$(service_health_url worker)" 90 1 || return 1
  wait_for_http_ok 'backend /ready' "$(service_health_url backend)" 90 1 || return 1
  wait_for_http_ok 'frontend /' "$(service_health_url frontend)" 90 1 || return 1
}

stack_up() {
  require_cmd curl
  require_cmd lsof
  require_python_env
  require_frontend_deps
  require_compose
  postgres_up
  wait_for_postgres_ready || fail 'postgres failed to become ready'
  run_migrate_head
  start_service worker
  start_service backend
  start_service frontend
  if ! wait_for_stack_ready; then
    warn 'stack failed readiness checks; shutting down partial services'
    stack_down false
    fail 'stack failed to become ready'
  fi
  write_status_file
  show_status
}

stack_down() {
  local stop_postgres="${1:-false}"
  require_cmd lsof
  ensure_run_dir
  stop_service frontend
  stop_service backend
  stop_service worker
  if [[ "${stop_postgres}" == 'true' ]]; then
    postgres_down
  fi
  write_status_file
  show_status
}

reset_db() {
  require_python_env
  require_compose
  local env_json
  env_json="$(${PYTHON_BIN} - <<'PY'
from rpg_backend.config.settings import get_settings
from sqlalchemy.engine import make_url
import json
url = make_url((get_settings().database_url or '').strip())
payload = {
    'drivername': url.drivername,
    'username': url.username,
    'host': url.host,
    'port': url.port,
    'database': url.database,
}
print(json.dumps(payload))
PY
)"
  PG_ENV_JSON="${env_json}" POSTGRES_EXPECTED_HOST="${POSTGRES_HOST}" POSTGRES_EXPECTED_PORT="${POSTGRES_PORT}" POSTGRES_EXPECTED_USER="${POSTGRES_USER}" POSTGRES_EXPECTED_DB="${POSTGRES_DEV_DB}" "${PYTHON_BIN}" - <<'PY'
import json, os, sys
cfg = json.loads(os.environ['PG_ENV_JSON'])
if not str(cfg.get('drivername','')).startswith('postgresql'):
    raise SystemExit('APP_DATABASE_URL is not a local postgres url; resetdb only supports local compose postgres')
if cfg.get('host') != os.environ['POSTGRES_EXPECTED_HOST']:
    raise SystemExit('resetdb only supports host 127.0.0.1')
if int(cfg.get('port') or 0) != int(os.environ['POSTGRES_EXPECTED_PORT']):
    raise SystemExit('resetdb only supports port 8132')
if cfg.get('username') != os.environ['POSTGRES_EXPECTED_USER']:
    raise SystemExit('resetdb only supports local postgres user rpg_local')
if cfg.get('database') != os.environ['POSTGRES_EXPECTED_DB']:
    raise SystemExit('resetdb only supports local postgres database rpg_dev')
PY
  stack_down false
  postgres_up
  wait_for_postgres_ready || fail 'postgres failed to become ready'
  log "recreating postgres database ${POSTGRES_DEV_DB}"
  POSTGRES_HOST="${POSTGRES_HOST}" POSTGRES_PORT="${POSTGRES_PORT}" POSTGRES_USER="${POSTGRES_USER}" POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" POSTGRES_DEV_DB="${POSTGRES_DEV_DB}" \
  "${PYTHON_BIN}" - <<'PY'
import os
import psycopg
host=os.environ['POSTGRES_HOST']
port=int(os.environ['POSTGRES_PORT'])
user=os.environ['POSTGRES_USER']
password=os.environ['POSTGRES_PASSWORD']
database=os.environ['POSTGRES_DEV_DB']
with psycopg.connect(host=host, port=port, user=user, password=password, dbname='postgres', autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()", (database,))
        cur.execute(f'DROP DATABASE IF EXISTS "{database}"')
        cur.execute(f'CREATE DATABASE "{database}"')
PY
  run_migrate_head
  start_service worker
  start_service backend
  start_service frontend
  wait_for_stack_ready || fail 'stack failed to become ready after resetdb'
  write_status_file
  show_status
}

show_logs() {
  ensure_run_dir
  if [[ $# -eq 0 ]]; then
    for name in postgres worker backend frontend; do
      printf '===== %s =====\n' "${name}"
      if [[ "${name}" == 'postgres' ]]; then
        (cd "${REPO_ROOT}" && compose_cmd logs --tail "${TAIL_LINES}" postgres) || true
      elif [[ -f "$(service_log_file "${name}")" ]]; then
        tail -n "${TAIL_LINES}" "$(service_log_file "${name}")"
      else
        printf '(no log yet)\n'
      fi
      printf '\n'
    done
    return 0
  fi
  case "$1" in
    postgres)
      (cd "${REPO_ROOT}" && compose_cmd logs --tail "${TAIL_LINES}" postgres)
      ;;
    worker|backend|frontend)
      if [[ -f "$(service_log_file "$1")" ]]; then tail -n "${TAIL_LINES}" "$(service_log_file "$1")"; else printf '(no log yet for %s)\n' "$1"; fi
      ;;
    *) fail "unknown service '$1'; expected one of: postgres backend worker frontend" ;;
  esac
}

main() {
  local command="${1:-}"
  case "${command}" in
    up)
      stack_up ;;
    down)
      shift || true
      if [[ "${1:-}" == '--all' ]]; then stack_down true; else stack_down false; fi ;;
    restart)
      stack_down false
      stack_up ;;
    status)
      show_status ;;
    resetdb)
      reset_db ;;
    logs)
      shift || true
      show_logs "$@" ;;
    ready)
      show_ready ;;
    ''|-h|--help|help)
      usage ;;
    *)
      usage >&2
      fail "unknown command '${command}'" ;;
  esac
}

main "$@"
