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
sudo install -d -o mediaops -g mediaops -m 0750 /var/lib/mediaops/bin
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
MEDIAOPS_ENABLED_PLATFORMS=bili
MEDIACRAWLER_PYTHON=/opt/mediacrawler/.venv/bin/python
MEDIACRAWLER_RUNNER=/var/lib/mediaops/bin/run_mediacrawler.py
MEDIAOPS_OUTPUT_ROOT=/var/lib/mediaops/crawler-output
MEDIAOPS_LOG_ROOT=/var/log/mediaops
MEDIAOPS_QRCODE_ROOT=/var/lib/mediaops/qrcodes
MEDIAOPS_NODE_BINARY=/www/server/nodejs/v22.22.3/bin/node
CRAWLER_POLL_INTERVAL_SECONDS=1
DOUYIN_QRCODE_STARTUP_TIMEOUT_SECONDS=180
MEDIAOPS_SECURE_SESSION_COOKIE=true
MEDIAOPS_SESSION_LIFETIME_SECONDS=604800
MEDIAOPS_LOGIN_FAILURE_LIMIT=5
MEDIAOPS_LOGIN_LOCKOUT_SECONDS=900
MEDIAOPS_MAX_OWNER_ACCOUNTS=3
MEDIAOPS_AUTOMATION_POLL_INTERVAL_SECONDS=30
MEDIAOPS_AI_PROVIDER=disabled
MEDIAOPS_MODEL_GATEWAY_MASTER_KEY_PATH=/var/lib/mediaops/secrets/model-gateway-master.key
MEDIAOPS_MODEL_GATEWAY_MAX_CONNECTIONS=20
MEDIAOPS_MODEL_GATEWAY_MAX_KEEPALIVE_CONNECTIONS=10
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

SQLite schema 由 `backend/migrations/` 中的 Alembic revision 管理。首次初始化或
现有旧库升级都使用同一命令：

```bash
cd /opt/personal-media-ops/backend
MEDIAOPS_DATABASE_PATH=/var/lib/mediaops/mediaops.db \
  uv run alembic upgrade head
```

`0001_legacy_tasks` 会创建空库，或在列结构完全匹配时接管原 B 站任务表；
`0002_multiplatform_tasks` 将平台约束扩展为 `bili/xhs/dy`，逐列复制原记录，因此
B 站任务 ID、状态、时间、计数和路径保持不变。`0003_remaining_platforms` 再将
约束扩展为 `bili/xhs/dy/zhihu/wb/tieba/ks`，同样逐列复制全部记录，不读取或改写
JSONL。`0004_content_modes` 保留原任务列和记录，增加五模式目标与限量字段；
`0005_library_entities` 新增内容、创作者、评论、内容创作者关系和任务实体溯源表；
`0006_access_control` 新增所有者、会话与 Scoped API Key；`0007_subscriptions`
新增订阅、平台、运行和任务关系；`0008_library_organization` 新增收藏字段、标签和
有序专题；`0009_metrics_and_intelligence` 新增创作者监控、指标快照、趋势、简报
和每日简报调度；`0010_ai_model_gateway` 新增 AI Provider、认证加密凭证、模型、
角色路由、能力健康检查与调用审计表。
`0011_research_quality_foundation` 增加查询来源链、查询质量闸门、Finding 支持类型与
证据发生记录；`0012_research_quality_foundation` 保留并校验既有研究质量数据。
`0013_cross_platform_research_completion` 增加跨平台 Coverage Plan、查询生命周期与
边际收益、内容采用/转载判定、Runtime checkpoint、步骤级用量、预算事件、Billing
Profile 和 Provider 价格版本；该迁移会为既有 Provider/Invocation 快照补齐账务语义，
不会改写原始 JSONL。
`0014_research_intent_and_information_utility` 增加 Research Intent Contract、意图版本与
假设、未知项、查询 `record_type`/`decision`/`query_role`、信息价值分类、发现实体、
事件候选、长期记忆和 Intent Alignment Review。它为历史 Research Task 建立只读
`legacy_migrated` 意图投影，不重新执行旧任务，也不删除旧 Finding 或证据。
`0015_limited_discovery_and_feedback` 增加有深度上限的 Discovery Run/Seed/Candidate、
来源与分数快照、候选生命周期、所有者反馈和可撤销的偏好规则；`0016_research_spaces`
增加所有者隔离的 Research Space 与带类型的 Space Item，可容纳研究任务、Discovery、
证据、实体、事件、结论、未解问题和长期记忆。Discovery 只从真实内容/8D-0 候选建立
来源绑定候选，深度固定为 0/1；反馈 undo 必须同时停用对应偏好规则。两次迁移均要求
已有数据兼容测试，downgrade 在新表有数据时拒绝。应用启动只校验当前 revision，不会
静默执行迁移。
唯一约束按“平台 + 源 ID”建立，互动指标允许 `null` 并有非负约束。存在非搜索任务或
资料库数据时，对应 downgrade 会拒绝执行，避免隐式丢失。应用启动只校验当前
revision，不会静默执行迁移。

