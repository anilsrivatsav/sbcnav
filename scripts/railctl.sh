#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env.docker"
COMPOSE_FILE="$ROOT/compose.yaml"
CLIENT_COMPOSE_FILE="$ROOT/compose.client.yaml"
BACKUPS="$ROOT/backups"
ACTION="${1:-status}"
BACKUP="${2:-}"

initialize_environment() {
  [ -f "$ENV_FILE" ] && return
  password="$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')"
  sed "s/replace-with-a-long-url-safe-password/$password/" \
    "$ROOT/.env.docker.example" > "$ENV_FILE"
  echo "Created .env.docker with a generated PostgreSQL password."
}

env_value() {
  name="$1"
  fallback="$2"
  value="$(sed -n "s/^${name}=//p" "$ENV_FILE" | tail -n 1)"
  printf '%s' "${value:-$fallback}"
}

assert_docker() {
  command -v docker >/dev/null 2>&1 || {
    echo "Docker is not installed. Install Docker Desktop or Docker Engine." >&2
    exit 1
  }
  docker version >/dev/null 2>&1 || {
    echo "Docker is installed but its engine is not running." >&2
    exit 1
  }
  docker compose version >/dev/null 2>&1 || {
    echo "Docker Compose v2 is required." >&2
    exit 1
  }
}

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

client_compose() {
  docker compose --env-file "$ENV_FILE" -f "$CLIENT_COMPOSE_FILE" "$@"
}

wait_for_stack() {
  backend_port="$(env_value BACKEND_PORT 8000)"
  frontend_port="$(env_value FRONTEND_PORT 3000)"
  attempts=0
  while [ "$attempts" -lt 80 ]; do
    if curl -fsS "http://127.0.0.1:${backend_port}/api/health" >/dev/null 2>&1 &&
       curl -fsS "http://127.0.0.1:${frontend_port}" >/dev/null 2>&1; then
      echo "Stack is ready."
      echo "Dashboard: http://127.0.0.1:${frontend_port}"
      echo "API docs:  http://127.0.0.1:${backend_port}/docs"
      return
    fi
    attempts=$((attempts + 1))
    sleep 3
  done
  compose ps
  echo "The stack did not become healthy. Run ./scripts/railctl.sh logs." >&2
  exit 1
}

backup_database() {
  mkdir -p "$BACKUPS"
  name="rail_dashboard_$(date +%Y%m%d_%H%M%S).dump"
  compose exec -T db sh -c \
    "pg_dump -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -Fc -f '/backups/$name'"
  echo "Backup created: $BACKUPS/$name"
}

restore_database() {
  if [ -n "$BACKUP" ]; then
    file="$BACKUP"
  else
    file="$(find "$BACKUPS" -maxdepth 1 -name '*.dump' -type f -print | sort | tail -n 1)"
  fi
  [ -n "$file" ] && [ -f "$file" ] || {
    echo "No backup file was found." >&2
    exit 1
  }
  case "$(CDPATH= cd -- "$(dirname -- "$file")" && pwd)" in
    "$(CDPATH= cd -- "$BACKUPS" && pwd)") ;;
    *) echo "Restore files must be inside the project backups folder." >&2; exit 1 ;;
  esac
  name="$(basename "$file")"
  compose stop backend
  trap 'compose start backend' EXIT
  compose exec -T db sh -c \
    "pg_restore -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" --clean --if-exists --no-owner --no-privileges --exit-on-error '/backups/$name'"
  compose run --rm backend alembic upgrade head
  compose start backend
  trap - EXIT
  echo "Database restored from $file"
}

initialize_environment
assert_docker

case "$ACTION" in
  up) compose up -d --build; wait_for_stack ;;
  down) compose down ;;
  restart) compose restart; wait_for_stack ;;
  status) compose ps ;;
  logs) compose logs --tail 200 -f ;;
  open)
    wait_for_stack
    frontend_port="$(env_value FRONTEND_PORT 3000)"
    if command -v open >/dev/null 2>&1; then open "http://127.0.0.1:${frontend_port}"
    elif command -v xdg-open >/dev/null 2>&1; then xdg-open "http://127.0.0.1:${frontend_port}"
    else echo "Open http://127.0.0.1:${frontend_port}"; fi
    ;;
  backup) backup_database ;;
  restore) restore_database ;;
  migrate) compose run --rm backend alembic upgrade head ;;
  rebuild) compose build --pull; compose up -d; wait_for_stack ;;
  client-up)
    client_compose up -d --build
    echo "Frontend client started."
    ;;
  client-down) client_compose down ;;
  *)
    echo "Usage: $0 {up|down|restart|status|logs|open|backup|restore|migrate|rebuild|client-up|client-down} [backup-file]" >&2
    exit 2
    ;;
esac
