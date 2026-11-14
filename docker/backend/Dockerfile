# ============================================================================
# Argus 后端镜像（源码构建路径）
#
# 构建参数 DB 决定安装哪套数据库驱动：
#   docker build --build-arg DB=mysql    -f docker/backend/Dockerfile .   # 默认
#   docker build --build-arg DB=postgres -f docker/backend/Dockerfile .
#
# 正式部署：在部署服务器运行 deploy.sh 构建并启动。
# ============================================================================
FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/Han-GR/argus-workhub-ai"

ARG DB=mysql

ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    DB=${DB}

WORKDIR /home

# 依赖清单先复制（layer 缓存：只改代码时不重装依赖）
COPY ./backend/requirements/ /home/requirements/

# 只装所选数据库的驱动 + 存储与加密依赖
RUN pip install --no-cache-dir \
      -r /home/requirements/base.txt \
      -r /home/requirements/db/${DB}.txt \
      -r /home/requirements/storage.txt

# 应用代码（backend/.venv、logs、缓存、真实 .env.* 由根 .dockerignore 排除）
COPY ./backend/ /home/

# 以非 root 用户运行；运行时需要写的目录预先建好并交给该用户
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin app \
 && mkdir -p /home/logs /home/static/upload /home/data/archive /home/alembic/versions \
 && chown -R app:app /home
USER app

EXPOSE 8001

CMD ["python", "main.py", "run", "--env=prod"]
