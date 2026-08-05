# 项目开发、验证与发布流程

本文是给人阅读的执行手册；仓库级强制规则仍以根目录
[`AGENTS.md`](../AGENTS.md) 为准，Trellis 的阶段语义以
[`../.trellis/workflow.md`](../.trellis/workflow.md) 为准。

## 1. 默认工作顺序

所有新阶段、功能、Bug 修复、重构、前端修改、AI Runtime 修改、数据库迁移、部署和
验收都按以下顺序推进：

```text
需求与验收标准
→ 本地实现
→ 本地自动化测试与前后端联调
→ 本地浏览器产品验证
→ 固定 Release Candidate
→ 生产部署
→ 生产冒烟
→ 少量真实业务闭环
→ 用户产品验收
```

生产服务器不是主要开发环境。页面布局、导航、字段映射、加载/空/错误状态、普通
业务状态转换、Discovery 卡片、Research 详情、Feedback、Research Space、移动端溢出
等，应在本地发现并修复。生产数据不能掩盖本地失败。

每次产品修改先对照 [产品愿景 SVG](product-vision.svg)：它必须属于 AI 工作台、研究
任务、发现收件箱、研究空间、记忆与证据、监控任务或工具与设置之一，并说明它帮助
用户完成的核心任务。旧的“指挥中心、今日情报、趋势雷达、订阅中心、创作者观察、
采集中心”继续保持隐藏、合并或工具化决策，不因技术实现方便而重新成为一级入口。

## 2. 本地运行入口

项目提供单入口脚本，所有路径都相对于仓库根目录。脚本只使用本地 `.local-dev/`
目录和本地临时数据库，不读取生产 `.env`、生产数据库、Cookie、Token 或浏览器状态。

```bash
./scripts/dev/start-local.sh
```

它会准备本地 SQLite schema，并启动 `127.0.0.1:8000` 的 FastAPI 与
`127.0.0.1:5173` 的 Vite。日志和 PID 只写入 `.local-dev/`。

```bash
./scripts/dev/stop-local.sh
./scripts/dev/reset-local-db.sh
```

`reset-local-db.sh` 只允许删除仓库内的 `.local-dev/` 数据；不得把它改成生产数据库
清理命令。首次本地 Owner 创建仍通过产品登录页或项目已有的本地 CLI 完成，不把密码
写入脚本或 fixture。

本地产品状态浏览入口是：

```text
http://127.0.0.1:5173/__local/fixtures
```

它是显式的开发可视化入口，不出现在生产构建和生产导航中。该入口用脱敏的
Recorded Response/Fixture 展示研究状态、候选、反向证据、反馈撤销、研究空间、证据、
Finding、事件候选和记忆更新，不能作为生产业务验收证据。

## 3. Fixture 与 Recorded Response

Fixture 只用于本地 UI、组件测试、本地 E2E、状态覆盖和回归测试，不代表生产业务已经
运行。生产默认不启用 mock；本地 fixture 入口必须由开发环境显式暴露，且构建后的
生产 bundle 不包含可用的 fixture 路径。

Recorded Response 应通过当前前端 Zod schema 解析。API schema 变化时，fixture schema
测试必须失败；不要用 `any`、静默字段丢弃或假成功修复契约不一致。Fixture 不得包含
真实 Cookie、Session Token、API Key、密码、二维码、平台登录状态或个人敏感数据。

## 4. AI 功能的三级验证

### Level 1：固定样本

不调用真实模型，验证结构化输出解析、schema 兼容、证据关联、Finding/Discovery 展示、
部分完成说明和报告渲染。

### Level 2：本地有限真实模型

在明确次数和 Token 上限内验证 Model Gateway、Provider 兼容、Prompt 可执行性、结构化
输出、预算、Fallback 和 Tool Contract。改普通 UI 不运行完整多平台研究。

### Level 3：生产真实任务

只验证本地不能完整模拟的生产 Provider 配置、服务器 Research Runtime、Crawler Worker、
平台登录状态、真实数据质量和生产资源限制。生产真实任务不能代替 Level 1/2、本地
单元测试、组件测试和本地页面验证。

## 5. 本地门禁

统一入口为：

```bash
./scripts/test/local-gate.sh
```

门禁失败即停止并返回非零状态，不连接生产。它执行后端测试、临时 SQLite migration
升级与 current-head 校验、前端 lint/test/build、Shell 语法检查、发布脚本的无网络测试、
diff 检查和本地安全断言。前端或产品流程变更还必须用本地浏览器检查：

```text
1440×900  桌面宽屏
1280×720  普通桌面
390×844   移动端
```

视觉证据放在 `docs/evidence/`（该目录被忽略，不进入代码提交），报告记录路径、页面、
视口和结论。没有真实浏览器能力时，必须明确标记 `local_visual_status= pending`，不得
把单元测试冒充视觉通过。

