#!/usr/bin/env bash
# 在本地电脑或 CI 运行；先登录阿里云 ACR，再构建发布服务器所需的 AMD64 镜像。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
VERSION="${1:?用法: bash publish.sh <版本号，例如 20261114-1>}"
REGISTRY="registry.cn-beijing.aliyuncs.com/argus-ai"

docker buildx build --platform linux/amd64 --load \
  --build-arg DB=mysql \
  --build-arg "PIP_INDEX_URL=${PIP_INDEX_URL:-https://pypi.org/simple}" \
  -f docker/backend/Dockerfile -t "$REGISTRY/argus-backend:$VERSION" .
docker buildx build --platform linux/amd64 --load \
  -f docker/nginx/Dockerfile -t "$REGISTRY/argus-web:$VERSION" .

docker push "$REGISTRY/argus-backend:$VERSION"
docker push "$REGISTRY/argus-web:$VERSION"
printf '发布完成，请将服务器 docker/.env 中的 IMAGE_TAG 设置为 %s，再执行 pull/start。\n' "$VERSION"