迁移、受限 helper 激活和健康检查完成后，通过交互式终端初始化所有者：

```bash
cd /opt/personal-media-ops/backend
uv run python -m app.cli create-owner --username owner
```

密码由用户亲自输入两次，不要作为命令参数、环境变量、聊天内容或部署日志传递。若
已有所有者，命令不会覆盖。部署前端后，除公开健康检查和认证入口外，旧 API 也会要求
会话或对应 API Key Scope。

生产迁移顺序固定为：确认无未审查变更 → SQLite 一致性备份 → 拉取目标代码 → 测试与
前端构建 → `alembic upgrade head` → 受限 helper 激活 → 健康检查 → 必要时交互式
创建所有者并验证登录。数据库恢复属于
破坏性 root 操作，本仓库不会自动执行。

阶段 8C 的 `0013_cross_platform_research_completion` 发布前必须确认生产仍在
`0012_research_quality_foundation`，先执行 SQLite 一致性备份并记录备份目录与
SHA-256，再使用 `--allow-migrations` 发布。迁移后必须核对 Alembic head 为
`0013_cross_platform_research_completion`、`PRAGMA integrity_check` 为 `ok`，并确认
既有 Research、Finding、Evidence 和 AI Invocation 行数未减少。若迁移或应用验证失败，
保持新 schema，优先回滚应用代码或提交前向修复；不得执行未经审查的 downgrade 或
替换生产数据库。

阶段 8D-0 的 `0014_research_intent_and_information_utility` 发布前必须确认生产仍在
`0013_cross_platform_research_completion`，先执行 SQLite 备份并记录备份路径与
SHA-256，再审查迁移中的历史意图投影、查询 `user_goal` 标记和外键约束，使用
`--allow-migrations --execute` 发布。迁移后必须核对 Alembic head 为
`0014_research_intent_and_information_utility`、`PRAGMA integrity_check` 为 `ok`，
并比较旧 Research、Finding、Evidence、Query、AI Invocation 行数没有减少。不要执行
未经审查的 downgrade；数据库回滚只能通过前向修复或经授权的恢复操作完成。

阶段 8D-1/2/3 的 `0015_limited_discovery_and_feedback` 与
`0016_research_spaces` 发布前必须确认生产仍在
`0014_research_intent_and_information_utility`，先执行 SQLite 一致性备份并记录备份
路径与 SHA-256，再审查候选深度/来源约束、反馈撤销和空间 item 类型，使用
`--allow-migrations --execute` 发布。迁移后必须核对 Alembic head 为
`0016_research_spaces`、`PRAGMA integrity_check` 为 `ok`，并比较旧 Research、Finding、
Evidence、Query、AI Invocation 与 Library 行数没有减少。验收至少调用认证的
`/api/research/tasks`、每个验收任务的 detail/events、`/api/research/discoveries`、
`/api/research/preferences` 和 `/api/research/spaces`；Research detail 必须通过
`ResearchTaskDetail` 响应模型，包含 utilities、entity/event candidates、memory、
alignment、queries、evidence 和 Discovery 字段。不得用假数据掩盖 500 或 schema mismatch。
不要执行未经审查的 downgrade；数据库回滚只能通过前向修复或经授权的恢复操作完成。

