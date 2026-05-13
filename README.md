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
BYSJ/
├─ cfix/
│  ├─ cfix_frontend/   # Vue 3 前端
│  ├─ cfix_server/     # FastAPI 后端
│  └─ cfix_schema.sql  # MySQL 初始化脚本
├─ docker-compose.yml
└─ README.md
```

## 运行方式

### 1. 前置条件

建议先准备以下环境：

- Node.js 18+
- Python 3.11+
- MySQL 8.x
- Docker

### 2. 初始化数据库

根据 MySQL 脚本 `cfix/cfix_schema.sql` 创建数据库 `cfix_db`。


### 3. 构建 Docker 沙箱镜像

后端配置中已经预留了 Docker 沙箱执行器，默认镜像名为 `cfix-python-sandbox:latest`。先在后端目录构建镜像：

```powershell
Set-Location cfix\cfix_server
docker build -t cfix-python-sandbox:latest -f sandbox/py/Dockerfile .
```

### 4. 配置并启动后端

进入后端目录，安装依赖并准备 `.env`：

```powershell
Set-Location cfix\cfix_server
cp .env.example .env
pip install -r req.txt
```

至少确认下面几组配置和你的实际环境一致：

- `MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DB`
- `JWT_SECRET`
- `CORS_ALLOW_ORIGINS`
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
Set-Location cfix\cfix_frontend
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
Set-Location cfix\cfix_frontend
cp .env.example .env
npm install
npm run build
```

将生成的 `dist/` 发布到静态站点目录。

#### 后端

```powershell
Set-Location cfix\cfix_server
cp .env.example .env
pip install -r req.txt
docker build -t cfix-python-sandbox:latest -f sandbox/py/Dockerfile .
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 云平台提交建议

如果你的目标是完成老师要求的“GitHub 仓库 + 云平台在线演示”，当前这个项目最稳妥的方案不是纯前后端 Serverless 拆分，而是：

1. GitHub 仓库保留当前完整代码。
2. 云平台优先选支持 Docker 和长期运行进程的 Linux 主机，例如腾讯云轻量应用服务器、阿里云 ECS、华为云云耀云服务器。
3. 前端静态资源和后端 API 可以部署在同一台主机上；MySQL 也可以同机部署，便于课程演示。
4. 如果必须拆分部署到腾讯 EdgeOne Pages + 腾讯 CloudBase 这类平台，后端请改为 `SANDBOX_BACKEND=safe_exec`，不要依赖 Docker 沙箱。

这样做的原因很直接：当前系统的“代码运行/实验”链路依赖 MySQL，并且推荐用 Docker 做隔离执行；很多免费 PaaS 对 Docker-in-Docker、宿主机挂载和长时任务支持都不稳定。

### 腾讯 EdgeOne Pages 前端 + 腾讯 CloudBase 后端

如果你决定采用“腾讯 EdgeOne Pages 部署前端 + 腾讯 CloudBase 云托管部署后端”的分离方案，当前仓库已经按这个方向做了两处调整：

1. 前端路由已经切换为 hash 模式，避免静态站点在刷新深层路由时返回 404。
2. 后端目录 `cfix/cfix_server` 下增加了 `Dockerfile`，可以直接用于 CloudBase 云托管的容器部署。

这个方案能跑通，但有两个前提你必须先接受：

1. CloudBase 这里不要使用 Docker 沙箱，环境变量里必须设置 `SANDBOX_BACKEND=safe_exec`。
2. 当前后端仍然使用 MySQL，所以你还需要准备一个可从 CloudBase 访问的 MySQL 实例，最方便的选择就是腾讯云 MySQL。

#### 1. 部署前端到 EdgeOne Pages

在 EdgeOne Pages 新建项目时，直接连接这个 GitHub 仓库，然后把项目根目录设置为：

```text
cfix/cfix_frontend
```

建议填写如下构建参数：

```text
Framework Preset: Vite
Install Command: npm install
Build Command: npm run build
Output Directory: dist
```

前端环境变量至少配置：

```env
VITE_API_BASE_URL=https://你的-cloudbase-后端域名/api/v1
```

由于 EdgeOne Pages 的静态重写规则不适合直接托管 Vue history 路由，当前前端已经改为 hash 路由。部署后访问地址会是这种形式：

```text
https://你的-edgeone-域名/#/workbench
```

#### 2. 部署后端到 CloudBase 云托管

在 CloudBase 云托管中新建服务时，建议直接使用 GitHub 仓库部署，项目目录填写：

```text
cfix/cfix_server
```

当前后端目录已经包含 `Dockerfile`，CloudBase 可直接按容器服务构建。服务端口填写：

```text
80
```

后端环境变量至少配置这些：

```env
APP_ENV=cloudbase
APP_DEBUG=false
API_V1_STR=/api/v1
JWT_SECRET=换成随机长字符串
CORS_ALLOW_ORIGINS=https://你的-edgeone-前端域名
MYSQL_HOST=你的-mysql-主机
MYSQL_PORT=你的-mysql-端口
MYSQL_USER=你的-mysql-用户名
MYSQL_PASSWORD=你的-mysql-密码
MYSQL_DB=你的-mysql-数据库名
SANDBOX_BACKEND=safe_exec
SANDBOX_TIMEOUT_SEC=8
SANDBOX_WORK_ROOT=/tmp/cfix_sandbox
LLM_ENABLE=false
```

当前 `Dockerfile` 启动时会先执行：

```text
python -m app.db.init_db
```

所以在数据库权限足够的情况下，基本表结构会自动初始化。如果你还希望和本地完全一致，也可以提前导入 `cfix/cfix_schema.sql`。

如果你需要演示真实模型链路，再额外补：

```env
LLM_ENABLE=true
LLM_PROVIDER=qwen
LLM_MODEL=qwen3-coder-next
LLM_BASE_URL=你的模型兼容接口地址
LLM_API_KEY=你的模型密钥
```

#### 3. 两边连通顺序

建议按这个顺序做，不要反过来：

1. 先准备 MySQL，并确认可以被 CloudBase 云托管服务访问。
2. 再部署 CloudBase 后端，直到 `https://你的-cloudbase-域名/` 能返回 `cfix-server running`。
3. 然后部署 EdgeOne 前端，并把 `VITE_API_BASE_URL` 指到 CloudBase。
4. 最后回到 CloudBase，把 `CORS_ALLOW_ORIGINS` 改成最终的 EdgeOne 域名，再重新部署一次后端。

