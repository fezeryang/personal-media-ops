# personal-media-ops

当前后端提供健康检查和轻量级 MediaCrawler 任务管理。任务元数据保存在 SQLite；独立 Worker 串行执行已经部署在仓库外部的 MediaCrawler。当前只支持 B站关键词搜索和二维码登录，不包含 Redis、Celery、Docker、AI 分析或自动发布。

## 本地开发

需要 Python 3.11 和 [uv](https://docs.astral.sh/uv/)。

```bash
cd backend
uv sync
uv run pytest
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查：`GET http://127.0.0.1:8000/api/health`

独立 Worker：

```bash
cd backend
uv run python -m app.workers.crawler_worker
```

## 配置

复制 `backend/.env.example` 为 `backend/.env`。通过 `FRONTEND_ORIGINS` 配置允许的前端来源；通过 `MEDIAOPS_*` 和 `MEDIACRAWLER_*` 变量配置数据库、运行数据、Node.js、外部 Python 和固定 Runner。默认不允许任何跨域来源。

## systemd

`deploy/systemd/` 包含 API 和 crawler worker 的 Ubuntu 22.04 服务单元模板。两个服务均以 `mediaops` 用户运行；实际 `.env`、SQLite、日志、二维码、浏览器数据和采集结果只保留在服务器上。

详细接口与部署说明：

* [Crawler API contract](docs/api-contract.md)
* [Deployment guide](docs/deployment.md)