8D 前端的生产主导航固定为 `/research`、`/discoveries`、`/spaces`、`/memory`、
`/tools`、`/settings`。`/today`、`/subscriptions`、`/trends`、`/creators`、
`/collections`、`/system`、`/crawler/tasks`、`/ai/models` 和 `/integrations` 只作兼容
重定向或工具子页，不得重新成为主导航。生产构建必须通过同源 `/api`，不得直接编辑
`frontend/dist`。

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

Worker 通过参数数组调用固定 Python 和固定 Runner，绝不使用 `shell=True`。仓库审查
源为 `scripts/crawler/run_mediacrawler.py`，运行时固定路径仍为
`/var/lib/mediaops/bin/run_mediacrawler.py`。Runner 必须支持：

```text
--platform bili|xhs|dy|zhihu|wb|tieba|ks
--crawler-type search|detail|creator|comments|sub_comments
--keywords <text>                          # search
--target-id/--target-url <value>           # detail/comments/sub_comments
--creator-id/--creator-url <value>         # creator
--parent-content-id <value>                # comments/sub_comments alternative
--parent-comment-id <value>                # sub_comments
--login-type qrcode
--requested-count <1..20>
--requested-comment-count <0..10>
--requested-sub-comment-count <0..5>
--output-dir <generated task directory>
--qrcode-path <generated PNG path>
--max-concurrency-num 1
--enable-comments true|false
--enable-sub-comments false
--headless true|false
```

`--enable-comments` 只允许在显式 `comments` 模式为 `true`；Runner 永远拒绝
`--enable-sub-comments true`，避免上游递归抓取全部回复。独立二级评论只通过已审计的
平台定向、可限量 client seam 执行。成功状态还要求输出发现、JSONL 解析、标准化、
幂等资料库写入和任务溯源同一事务完成；非零或异常空结果都不得伪装为成功。

`--headless` 由 Adapter 的平台能力决定，不由 API 调用方传入：除抖音外当前平台为
`true`，抖音为 `false`。抖音站点会对无头浏览器返回“验证码中间页”，登录按钮不会出现，
任务会在生成二维码前因点击超时失败；有头浏览器在虚拟显示下可正常打开登录弹窗。
因此当 `--headless false` 且环境没有可用 `DISPLAY` 时，仓库 Runner 会以
`xvfb-run -a` 重新 exec 自身（用 `MEDIAOPS_XVFB_WRAPPED` 标记防止循环）；服务器必须
安装 `xvfb`，否则 Runner 会明确报错退出。B 站与小红书行为不变，仍为无头运行。

抖音首页在 `goto()` 返回后仍可能发生一次重定向，MediaCrawler 随即读取
`navigator.userAgent` 时会收到 Playwright `Execution context was destroyed`。
仓库 Runner 只在 `dy` 平台、只对该精确导航竞态，在等待
`domcontentloaded` 后最多重试客户端初始化 3 次；其他 Playwright 异常和重试耗尽
仍直接失败。补丁在进程内安装到集成 seam，不复制或修改 `/opt/mediacrawler` 源码。