#### 4. 交付给老师时建议填写

```text
系统访问地址：你的 EdgeOne 链接
后端接口地址：你的 CloudBase 链接
代码仓库地址：你的 GitHub 仓库链接
测试账号：demo
测试密码：Demo123456
```

首次使用 `demo / Demo123456` 登录时，系统会自动创建该用户；之后老师就可以直接复用这组账号。

#### 5. 这个方案的边界

这套“EdgeOne + CloudBase”分离部署更适合课程演示，不适合强调强隔离执行的正式生产环境，原因有两点：

1. CloudBase 这里我们明确退回了 `safe_exec`，没有继续使用 Docker 沙箱。
2. 前端为了适配静态托管环境，已经切换成 hash 路由，链接里会带 `#/`。

### 云端上线前需要改的配置

后端 `.env` 里至少补这几项：

```env
APP_DEBUG=false
JWT_SECRET=请替换成强随机字符串
CORS_ALLOW_ORIGINS=https://你的前端域名
```

前端 `.env` 里把接口地址改成你的线上后端：

```env
VITE_API_BASE_URL=https://你的后端域名/api/v1
```

如果你打算直接使用仓库根目录的 `docker-compose.yml` 在云服务器上拉起整套演示，建议在启动前先设置这两个 Compose 变量：

```env
CFIX_PUBLIC_API_BASE_URL=https://你的后端域名/api/v1
CFIX_CORS_ALLOW_ORIGINS=https://你的前端域名
```

这样前端打包后的请求地址和后端允许的跨域来源才会和线上域名一致。否则浏览器会继续请求本地 `127.0.0.1`，线上页面虽然能打开，但接口会失败。

### 演示账号说明

当前登录接口保留了“首次登录自动创建用户”的逻辑，所以交付时你可以直接在 README 或作业表格里提供一个测试账号，例如：

```text
测试账号：demo
测试密码：Demo123456
```

第一次用这组账号登录时，系统会自动创建该用户；后续老师就可以直接复用这组账号进行演示。

### 部署时建议额外确认

- 将 `APP_DEBUG` 设为 `false`。
- 使用强随机值替换 `JWT_SECRET`。
- 将 `CORS_ALLOW_ORIGINS` 设置为实际前端访问域名。
- 只有在模型地址和密钥都可用时再启用 `LLM_ENABLE=true`。
- `SANDBOX_WORK_ROOT` 必须是宿主机上可写目录；Windows 可用 `D:\cfix_sandbox`，Linux 更适合 `/tmp/cfix_sandbox`。
- 运行后端的主机必须安装 Docker，并且应用进程能够直接调用 `docker` 命令。

如果后续需要把前后端和数据库也全部容器化，可以再在当前 README 基础上补 `docker-compose.yml`；但就仓库现状而言，以上说明和代码实现是一致的。

## 补充文档

- `TENCENT_DEPLOY_GUIDE.md`：腾讯云 MySQL + CloudBase + EdgeOne 的分离部署实操清单
- `cfix_frontend/README.md`：前端页面与接口说明
- `cfix_server/README.md`：后端接口、配置项和模块分工说明