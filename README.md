# personal-media-ops

第一阶段提供一个可部署到 Ubuntu 22.04 的最小 FastAPI 后端。当前不连接数据库，也不包含 Redis、Celery、MediaCrawler、Playwright 或 AI SDK。

## 本地开发

需要 Python 3.11 和 [uv](https://docs.astral.sh/uv/)。

```bash
cd backend
uv sync
uv run pytest
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查：`GET http://127.0.0.1:8000/api/health`

## 配置

复制 `backend/.env.example` 为 `backend/.env`，通过 `FRONTEND_ORIGINS` 配置允许的前端来源，多个来源使用逗号分隔。默认不允许任何跨域来源。

## systemd

`deploy/systemd/mediaops-api.service.example` 是 Ubuntu 22.04 的服务单元模板。部署时请根据服务器路径、运行用户和 `uv` 路径调整，并将实际 `.env` 保留在服务器上，不要提交到 Git。
