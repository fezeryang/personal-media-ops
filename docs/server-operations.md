# Server Operations

## Skill Discovery

服务器运维 Skill 的唯一规范源是：

```text
.agents/skills/mediaops-server/
```

当前 Codex 会在仓库级 `.agents/skills/` 自动发现 Skill，因此不需要安装到
`~/.codex/skills`，也不维护第二份副本。在仓库根目录打开新的 Codex 会话即可使用
`$mediaops-server`；如果会话早于 Skill 文件创建，重新打开会话以刷新发现结果。

Skill 包含无凭证服务器库存、部署边界和一个调用 `scripts/server/` 规范脚本的
dispatcher。

## SSH Alias

仓库只提供 `infra/ssh/config.example`，不包含私钥。若 `~/.ssh/config` 不存在，可
安装示例：

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
install -m 600 infra/ssh/config.example ~/.ssh/config
chmod 600 ~/.ssh/mediaops_prod
```

如果配置文件已存在，请人工合并 `Host mediaops-prod` 块，切勿覆盖原文件。私钥仅
保存在本机 `~/.ssh/mediaops_prod`。可用 `MEDIAOPS_SSH_HOST` 覆盖默认别名。

验证解析和非交互连接：

```bash
ssh -G mediaops-prod
scripts/server/connect.sh
```

实际连接统一为 `ssh mediaops-prod`。脚本使用 `BatchMode=yes` 和 10 秒连接超时。
Key、配置或网络缺失时会停止并报告，不会重复重试或索要密码。

## Read-Only Operations

完整状态：

```bash
scripts/server/status.sh
```

它检查服务器 commit、工作树、两个 systemd 服务、8000 端口、本机健康接口、
Nginx 配置、磁盘、内存、最近 24 小时失败任务数、静态 `index.html` 哈希，以及部署
写入的 `.mediaops-release` commit。权限不足会明确显示，不会误报成服务或文件不存在。

公网和本机健康：

```bash
scripts/server/healthcheck.sh
scripts/server/healthcheck.sh --with-ssh
```

检查目标是首页、`/api/health`、`/crawler/tasks`，以及可选的
`http://127.0.0.1:8000/api/health`。健康接口会验证关键 JSON 字段。

查看线上版本：

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 mediaops-prod \
  'git -C /opt/personal-media-ops rev-parse HEAD'
