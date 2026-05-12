# cfix_backend

## 项目说明

这是这个项目当前代码对应的后端部分。它是一个基于 FastAPI 的服务端，用来承接代码生成、自修复、版本记录、执行反馈、实验批跑和数据接口。

从现在这版代码来看，后端已经不是单纯的“调模型接口”服务。它把任务、版本、运行记录、trace、plan、lesson、实验结果这些对象都拆开保存了，前端工作台和实验页看到的大部分内容都来自这里。

## 技术栈

- FastAPI
- SQLAlchemy
- MySQL
- Pydantic / pydantic-settings
- PyMySQL
- python-jose
- passlib
- Docker（可选，用于容器沙箱）

## 当前代码里的核心能力

### 1. 认证

当前后端提供了这几个基础认证接口：

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/logout`

登录逻辑比较适合本地开发：如果用户名不存在，后端会先创建用户，再返回 token。也就是说，这个项目当前没有单独做注册页，而是把“首次登录即创建用户”写在了登录接口里。

### 2. 会话与任务

后端已经把“聊天会话”和“代码任务”分开建模。

会话接口主要在：

- `GET /api/v1/chat/sess`
- `POST /api/v1/chat/sess`
- `GET /api/v1/chat/sess/{sess_id}`
- `PUT /api/v1/chat/sess/{sess_id}`
- `GET /api/v1/chat/sess/{sess_id}/msg`
- `POST /api/v1/chat/sess/{sess_id}/msg`
- `POST /api/v1/chat/sess/{sess_id}/to-task`

任务接口主要在：

- `GET /api/v1/task`
- `POST /api/v1/task`
- `PUT /api/v1/task/{task_id}`
- `GET /api/v1/task/{task_id}`
- `DELETE /api/v1/task/{task_id}`
- `POST /api/v1/task/{task_id}/gen`
- `POST /api/v1/task/{task_id}/run`
- `POST /api/v1/task/{task_id}/auto`
- `POST /api/v1/task/{task_id}/stop`
- `GET /api/v1/task/{task_id}/status`
- `GET /api/v1/task/{task_id}/summary`
- `GET /api/v1/task/{task_id}/ver`
- `GET /api/v1/task/{task_id}/case`
- `PUT /api/v1/task/{task_id}/case`
- `GET /api/v1/task/{task_id}/plan`
- `GET /api/v1/task/{task_id}/lesson`
- `POST /api/v1/task/case/gen`

这里已经把“创建任务、生成初始代码、运行测试、自动修复、更新测试用例、查看计划和 lesson”串起来了。

### 3. 运行结果与版本

运行结果接口：

- `GET /api/v1/run/task/{task_id}`
- `GET /api/v1/run/{run_id}`
- `GET /api/v1/run/{run_id}/fb`
- `GET /api/v1/run/{run_id}/trace`
- `GET /api/v1/run/{run_id}/cases`

版本接口：

- `GET /api/v1/ver/{ver_id}`
- `GET /api/v1/ver/{ver_id}/code`
- `GET /api/v1/ver/{ver_id}/diff/{to_id}`
- `POST /api/v1/ver/{ver_id}/rollback`

从这部分代码能看出来，后端现在已经把“版本演进”和“运行记录”当成两类独立数据在维护，而不是简单覆盖代码文本。

### 4. 实验评估

实验相关接口：

- `GET /api/v1/exp`
- `POST /api/v1/exp`
- `DELETE /api/v1/exp/{exp_id}`
- `GET /api/v1/exp/{exp_id}`
- `POST /api/v1/exp/{exp_id}/start`
- `POST /api/v1/exp/{exp_id}/stop`
- `GET /api/v1/exp/{exp_id}/item`
- `GET /api/v1/exp/{exp_id}/report`
- `GET /api/v1/exp/{exp_id}/chart`

当前代码里，实验已经支持列表、创建、启动、停止、轮询进度、查看明细和报告。

### 5. 数据集

数据集接口：

- `GET /api/v1/data/set`
- `GET /api/v1/data/set/{name}`

按照当前 `bench_bank.py` 的实现，实验创建界面主要使用三个主数据集：

- `custom`：函数级题库
- `class_bank`：类文件级题库
- `file_bank`：文件级题库

后端仍兼容旧别名：

- `mbpp`、`humaneval` -> `custom`
- `class_eval` -> `class_bank`
- `file_ultra` -> `file_bank`

## 目录结构

```text
cfix_backend/
├─ app/
│  ├─ agent/            # gen / inst / ana / fix
│  ├─ api/v1/           # 路由
│  ├─ core/             # 配置、依赖、鉴权
│  ├─ data/             # 内置题库
│  ├─ db/               # 数据库初始化与连接
│  ├─ llm/              # 模型接入层
│  ├─ models/           # ORM 模型
│  ├─ repo/             # 数据访问
│  ├─ sand/             # 执行沙箱
│  ├─ schemas/          # Pydantic 模型
│  ├─ svc/              # 业务服务
│  └─ utils/            # 工具函数
├─ sandbox/py/          # Docker 沙箱文件
├─ scripts/             # 辅助脚本
├─ tests/
├─ .env
├─ .env.example
├─ req.txt
└─ README.md
```

## 当前后端的模块分工

### `app/agent`

这里放的是和代码生成、自修复直接相关的几个代理：

- `gen_agent.py`
- `inst_agent.py`
- `ana_agent.py`
- `fix_agent.py`

### `app/svc`

这里是任务主链路真正被编排的地方。当前比较关键的服务文件有：

- `task_svc.py`
- `gen_svc.py`
- `run_svc.py`
- `fb_svc.py`
- `trace_svc.py`
- `plan_svc.py`
- `fix_svc.py`
- `lesson_svc.py`
- `rb_svc.py`
- `exp_svc.py`
- `case_svc.py`

### `app/sand`

这部分是执行沙箱。当前代码保留了两种后端：

- `safe_exec`
- `docker`

如果只是本地先把流程跑通，`safe_exec` 会更省事；如果想做更严格的隔离执行，可以切到 `docker`。

### `app/llm`

模型提供方当前支持：

- `qwen`
- `openai`
- `deepseek`

是否真的调用外部模型，由 `.env` 里的 `LLM_ENABLE` 决定。

## 环境变量

当前配置来自 `.env`，对应字段定义在 `app/core/cfg.py`。常用项包括：

### 应用本身

```env
APP_NAME=cfix-server
APP_ENV=dev
APP_DEBUG=true
API_V1_STR=/api/v1
```

### 数据库

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DB=cfix_db
```

