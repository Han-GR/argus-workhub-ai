# Argus 线上部署

仅部署 Web 和后端，连接已有 MySQL/Redis。首次部署前确保 `argus.ruitoolai.com` 已解析到服务器，开放 80/443，并把域名证书放在 `docker/nginx/ssl/server.pem` 与 `server.key`。

1. 复制 `docker/.env.example` 为 `docker/.env`，填写现有数据库、Redis 和密钥。容器不能用 localhost 连接宿主机服务；同机可使用 `host.docker.internal`，远程服务使用其实际地址。
2. 在服务器创建 `docker/backend/static/upload`，使运行后端的 UID 1000 可读写。
3. 在 `frontend/web` 执行 `pnpm install`。
4. 回到项目根目录，运行 `./deploy.sh build`，再运行 `./deploy.sh start`。启动会初始化空库的表和种子数据；已有库会应用保留的迁移，不自动删除历史业务表。
5. 打开 https://argus.ruitoolai.com，使用 `./deploy.sh status` 和 `./deploy.sh logs` 查看服务。

上传文件通过卷持久化，AI 会话保存在 MySQL。停止使用 `./deploy.sh stop`，不会删除数据。源码变更后重新 build/start。