git rev-parse origin/main
```

两者一致且工作树干净，才表示服务器代码与目标 GitHub revision 一致；`status.sh`
还会比较静态 `.mediaops-release` 与仓库 commit。三者一致且健康检查通过，才能判断
部署完整。

## Logs

默认只读取最后 200 行，最大 5000 行：

```bash
scripts/server/logs.sh --api
scripts/server/logs.sh --worker --lines 500
scripts/server/logs.sh --nginx-access
scripts/server/logs.sh --nginx-error
scripts/server/logs.sh --task <canonical-uuid>
```

只有明确需要持续观察时才加 `--follow`。task ID 必须是标准 UUID，脚本不会接受任意
日志路径。无法读取 journal 或 Nginx 日志时应请求相应只读权限，不要使用交互式 sudo。

## Backup

默认只显示计划：

```bash
scripts/server/backup.sh
```

明确执行：

```bash
scripts/server/backup.sh --execute
```

备份 SQLite、当前 commit、UTC 时间和校验值到 `/var/backups/mediaops`。不备份
`.env`、Cookie、二维码、SSH key、虚拟环境、缓存或全部采集结果。目录不存在或不可写
时，脚本会输出管理员准备命令并停止。

## Standard Deployment

先取得并确认 `origin/main` 的 commit，再 dry-run：

```bash
git fetch origin main
git rev-parse origin/main
scripts/server/deploy.sh --target-ref <origin-main-sha> --dry-run
```

真实部署必须单独获得授权，并显式执行：

```bash
scripts/server/deploy.sh --target-ref <origin-main-sha> --execute
```

脚本按阶段执行：`preflight`（身份、工作树、目标、迁移检测、helper 版本）、
`backup`、`git-sync`、`runner-sync`（把仓库审查版 runner 同步到 Worker 实际
执行的 `/var/lib/mediaops/bin/run_mediacrawler.py`，不一致时先做时间戳备份；
该副本曾漂移并导致真实小红书任务 argparse 失败）、`backend-test`、
`frontend-build`、`migrate`（仅授权时）、
`finalize`、`verify`。每个阶段使用独立 SSH 会话，长时间运行的阶段附加
keepalive；`backup` 到 `finalize` 这些标记阶段在远端成功后才在
`/var/lib/mediaops/deploy-state/<target-commit>.stages` 记录
`<stage>=done <UTC 时间戳>`。所有 gate 通过后，特权操作只调用：

```bash
sudo -n /usr/local/sbin/mediaops-release finalize
```

包含 migration/schema 路径的发布默认停止。迁移和回滚方案经审查后，使用
`--allow-migrations --execute` 显式授权；脚本会在备份、测试和构建成功后执行
`uv run alembic upgrade head`，校验 revision 后才调用 `finalize`。

中断后的重试可加 `--resume`：脚本读取目标 commit 的阶段标记，跳过已完成阶段，
`preflight` 和 `verify` 始终重新执行。不带 `--resume` 的 execute 运行会先清空
该目标 commit 的标记文件，避免历史标记干扰本次判定。某阶段 SSH 以 255 退出
时，脚本重连一次检查远端标记；标记为 `done` 则输出 `SSH transport anomaly`
警告并继续，否则按阶段名报告失败。

已部署 helper v1 的 finalize 会因静态目录中不可变的 BaoTa `.user.ini` 在
rsync `--delete` 时以 exit 23 中止。deploy.sh 会在 finalize 失败后核对发布端与
构建端的 `.mediaops-release` 是否都等于目标 commit：一致时依次单独调用白名单内
的 `restart-services`、`nginx-reload`、`verify` 完成激活；不一致则中止并报告
可能的部分激活。

任何前置 gate 失败都不会调用 `finalize`。helper 或健康检查失败时，脚本报告具体
阶段并检查真实状态，不会把部分准备或部分激活描述为成功；属于授权范围内且可修复的
异常由 Agent 修复、测试、提交、push 后从安全检查点继续。

外部 Codex 观察者若出现已复现的 `403`、`525` 或 TLS/连接失败，部署脚本会从生产
服务器执行证书有效的 SNI 回环，并通过受限 helper status 复核服务、Nginx 与
localhost API。全部通过才记录 `failed-nonblocking`；其他 HTTP、origin 或 SNI
失败不会被例外吞掉。

## Restricted Release Helper

服务器安装入口为 `/usr/local/sbin/mediaops-release`，当前版本 `1`。只允许：

```text
version
status
publish-frontend
restart-services
nginx-check
nginx-reload
verify
finalize
```

只读验证：

```bash
ssh -o BatchMode=yes mediaops-prod \
  'sudo -n /usr/local/sbin/mediaops-release version'
ssh -o BatchMode=yes mediaops-prod \
  'sudo -n /usr/local/sbin/mediaops-release status'
