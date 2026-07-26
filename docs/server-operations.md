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
scripts/server/deploy.sh --commit <origin-main-sha>
```

非 root 准备阶段：

```bash
scripts/server/deploy.sh --commit <origin-main-sha> --execute
```

它完成数据库备份、快进拉取、后端测试和前端 lint/test/build。无 root 阶段时脚本
明确返回“代码准备完成，生产操作待执行”并列出静态同步、服务重启和 Nginx 命令。

仅在本次部署明确授权、且 `infra/sudoers/mediaops.example` 已由管理员审查安装时：

```bash
scripts/server/deploy.sh \
  --commit <origin-main-sha> \
  --execute \
  --root-stage
```

脚本仅使用 `sudo -n`，不会等待密码。部署结束必须运行状态和健康检查，并保存旧
commit、目标 commit、备份位置和结果。

## Permission Boundary

`mediaops` 可执行 Git 检查/拉取、依赖安装、测试、前端构建、允许范围内的日志读取、
API/进程/端口/磁盘/内存检查。

systemd 修改和重启、静态目录写入、Nginx 修改和重载、所有权、系统软件、防火墙、
用户/sudoers、数据库删除或恢复需要 root 或受限 sudo。无权限时输出精确命令并报告
“代码准备完成，生产操作待执行”，不得绕过权限。

## Current Automation Boundary

- 不自动恢复或删除数据库；
- 不修改 sudoers、Nginx、systemd 或防火墙；
- 不清理日志、浏览器登录状态或采集数据；
- 不编辑 `/opt/mediacrawler`；
- 不自动回滚；
- 不在未验证本地修改后直接尝试生产；
- 不把无法连接或权限不足报告成操作成功。
