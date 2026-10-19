# Docker 完整部署示例（KylinOps）

本文以本仓库真实的 `docker-compose.yml` 与 `deploy/docker/Dockerfile` 为主线，串联 **Dockerfile → 镜像分层 → 环境变量 → 网络 → 数据卷 → 服务编排** 的完整链路。

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│  宿主机 (Windows / Linux / macOS + Docker Desktop)                │
│                                                                 │
│  ┌──────────────────┐      bridge 网络 (默认)                  │
│  │  kylinops-app      │────── SSH_HOST=target-vm ──────────────┐ │
│  │  :8000 → 浏览器    │                                      │ │ │
│  │  Volume: data      │                                      │ │ │
│  └──────────────────┘                                      │ │ │
│           │                                                │ │ │
│           │  depends_on + healthcheck                      │ │ │
│           ▼                                                ▼ │ │
│  ┌──────────────────┐         ┌──────────────────┐         │ │ │
│  │  target-vm       │         │  postgres        │         │ │ │
│  │  (profile: demo) │         │  (profile: pg)   │         │ │ │
│  │  SSH :22         │         │  :5432           │         │ │ │
│  │  模拟麒麟 VM     │         │  Volume: pg-data │         │ │ │
│  └──────────────────┘         └──────────────────┘         │ │ │
│                                                                 │
│  命名卷: kylinops-data, pg-data                                 │
└─────────────────────────────────────────────────────────────────┘
```

| 服务 | 容器名 | 作用 | 默认是否启动 |
|------|--------|------|--------------|
| `app` | `kylinops-app` | FastAPI + Vue 一体，对外 8000 | 是 |
| `target-vm` | `kylinops-target-vm` | Demo SSH 目标机 | 需 `--profile demo` |
| `postgres` | `kylinops-postgres` | PostgreSQL 16 | 需 `--profile postgres` |

---

## 2. Dockerfile 与镜像分层

### 2.1 应用镜像（多阶段构建）

文件：`deploy/docker/Dockerfile`

```dockerfile
# ── Stage 1: frontend-build ── 只负责编译前端，不进入最终镜像
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com   # ← 独立一层：依赖缓存
COPY frontend/ ./
RUN npm run build                                      # ← 产出 dist/

# ── Stage 2: runtime ── 最终运行镜像
FROM python:3.11-slim-bookworm AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y openssh-client curl ...  # ← 系统层
COPY backend/requirements.txt ./backend/
RUN pip install -r backend/requirements.txt                       # ← Python 依赖层
COPY backend/ ./backend/
COPY tools/ ./tools/
COPY deploy/ ./deploy/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist     # ← 只拷贝构建产物
COPY deploy/docker/entrypoint.sh /entrypoint.sh
ENV PYTHONPATH=/app/backend
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK ... CMD curl -f http://127.0.0.1:8000/api/v1/system/health
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**为什么要多阶段？**

- Stage 1 含 Node.js、node_modules，体积大；最终镜像只需 `dist/` 静态文件
- 最终 `runtime` 镜像不含 npm，更小、更安全

### 2.2 Demo 目标机镜像

文件：`deploy/docker/target-vm/Dockerfile`

```dockerfile
FROM debian:bookworm-slim
RUN apt-get install openssh-server sudo ...     # 层 1：系统包
RUN useradd ops && sudoers ...                  # 层 2：用户
RUN mkdir /var/run/sshd && ssh-keygen -A        # 层 3：SSH
COPY init-ssh.sh /init-ssh.sh                   # 层 4：启动脚本
EXPOSE 22
CMD ["/init-ssh.sh"]
```

### 2.3 镜像分层原理

每条 `RUN`、`COPY`、`ENV` 都会生成一个 **只读层**；容器是在最上层加 **可写层**。

```bash
# 查看镜像层历史
docker history kylinops-app:latest

# 查看镜像占用
docker image inspect kylinops-app:latest --format '{{.Size}}'
```

**缓存规则（面试常考）：**

1. 把 **变动少** 的指令放前面（`requirements.txt` 先于 `COPY backend/`）
2. `COPY` 源文件变化会导致该层及之后所有层失效重建
3. `.dockerignore` 排除 `node_modules`、`__pycache__` 等，避免无意义失效

本仓库 `.dockerignore` 已排除：

```
frontend/node_modules
backend/__pycache__
backend/data
.git
```

---

## 3. 环境变量

### 3.1 三层来源（优先级从低到高）

| 来源 | 示例 | 说明 |
|------|------|------|
| Dockerfile `ENV` | `PYTHONUNBUFFERED=1` | 镜像内置默认值 |
| `env_file` | `.env.docker` | 批量注入，适合密钥与配置 |
| `environment` | `SSH_KEY_PATH=/run/secrets/ssh_key` | compose 内覆盖 |

