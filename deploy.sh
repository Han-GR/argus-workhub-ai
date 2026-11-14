#!/usr/bin/env bash
# Argus 部署助手。在部署服务器运行，统一管理 Web、后端、MySQL 和 Redis。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
compose() { docker compose --env-file docker/.env -f docker/docker-compose.yaml "$@"; }
case "${1:-help}" in
  build) compose build ;;
  start) compose up -d ;;
  stop) compose stop ;;
  restart) compose restart ;;
  logs) compose logs --tail=100 -f ;;
  status) compose ps ;;
  *) echo "用法: ./deploy.sh build|start|stop|restart|logs|status" ;;
esac
