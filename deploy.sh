#!/usr/bin/env bash
# Argus 服务器部署助手，只拉取预构建镜像，不在服务器编译。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
compose() { docker compose --env-file docker/.env -f docker/docker-compose.yaml "$@"; }
case "${1:-help}" in
  pull) compose pull ;;
  start) compose up -d --no-build ;;
  stop) compose stop ;;
  restart) compose restart ;;
  logs) compose logs --tail=100 -f ;;
  status) compose ps ;;
  *) echo "用法: ./deploy.sh pull|start|stop|restart|logs|status" ;;
esac