抖音主页的登录入口不再保证是 `<p>登录</p>`。Runner 会先保留
`#login-panel-new` 和当前 `[id^="login-full-panel-"]` 两种弹窗路径；若弹窗未出现，
则只枚举文本严格等于“登录”的可见元素。WAF 重载期间入口可能短暂不存在，Runner 会以
0.5 秒间隔最多检查 40 次，再逐个用短超时点击并确认任一受支持弹窗已可见。没有可用
入口或点击后仍无弹窗时会明确失败，不使用模糊文本点击，也不无限重试。这个兼容补丁
同样只安装在 `dy` 进程内。

抖音 WAF 的浏览器 proof-of-work 在低配单核主机上可能持续占满 CPU。完成 Xvfb 包装后，
Runner 只对 `dy` 进程增加 `nice +10`，浏览器子进程继承该优先级，避免 SSH、API 和
Worker 健康检查被采集任务饿死；B 站与小红书优先级不变。无法设置该非特权优先级时，
抖音任务会在浏览器启动前明确失败。Worker 另以
`DOUYIN_QRCODE_STARTUP_TIMEOUT_SECONDS` 限制二维码就绪前的启动阶段，默认 180 秒；
到期会终止整个抖音进程组并明确标记失败。二维码生成后该启动超时立即解除，不会缩短
操作员的扫码时间。

所有 Adapter 都有有限的二维码启动窗口。Runner 会包装目标平台的只读 `pong`
登录态探测：已有登录状态有效时仅输出统一的
`[MediaOps] Existing login state ready: <platform>`，不输出 Cookie 或浏览器数据。
Worker 因而可以区分已有登录、二维码等待、验证码、登录失效和登录超时；超时、取消和
明确登录失败都终止完整进程组。该包装只作用于进程内集成 seam，不修改上游源码。

微博使用移动 UA 启动浏览器时，Passport 页面默认显示短信登录，只有点击精确可见的
“扫码登录”后才渲染上游等待的二维码节点。Runner 仅在 `wb` 进程内包装二维码发现
seam：已有二维码时不点击；否则以 0.5 秒间隔最多检查 20 次精确文本入口，点击后在
10 秒内确认二维码，再交回上游读取。入口缺失或二维码未出现时明确失败，不使用模糊
文本、不改登录方式，也不修改 `/opt/mediacrawler`。

贴吧上游即使已包含 PC 页面改版提交，仍会优先点击百度首页的 HTTP 贴吧链接，并在部分
请求中进入“百度安全验证”；其登录 fallback 也仍只查找旧 `li.u_login`。Runner 仅在
`tieba` 进程内让上游导航先完成，然后把 HTTP/安全验证页定向恢复到带百度 Referer 的
`https://tieba.baidu.com/`。持续安全验证会输出通用 `captcha required` 标记并失败，
不会把“扫码验证”当成登录二维码。正常页面则在上游首次等待前点击当前
`div.user-or-login` 或旧 `li.u_login`，确认 `tang-pass-qrcode-img` 后交回上游读取。
所有入口扫描和二维码等待都有上限，且不修改 MediaCrawler 源码。

快手当前页面的精确可见 `//p[text()='登录']` 节点可能被透明层拦截普通坐标点击。
Runner 只在 `ks` 进程内查找该精确入口并派发 DOM `click()`，随后必须在有限时间内
确认上游既有 `//div[@class='qrcode-img']//img` 节点；二维码已打开后只跳过上游紧接着
重复的一次坐标点击，其余二维码读取、扫码状态和采集流程仍交给未修改的 MediaCrawler。
入口不存在或二维码未出现时明确失败，不删除任意页面遮罩，也不使用模糊选择器。

2026-07-28 的真实扫码验证确认快手登录成功，但固定上游仍调用 GraphQL
`visionSearchPhoto`，返回 `result=50` 和 0 条 feeds；当前网页已改用
`POST /rest/v/search/feed`，且生产环境的 headless 与 headful/Xvfb 对照请求均返回
`result=2`、无结果数据。Runner 的 `ks` 专用搜索保护会把缺失、非成功、结构错误或空
feeds 明确转为非零失败，禁止 0 条结果被记为 `succeeded`。模式级能力门禁允许生产
配置包含 `ks`，但 search 仍返回 `deferred_upstream_breakage`，不能提交。阶段六的
独立真实任务已经验证 detail 与 comments；creator 因固定上游资料接口持续返回空资料
而延期，sub_comments 仍为未生产验证的 `code_ready`。

