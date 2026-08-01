# AI 研究中心多平台范围与 HTML 结果

## Goal

让 AI 研究中心不再把 Bilibili 写死为唯一平台，并让研究结果在保留原始
Markdown 的同时提供经过安全处理的 HTML 渲染结果。平台选择必须以真实的
Adapter 能力矩阵为准，不能把未验证的平台伪装成可用；研究任务仍通过现有
单并发 Worker 和 Model Gateway 执行。

## What I already know

* 当前研究创建表单在 `frontend/src/pages/research-tasks-page.tsx` 中将
  `platforms` 初始化为 `["bili"]`，并直接显示“当前平台范围：Bilibili”。
* `backend/app/models/research.py` 同样把默认平台设为 `bili`，且只允许最多
  2 个平台；`ResearchToolService._submit_crawl` 要求平台既在任务快照中，
  又通过 `platform_registry.require_mode_enabled(..., "search", ...)`。
* `GET /api/crawler/capabilities` 已返回七个平台及每个平台五种模式的真实
  状态，前端已有 `useCrawlerCapabilitiesQuery` 和能力矩阵组件可复用。
* 生产默认 `MEDIAOPS_ENABLED_PLATFORMS=bili` 是低资源与安全边界配置，不等于
  所有平台的 search 模式都已生产验证。能力状态必须继续区分 enabled、
  production_verified、deferred、disabled 等事实。
* 研究结果目前由 `ResearchRuntime._summarize` 保存为 `result.summary` Markdown，
  研究页使用 `whitespace-pre-wrap` 纯文本显示，没有 Markdown/HTML 渲染层。
* 前端没有现成 Markdown 渲染或清洗依赖；任何模型输出都不能直接写入
  `dangerouslySetInnerHTML`。HTML 需要转义、协议过滤和 XSS 清洗。
* 研究任务数据与 Finding/证据结构已稳定，目标是扩展结果表示和平台选择，
  不改变 8A Gateway、Provider、凭证或 MediaCrawler 核心。

## Assumptions (confirmed)

* 采用方案 A：把能力矩阵中的所有平台注册到研究表单：可选项显示真实模式状态；只有
  当前 `search` 模式 `enabled` 的平台可勾选并提交，其他平台显示禁用原因，
  而不是强行把所有平台都标记为可采集。
* 研究任务默认选择所有当前可用的 search 平台，而不是单独硬编码 `bili`；
  如果没有可用平台，创建表单应明确报错并引导先完成平台配置/验证。
* 用户确认第一种 HTML 方案：结果 API 同时返回 `summary_markdown`（原文）和
  `summary_html`（安全 HTML），前端默认渲染 HTML，并提供“查看 Markdown/复制
  Markdown”的可追溯入口。
* HTML 只用于展示，不替代 Finding 的证据绑定，也不保存完整 Prompt 或密钥。

## Open Questions

* 无。平台范围和 HTML API 形态均已确认；实现中仍需遵守能力矩阵和安全清洗边界。

## Requirements (evolving)

### Platform scope

* 研究创建页从能力 API 动态加载所有平台，不再写死 Bilibili 文案或数组。
* 展示平台名称、平台 key、search 模式状态、验证状态、禁用/延期原因。
* 支持多选；提交前只允许选择 search `enabled` 的平台。
* 后端默认值与校验必须和能力矩阵一致，拒绝未启用、未实现或超出范围的平台。
* 任务创建后保存平台快照，历史任务不随全局平台配置变化而漂移。
* 保持全局采集并发为 1；一次研究任务可跨多个已启用平台，但采集仍串行。

### HTML result

* 保留模型生成的 Markdown 原文，新增安全 HTML 表示。
* 支持标题、段落、列表、强调、代码块、引用、表格（如现有渲染器支持）和
  安全的 http/https 链接；过滤脚本、事件属性、javascript/data 协议和危险标签。
* API 明确声明两种格式；前端默认渲染 HTML，在没有 HTML 时对旧任务 Markdown
  做兼容渲染。
* HTML 渲染失败不能吞掉原文；显示可读错误并保留 Markdown 复制能力。
* 新增前端测试覆盖 Markdown 转 HTML、XSS 清洗、空结果、窄屏和旧任务兼容。

## Acceptance Criteria (evolving)

* [ ] 研究页从能力 API 展示全部七个平台及真实状态，不再只显示 Bilibili。
* [ ] 当前 search 能力可用的平台可多选，未启用/延期平台不能提交并显示原因。
* [ ] 后端默认值、平台校验、任务平台快照与前端选择一致。
* [ ] 一个真实跨平台研究任务能够按选定平台串行执行；不伪造未验证平台成功。
* [ ] 研究结果 API 同时提供 Markdown 与安全 HTML。
* [ ] 前端研究结果默认呈现渲染后的 HTML，仍可查看/复制 Markdown。
* [ ] 模型输出中的脚本、事件属性和危险 URL 不会执行或进入 DOM。
* [ ] 8A Gateway、现有 14 个页面、单并发 Worker 和旧研究任务兼容。
* [ ] 后端测试、前端 lint/test/build、迁移/脚本检查全部通过。

## Definition of Done (team quality bar)

* Backend/API/domain tests cover platform capability validation and result format.
* Frontend tests cover dynamic platform selection, blocked capability states, HTML
  rendering and sanitization.
* No new database is introduced; schema changes, if needed, have an Alembic migration
  and preserve existing research data.
* Production validation uses only platforms whose search capability is genuinely
  enabled/verified; no synthetic results are used.
* Documentation records the distinction between “all platforms shown” and “all
  platforms production-verified”.

## Out of Scope (explicit)

* 不在本任务内强行完成所有七个平台的 MediaCrawler 上游适配、登录态或资源验证。
* 不修改 MediaCrawler 核心、不引入 Redis/Celery/新数据库、不改变全局单并发锁。
* 不重构 8A Model Gateway、Provider、密钥加密、路由或审计模型。
* 不实现 Markdown 编辑器、完整 AI 聊天工作台、导出中心或自动发布。

## Technical Notes

* 主要后端入口：`backend/app/models/research.py`、
  `backend/app/api/research.py`、`backend/app/services/ai/research_runtime.py`、
  `backend/app/services/ai/research_tools.py`。
* 主要前端入口：`frontend/src/api/research.ts`、
  `frontend/src/pages/research-tasks-page.tsx`、
  `frontend/src/features/crawler/hooks/use-crawler-queries.ts`。
* 能力事实来源：`backend/app/crawler/registry.py`、
  `backend/app/crawler/adapters.py`、`GET /api/crawler/capabilities`。
* Markdown/HTML 方案研究记录在
  [`research-markdown-html.md`](research-markdown-html.md)，采用服务端
  `mistune` + `bleach`，前端使用 `DOMPurify` 做第二道清洗。
* 依赖版本和锁文件变化必须在实现中记录，不得用未经清洗的模型 HTML 直接注入 DOM。
