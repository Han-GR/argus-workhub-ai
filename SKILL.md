---
name: argus-dev
description: Argus Web 与后端开发说明。
---

# Argus 开发指南

- backend：Python 3.12 + FastAPI + SQLAlchemy，`uv sync --extra mysql`，`uv run --extra mysql main.py run --env=dev`。
- frontend/web：Vue 3 + TypeScript + Element Plus，`pnpm install`、`pnpm dev`、`pnpm ts:check`、`pnpm test`、`pnpm build`。
- 后端读取 `backend/env/.env.dev`，线上 Docker 配置在 `docker/.env`；不输出或提交真实凭据。
- 保留功能：工作台、文件管理与存储传输、协作工单、AI 对话、用户/角色/部门/权限/日志、个人中心与登录会话、健康检查。
- 路由集中在 `backend/app/api/v1/routers.py`，菜单种子为 `backend/sql/sys_menu.json`。
- 公共 UI 组件以 Argus 开头，沿用现有表格/表单/弹窗套件；按钮权限与后端一致。
- MySQL/Redis 已有服务，部署说明见 docker/README.md。任何部署、数据库表删除、密钥轮换或远程服务重启，先说明影响并取得当次明确授权。
- 前端构建后同步 `frontend/web/dist` 到 `backend/dist` 与 `docker/nginx/web/dist`，避免部署旧包。
