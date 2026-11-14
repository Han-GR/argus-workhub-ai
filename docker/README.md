# Argus 线上部署

应用镜像在本地电脑或 CI 中通过 Docker 构建，再推送到阿里云北京 ACR。服务器只拉取镜像并启动 Nginx（含 Web）、后端、MySQL 8.4 和 Redis 8.2，不执行前端编译或依赖安装。服务器只需 Git、Docker Engine 和 Compose 插件。

## 本地构建发布

先启动 Docker Desktop，并登录仓库（使用 ACR 访问凭证密码，不是服务器密码）：

```bash
docker login --username 你的ACR用户名 registry.cn-beijing.aliyuncs.com
bash publish.sh 20261114-1
```

`publish.sh` 固定构建 `linux/amd64`，适用于当前 x86_64 服务器；即使本机是 Apple Silicon，也不会误发布 ARM 镜像。两个镜像都构建完成后再推送：

- `registry.cn-beijing.aliyuncs.com/argus-ai/argus-backend:20261114-1`
- `registry.cn-beijing.aliyuncs.com/argus-ai/argus-web:20261114-1`

每次发布使用新版本号，例如下一次 `20261114-2`。本地构建如需更换 Python 包源，执行 `PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ bash publish.sh 20261114-1`。此脚本不读取服务器 `.env`，无需在本地准备生产数据库密码。

## 服务器首次部署

1. 域名 `argus.ruitoolai.com` 解析到服务器；确认 80/443 可用。将证书和私钥放在 `docker/nginx/ssl/server.pem` 和 `server.key`。使用 Cloudflare Origin CA 时开启代理，并选择 Full (strict)。
2. 拉取代码，在项目根目录复制 `docker/.env.example` 为 `docker/.env`，设置 `chmod 600 docker/.env`。已有 `.env` 不要覆盖，仅补充 `IMAGE_TAG=20261114-1`，与已发布版本保持一致。
3. 首次部署替换 MySQL root 密码、应用数据库密码、Redis 密码、`SECRET_KEY` 和 `DATA_ENCRYPTION_KEY`。每个值单独生成，可执行 `docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_hex(32))"`。密钥之后保持不变。数据库应用账号默认 `argus`，不能设为 `root`；无需手动建库。
4. 登录 ACR 后执行：

   ```bash
   docker login --username 你的ACR用户名 registry.cn-beijing.aliyuncs.com
   bash deploy.sh pull
   bash deploy.sh start
   bash deploy.sh status
   bash deploy.sh logs
   ```

   等价的部署命令是：

   ```bash
   docker compose --env-file docker/.env -f docker/docker-compose.yaml pull
   docker compose --env-file docker/.env -f docker/docker-compose.yaml up -d --no-build
   ```

5. MySQL、Redis 健康检查通过后，后端应用 `argus_initial` 并初始化 25 张表、董事长办公室及七个下属部门、8 个账号及默认角色权限，随后 Nginx 启动。不导入本地测试库，不兼容旧版数据库结构。
6. 打开 https://argus.ruitoolai.com，以 `super` / `123456` 登录，修改初始化账号密码，再配置向量模型和聊天模型，验证上传、问答及部门权限。

## 后续更新

本地修改并提交代码，使用新版本运行 `publish.sh`，确认两个镜像推送成功。服务器拉取最新代码，将 `.env` 的 `IMAGE_TAG` 改成新版本，再执行 `pull` 和 `start`。不要在这台 2 GB 服务器运行镜像构建。回退应用镜像可恢复先前版本号并执行 pull/start；数据库迁移不能仅靠换镜像回滚，结构变更前必须备份。

## 网络与数据

四个服务共用 Docker 网络，后端通过 `mysql:3306`、`redis:6379` 连接。仅 Nginx 发布 80/443。MySQL、Redis 首次仍需从 Docker Hub 拉取，已有本地镜像可复用。

Redis 官方 8.2 镜像包含 Search，开启 AOF（每秒刷盘）；健康检查验证认证和 `FT.SEARCH`。业务缓存使用 DB 1，向量索引固定 DB 0。前端使用 `frontend/web/.env.production.example`，Nginx 配置和静态产物打包进应用镜像，运行时仅挂载证书。

数据位于 `mysql_data`、`redis_data`、`backend_uploads`、`backend_data` 命名卷（名称带项目前缀）。备份包括 MySQL、Redis、两个文件卷及部署密钥。`bash deploy.sh stop` 不删除数据；不要运行 `docker compose down -v`。

MySQL 的建库和密码环境变量仅在空卷初始化时生效。改 `.env` 不会自动修改库内密码，轮换时先修改数据库账号，再更新配置并重建后端。修改 `.env` 后使用 start，restart 不加载新环境变量。运行内存仍需结合服务器其他容器的占用监控，免构建不代表 2 GB 一定足够运行全部服务。