`docker-compose.yml` 片段：

```yaml
services:
  app:
    env_file:
      - .env.docker
    environment:
      SSH_KEY_PATH: /run/secrets/ssh_key   # 覆盖 env_file 中同名项
```

### 3.2 关键环境变量（`.env.docker.example`）

```bash
# 必填
LLM_API_KEY=your_deepseek_api_key

# 数据库（默认 SQLite，数据在 Volume 里）
DATABASE_URL=sqlite+aiosqlite:////app/backend/data/kylinops.db

# Demo SSH（容器间通过服务名通信）
SSH_HOST=target-vm
SSH_PORT=22
SSH_USER=ops
SSH_KEY_PATH=/run/secrets/ssh_key

# 启用 PostgreSQL 时改为：
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/yunwei
```

### 3.3 容器内查看

```bash
docker exec kylinops-app env | grep -E 'LLM|SSH|DATABASE'
```

### 3.4 entrypoint 启动校验

`deploy/docker/entrypoint.sh` 在进程启动前：

- 检查 `LLM_API_KEY` 是否有效
- 创建上传目录
- 等待 `target-vm` SSH 就绪（最多 60 秒）

---

## 4. 网络

### 4.1 默认 bridge 网络

`docker compose up` 会创建项目级网络（如 `ruanjian_default`），各服务可通过 **服务名** 互访：

```
app 容器内:  ssh ops@target-vm
postgres 模式:  postgres:5432
```

**不要用 `localhost` 跨容器访问**——`localhost` 在容器内指向自身。

### 4.2 端口映射

```yaml
ports:
  - "${KYLINOPS_PORT:-8000}:8000"   # 宿主机:容器
```

仅 `app` 对外暴露 8000；`target-vm` 的 22 端口 **未映射到宿主机**，只能同网络内访问（更安全）。

### 4.3 常用网络命令

```bash
# 列出网络
docker network ls

# 查看 compose 网络详情
docker network inspect ruanjian_default

# 从 app 容器测试 SSH
docker exec kylinops-app ssh -o StrictHostKeyChecking=no -i /run/secrets/ssh_key ops@target-vm echo ok
```

### 4.4 自定义网络示例（扩展）

若需隔离，可显式声明：

```yaml
networks:
  frontend:
  backend:

services:
  app:
    networks: [frontend, backend]
  postgres:
    networks: [backend]
```

本仓库使用默认单网络，满足 Demo 与生产简化部署。

---

## 5. 数据卷（Volume）

### 5.1 命名卷 — 持久化应用数据

```yaml
volumes:
  kylinops-data:    # SQLite、上传文件、RAG 索引等
  pg-data:          # PostgreSQL 数据目录

services:
  app:
    volumes:
      - kylinops-data:/app/backend/data
```

数据生命周期 **独立于容器**：删容器不删卷，重建容器数据仍在。

```bash
# 查看卷
docker volume ls
docker volume inspect ruanjian_kylinops-data

# 备份 SQLite
docker run --rm -v ruanjian_kylinops-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/kylinops-data-backup.tar.gz -C /data .
```

### 5.2 绑定挂载 — 注入密钥（只读）

```yaml
volumes:
  - ./deploy/docker/demo-keys/id_ed25519:/run/secrets/ssh_key:ro
  - ./deploy/docker/demo-keys/id_ed25519.pub:/run/secrets/demo_pubkey:ro
```

| 类型 | 路径示例 | 用途 |
|------|----------|------|
| 命名卷 | `kylinops-data` | 数据库、上传文件 |
| 绑定挂载 `:ro` | SSH 私钥 | 密钥不进镜像，只读挂载 |

### 5.3 容器内临时层

未挂载的路径在容器删除后丢失——不要把重要数据只写在 `/tmp`。

---

## 6. 服务编排（docker-compose）

### 6.1 完整 compose 结构

```yaml
services:
  app:
    build:
      context: .                          # 构建上下文 = 项目根目录
      dockerfile: deploy/docker/Dockerfile
    container_name: kylinops-app
    ports:
      - "${KYLINOPS_PORT:-8000}:8000"
    env_file: [.env.docker]
    environment:
      SSH_KEY_PATH: /run/secrets/ssh_key
    volumes:
      - kylinops-data:/app/backend/data
      - ./deploy/docker/demo-keys/id_ed25519:/run/secrets/ssh_key:ro
    depends_on:
      target-vm:
        condition: service_healthy
        required: false                  # 无 demo profile 时不强制依赖
    restart: unless-stopped

  target-vm:
    profiles: ["demo"]                    # 仅 --profile demo 时启动
    build:
      context: ./deploy/docker/target-vm
    volumes:
      - ./deploy/docker/demo-keys/id_ed25519.pub:/run/secrets/demo_pubkey:ro
    restart: unless-stopped

  postgres:
    profiles: ["postgres"]
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: yunwei
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
    volumes:
      - pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d yunwei"]
      interval: 5s
      retries: 20
    restart: unless-stopped

volumes:
  kylinops-data:
  pg-data:
```