最低状态门槛是：后端 pytest、前端 lint/test/build、迁移检查、Shell 检查、本地主要 API
流程、本地主要页面、桌面和移动视觉检查以及愿景对齐全部通过，之后才能进入
`local_verified` 和 `release_candidate_ready`。

## 6. Release Candidate

Release Candidate（RC）只能是已经提交并 push 的完整 40 位 Commit Hash。使用：

```bash
./scripts/release/prepare-release.sh --output .release/rc.env
```

脚本会确认当前 commit、`origin/main`、本地门禁结果、迁移影响和受控工作树状态，并
写入不含秘密的 manifest。发布前另行记录：

```text
release_commit
previous_production_commit
migration_state
local_gate_result
visual_evidence
backup_path_and_sha256
```

默认拒绝未提交代码、未 push 的 commit、未知目标 ref 和含有生产数据的证据。若工作树
有任务外的既有用户改动，只能逐一显式列入 `--allow-unrelated-dirty`，manifest 必须
记录完整路径；这些路径不得与 RC 中的发布文件重叠。不能用这个选项掩盖当前任务的
未提交代码。

部署入口应携带 RC manifest：

```bash
scripts/server/deploy.sh \
  --target-ref <release_commit> \
  --release-candidate .release/rc.env \
  --execute
```

包含迁移的 RC 还必须显式使用 `--allow-migrations`，并先完成迁移/回滚审查。

## 7. 部署、marker 与 SSH 分类

服务器部署继续复用 `/usr/local/sbin/mediaops-release` 与
`/var/lib/mediaops/deploy-state/<commit>.stages`，不建立第二套发布体系。目标 commit
必须在服务器仓库、构建 marker、发布 marker 和部署记录中一致。服务器需要安装依赖、
执行迁移（如获授权）、构建前端、重启服务并做健康检查；完整测试以本地门禁为准，远端
检查是环境准备和发布后验证的补充。

发布应尽量由一次服务器端 release job 触发，后续用短连接读取 marker/日志/状态；如果
现有脚本仍处于阶段化 SSH 模式，必须保持 marker 可恢复，且每个阶段只能从最后一个
已确认 checkpoint 继续。

SSH banner、握手失败、连接重置、超时、EOF 或客户端失联统一记为：

```text
deployment_status=deployment_transport_failed
```

它不能覆盖已经通过的 `implementation_status`、`local_test_status` 或
`local_visual_status`。第一次安全重试后，停止盲目重试，读取 marker、远端 commit、
数据库 revision、进程、服务和健康接口；只有发现 release 尚未完成或代码有变化时才
恢复相应步骤。不能因为 SSH 失败重新开发、重复完整本地门禁或恢复数据库。

## 8. 认证、浏览器与生产验收

Owner Workbench 登录和第三方平台扫码是两个不同的认证域：

* Windows Chrome 只负责生产前端登录、扫码、验证码、一次明确确认和最终视觉判断。
* 服务器负责 Research Runtime、单并发 Crawler Worker、Discovery、反馈、研究空间、
  数据库、任务状态和日志。
* Codex 负责代码、部署、服务器状态/API/数据库/日志验证。
* Codex 不读取或复制 Cookie、Session Token、浏览器状态，不连接 Chrome 调试端口，
  不创建 Playwright 临时登录绕过，也不要求用户配置 WSL、执行服务器命令或处理 CSRF。

只有真实需要时才打断用户：告诉用户生产前端的具体页面，用户完成一次登录、扫码、
验证码或确认并回复“已完成”，之后从服务器会话、任务状态、正式 API、数据库和日志
继续。没有实际认证要求时，不启动新浏览器，不重复要求登录。

部署后验收分为两步：

### Production Smoke

确认生产 commit、API/Worker active、数据库 revision 与 integrity_check、健康接口、
静态资源、登录入口和无异常浏览器残留。

### Production Business Acceptance

只运行少量代表性流程：创建一条研究任务、等待服务器执行、确认 Discovery、提交并
撤销一条反馈、创建 Research Space、加入候选、创建一次后续研究。遇到平台权限、验证码
或登录限制如实记录为 `blocked_by_user_auth` 或 `blocked_by_platform`，不伪造结果，也
不把它改写成代码失败。

## 9. 阶段状态与完成定义

所有阶段使用 [`templates/phase-status.md`](templates/phase-status.md) 的八个维度：

```text
implementation_status
local_test_status
local_visual_status
release_candidate_status
deployment_status
production_smoke_status
production_business_status
user_product_review_status
```

常用状态包括 `not_started`、`in_progress`、`passed`、`failed`、`pending`、
`not_applicable`、`blocked_by_user_auth`、`blocked_by_platform`、
`deployment_transport_failed`、`awaiting_user_review`。禁止只写无上下文的
`blocked`。工程完成不等于用户产品验收完成；用户验收未完成也不否定已通过的本地工程
结果。

长期产品路线只保留 8D、8E、8F；8F 之后依据真实使用重新决定，不提前规划 8G/8H。
