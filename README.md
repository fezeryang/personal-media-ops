# personal-media-ops

Personal Media Ops 是一个面向个人使用的互联网情报与内容运营工作台。当前已提供采集工作台、FastAPI 任务 API 和独立 Worker：用户可以创建 B 站关键词任务、完成二维码登录、查看受限长度的实时日志，并分页浏览采集结果。

任务元数据保存在 SQLite；独立 Worker 串行执行仓库外部的 MediaCrawler。当前只支持 B 站关键词搜索和二维码登录，不包含 Redis、Celery、Docker、AI 分析或自动发布。

## 本地开发

需要 Python 3.11、[uv](https://docs.astral.sh/uv/) 和 Node.js 22。

先启动后端：

```bash
cd backend
uv sync
uv run pytest
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查：`GET http://127.0.0.1:8000/api/health`

另开一个终端启动前端：

```bash
cd frontend
npm install
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
npm run test:coverage
npm run build
```

生产文件统一输出到 `frontend/dist`。

独立 Worker：

```bash
cd backend
uv run python -m app.workers.crawler_worker
```

## 配置

复制 `backend/.env.example` 为 `backend/.env`。通过 `FRONTEND_ORIGINS`
配置允许的前端来源；通过 `MEDIAOPS_*` 和 `MEDIACRAWLER_*` 变量配置数据库、
运行数据、Node.js、外部 Python 和固定 Runner。默认不允许任何跨域来源。

`frontend/.env.example` 只包含构建期 API Base URL。生产推荐 Nginx 同源代理
`/api`，因此无需配置该值。不要提交任何 `.env` 文件。

## 生产部署

`deploy/systemd/` 包含 API 和 crawler worker 的 Ubuntu 22.04 服务单元模板。两个服务均以 `mediaops` 用户运行；实际 `.env`、SQLite、日志、二维码、浏览器数据和采集结果只保留在服务器上。

Nginx 或宝塔站点的静态目录应指向
`/opt/personal-media-ops/frontend/dist`，所有 `/api/` 请求反向代理到
`http://127.0.0.1:8000`，SPA 路由使用 `try_files ... /index.html` 回退。

详细接口与部署说明：

* [Crawler API contract](docs/api-contract.md)
* [Deployment guide](docs/deployment.md)
