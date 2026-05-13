# 腾讯云分离部署清单

本文把当前项目的三块上线工作汇总到一处：

1. 腾讯云 MySQL 准备
2. 腾讯 CloudBase 后端部署
3. 腾讯 EdgeOne Pages 前端部署

适用对象：当前仓库 `D:\BYSJ` 下的 `cfix` 项目。

## 0. 当前仓库已经完成的适配

当前代码已经针对这条部署路线做了两项处理：

1. 前端已经切换到 hash 路由，适合 EdgeOne Pages 静态托管。
2. 后端目录 `cfix/cfix_server` 已增加 `Dockerfile`，可直接用于 CloudBase 云托管容器部署。

因此，你后面在控制台里最需要填写的是路径、构建参数、环境变量和数据库连接信息。

## 1. 腾讯云 MySQL 准备

### 1.1 推荐选择

为了尽快完成课程演示，优先采用下面这条最省事的路径：

1. 购买一台腾讯云 MySQL 实例。
2. 开启外网地址。
3. 先临时放开白名单用于联调。
4. 导入 `cfix/cfix_schema.sql`。
5. 将得到的主机、端口、账号、密码、数据库名填入 CloudBase 环境变量。

如果你后面要继续长期使用，再把白名单收紧，或者改为同地域 VPC 内网访问。

### 1.2 控制台购买时怎么选

打开腾讯云控制台，进入 `云数据库 MySQL`，新建实例时建议这样选：

1. 地域：和 CloudBase 保持一致，拿不准时优先都选上海。
2. 版本：MySQL 8.0。
3. 规格：选择能通过创建的最低可用规格，课程演示足够。
4. 网络：如果你只是先跑通演示，后续会开启外网地址即可。
5. 密码：设置一串新的强密码，不要继续用仓库里的默认密码。

建议你单独创建一个业务账号，例如：

```text
账号名：cfix_user
数据库名：cfix_db
```

### 1.3 创建数据库和账号

实例创建完成后，在 MySQL 控制台里完成这三件事：

1. 创建数据库 `cfix_db`。
2. 创建账号 `cfix_user`。
3. 给 `cfix_user` 授予 `cfix_db` 的读写权限。

如果控制台默认只给了 `root`，也可以先直接使用 `root` 完成部署；但为了后续更稳妥，仍然建议单独创建业务账号。

### 1.4 开启外网地址

在实例详情页找到外网连接能力，开启后你会得到：

```text
MYSQL_HOST=你的外网地址
MYSQL_PORT=你的外网端口
```

腾讯云官方 MySQL 文档说明，外网连接时可以直接使用如下命令测试：

```bash
mysql -h <外网地址> -u <用户名> -P <外网端口> -p
```

### 1.5 白名单怎么配

为了先把系统跑通，演示阶段可以临时这样配：

1. 在数据库白名单里先允许 `0.0.0.0/0`。
2. 部署验证成功后，再把白名单收紧。

这不是长期生产配置，只是为了避免你在 CloudBase 容器出口 IP、地域和网络联通上卡很久。

### 1.6 导入初始化 SQL

这个步骤建议做，不要跳过。原因是 `cfix/cfix_schema.sql` 里不只是建表，还包含默认模型配置数据。

如果你在 bash、Git Bash 或 WSL 里执行，最直接的导入命令如下：

```bash
mysql -h <MYSQL_HOST> -P <MYSQL_PORT> -u <MYSQL_USER> -p <MYSQL_DB> < d:\BYSJ\cfix\cfix_schema.sql
```

如果你在 PowerShell 里执行，可以先切到仓库根目录，再用管道把 SQL 送给 `mysql`：

```powershell
Set-Location d:\BYSJ
Get-Content .\cfix\cfix_schema.sql | mysql -h <MYSQL_HOST> -P <MYSQL_PORT> -u <MYSQL_USER> -p <MYSQL_DB>
```

如果本机没有 `mysql` 客户端，也可以用腾讯云控制台自带的数据库管理入口，或者用 Navicat / DBeaver / MySQL Workbench 导入这个 SQL 文件。

### 1.7 导入后怎么检查

登录数据库后，至少检查这两项：

```sql
SHOW TABLES;
SELECT COUNT(*) FROM cf_model;
```

预期结果：

1. 能看到 `cf_user`、`cf_task`、`cf_ver`、`cf_run` 等表。
2. `cf_model` 至少应有 3 条默认占位模型数据。

### 1.8 最终要拿到的 5 个值

MySQL 准备完成后，你最终需要保存这 5 个值，后面填入 CloudBase：

```env
MYSQL_HOST=你的外网地址
MYSQL_PORT=你的外网端口
MYSQL_USER=cfix_user
MYSQL_PASSWORD=你的密码
MYSQL_DB=cfix_db
```

## 2. 腾讯 CloudBase 后端部署

### 2.1 服务创建方式

打开 `CloudBase 云托管`，新建服务时建议直接选 GitHub 仓库部署。

仓库使用当前项目，服务路径填写：

```text
cfix/cfix_server
```

