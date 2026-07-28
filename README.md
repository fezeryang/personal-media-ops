# personal-media-ops

**Personal Media Ops（个人互联网情报与内容运营平台）** 是用户自己的互联网
信息获取、整理、分析与内容运营基础设施，不是普通爬虫面板。当前已提供五种独立采集
模式（搜索、详情、创作者、一级评论、二级评论）、七平台模式级能力矩阵、FastAPI
任务与资料库 API、单并发 Worker，以及内容、创作者、评论和任务溯源的持久化资料库。

任务元数据保存在 SQLite，并由 Alembic 管理版本；独立 Worker 串行执行仓库外部的
MediaCrawler。B 站、小红书、知乎、微博和贴吧的关键词搜索已真实验证；快手搜索因
固定上游协议变化延期，抖音因当前生产资源限制延期。每个非搜索模式单独记录
`code_ready`、`enabled`、`production_verified` 或明确的 deferred 原因，搜索成功
不会被当作其他模式成功。不包含 Redis、Celery、Docker、Elasticsearch、AI 分析或
自动发布，未完成模块不会用 Mock 数据冒充真实能力。

2026-07-28 的阶段六生产验证已确认：B站与知乎的详情、创作者、一级评论和二级评论；
微博与贴吧的详情、创作者和一级评论；快手的详情和一级评论。小红书非搜索模式因
安全设计不保存平台签名 URL 上下文而保持 `deferred_login_required`；快手创作者
接口保持 `deferred_upstream_breakage`，其二级评论保持 `code_ready`。

## 工程协作

根目录 [AGENTS.md](AGENTS.md) 是覆盖全仓库的长期工程规则。Codex 按完整产品链路负责
数据库、领域模型、后端、API、Worker、前端、测试、文档和部署影响，不需要用户自行
协调前后端。

仓库级 `.agents/skills/mediaops-server/` 是服务器运维 Skill 的唯一规范源。当前
Codex 会在项目中自动发现它，无需复制到用户级 Skills 目录。服务器库存、SSH 配置、
权限边界和操作手册见：

- [Agent workflow](docs/agent-workflow.md)
- [Server operations](docs/server-operations.md)

## 本地开发

需要 Python 3.11、[uv](https://docs.astral.sh/uv/) 和 Node.js 22。

先启动后端：

```bash
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run pytest
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查：`GET http://127.0.0.1:8000/api/health`

另开一个终端启动前端：

```bash
cd frontend
npm ci --include=dev
npm run dev
```

访问 `http://127.0.0.1:5173`。Vite 会把本地 `/api` 请求代理到
`http://127.0.0.1:8000`；前端代码不写死服务器地址。只有跨域调试时才需要在
`frontend/.env.local` 中设置 `VITE_API_BASE_URL`，生产同源部署应保持为空。

前端质量检查与生产构建：

```bash
cd frontend
npm run lint
npm run test
npm run build
```

可选覆盖率检查为 `npm run test:coverage`。

生产文件统一输出到 `frontend/dist`。

独立 Worker：

```bash
cd backend
uv run python -m app.workers.crawler_worker
```

## 配置

复制 `backend/.env.example` 为 `backend/.env`。通过 `FRONTEND_ORIGINS`
配置允许的前端来源；通过 `MEDIAOPS_*` 和 `MEDIACRAWLER_*` 变量配置数据库、
运行数据、Node.js、外部 Python 和固定 Runner。`MEDIAOPS_ENABLED_PLATFORMS`
默认仅为 `bili`。平台是否配置启用和各模式的验证成熟度是两套独立状态；抖音仍保持
资源延期，不能通过该变量绕过能力矩阵。默认不允许任何跨域来源。

`frontend/.env.example` 只包含构建期 API Base URL。生产推荐 Nginx 同源代理
`/api`，因此无需配置该值。不要提交任何 `.env` 文件。

## 生产部署

`deploy/systemd/` 包含 API 和 crawler worker 的 Ubuntu 22.04 服务单元模板。两个
服务均以 `mediaops` 用户运行；实际 `.env`、SQLite、日志、二维码、浏览器数据和
采集结果只保留在服务器上。

生产构建位于 `/opt/personal-media-ops/frontend/dist`，发布后同步到宝塔 Nginx
静态目录 `/www/wwwroot/ops.fezern8n.com`。所有 `/api/` 请求反向代理到
`http://127.0.0.1:8000`，SPA 路由使用 `try_files ... /index.html` 回退。

`scripts/server/` 提供只读连接、状态、健康、日志以及 dry-run 优先的备份和部署：

```bash
scripts/server/connect.sh
scripts/server/status.sh
scripts/server/healthcheck.sh
scripts/server/deploy.sh --target-ref <origin-main-sha> --dry-run
```

Real releases require an explicit `--execute` and use the manually installed
restricted helper `/usr/local/sbin/mediaops-release`. Releases that contain
reviewed database migrations additionally require `--allow-migrations`.
Reviewed, non-installed sources live under `infra/release/` and
`infra/sudoers/`.

生产部署、root 权限阶段和回滚边界以
[deployment guide](docs/deployment.md) 与
[server operations](docs/server-operations.md) 为准。

详细接口与部署说明：

- [Crawler API contract](docs/api-contract.md)
- [Platform capability matrix](docs/platform-capability-matrix.md)
- [Agent API foundation](docs/agent-api-foundation.md)
- [Deployment guide](docs/deployment.md)
