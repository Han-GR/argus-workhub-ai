# Argus Workhub AI

基于 FastAPI + Vue 3 的企业内部协作演示项目。在线地址：https://argus.ruitoolai.com

## 功能范围

- 工作台：集中进入业务页面，按账号权限显示入口。
- 档案文件：文件上传、浏览、下载、目录管理及存储传输。
- 任务协同：协作工单、状态跟踪与评论。
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

### 知识库问答

已有数据库先在 `backend` 目录执行 `uv run --extra mysql main.py upgrade --env=dev`，创建知识库文档表。Redis 必须支持 Search 向量索引（`FT.CREATE`、`FT.SEARCH`）；普通不带 Search 的 Redis 无法使用知识库。数据库保存文档原文，Redis 保存向量和分块，备份时需同时考虑两者。

知识库向量索引固定使用同一 Redis 实例的 **DB 0**（Search 的限制），登录会话与普通缓存仍使用 `REDIS_DB_NAME` 指定的数据库，无需将业务缓存切换到 DB 0。

进入左侧 **知识库**，超级管理员在“向量模型配置”中统一保存服务商、模型、维度和密钥，所有成员共用，不需要个人向量 API Key。问答暂时使用各成员在 AI 助手中保存的聊天模型配置。维护人创建知识库时选择“全公司”或具体部门，再上传 TXT、Markdown 或文字 PDF。每份文件最多 2 MB，PDF 最多 50 页，提取文字最多 60 KB；每个知识库最多 100 份文档。更换向量模型或维度后，维护人需要重建所有已有文档的索引。提问后可核对引用原文。

通过角色菜单授权 `module_ai:knowledge:query` 开放查看和提问；`module_ai:knowledge:manage` 指定全局维护人，`module_ai:knowledge:department` 指定本部门维护人。普通成员可读全公司和本人当前部门的资料；部门范围严格匹配部门，不自动包含子部门。全局维护人可管理全部知识库，部门维护人仅可创建和维护本部门知识库。超级管理员可维护全部知识库并配置企业向量模型；普通成员和维护人均不能读取密钥。知识库创建后不修改可见范围，删除知识库前须先清空文档。本功能采用全新的企业知识库表结构和接口，不迁移旧的个人知识库或个人向量配置。

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

测试默认使用隔离 SQLite 和模拟 Redis；真实 PostgreSQL/Redis/存储集成测试需要单独配置，不会默认连接开发业务库。现有历史数据库表不自动删除，迁移历史保留以保障已有库升级。

Logo 单一来源为 `design/assets`，使用 `node scripts/sync-brand-assets.mjs` 同步；设计 token 由 `node scripts/design-tokens/generate.mjs` 生成，品牌检查为 `node scripts/check-brand-consistency.mjs`。

## 线上部署

见 [docker/README.md](docker/README.md)。部署仅包含 Web、后端和 Nginx，连接已有 MySQL/Redis。`./deploy.sh build` 构建并同步三份 Web 产物，`./deploy.sh start` 启动。域名首页跳转 `/web/`。