API 调用方不能覆盖命令、脚本或文件路径。每台服务器只启用一个 Worker；第二个
Worker 会因独占锁失败退出。Worker 重启时会把遗留的 `running` 或
`waiting_login` 任务标记为异常中断。代理开关不暴露为 Runner 参数；仓库 Runner
在配置层和 MediaCrawler CLI 参数层都固定关闭代理。保持既有 B 站参数契约意味着
只发布应用代码不会要求先替换生产 Runner。

仓库 Runner 不属于 MediaCrawler 核心源码。首次启用任一新 Adapter 前，先以
`mediaops` 身份把已审查版本安装到固定运行路径并验证语法：

```bash
cd /opt/personal-media-ops
python3 -m py_compile scripts/crawler/run_mediacrawler.py
install -m 0750 scripts/crawler/run_mediacrawler.py \
  /var/lib/mediaops/bin/run_mediacrawler.py
```

不要编辑 `/opt/mediacrawler`。固定版本与升级流程见
`docs/upstream-mediacrawler.md`。`MEDIAOPS_ENABLED_PLATFORMS` 默认只含 `bili`。
小红书已通过 2026-07-26 的真实运营任务验证，可在操作员批准后显式启用 `xhs`。
抖音仍是代码就绪状态；只有 Runner、扫码登录、输出和结果转换完成真实验证后，才可把
`dy` 保留在 `.env` 的启用列表中。代码完成本身不等同于生产验证。

当前低资源生产机必须从 `MEDIAOPS_ENABLED_PLATFORMS` 排除 `dy`，让能力接口和前端
明确显示抖音暂不可用；截至 2026-07-28，知乎、微博和贴吧均已通过 5 条真实任务验证并
可与 `bili,xhs` 一起启用。不要改用 Cookie 登录规避抖音限制：Cookie 属于敏感浏览器登录态，
而 MediaCrawler 的 Cookie 模式仍会启动 Chromium，不能解决主机资源瓶颈。恢复抖音前
需要先提供足够的浏览器资源，或引入经过单独授权和评审的官方接口登录方案。

知乎、微博、贴吧、快手的基础代码可以随应用发布，但每次只把一个新平台加入
`MEDIAOPS_ENABLED_PLATFORMS` 并运行小规模真实任务；只有任务成功、结果字段正确、
浏览器退出和资源恢复后才把该平台标记为 `production_verified`。

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

日常发布中的 Nginx 验证与重载只能通过受限 helper：

```bash
sudo -n /usr/local/sbin/mediaops-release nginx-check
sudo -n /usr/local/sbin/mediaops-release nginx-reload
```

同源部署不依赖 CORS。只有明确的跨域开发来源才加入 `FRONTEND_ORIGINS`，生产不得
使用通配符。

## Controlled Deployment

部署入口为 `scripts/server/deploy.sh`。默认只显示计划，不连接服务器：

```bash
scripts/server/deploy.sh --target-ref <origin-main-sha> --dry-run
```

确认目标主机、当前/目标 commit、迁移检测、备份和测试计划后，真实发布必须显式执行：

```bash
scripts/server/deploy.sh --target-ref <origin-main-sha> --execute
```

如果待发布 diff 包含 Alembic、模型或 schema 路径，默认会在备份前停止。审查迁移与
回滚方案后，才可显式授权：

```bash
scripts/server/deploy.sh \
  --target-ref <origin-main-sha> \
  --allow-migrations \
  --execute
```

部署按阶段执行，每个阶段使用独立的短连接 SSH 会话：

