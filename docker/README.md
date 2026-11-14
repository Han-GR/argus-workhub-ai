# Argus 线上部署

仅部署 Web 和后端，连接已有 MySQL/Redis。首次部署前确保 `argus.ruitoolai.com` 已解析到服务器，开放 80/443，并把域名证书放在 `docker/nginx/ssl/server.pem` 与 `server.key`。

1. 复制 `docker/.env.example` 为 `docker/.env`，填写现有数据库、Redis 和密钥。容器不能用 localhost 连接宿主机服务；同机可使用 `host.docker.internal`，远程服务使用其实际地址。
2. 为项目创建独立的空 MySQL 数据库（utf8mb4），并授予后端建表及读写权限。Redis 需要支持 Search 向量索引。
3. 在 `frontend/web` 执行 `pnpm install`。
4. 回到项目根目录，运行 `./deploy.sh build`，再运行 `./deploy.sh start`。启动会初始化空库的表和种子数据；以 `argus_initial` 为唯一初始迁移，共创建 25 张表，不支持旧版数据库结构。默认初始化董事长办公室及七个下属部门，并为普通角色分配业务菜单权限。
5. 打开 https://argus.ruitoolai.com，使用 `./deploy.sh status` 和 `./deploy.sh logs` 查看服务。

上传文件使用 `backend_uploads` 命名卷，档案及应用数据使用 `backend_data` 命名卷持久化，AI 会话保存在 MySQL。备份需同时包含 MySQL、Redis 和这两个数据卷；不要使用 `docker compose down -v` 删除数据卷。首次登录后修改所有初始化账号的默认密码。停止使用 `./deploy.sh stop`，不会删除数据。源码变更后重新 build/start。
