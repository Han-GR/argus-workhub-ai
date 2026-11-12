#!/usr/bin/env bash
# Argus Web + 后端部署助手。在部署服务器运行；MySQL/Redis 使用现有服务。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
compose() { docker compose --env-file docker/.env -f docker/docker-compose.yaml "$@"; }
case "${1:-help}" in
  build)
    (cd frontend/web && pnpm build)
    mkdir -p docker/nginx/web/dist backend/dist
    rsync -a --delete frontend/web/dist/ docker/nginx/web/dist/
    rsync -a --delete frontend/web/dist/ backend/dist/
    compose build backend
    ;;
  start) compose up -d ;;
  stop) compose stop ;;
  restart) compose restart ;;
  logs) compose logs --tail=100 -f ;;
  status) compose ps ;;
  *) echo "用法: ./deploy.sh build|start|stop|restart|logs|status" ;;
esac
