# 麒麟智能运维 Agent

## 项目简介

本项目面向麒麟操作系统场景，建设一个支持自然语言运维、受控执行、审计追踪与安全审批的智能运维平台。

## 目录结构

- `frontend/`：Vue 3 + TypeScript + Vite 前端
- `backend/`：Python FastAPI 后端
- `agent/`：Agent 编排层
- `mcp-servers/`：MCP 工具服务
- `docs/`：需求、设计、规范文档
- `deploy/`：部署脚本与服务配置
- `scripts/`：辅助脚本

## 当前技术栈

### 前端

- Vue 3
- TypeScript
- Vite
- Vue Router 4
- Pinia
- Element Plus
- Axios
- VueUse
- ECharts
- pnpm

### 后端

- Python 3.10+
- FastAPI
- Uvicorn
- Pydantic
- SQLAlchemy
- PostgreSQL
- Alembic
- DeepSeek Agent

## Docker 一键部署（推荐）

新电脑只需安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)，无需单独安装 Node.js / Python / PostgreSQL。

### 快速启动

**Linux / macOS**

```bash
git clone <repo-url> kylinops
cd kylinops
cp .env.docker.example .env.docker
# 编辑 .env.docker，填入 LLM_API_KEY

chmod +x scripts/docker-up.sh
./scripts/docker-up.sh
```

**Windows PowerShell**

```powershell
git clone <repo-url> kylinops
cd kylinops
Copy-Item .env.docker.example .env.docker
# 编辑 .env.docker，填入 LLM_API_KEY

.\scripts\docker-up.ps1
```

启动后访问 `http://localhost:8000`，默认账号 `admin / admin123`。

### Docker 架构

默认启用 **Demo SSH 模式**（`--profile demo`），包含两个容器：

| 容器 | 说明 |
|------|------|
| `kylinops-app` | 前后端一体（FastAPI + Vue 静态资源），端口 8000 |
| `kylinops-target-vm` | Demo Linux SSH 目标机，供 Agent 执行运维命令 |

数据（SQLite、上传文件、生成资源）持久化在 Docker Volume `kylinops-data` 中。

### 常用命令

```bash
# 启动（Demo SSH 模式）
docker compose --profile demo up -d --build

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f app

# 停止
docker compose --profile demo down

# 重置数据（重新初始化默认用户）
docker compose --profile demo down -v
docker compose --profile demo up -d --build
```

### 连接真实 SSH 目标机

编辑 `.env.docker`，将 SSH 指向局域网内的麒麟 / Linux 主机，并挂载你的私钥：

```yaml
# docker-compose.yml 中 app.volumes 改为：
# - C:/Users/你/.ssh/id_ed25519:/run/secrets/ssh_key:ro
```

```env
SSH_HOST=192.168.x.x
SSH_PORT=22
SSH_USER=ty
SSH_KEY_PATH=/run/secrets/ssh_key
```

然后不带 demo profile 启动：

```bash
docker compose up -d --build
```

### 可选：PostgreSQL

```bash
# .env.docker 中设置：
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/yunwei

docker compose --profile demo --profile postgres up -d --build
```

### 相关文件

```
docker-compose.yml
.env.docker.example
deploy/docker/Dockerfile
deploy/docker/target-vm/
scripts/docker-up.sh
scripts/docker-up.ps1
```

---

## 启动前准备

### 前端环境

```bash
node -v
pnpm -v
```

建议使用：
- Node.js 20+
- pnpm 9+

### 后端环境

```bash
python --version
```

建议使用：
- Python 3.10+

### PostgreSQL

- 安装并启动 PostgreSQL 14+
- 创建数据库：`yunwei`
- 确认数据库连接串可用

### DeepSeek

- 准备 DeepSeek API Key
- 配置后端 `.env`

## 安装依赖

### 前端

```bash
cd frontend
pnpm install
```

### 后端

```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

## 环境变量配置

复制 `backend/.env.example` 为 `backend/.env`，按实际情况修改：

- `DATABASE_URL`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`

## 数据库初始化与迁移

### 执行迁移

```bash
cd backend
.venv\\Scripts\\activate
alembic upgrade head
```

### 初始化演示数据

```bash
cd backend
.venv\\Scripts\\activate
python scripts/init_db.py
```

## 启动项目

### 启动后端

```bash
cd backend
.venv\\Scripts\\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

访问：
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/api/info`

### 启动前端

```bash
cd frontend
pnpm dev
```

默认访问：
- `http://127.0.0.1:5173`

## 联调接口

- `GET /health`
- `GET /api/info`
- `POST /api/chat`
- `GET /api/sessions`
- `POST /api/sessions`
- `GET /api/sessions/{session_id}/messages`
- `POST /api/approval`
- `GET /api/audits`

## 会话切换说明

- 点击左侧“会话列表”打开抽屉
- 支持搜索会话
- 支持新建会话
- 选择会话后会自动切换到该会话
- 中间对话区会重新读取对应会话的历史消息

## 开发顺序建议

1. 启动 PostgreSQL 并配置 `.env`
2. 执行 Alembic 迁移
3. 初始化演示数据
4. 启动后端，确认健康检查接口正常
5. 配置 DeepSeek API Key，确认聊天接口返回可用内容
6. 启动前端，确认首页与联调接口正常
7. 继续扩展 Agent 工具调用与安全护栏

## 说明

当前仓库已完成项目骨架、前后端联调基础与页面原型，并开始接入 PostgreSQL 与 DeepSeek Agent。聊天、会话、审计接口已具备数据库读写能力，会话切换也已联动到消息历史刷新。后续可继续扩展数据库迁移、真实会话存储、MCP 工具与更完整的安全控制逻辑。
