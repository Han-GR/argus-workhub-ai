# Argus 线上部署

Docker Compose 统一运行 Nginx（提供 Web 和 HTTPS）、后端、MySQL 8.4 和 Redis 8.2。四个服务位于同一网络，后端通过 `mysql:3306` 和 `redis:6379` 连接；MySQL、Redis 和后端不映射宿主机端口，仅 Nginx 对外开放 80/443。Redis 官方 8.2 镜像包含 Search，适用于 amd64/arm64 服务器。

1. 服务器仅需安装 Git、Docker Engine 和 Compose 插件；Node.js、pnpm 和 Python 依赖均在镜像内安装，前端在 Docker 多阶段构建中编译，无需宿主机工具链。确认 80/443 未被其他服务占用，域名 `argus.ruitoolai.com` 已解析到服务器。
2. 将域名证书及私钥放到 `docker/nginx/ssl/server.pem` 和 `docker/nginx/ssl/server.key`。使用 Cloudflare Origin CA 证书时开启域名代理，并选择 Full (strict)。
3. 复制 `docker/.env.example` 为 `docker/.env`，设置 `chmod 600 docker/.env`，替换 MySQL root 密码、应用数据库密码、Redis 密码及令牌密钥。`DATABASE_USER` 使用独立应用账号（默认 `argus`），不能设为 `root`。每个密码或密钥分别运行一次 `docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_hex(32))"` 生成；`SECRET_KEY` 和 `DATA_ENCRYPTION_KEY` 部署后保持不变。无需手动建库，也无需配置数据库地址。
4. 在项目根目录执行（首次部署和后续更新使用相同命令）：

   ```bash
   docker compose --env-file docker/.env -f docker/docker-compose.yaml up -d --build
   bash deploy.sh status
   bash deploy.sh logs
   ```

5. MySQL、Redis 健康检查通过后，后端自动应用 `argus_initial` 初始迁移并导入种子，随后 Nginx 启动。业务库共 25 张表，初始化董事长办公室及七个下属部门、8 个账号和默认角色权限；不支持旧版数据库结构，无需导入本地测试库。
6. 打开 https://argus.ruitoolai.com，以 `super` / `123456` 登录，修改所有初始化账号的默认密码，再配置向量模型、聊天模型，验证上传、问答及部门权限。

Redis 开启 AOF（每秒刷盘），健康检查同时验证登录和 `FT.SEARCH` 命令可用。业务缓存使用 `REDIS_DB_NAME`（默认 1），知识库向量索引固定使用 DB 0。

数据保存在 `mysql_data`、`redis_data`、`backend_uploads`、`backend_data` 四个命名卷中（实际名称带 Compose 项目前缀）。备份需包含 MySQL 数据库、Redis 数据、两个文件卷及安全保存的部署密钥。停止使用 `bash deploy.sh stop`，不会删除数据；不要运行 `docker compose down -v`。

MySQL 的账号密码及建库环境变量只在空数据卷首次初始化时生效。后续修改 `.env` 不会修改库内密码，轮换时需先在 MySQL 中修改对应账号，再更新配置并重建后端容器。源码变更后重新执行 build/start；修改 `.env` 后执行 start 使容器重建，单独 restart 不会载入新环境变量。

前端构建使用 `frontend/web/.env.production.example`，默认域名为 `argus.ruitoolai.com`；前端配置属于公开构建参数，不要填写任何服务端密钥。Nginx 配置及静态产物打包进镜像，运行时仅挂载证书。`bash deploy.sh build` / `start` 仍可分别构建和启动，均只调用 Docker Compose。
