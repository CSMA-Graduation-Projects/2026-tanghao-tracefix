# cfix

## 项目简介

cfix 是一个围绕“代码生成 -> 执行反馈 -> 自动修复 -> 版本对比 -> 实验评估”流程构建的全栈系统。

仓库当前由三部分组成：

- `cfix_frontend`：基于 Vue 3 + Vite + Element Plus 的前端工作台。
- `cfix_server`：基于 FastAPI + SQLAlchemy 的后端服务，负责认证、任务编排、运行记录、版本管理和实验评估。
- `cfix_schema.sql`：MySQL 8.x 初始化脚本。

执行链路里最重要的约束是：前后端服务本身默认运行在宿主机上，真正需要隔离的用户代码通过 Docker 容器沙箱执行。后端的 `SANDBOX_BACKEND=docker` 时，会调用 `cfix_server/sandbox/py/Dockerfile` 构建出来的镜像 `cfix-python-sandbox:latest` 完成隔离运行。

## 仓库结构

```text
cfix/
├─ cfix_frontend/      # Vue 3 前端
├─ cfix_server/        # FastAPI 后端
└─ cfix_schema.sql     # MySQL 初始化脚本
```

## 运行方式

### 1. 前置条件

建议先准备以下环境：

- Node.js 18+
- Python 3.11+
- MySQL 8.x
- Docker

### 2. 初始化数据库

根据 MySQL 脚本：cfix_schema.sql 创建数据库：cfix_db


### 3. 构建 Docker 沙箱镜像

后端配置中已经预留了 Docker 沙箱执行器，默认镜像名为 `cfix-python-sandbox:latest`。先在后端目录构建镜像：

```powershell
Set-Location cfix_server
docker build -t cfix-python-sandbox:latest -f sandbox/py/Dockerfile .
```

### 4. 配置并启动后端

进入后端目录，安装依赖并准备 `.env`：

```powershell
Set-Location cfix_server
cp .env.example .env
pip install -r req.txt
```

至少确认下面几组配置和你的实际环境一致：

- `MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DB`
- `JWT_SECRET`
- `SANDBOX_BACKEND=docker`
- `SANDBOX_IMAGE=cfix-python-sandbox:latest`
- `SANDBOX_WORK_ROOT`

Windows 本机常见配置示例：

```env
SANDBOX_BACKEND=docker
SANDBOX_IMAGE=cfix-python-sandbox:latest
SANDBOX_WORK_ROOT=D:\cfix_sandbox
```

后端启动命令：

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

启动后可访问：

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/docs`

如果只是临时联调，也可以把 `LLM_ENABLE=false` 避免依赖真实模型额度；真正验证生成与修复链路时，再补齐模型配置。

### 5. 配置并启动前端

进入前端目录，准备环境变量并安装依赖：

```powershell
Set-Location ..\cfix_frontend
cp .env.example .env
npm install
```

前端默认通过 `VITE_API_BASE_URL` 指向后端：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

开发启动命令：

```powershell
npm run dev
```

启动后通常可在 `http://127.0.0.1:5173` 打开系统。

### 6. 使用 Docker Compose

根目录现在已经提供 `docker-compose.yml`，可以直接拉起 MySQL、后端和前端开发环境：

```powershell
docker compose up --build
```

默认暴露端口：

- MySQL：`3306`
- 后端：`8000`
- 前端：`5173`

需要注意的是，当前后端的 `docker_runner` 依赖宿主机绝对路径做 bind mount，所以当后端本身也运行在 Compose 容器里时，默认更稳妥的配置是 `SANDBOX_BACKEND=safe_exec`。根目录的 compose 已经按这个默认值处理，保证整套容器化联调可以直接启动。

如果你要继续使用“每次执行都新开一个独立 Docker 容器”的沙箱模式，建议让后端继续运行在宿主机，或者进一步改造 `cfix_server/app/sand/docker_runner.py` 的挂载策略。

## 部署说明

根目录已经提供 `docker-compose.yml`，适合本地一体化联调。如果要做更接近生产环境的部署，当前代码仍然更适合下面这种拆分方式：

1. MySQL 独立部署，并提前导入 `cfix_schema.sql` 或执行 `python -m app.db.init_db`。
2. 后端以 Python 进程方式部署在应用主机上。
3. Docker 只负责承载待执行代码的沙箱，不直接替代后端 Web 服务。
4. 前端通过 `npm run build` 生成静态资源，再由 Nginx、Caddy 或其他静态服务器托管。

### 建议的单机部署步骤

#### 前端

```powershell
Set-Location cfix_frontend
cp .env.example .env
npm install
npm run build
```

将生成的 `dist/` 发布到静态站点目录。

#### 后端

```powershell
Set-Location cfix_server
cp .env.example .env
pip install -r req.txt
docker build -t cfix-python-sandbox:latest -f sandbox/py/Dockerfile .
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 部署时建议额外确认

- 将 `APP_DEBUG` 设为 `false`。
- 使用强随机值替换 `JWT_SECRET`。
- 只有在模型地址和密钥都可用时再启用 `LLM_ENABLE=true`。
- `SANDBOX_WORK_ROOT` 必须是宿主机上可写目录；Windows 可用 `D:\cfix_sandbox`，Linux 更适合 `/tmp/cfix_sandbox`。
- 运行后端的主机必须安装 Docker，并且应用进程能够直接调用 `docker` 命令。

如果后续需要把前后端和数据库也全部容器化，可以再在当前 README 基础上补 `docker-compose.yml`；但就仓库现状而言，以上说明和代码实现是一致的。

## 补充文档

- `cfix_frontend/README.md`：前端页面与接口说明
- `cfix_server/README.md`：后端接口、配置项和模块分工说明