```text
preflight：身份、工作树、目标 commit、迁移检测、helper 版本
→ backup：SQLite 一致性备份
→ git-sync：fetch 并 git pull --ff-only 到固定目标 commit
→ model-gateway-key：以 mediaops 用户幂等创建或验证 32 字节 master key，
  目录/文件权限固定为 0700/0600，不回显内容且不使用 root helper
→ runner-sync：将仓库审查版 scripts/crawler/run_mediacrawler.py 同步到
  /var/lib/mediaops/bin/run_mediacrawler.py（Worker 实际执行的已安装副本）
→ backend-test：uv sync --frozen 与后端 pytest
→ frontend-build：npm ci 与前端 lint/test/build，写入 .mediaops-release 标记
→ migrate：已授权时执行 Alembic upgrade 并校验 head
→ finalize：restricted helper finalize
→ verify：内部健康检查、公网健康检查、记录新旧 commit
```

长时间运行的阶段附加 SSH keepalive（`ServerAliveInterval=15`、
`ServerAliveCountMax=8`）。`backup` 到 `finalize` 这些标记阶段在服务器端成功
完成后追加一行 `<stage>=done <UTC 时间戳>` 到
`/var/lib/mediaops/deploy-state/<target-commit>.stages`（`preflight` 与
`verify` 不写标记），标记目录用 `mkdir -p` 幂等创建。不带 `--resume` 的
execute 运行会先清空该目标 commit 的标记文件，确保历史尝试遗留的标记不会满足
255 重查。

`runner-sync` 存在的原因：Worker 通过生产 `MEDIACRAWLER_RUNNER` 执行的是
`/var/lib/mediaops/bin/run_mediacrawler.py` 这个已安装副本，而不是仓库文件。
该副本曾因发布流水线不同步而漂移（旧副本的 `--platform` 仍只允许 `bili`，导致
一次真实的小红书任务以 argparse exit 2 失败）。此阶段以 mediaops 用户、不使用
sudo 执行：源文件缺失即硬失败；与已安装副本逐字节一致（`cmp -s`）时记录
`runner_sync=unchanged` 并只写阶段标记；不一致时先以 `install -m 750` 生成带
UTC 时间戳的 `.backup-*` 备份，再安装新副本、清除
`/var/lib/mediaops/bin/__pycache__`，并记录 `runner_sync=updated` 与新文件的
sha256。

`model-gateway-key` 只操作固定的服务端 secrets 目标。key 不存在时使用操作系统随机源
和排他创建写入 32 字节；存在时验证真实普通文件、所有者和长度，绝不读取、打印或
替换。异常状态 fail-closed。key 位于数据库与数据库备份目录之外，也不写入 `.env`。

所有测试和构建成功后，部署脚本只调用：

```bash
sudo -n /usr/local/sbin/mediaops-release finalize
```

迁移只会在数据库备份、后端测试和前端构建全部成功后执行；未提供
`--allow-migrations` 时不得执行。任何前置 gate 失败都不得调用 helper。helper 或
发布后健康检查失败时可能存在部分
激活状态，必须先检查真实状态，不能把部分激活宣称为成功；授权范围内的可修复异常由
Agent 修复、测试、提交、push 后从安全检查点继续。

### Resume 与 SSH 传输异常

- `--resume` 会在 preflight 之后读取目标 commit 的阶段标记文件，跳过已记录
  `done` 的阶段；preflight 和 verify 始终重新执行。各阶段自身幂等（已在目标
  commit 时 `git pull --ff-only` 为 no-op，pytest/npm 重跑安全），也可单独重跑：

  ```bash
  scripts/server/deploy.sh --target-ref <origin-main-sha> --resume --execute
  ```

