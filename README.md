# Argus Workhub AI

基于 FastAPI + Vue 3 的企业内部协作演示项目。在线地址：https://argus.ruitoolai.com

## 功能范围

- 工作台：集中进入业务页面，按账号权限显示入口。
- 档案文件：按个人、部门、全公司共享文件，支持上传、下载、文件夹管理和受权限控制的复制、移动。
- 任务协同：下设“我的任务”和“会议纪要”，支持任务分配、状态跟踪、评论，以及会议待办提取与人工确认创建。
- 知识库：独立入口，支持全公司与部门资料共享，使用 LlamaIndex + Redis Search 检索并展示引用原文。
- AI 助手：智能对话、会话记录和只读文件查询工具。
- 系统管理：用户、角色、部门、岗位、菜单按钮权限、数据范围、字典、参数和操作日志。
- 个人中心：个人资料、头像、密码和当前用户的登录会话。

## 本地启动

Python 3.12+、Node.js 20.19+，先准备 MySQL 与 Redis。

后端（从项目根目录开始）：

```bash
cd backend
cp -n env/.env.example env/.env.dev
# 编辑 env/.env.dev，填写 MySQL、Redis、SECRET_KEY；先创建 argus 数据库
uv sync --extra mysql
uv run --extra mysql main.py run --env=dev
```

另一个终端启动前端：

```bash
cd frontend/web
cp -n .env.development.example .env.development
pnpm install
pnpm dev
```

访问 http://localhost:5180/web/，接口文档为 http://localhost:8001/api/v1/docs。首次初始化账号 `super` / `123456`；公开部署前修改默认密码。AI 功能需要有效的模型连接配置。

### 档案文件权限

左侧 **档案文件** 直接包含 **文件管理** 和 **存储源管理**。根目录上传文件或新建文件夹时选择“仅自己可见”“仅部门可见”或“全公司可见”，文件夹内的条目统一继承顶层文件夹范围。

成员只能管理自己上传的文件；`module_task:storage:browse:department_manage` 允许管理本部门非私有档案，`module_task:storage:browse:manage_all` 单独授予跨部门档案管理权。超级管理员身份不自动绕过文件可见范围。文件夹的重命名、移动、删除和共享范围修改会校验全部内部条目，不允许借自己的文件夹删除他人文件。复制和上传均不覆盖已有路径。

存储配置管理员使用 `module_task:storage:node:manage`，与跨部门文件权限分开授权。普通成员从文件接口取得不含地址和凭据的存储源摘要。AI 文件查询使用相同的档案权限；下载需登录，文件不提供匿名分享链接。原始传输任务的创建需要同时拥有存储配置及跨部门档案管理权限，且禁止操作档案保留目录。

本地档案保存在 `backend/data/archive`，数据库保存逻辑路径、上传者和共享范围，备份时需同时保存两者；对象存储须配置为私有桶。首次启动自动创建档案目录及权限表。

### 知识库问答

首次启动自动创建知识库文档表。Redis 必须支持 Search 向量索引（`FT.CREATE`、`FT.SEARCH`）；普通不带 Search 的 Redis 无法使用知识库。数据库保存文档原文，Redis 保存向量和分块，备份时需同时考虑两者。

知识库向量索引固定使用同一 Redis 实例的 **DB 0**（Search 的限制），登录会话与普通缓存仍使用 `REDIS_DB_NAME` 指定的数据库，无需将业务缓存切换到 DB 0。

左侧 **知识库** 下设 **文档管理** 和 **知识问答** 两个独立页面。文档管理负责上传、筛选和维护资料，知识问答负责提问及查看引用来源；管理员的向量模型配置入口放在文档管理页面。

进入 **知识库 → 文档管理**，所有拥有知识库访问权限的成员都可以上传 TXT、Markdown 或文字 PDF。上传时选择“全公司可见”或“仅部门可见”，部门由后端读取当前账号所属的有效部门，不能指定其他部门；没有有效部门时只能选择全公司可见。每份文件最多 2 MB，PDF 最多 50 页，提取文字最多 60 KB。

文档列表可筛选全部可见、全公司、本部门、我上传的。只有上传者能编辑名称、调整共享范围、替换文件、重建索引或删除文档，超级管理员也不能删改他人的文件。部门调动后，“我上传的”仍可维护原文件，但问答只允许访问全公司及当前部门的资料。

进入 **知识库 → 知识问答**，问答会先在数据库筛选当前账号可访问的文档，再执行向量检索；检索片段和引用同样经过权限过滤，其他部门的私有内容不会传给聊天模型。文档管理页面的列表筛选不改变问答范围，问答始终使用全公司及当前部门的可见资料。

通过角色菜单授权 `module_ai:knowledge:query` 开放整个文档共享与问答功能，无需再分配维护权限。菜单和操作权限默认独立勾选；接口每次请求实时核对入口授权，撤回后旧登录会话也无法继续使用知识库。向量模型由超级管理员统一配置，全员共用加密保存在后端的密钥；聊天模型暂时使用成员自己的配置。更换向量模型或维度后，已有文档由各自上传者重建索引。

分块会发送给配置的向量服务商，提问和检索片段会发送给聊天模型服务商。删除或重建后的旧向量在数据库提交成功后清理；清理失败会记警告，这些未引用向量不会再参与检索，但仍需运维清理。

## 检查

```bash
cd backend
uv run --extra mysql pytest -q
```

```bash
cd frontend/web
pnpm ts:check
pnpm test
pnpm build
```

测试默认使用隔离 SQLite 和模拟 Redis；真实 PostgreSQL/Redis/存储集成测试需要单独配置，不会默认连接开发业务库。数据库采用单一初始迁移 `argus_initial`，面向全新部署，不提供旧版结构兼容。首次启动创建 22 张业务表、2 张 AI 会话内部表及 1 张迁移版本表，共 25 张表。后续结构变更需生成并审查迁移后再升级，启动过程不会自动生成迁移。

Logo 单一来源为 `design/assets`，使用 `node scripts/sync-brand-assets.mjs` 同步；设计 token 由 `node scripts/design-tokens/generate.mjs` 生成，品牌检查为 `node scripts/check-brand-consistency.mjs`。

## 线上部署

见 [docker/README.md](docker/README.md)。本地通过 `bash publish.sh <版本号>` 在 Docker 中构建 AMD64 应用镜像并推送到阿里云北京 ACR；服务器设置相同的 `IMAGE_TAG` 后执行 `bash deploy.sh pull` 和 `bash deploy.sh start`，仅拉取运行，不在服务器编译。Compose 统一管理 Nginx（含 Web）、后端、MySQL 和 Redis Search，数据卷持久化，域名首页跳转 `/web/`。
