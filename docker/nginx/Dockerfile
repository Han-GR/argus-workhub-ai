FROM node:22-bookworm-slim AS web-build

WORKDIR /build/web
ENV HUSKY=0
RUN npm install --global pnpm@9.15.3

COPY frontend/web/package.json frontend/web/pnpm-lock.yaml frontend/web/.npmrc ./
RUN pnpm install --frozen-lockfile

COPY frontend/web/ ./
COPY frontend/web/.env.production.example .env.production
RUN pnpm build

FROM nginx:1.27-alpine
COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf
COPY docker/nginx/cache-headers.inc /etc/nginx/cache-headers.inc
COPY --from=web-build /build/web/dist/ /usr/share/nginx/html/web/dist/
