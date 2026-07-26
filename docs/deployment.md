# Personal Media Ops Deployment

本文描述 Ubuntu 22.04 生产环境的真实部署布局。MediaCrawler 保持为仓库外部安装，
不得复制进本项目或修改其核心源码。

## Production Layout

```text
/opt/personal-media-ops
├── backend
└── frontend/dist

/www/wwwroot/ops.fezern8n.com
/opt/mediacrawler
/var/lib/mediaops
/var/log/mediaops
/var/backups/mediaops
```

运行用户为 `mediaops`。FastAPI 监听 `http://127.0.0.1:8000`，公网入口为
`https://ops.fezern8n.com`。systemd 服务为 `mediaops-api` 和
`mediaops-crawler-worker`。

## One-Time Root Preparation

以下操作需要管理员执行：

```bash
sudo install -d -o mediaops -g mediaops -m 0750 /var/lib/mediaops
sudo install -d -o mediaops -g mediaops -m 0750 /var/lib/mediaops/crawler-output/tasks
sudo install -d -o mediaops -g mediaops -m 0750 /var/lib/mediaops/qrcodes
sudo install -d -o mediaops -g mediaops -m 0750 /var/log/mediaops/crawler
sudo install -d -o mediaops -g mediaops -m 0750 /var/backups/mediaops
sudo install -d -o root -g root -m 0755 /www/wwwroot/ops.fezern8n.com
```

`mediaops` 必须能读取并执行 `/opt/mediacrawler/.venv/bin/python` 和
`/var/lib/mediaops/bin/run_mediacrawler.py`。不要扩大到不必要的目录写权限。

## Backend Configuration

在 `/opt/personal-media-ops/backend` 中创建不提交到 Git 的 `.env`。生产值至少包括：

```dotenv
MEDIAOPS_DATABASE_PATH=/var/lib/mediaops/mediaops.db
MEDIACRAWLER_PYTHON=/opt/mediacrawler/.venv/bin/python
MEDIACRAWLER_RUNNER=/var/lib/mediaops/bin/run_mediacrawler.py
MEDIAOPS_OUTPUT_ROOT=/var/lib/mediaops/crawler-output
MEDIAOPS_LOG_ROOT=/var/log/mediaops
MEDIAOPS_QRCODE_ROOT=/var/lib/mediaops/qrcodes
MEDIAOPS_NODE_BINARY=/www/server/nodejs/v22.22.3/bin/node
CRAWLER_POLL_INTERVAL_SECONDS=1
```

也可用 `MEDIAOPS_NODE_BIN_DIR=/www/server/nodejs/v22.22.3/bin` 代替
`MEDIAOPS_NODE_BINARY`。Worker 会显式构造子进程 `PATH`，不依赖交互式 Shell profile。

安装和验证后端：

```bash
cd /opt/personal-media-ops/backend
uv sync --frozen
uv run pytest
```

## Database Initialization and Migration Policy

当前应用启动时使用幂等的 `CREATE TABLE IF NOT EXISTS` /
`CREATE INDEX IF NOT EXISTS` 初始化 SQLite，没有正式迁移工具。首次初始化可执行：

```bash
cd /opt/personal-media-ops/backend
uv run python -c \
  "from app.core.config import settings; from app.repositories.crawler_tasks import CrawlerTaskRepository; CrawlerTaskRepository(settings.database_path).initialize()"
```

未来首次结构变化前必须先建立版本化迁移机制，不得只改模型或初始化器。迁移必须兼容
已有数据；生产顺序必须是备份、迁移、代码发布、验证。数据库恢复属于破坏性 root
操作，本仓库不会自动执行。

## Frontend Build

生产前端保持 `VITE_API_BASE_URL` 为空并通过同源 `/api` 访问后端：

```bash
cd /opt/personal-media-ops/frontend
npm ci --include=dev --cache "$HOME/.npm-cache"
npm run lint
npm run test
npm run build
```

构建产物固定为 `/opt/personal-media-ops/frontend/dist`。发布阶段再将它同步到
`/www/wwwroot/ops.fezern8n.com`，不要直接编辑构建后的 JS/CSS。