当前目录下已经有 `Dockerfile`，CloudBase 可以直接按容器项目构建。

### 2.2 控制台关键项怎么填

建议你在 CloudBase 面板里按下面填：

```text
部署方式：GitHub 仓库
代码目录：cfix/cfix_server
构建方式：使用仓库中的 Dockerfile
容器端口：80
```

如果控制台需要资源规格，课程演示先用最低能创建成功的规格即可；如果有选项，`1 核 / 1 GB` 会比更小规格稳一点。

### 2.3 后端环境变量模板

首次部署建议使用下面这组最小变量：

```env
APP_ENV=cloudbase
APP_DEBUG=false
API_V1_STR=/api/v1
JWT_SECRET=请替换为随机长字符串
CORS_ALLOW_ORIGINS=https://你的-edgeone-前端域名
MYSQL_HOST=你的外网地址
MYSQL_PORT=你的外网端口
MYSQL_USER=cfix_user
MYSQL_PASSWORD=你的数据库密码
MYSQL_DB=cfix_db
SANDBOX_BACKEND=safe_exec
SANDBOX_TIMEOUT_SEC=8
SANDBOX_WORK_ROOT=/tmp/cfix_sandbox
LLM_ENABLE=false
```

说明：

1. `SANDBOX_BACKEND` 必须是 `safe_exec`，不要在 CloudBase 里继续依赖 Docker 沙箱。
2. `LLM_ENABLE` 第一轮先设为 `false`，先把登录、任务、历史、数据集这些基础链路跑通。
3. `CORS_ALLOW_ORIGINS` 在 EdgeOne 域名还没出来之前，可以先留空占位，等前端部署完成后回来补。

### 2.4 如果你要演示真实模型链路

在基础链路跑通后，再补下面这些变量：

```env
LLM_ENABLE=true
LLM_PROVIDER=qwen
LLM_MODEL=qwen3-coder-next
LLM_BASE_URL=你的模型兼容接口地址
LLM_API_KEY=你的模型密钥
```

### 2.5 CloudBase 首次发布后怎么验收

部署成功后，先打开默认域名，检查：

1. `https://你的-cloudbase-域名/` 返回 `cfix-server running`
2. `https://你的-cloudbase-域名/docs` 能打开 FastAPI 文档

如果根路径打不开，优先检查：

1. 容器端口是不是填了 `80`
2. MySQL 环境变量是否填错
3. 数据库白名单是否放通

## 3. 腾讯 EdgeOne Pages 前端部署

### 3.1 项目创建时怎么填

打开 `EdgeOne Pages`，导入当前 GitHub 仓库，然后按下面填写：

```text
项目根目录：cfix/cfix_frontend
Framework Preset：Vite
Install Command：npm install
Build Command：npm run build
Output Directory：dist
```

### 3.2 前端环境变量模板

```env
VITE_API_BASE_URL=https://你的-cloudbase-后端域名/api/v1
```

### 3.3 为什么这里要用 hash 路由

当前前端已经改成 hash 路由，因此上线后链接会长这样：

```text
https://你的-edgeone-域名/#/login
https://你的-edgeone-域名/#/workbench
```

这样做是为了避免静态托管场景下刷新深层路径时出现 404。

### 3.4 EdgeOne 首次发布后怎么验收

部署成功后，至少验证这几项：

1. 能打开登录页 `/#/login`
2. 用测试账号登录后能进入 `/#/workbench`
3. 刷新页面不会丢失路由

如果页面能打开但接口失败，优先回头检查：

1. `VITE_API_BASE_URL` 是否写成了 CloudBase 的真实域名
2. CloudBase 的 `CORS_ALLOW_ORIGINS` 是否写成了 EdgeOne 的真实域名

## 4. 推荐执行顺序

严格按这个顺序做，最省时间：

1. 先创建腾讯云 MySQL。
2. 再导入 `cfix/cfix_schema.sql`。
3. 再部署 CloudBase 后端。
4. 后端根路径可访问后，再部署 EdgeOne 前端。
5. 前端域名生成后，回 CloudBase 把 `CORS_ALLOW_ORIGINS` 改成最终前端域名并重新发布。
6. 最后用测试账号登录一遍，确认老师能演示核心功能。

## 5. 推荐测试账号

当前项目登录逻辑支持“首次登录自动建号”，所以可以直接提供：

```text
测试账号：demo
测试密码：Demo123456
```

第一次登录时会自动创建该用户，后续老师即可复用。

## 6. 最终提交给老师的信息

建议你最后整理成下面这 4 项：

```text
系统访问地址：你的 EdgeOne 链接
后端接口地址：你的 CloudBase 链接
代码仓库地址：你的 GitHub 仓库链接
测试账号：demo / Demo123456
```

## 7. 你现在最应该做什么

如果你还没开始点控制台，先做这三步：

1. 先购买腾讯云 MySQL，并记下 `MYSQL_HOST`、`MYSQL_PORT`。
2. 导入 `d:\BYSJ\cfix\cfix_schema.sql`。
3. 把 MySQL 的 5 个值填到 CloudBase 环境变量模板里备用。