# Argus Workhub AI

基于 FastAPI + Vue 3 的企业内部协作演示项目。在线地址：https://argus.ruitoolai.com

## 功能范围

- 工作台：集中进入业务页面，按账号权限显示入口。
- 档案文件：文件上传、浏览、下载、目录管理及存储传输。
- 任务协同：协作工单、状态跟踪与评论。
- AI 助手：智能对话、会话记录和只读文件查询工具。
- 系统管理：用户、角色、部门、岗位、菜单按钮权限、数据范围、字典、参数和操作日志。
- 个人中心：个人资料、头像、密码和当前用户的登录会话。

独立档案业务与 AI 信息提取尚未实现。运维、SQL/SSH 控制台、生成器、定时调度、存储流程编排、公告、版本管理、示例页面、移动端和独立文档站已从源码移除。文件管理所需的存储节点和传输接口保留。

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