### 6.2 Profiles（按需组合）

| 命令 | 启动服务 | 场景 |
|------|----------|------|
| `docker compose up -d` | 仅 `app` | 最小启动（需自备 SSH 目标机） |
| `docker compose --profile demo up -d` | `app` + `target-vm` | **推荐 Demo** |
| `docker compose --profile demo --profile postgres up -d` | 全部 | 生产式 PostgreSQL |

### 6.3 健康检查与启动顺序

```yaml
depends_on:
  target-vm:
    condition: service_healthy   # 等 target-vm HEALTHCHECK 通过后再启动 app
```

`app` 镜像 HEALTHCHECK：轮询 `/api/v1/system/health`  
`target-vm` HEALTHCHECK：`pgrep sshd`

### 6.4 一键脚本

```bash
# Linux / macOS
./scripts/docker-up.sh

# Windows
.\scripts\docker-up.ps1
```

脚本等价于：检查 `.env.docker` → `docker compose --profile demo up -d --build`

---

## 7. 端到端操作手册

### 7.1 首次部署

```bash
cp .env.docker.example .env.docker
# 编辑 LLM_API_KEY

docker compose --profile demo up -d --build
```

### 7.2 验证各环节

```bash
# 1. 容器状态（应 healthy / running）
docker compose ps

# 2. 应用健康
curl http://localhost:8000/api/v1/system/health

# 3. 环境变量
docker exec kylinops-app printenv SSH_HOST

# 4. 卷已挂载
docker exec kylinops-app ls -la /app/backend/data

# 5. 网络互通
docker exec kylinops-app ping -c 2 target-vm

# 6. 浏览器
# http://localhost:8000  账号 admin / admin123
```

### 7.3 日常运维

```bash
docker compose logs -f app          # 看日志
docker compose restart app          # 重启
docker compose down                 # 停止（保留卷）
docker compose down -v              # 停止并删除卷（清空数据！）
docker compose build --no-cache app # 强制重建镜像
```

---

## 8. 最小对照示例（理解用）

若脱离本仓库，一个「单服务 + 卷 + 环境变量 + 端口」的最小例子：

```dockerfile
# mini/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
ENV APP_ENV=production
EXPOSE 8080
CMD ["python", "app.py"]
```

```yaml
# mini/docker-compose.yml
services:
  web:
    build: .
    ports:
      - "8080:8080"
    environment:
      APP_ENV: production
      DB_HOST: db
    volumes:
      - app-logs:/var/log/app
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: secret
    volumes:
      - pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      retries: 5

volumes:
  app-logs:
  pg-data:
```

KylinOps 的 compose 是该模式的 **超集**：多了 profile、SSH demo、多阶段构建、entrypoint 校验。

---

## 9. 常见问题

| 问题 | 原因 | 处理 |
|------|------|------|
| 启动报 LLM_API_KEY | `.env.docker` 未配置 | 填入有效 Key |
| SSH 连接失败 | 未加 `--profile demo` | `docker compose --profile demo up -d` |
| 数据丢失 | 用了 `down -v` | 从备份恢复卷 |
| 改代码不生效 | 未重建镜像 | `docker compose up -d --build` |
| 端口占用 | 8000 已被占用 | 改 `KYLINOPS_PORT=8080` |

---

## 10. 文件索引

| 文件 | 作用 |
|------|------|
| `docker-compose.yml` | 服务编排主文件 |
| `deploy/docker/Dockerfile` | 应用多阶段镜像 |
| `deploy/docker/target-vm/Dockerfile` | Demo SSH 目标机 |
| `deploy/docker/entrypoint.sh` | 启动前校验与等待 SSH |
| `.env.docker.example` | 环境变量模板 |
| `.dockerignore` | 构建上下文过滤 |
| `scripts/docker-up.sh` / `.ps1` | 一键启动脚本 |

---

**总结：** Dockerfile 定义镜像如何构建；分层决定构建速度与镜像大小；环境变量注入运行时配置；bridge 网络让服务名互通；Volume 持久化数据；Compose 用 profiles、depends_on、healthcheck 编排多服务生命周期。本仓库已具备完整可运行实例，按第 7 节命令即可端到端验证。