```

规范源为 `infra/release/mediaops-release` 和
`infra/sudoers/mediaops-release.example`。它们只能由管理员人工审查安装；
`deploy.sh` 不会覆盖 helper 或 sudoers。不得尝试 root shell、额外参数、任意命令
或 direct sudo rsync/systemctl/Nginx。

## Douyin Headful Browser

抖音站点对无头浏览器返回“验证码中间页”，MediaCrawler 点击登录按钮会超时，任务在
生成二维码前失败。同一台服务器上有头浏览器配虚拟显示可正常打开登录弹窗，因此
Adapter 把抖音标记为需要有头浏览器，Runner 收到 `--headless false` 且没有可用
`DISPLAY` 时会自动以 `xvfb-run -a` 重新 exec 自身。

服务器必须安装 `xvfb`（提供 `/usr/bin/xvfb-run`），缺失时 Runner 直接报错退出而不是
静默降级。安装系统软件属于管理员职责，不在自动化边界内。B 站与小红书保持无头运行，
不受此改动影响。

有头模式下抖音首页可能在初次加载后继续重定向，使 MediaCrawler 创建 HTTP 客户端时
读取 `navigator.userAgent` 遇到 `Execution context was destroyed`。Runner 对
Douyin 的这个精确错误等待 `domcontentloaded` 后最多重试 3 次；不匹配的错误不重试，
也不修改第三方 MediaCrawler 文件。

生产诊断还确认抖音主页会先经过短暂 WAF challenge，进入实际页面后的可见登录入口
文本仍为“登录”，但元素不再固定为 `<p>`。Runner 保留自动弹窗检查；未自动弹出时，
会在 WAF 重载窗口内以 0.5 秒间隔最多检查 40 次，只点击文本严格匹配且可见的登录
入口，并在固定超时内确认旧 `#login-panel-new` 或当前
`[id^="login-full-panel-"]` 弹窗。入口缺失或弹窗未出现会明确失败，不进行无界
选择器重试。

WAF proof-of-work 在单核生产机上可能把普通 SSH/API 诊断拖延到数十秒。Runner 在
Xvfb 重执行完成后仅对 `dy` 设置 `nice +10`，浏览器子进程继承较低调度优先级；
这不是提高采集并发，也不影响 B 站或小红书。进程优先级设置失败时不要静默继续，
Runner 会在启动浏览器前退出并记录明确错误。

Worker 同时限制抖音二维码就绪前的启动时间，默认
`DOUYIN_QRCODE_STARTUP_TIMEOUT_SECONDS=180`。超时后终止该任务的完整进程组并将
任务标记为失败；一旦二维码出现，这个启动超时即停止计时。资源不足的生产机应将
`MEDIAOPS_ENABLED_PLATFORMS` 保持为 `bili,xhs`，而不是切换到仍需 Chromium 且会
引入敏感登录态的 Cookie 登录。

## Permission Boundary

`mediaops` 可执行 Git 检查/拉取、依赖安装、测试、前端构建、允许范围内的日志读取、
API/进程/端口/磁盘/内存检查。

日常静态发布、两个应用服务重启和 Nginx 检查/重载只能通过受限 helper 完成。helper
安装、sudoers、所有权、系统软件、防火墙、用户管理以及数据库删除/恢复仍需管理员
人工处理，不得绕过权限。

## Current Automation Boundary

- 不自动恢复或删除数据库；
- 不安装或修改 helper、sudoers、Nginx、systemd 或防火墙配置；
- 不清理日志、浏览器登录状态或采集数据；
- 不编辑 `/opt/mediacrawler`；
- 不自动回滚；
- 不在未验证本地修改后直接尝试生产；
- 不把无法连接或权限不足报告成操作成功。

## Agent Recovery Boundary

用户已授权完整发布结果后，正常工程步骤不再逐项请求确认。SSH 255/EOF、临时网络
失败、测试或构建失败、服务/Helper/Adapter/Runner 错误都先保持当前阶段 fail-closed，
然后由 Agent 收集服务器证据、修复代码、补测试、commit、push、恢复部署并继续验证。
只有扫码/验证码/账号确认、新秘密或第三方授权、不可逆数据操作、以及超出既有
SSH/Helper 权限体系的 root/网络/系统基础设施变更才暂停。

定向修改 `MEDIAOPS_ENABLED_PLATFORMS` 属于平台 rollout 的非敏感配置操作：修改前
创建权限安全的备份，只替换该变量，不打印 `.env` 其他内容，修改后仅报告变量名与
由能力注册表支持的平台代码。阶段五每个生产窗口只增加
`zhihu`、`wb`、`tieba`、`ks` 中的一个；`dy` 在资源延期解除前不得加入。