### 鉴权

```env
JWT_SECRET=change-this-secret
JWT_ALG=HS256
JWT_EXPIRE_MIN=120
```

### LLM

```env
LLM_PROVIDER=qwen
LLM_ENABLE=false
LLM_MODEL=qwen3-coder-next
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=
LLM_TIMEOUT=120
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4096
LLM_STRICT=false
LLM_RETRY_COUNT=2
LLM_RETRY_BACKOFF_SEC=1.0
LLM_STRIP_THINK=true
```

### 沙箱

```env
SANDBOX_BACKEND=safe_exec
SANDBOX_TIMEOUT_SEC=8
SANDBOX_IMAGE=cfix-python-sandbox:latest
SANDBOX_WORK_ROOT=/tmp/cfix_sandbox
SANDBOX_MEMORY=256m
SANDBOX_CPUS=0.5
SANDBOX_PIDS_LIMIT=64
SANDBOX_READ_ONLY=true
SANDBOX_DOCKER_BIN=docker
SANDBOX_KEEP_TEMP=false
```

## 安装依赖

在后端目录执行：

```bash
pip install -r req.txt
```

当前 `req.txt` 里已经列出了运行这个项目需要的核心依赖，包括 FastAPI、SQLAlchemy、PyMySQL、Pydantic、JWT 和表单上传支持。

## 数据库准备

根据 MySQL 脚本：cfix_schema.sql 创建数据库：cfix_db

## 启动方式

### 1. 本地开发启动

在后端目录执行：

```bash
python -m uvicorn app.main:app --reload --port 8000
```

启动后可以先打开下面两个地址确认服务是否正常：

- 根路径：`http://127.0.0.1:8000/`
- OpenAPI 文档：`http://127.0.0.1:8000/docs`

### 2. 推荐的本地调试组合

如果你现在只是想确认整套主链路能跑起来，比较稳妥的一组配置是：

```env
LLM_ENABLE=false
SANDBOX_BACKEND=safe_exec
```

这样做的好处是：

- 不依赖真实模型额度
- 不要求 Docker 先完全就绪
- 更适合先跑通任务创建、代码生成、执行记录、版本保存和实验页联调

### 3. 切到真实模型

当你需要测试真实生成和真实修复时，再把 `LLM_ENABLE` 打开，并补上对应模型的 `BASE_URL` 和 `API_KEY`。

### 4. 切到 Docker 沙箱

如果你需要容器执行，在后端目录先构建镜像：

```bash
docker build -t cfix-python-sandbox:latest -f sandbox/py/Dockerfile .
```

然后在 `.env` 里改成：

```env
SANDBOX_BACKEND=docker
SANDBOX_IMAGE=cfix-python-sandbox:latest
```

## 当前已经写到代码里的几个实现细节

### 1. 统一返回格式

当前大部分接口都返回：

```json
{
  "code": 200,
  "msg": "ok",
  "data": {}
}
```

这和前端 `src/utils/req.js` 的拦截器是配套的。

### 2. 数据库 URL 来自配置对象

数据库连接串不是写死在代码里的，而是通过 `app/core/cfg.py` 的 `db_url` 属性拼出来。

### 3. 根路由和 CORS 已配置

当前后端已经在 `app/main.py` 里配置了：

- FastAPI 应用实例
- CORS
- 各个路由模块注册

本地开发默认允许的前端来源包括：

- `http://127.0.0.1:8000`
- `http://127.0.0.1:5173`
- `http://localhost:5173`

### 4. stream 接口目前还是占位实现

`/api/v1/stream/task/{task_id}` 现在返回的是一个占位的 SSE 输出，还没有变成真正的任务流。这个接口已经留好了入口，但如果你后面要做实时推送，还需要继续往里补。

## 开发时建议先跑通的顺序

如果你是第一次把这个后端拉起来，建议按下面的顺序做：

1. 配置 `.env`
2. 准备 MySQL 数据库
3. 执行 `python -m app.db.init_db`
4. 启动 `uvicorn`
5. 用 `/docs` 或前端登录页测试登录
6. 先新建一个任务，跑通生成和执行
7. 再去测自动修复、版本、trace 和实验

## 说明

这个 README 只围绕当前压缩包里的实际代码来写，没有沿用旧版 README 里已经过时的描述，也没有把还没落到代码里的设想继续写进去。后面如果路由、目录、数据模型或者运行方式又变了，README 也应该跟着当前代码一起改。