- 某阶段 SSH 以 255（传输错误）退出时，脚本不会立即判定失败，而是重连一次并
  检查该阶段的远端标记；标记为 `done` 时输出
  `SSH transport anomaly, stage completed remotely` 警告并继续，否则按原样以
  阶段名报告本次尝试失败。Agent 随后重新连接，综合 commit、marker、数据库
  revision、进程与健康状态，从最近安全检查点修复并恢复；不因单一退出码要求用户选择
  技术方案，也不重复已经验证成功的迁移。其他非零退出码同样先保持该阶段 fail-closed，
  再进入证据驱动的修复/重试循环。

### 外部观察者健康检查例外

Codex 执行环境经过 Beaver/WAF 的公网路径可能出现已复现的 `403`、`525` 或 TLS/
连接重置。`deploy.sh` 只对这些外部观察者结果启用窄例外：它会从生产服务器通过
`--resolve ops.fezern8n.com:443:127.0.0.1` 验证真实公网主机名、证书、首页、
`/api/health` 与 SPA 路由，并再次运行受限 helper 的 status（服务、Nginx 和
localhost API）。全部通过后记录 `external_observer=failed-nonblocking` 并完成
部署；SNI 回环、Helper、Nginx、服务、localhost 或任意其他公网 HTTP 失败仍会阻断。

### finalize 的 .user.ini 回退

静态目录中存在 BaoTa 面板的不可变（`chattr +i`）`.user.ini` 文件，已部署的
helper v1 在 `rsync --delete` 尝试删除它时会以 exit 23 中止 finalize，即使发布
内容本身已完成。deploy.sh 对此提供回退：finalize 失败后核对
`/www/wwwroot/ops.fezern8n.com/.mediaops-release` 与
`/opt/personal-media-ops/frontend/dist/.mediaops-release` 是否都精确等于目标
commit。两者一致时，依次单独调用白名单内的 `restart-services`、
`nginx-reload`、`verify` 子命令完成激活，任何一步失败仍视为部署失败；标记
不一致则立即中止并报告可能的部分激活。日志会明确记录走了哪条路径。

## Restricted Helper Source

仓库中的人工审查源：

```text
infra/release/mediaops-release
infra/sudoers/mediaops-release.example
```

helper 版本为 `1`，固定子命令为 `version`、`status`、`publish-frontend`、
`restart-services`、`nginx-check`、`nginx-reload`、`verify` 和 `finalize`。
它不接受任意路径、服务或额外参数。

helper 源中的 `publish-frontend` rsync 已加入 `--exclude='.user.ini'` 与
`--filter='protect .user.ini'`，避免 `--delete` 尝试删除 BaoTa 面板的不可变
`.user.ini` 而以 exit 23 中止；版本号保持 `1`，该修复在下一次经审查的 helper
安装后生效。在此之前，deploy.sh 通过上述 finalize 回退兼容已部署的 helper v1。

管理员可在独立维护窗口审查后安装；应用部署脚本永远不会执行这些安装命令：

```bash
sudo install -o root -g root -m 0755 \
  infra/release/mediaops-release \
  /usr/local/sbin/mediaops-release
sudo visudo -cf infra/sudoers/mediaops-release.example
sudo install -o root -g root -m 0440 \
  infra/sudoers/mediaops-release.example \
  /etc/sudoers.d/mediaops-release
```

安装或更新 helper/sudoers 不属于普通应用发布。不得要求密码、获取 root shell，或
绕过白名单。前端构建会写入目标 commit 的 `.mediaops-release` 标记，供 helper 和
`status.sh` 验证发布版本。

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
禁止在生产运行 `git reset --hard`。`0010` 在存在任何 Provider 或调用历史时拒绝
downgrade；阶段 8A 回滚优先 Git revert 或前向修复并保留新表。`0002` 只有在数据库
不存在 `xhs/dy` 任务时才允许降级到 `0001`；否则应保持新 schema 并回滚应用代码。数据库恢复必须先停止 API
和 Worker 写入方，并使用单独授权、校验备份的人工审查方案。

完整 SSH、日志和权限说明见 [server-operations.md](server-operations.md)。
