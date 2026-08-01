# Phase 8B：AI Runtime 与受控研究任务

Phase 8B 在现有 Model Gateway 之上提供一个可恢复的 Research Runtime。所有模型
请求仍然由 `ModelGateway` 发出；Runtime 不持有 Provider 密钥，也不调用 SDK 或
Provider HTTP endpoint。

```text
研究任务 API / AI 研究任务页
        ↓
ResearchRuntime（SQLite 状态机 + 进程内 wake）
        ↓
ResearchToolService（8 个硬编码工具）
        ↓
ModelGateway（路由、重试、fallback、审计）
        ↓
Provider Adapter / library / 单并发 Crawler Worker
```

## 持久化状态与恢复

`research_tasks.status` 保存 `Draft`、`Planning`、`Researching`、`WaitingCrawl`、
`WaitingLogin`、`Summarizing`、`AwaitingReview`、`Done`、`BudgetExceeded`、
`Failed`、`Cancelled`。计划、上下文、结果、路由快照、提议动作和执行轨迹均为
SQLite JSON 字段；每次状态切换、工具调用、模型用量和采集完成都会追加轨迹。

`submit_crawl` 只创建 `crawler_tasks` 并立即返回。研究任务记录
`waiting_crawl_task_id` 后挂起，不占用 Runtime 执行协程或浏览器锁。Worker 仍然是
唯一持有全局 `fcntl` 锁的采集进程；Worker 在登录、成功、失败、取消和启动恢复时
更新研究任务关联状态。API Runtime 和 Worker 启动时都会扫描未完成关联，因此服务
重启不会依赖内存上下文或 `sleep` 轮询。

## 工具边界

Research Agent 只能调用：

`search_library`、`get_content`、`get_provenance`、`get_creator_history`、
`submit_crawl`、`dedupe_check`、`save_finding`、`propose_action`。

每轮先检索资料库；采集平台和模式通过 Adapter registry 能力矩阵校验。写入用户
动作只能进入 `proposed_actions` 待确认队列。`save_finding` 必须带至少一个真实
`library_contents.id`；推测型结论还必须提供 `derivation`。Finding 通过
`finding_contents` 引用内容，不复制原文。

## 预算

研究任务同时记录采集次数、新增内容、墙钟时长和输入/输出 Token。任一闸门触顶时
进入 `BudgetExceeded`，随后强制进入 `Summarizing`，使用已有证据收敛。金额闸门仅
在任务配置金额上限、币种且路由模型有完整输入/输出价格、币种和生效时间时启用；
缺失价格保持 `null`，后台显示“未配置”，不会伪造为 0。

## 迁移与回滚

迁移 revision：`0011_ai_runtime_research`，父 revision 为 `0010_ai_model_gateway`。
新增 `research_tasks`、`findings`、`finding_contents`、`events`、`event_contents`，
并为 `crawler_tasks`、`ai_model_invocations` 增加可空 `research_task_id` 及索引。

部署顺序：

1. 使用 `scripts/server/backup_sqlite.sh` 备份并记录 SHA-256。
2. 运行现有后端与前端质量门禁。
3. 通过受限 `mediaops-release` 并显式使用 `--allow-migrations` 应用
   `alembic upgrade head`。
4. 执行 SQLite `PRAGMA integrity_check`，核对既有业务表计数和服务健康状态。

Downgrade 只在五张新表和两条关联列为空时允许；存在研究任务、证据或调用关联时
迁移会 fail-closed，优先使用 Git revert 或前向修复，不执行破坏性降级。

## 工具能力实测

生产已对 MiniMax-M3 和 GLM 模型分别执行强制单轮、多轮 tool_result、8 工具选择、
流式工具共存、长上下文五项检查。MiniMax 五项通过并写入 `supports_tools=1`、
`supports_streaming=1`、`capabilities_source=tested`，`tool_calling` 路由指向
MiniMax。GLM 的多轮回传未通过，其余检查通过，因此写入 `supports_tools=0`、
`supports_streaming=1`、`capabilities_source=tested`，不会成为研究员工具路由。

## 研究中心平台范围与结果格式

研究中心创建页消费 `GET /api/crawler/capabilities`，展示注册表中的全部七个平台
以及 `search` 模式的真实状态。只有 `search.enabled=true` 的平台可以勾选；延期、
未启用或上游异常的平台仍可见，但会显示原因并在创建前禁用。未显式传入平台时，
后端默认使用当前配置中所有可提交搜索的平台，而不是硬编码某个平台。跨平台任务
仍由唯一的 Worker 串行执行，任务会保存平台快照。

研究结果同时提供 `summary_markdown` 原文和 `summary_html` 安全 HTML；历史只有
`summary` 的任务在 API 读取时兼容生成这两个字段。服务端使用受限 Markdown 转换
和 HTML allow-list 清洗，前端再用 DOMPurify 做浏览器边界清洗后渲染，原文仍可
查看/复制。HTML 只用于展示和后续导出，不替代 Finding 的证据关联。

## 当前限制

本阶段只有一个 Research Agent 和一套白名单工具；没有多 Agent、Discovery Engine、
长期监控、MCP、Notion、知识图谱或自动执行动作。流式研究响应不透明跨模型续写，
采集仍严格单并发，登录等待需要现有 Worker/登录态完成。
