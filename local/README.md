# 本地开发(Docker + LocalStack)

在本机运行 OpenRepoWiki 后端。AWS 服务由 [LocalStack](https://localstack.cloud) 模拟(DynamoDB + S3)。Step Functions / ECS 编排**不做**模拟——而是把处理器作为一次性容器直接运行。

此目录下均为仅用于开发的脚手架,不修改任何应用代码。

## 前置条件

- Docker(含 `docker compose` v2)
- 一个源码 token(处理器需要它来读取仓库)
- (可选)LLM API 密钥——不配置则只构建目录树、跳过 AI 摘要

## 1. 配置

```bash
cp local/.env.local.example local/.env.local
# 编辑 local/.env.local -> 设置源码 token(以及可选的 LLM_* 密钥)
```

在 `local/.env.local` 中选择源码提供方:

- **GitHub**(默认):`REPO_PROVIDER=github` + `GITHUB_TOKEN=...`
  (私有库需要带 `repo` 权限的 PAT)。
- **GitLab**:`REPO_PROVIDER=gitlab` + `GITLAB_TOKEN=...`
  (PAT 权限 `read_api`、`read_repository`;支持私有项目)。
  自建 GitLab 还需设置 `GITLAB_URL=https://gitlab.your-company.com`。

> `local/.env.local` 已被 git 忽略——真实 token/密钥只放这里,切勿写入
> `local/.env.local.example`(它是被追踪的模板)。

## 2. 启动 LocalStack + API

```bash
docker compose up -d
```

这会启动:
- **localstack**(端口 `:4566`)——通过 [`init-aws.sh`](init-aws.sh) 自动创建 DynamoDB 表、GSI 与 S3 桶
- **api**(`http://localhost:8000`)——只读 / 任务状态 API(本地跳过 HMAC 鉴权)

检查是否就绪:

```bash
curl -s http://localhost:8000/jobs/does-not-exist        # -> 404 JSON(API 存活)
docker compose logs -f api                                # 跟踪 API 日志
```

## 3. 处理一个仓库

```bash
./local/process-repo.sh tiangolo fastapi          # owner repo [branch]
```

这会针对 LocalStack 运行处理器容器:拉取 → 过滤 → 摘要 → 写入 DynamoDB/S3。在前台查看日志。提供方(GitHub/GitLab)取自 `local/.env.local` 中的 `REPO_PROVIDER`。

GitLab 示例(`owner` = group,`repo` = project;`repo` 可包含斜杠以表示嵌套组,例如 `group/subgroup`):

```bash
./local/process-repo.sh mygroup myproject               # gitlab.com
./local/process-repo.sh mygroup mysubgroup/myproject    # 嵌套组
```

> 本地只读 API(`/repos/{owner}/{name}/...`)假定为两段式 `owner/name`;
> 浏览嵌套超过一层 group 的仓库需要调整 API 路径,但处理与存储支持任意层级。

## 4. 浏览结果

```bash
# 顶层目录树
curl 'http://localhost:8000/repos/tiangolo/fastapi/tree?branch=main'

# 某个页面(path="" 表示仓库级摘要)
curl 'http://localhost:8000/repos/tiangolo/fastapi/page?branch=main&path='
```

也可以把前端指向这个 API:

```bash
cd frontend
echo 'VITE_API_URL=http://localhost:8000' > .env.local
npm install && npm run dev
```

## 与 AWS 的对应关系

| AWS(生产) | 本地等价物 |
|------------|------------------|
| DynamoDB | LocalStack DynamoDB(由 `init-aws.sh` 建表) |
| S3 | LocalStack S3(通过 `aws-config` 启用 path-style) |
| Lambda(API) | `api_server.py` HTTP 适配层 → 真实 handler |
| ECS Fargate(处理器) | `processor` compose 服务(一次性运行) |
| Step Functions | **不模拟**——由 `process-repo.sh` 直接运行处理器 |
| Lambda 授权器(HMAC) | 本地跳过 |

> `POST /jobs` 在本地可用并会创建任务记录,但由于未模拟 Step Functions,它不会
> 自动开始处理(当 `STATE_MACHINE_ARN` 未设置时会跳过状态机调用)。请用
> `process-repo.sh` 来执行处理。

## 重置 / 清理

```bash
docker compose down            # 停止容器(LocalStack 数据为内存态 -> 清空)
docker compose up -d           # 重新创建表/桶
```

## 排障

- **缺少 `local/.env.local`** → `process-repo.sh` 失败;请从示例文件复制。
- **`GITHUB_TOKEN` 为空** → 处理器以 "Missing required environment variables"
  退出,或触发 GitHub 限流。
- **找不到表** → 确认 `docker compose up -d` 已完成,并在
  `docker compose logs localstack` 中查看 `[init-aws] done.` 这一行。
- **重新处理某个仓库** → 执行 `docker compose down && docker compose up -d` 清空数据,
  因为 `POST /jobs` 会把已处理过的仓库视为已完成。
```