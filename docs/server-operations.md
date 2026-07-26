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

脚本依次确认身份与工作树、fetch 并固定目标、拒绝非 fast-forward 和数据库迁移、
备份 SQLite、pull、运行后端同步/pytest、运行前端 ci/lint/test/build，然后只调用：

```bash
sudo -n /usr/local/sbin/mediaops-release finalize
```

任何 gate 失败都不会调用 `finalize`。helper 或健康检查失败时，脚本报告具体阶段并
明确发布不成功，不会把部分准备或部分激活描述为成功。

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