本地 `npm run dev` 监听 `127.0.0.1:5173`，Vite 将 `/api` 代理到
`http://127.0.0.1:8000`。

## Worker and Runner Contract

Worker 通过参数数组调用固定 Python 和固定 Runner，绝不使用 `shell=True`。Runner
必须支持：

```text
--platform bili
--crawler-type search
--keywords <text>
--login-type qrcode
--requested-count <1..20>
--output-dir <generated task directory>
--qrcode-path <generated PNG path>
--max-concurrency-num 1
--enable-comments false
--enable-sub-comments false
```

API 调用方不能覆盖命令、脚本或文件路径。每台服务器只启用一个 Worker；第二个
Worker 会因独占锁失败退出。Worker 重启时会把遗留的 `running` 或
`waiting_login` 任务标记为异常中断。

## systemd

服务模板位于 `deploy/systemd/`，只安装一个 Worker：

```bash
sudo cp deploy/systemd/mediaops-api.service.example \
  /etc/systemd/system/mediaops-api.service
sudo cp deploy/systemd/mediaops-crawler-worker.service.example \
  /etc/systemd/system/mediaops-crawler-worker.service
sudo systemctl daemon-reload
sudo systemctl enable --now mediaops-api mediaops-crawler-worker
```

两个服务都必须使用 `User=mediaops`、`Group=mediaops`，并加载
`/opt/personal-media-ops/backend/.env`。第二个 Worker 会因独占锁失败退出；不要扩大
采集并发。

## BaoTa Nginx

站点静态目录为：

```text
/www/wwwroot/ops.fezern8n.com
```

关键配置：

```nginx
server {
    listen 80;
    server_name ops.fezern8n.com;
    root /www/wwwroot/ops.fezern8n.com;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

宝塔 Nginx 的验证与重载命令是：

```bash
sudo /www/server/nginx/sbin/nginx -t
sudo /www/server/nginx/sbin/nginx -s reload
```

同源部署不依赖 CORS。只有明确的跨域开发来源才加入 `FRONTEND_ORIGINS`，生产不得
使用通配符。

## Controlled Deployment

部署入口为 `scripts/server/deploy.sh`。默认只显示计划，不连接服务器：

```bash
scripts/server/deploy.sh --commit <origin-main-sha>
```

确认目标主机与提交后，执行非 root 阶段：

```bash
scripts/server/deploy.sh --commit <origin-main-sha> --execute
```

该阶段按顺序完成预检、SQLite 备份、`git pull --ff-only`、后端同步和测试、前端
安装/lint/test/build。若无 root 权限，脚本以非零状态结束并输出精确待执行命令；
此时状态是“代码准备完成，生产操作待执行”，不能视为上线完成。

仅在已人工审查 restricted sudo 且本次任务明确授权时执行完整阶段：

```bash
scripts/server/deploy.sh \
  --commit <origin-main-sha> \
  --execute \
  --root-stage
```

root 阶段使用 `sudo -n` 同步静态文件、重启两个应用服务、验证和重载 Nginx；不会
请求密码。前端构建会写入只含目标 Git commit 的 `.mediaops-release`，供
`status.sh` 检查静态版本。`infra/sudoers/mediaops.example` 仅供人工审查，本任务
不会安装它。

## Verification and Rollback

发布后必须检查：

```bash
scripts/server/status.sh
scripts/server/healthcheck.sh --with-ssh
```

也可直接检查：

```bash
curl -fsS http://127.0.0.1:8000/api/health
curl -I https://ops.fezern8n.com/
curl -fsS https://ops.fezern8n.com/api/health
```

部署前备份位于 `/var/backups/mediaops/<UTC timestamp>/`，包含 SQLite 一致性副本、
元数据和 SHA-256 校验值。代码回滚优先使用经过审查的 Git revert 或已知良好版本；
禁止在生产运行 `git reset --hard`。数据库恢复必须先停止写入方并使用单独的人工
审查方案。

完整 SSH、日志和权限说明见 [server-operations.md](server-operations.md)。
