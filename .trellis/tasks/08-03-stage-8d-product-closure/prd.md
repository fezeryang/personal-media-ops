# 阶段 8D 剩余闭环：Discovery、反馈、研究空间与 AI 研究产品重构

## Goal

在已完成并推送的 8D-0 Intent Foundation 之上，连续完成阶段 8D-1 至
8D-5，把 Personal Media Ops 从采集优先的情报面板收敛为 AI 研究与机会发现
工作台。用户可以自然表达研究目标，看到可解释的理解卡，完成一次有边界的
多平台研究，判断有限的新发现，用反馈影响后续排序，并把重要候选和证据加入
研究空间与长期记忆。来源、失败、部分完成和未实现的平台能力必须真实可追溯。

## Source requirements

完整产品愿景、阶段边界、验收任务和报告格式来自：
`/home/fezer/.codex/attachments/85affdbe-7257-4118-bb50-3707bd73e153/pasted-text-1.txt`。
该文件是本任务的产品要求原文；本 PRD 固化其可执行约束，不另行缩小范围。

## Requirements

### 8D-1 Limited Discovery Engine

- 复用现有 Research Runtime、Model Gateway、Tool Registry、Evidence 与
  Memory，不创建第二套任务框架。
- 从 `core_evidence`、`discovery_seed`、用户收藏、已采纳候选、研究空间重点
  实体和已确认事件生成有来源链的 Discovery Seed；默认排除 noise、duplicate、
  纯营销和无正文内容。
- 默认 Discovery 深度为 1；扩展必须记录来源内容/任务/实体或事件、与意图的
  关系、新颖性、置信度和信息用途。跨平台回搜只能使用当前
  `enabled` 且 `production_verified` 的平台；不伪造推荐关系或未验证能力。
- 统一候选类型：`entity`、`creator`、`topic`、`event`、`query`、`pain_point`、
  `need`、`product_opportunity_signal`、`content_opportunity_signal`。
- 候选保存父候选、种子、内容来源、平台、意图相关性、新颖性、证据强度、来源
  独立性、跨平台程度、可行动性、反馈、噪音/营销风险、饱和度、最终分数、解释、
  生命周期状态和审计历史。
- 支持实体/关键词扩展、跨平台验证、明确数据关系候选和真实 Adapter 支持的
  推荐关系；不可用能力必须显式标为 `experimental_not_available`。
- 识别相似转载、同稿同步、切片和同作者跨平台重复，展示内容数、独立来源数、
  平台数和疑似转载数。
- 对同一核心实体、相近时间和相似变化生成轻量 Event Candidate，展示正/负证据
  与未知问题；不引入图数据库。
- 候选评分必须由意图相关性、新颖性、证据强度、来源独立性、跨平台覆盖、反向
  证据、可行动性、用户反馈、噪音/营销风险、饱和度和资源成本组成，并返回可读
  的分数解释，不能只暴露黑箱总分。

### 8D-2 Discovery Inbox and feedback memory

- 提供只展示高价值新发现的收件箱，不展示全部抓取内容、日志、重复资料或低价值
  噪音。
- 候选生命周期至少支持 `generated`、`scored`、`queued`、`accepted`、`ignored`、
  `deferred`、`converted_to_research`、`added_to_space`、`dismissed_duplicate`、
  `expired`，每次变化保留审计历史。
- 提供候选列表/详情，以及“有价值、无关、已经知道、重复、稍后处理、继续研究、
  加入研究空间、降低同类优先级、屏蔽主题”等明确的 owner 操作；AI 不得自动采纳
  候选。“关注”只保存未来监控意图，不启动 8E 长期任务。
- `继续研究` 必须继承候选来源和必要证据，创建独立 Research Task，重新应用预算，
  禁止在原任务中无限递归扩展。
- 反馈支持 `valuable`、`irrelevant`、`already_known`、`duplicate`、`follow`、
  `mute_topic`、`deprioritize_similar`、`needs_more_evidence`、
  `converted_to_research`、`added_to_space`，作用域至少包括 global、platform、
  research_intent、research_space、topic；保存权重、理由与撤销能力。
- 反馈排序影响必须可解释：例如 `already_known` 降低基础介绍但提高后续变化，
  `needs_more_evidence` 提高独立来源与反向证据分支；不实现黑箱在线训练。

### 8D-3 Research Spaces and memory/evidence experience

- 将现有专题集合在产品层升级为研究空间，支持查看、创建和添加，不实现看板、多用户
  协作或复杂项目管理。
- 研究空间可关联 Research Task、Discovery Candidate、Evidence、Entity、Event
  Candidate、Finding 和 Unresolved Question，并保留顺序、来源和添加审计。
- 记忆与证据页面以长期研究记忆和可追溯证据为核心，而非“浏览全部抓取内容”；展示
  结论、直接/反向/背景证据、数据缺口和记忆来源。

### 8D-4 AI Research frontend

- 一级主导航收敛为：AI 研究、发现收件箱、研究空间、记忆与证据、工具中心、设置。
  设置包含 AI 模型中心、API Key、用户偏好和系统设置；运行概览、趋势、订阅、创作者
  观察、采集和平台能力降级到工具中心或历史区。
- `/` 默认重定向到 AI 研究；首屏突出自然语言输入、最近研究、待处理发现和需确认事项，
  不突出采集统计。
- 创建研究采用“目标输入 → 理解卡”两步流程；高级配置折叠。理解卡展示目标、主/次
  意图、需要发现的内容、时间范围、计划平台、证据和反向证据、排除项、预期输出与预算，
  支持开始、修改、补充和高级设置。
- 研究详情使用固定顶部摘要和标签页（概览、研究过程、发现、证据、查询、预算、技术
  详情），渐进披露内部参数。`partial_completion` 必须解释已完成目标、缺失证据和未生成
  结论的原因；技术字段只在技术详情中出现。
- 查询、轨迹、证据和预算展示使用中文语义、真实 API 数据和诚实空/错状态；不向普通用户
  直接展示 `unknowns_to_discover`、`information_utility`、`alignment_score`、
  `execution_query` 等内部字段名。
- 研究首页、详情、发现收件箱、空间、记忆与证据、工具中心在 1440×900、1280×720、
  390×844 下无横向溢出；长列表分页/虚拟化或折叠；重页面路由级拆分并消除大 chunk 警告。

### 8D-5 Product flags, compatibility and rollout

- 建立显式、前后端一致的产品功能配置：
  `research_primary_enabled=true`、`discovery_inbox_enabled=true`、
  `legacy_today_visible=false`、`legacy_trends_visible=false`、
  `legacy_subscriptions_visible=false`、`legacy_creator_watch_visible=false`、
  `manual_crawler_primary=false`；不得由数据库是否有数据推断导航。
- 保留旧数据和旧 API，兼容旧路由并给出迁移说明：`/→/research`、`/today→/discoveries`、
  `/trends→/tools/legacy-trends`、`/tasks→/tools/crawls`、`/capabilities→/tools/capabilities`、
  `/library→/memory`、`/collections→/spaces`、`/subscriptions→/tools/legacy-automation/subscriptions`、
  `/watch→/tools/legacy-automation/creators`；实际实现可按现有路由调整但不能丢失兼容。
- 所有写 API 继续使用 owner session、CSRF 和明确 owner 操作；不扩展 Agent API 外部写能力。
- 新 schema 必须使用 Alembic forward migration，升级已有数据并有迁移/降级测试；部署前备份
  SQLite 并记录 SHA-256，迁移发布显式使用 `--allow-migrations`。
- 维持单浏览器/单 Worker 并发，不启用抖音、不启用快手搜索、不自动抓评论/二级评论；不引入
  Redis、Kafka、Elasticsearch、图数据库、长期无人值守监控、自动通知、自动发布或多用户。

## API contracts

在现有 `/api/research/tasks` 体系上新增并通过 Pydantic response model 验证：

- `GET /api/research/discoveries`
- `GET /api/research/discoveries/{id}`
- `POST /api/research/discoveries/{id}/feedback`
- `POST /api/research/discoveries/{id}/continue`
- `POST /api/research/discoveries/{id}/add-to-space`
- `GET /api/research/spaces`
- `POST /api/research/spaces`
- `GET /api/research/spaces/{id}`
- `POST /api/research/spaces/{id}/items`
- `GET /api/research/preferences`

所有 payload 必须 owner-scoped；不可从列表成功推断详情成功，真实验收必须读取任务详情、
事件流、候选详情和空间详情。

## Acceptance criteria

- [ ] 自然语言目标可以生成理解卡并完成一次有限研究；用户能看到主/次意图、未知项、证据和反向证据。
- [ ] 真实研究产生有来源链、分数解释和生命周期的有限 Discovery Candidate；默认深度为 1，不能无限扩展。
- [ ] 发现收件箱支持详情、采纳/忽略/延后/重复/继续研究/加入空间等动作，且 AI 不自动采纳。
- [ ] 反馈保存、撤销、作用域和排序变化均可通过 API/数据库/测试证明，且变化有解释。
- [ ] 继续研究创建新的独立 Research Task，继承必要来源但不复用原任务无限扩展状态。
- [ ] 研究空间能创建、查看并关联候选、任务、证据、实体、事件、Finding 和未解决问题。
- [ ] 三个真实生产验收任务分别覆盖个人 AI 工具发现、AI 工具痛点负向证据和反馈闭环；XHS/Kuaishou 不可用时如实记录。
- [ ] 后端迁移、单元/API/权限/CSRF/旧数据保留测试通过；前端主导航、旧路由、创建两步、详情标签/折叠、发现/反馈/空间/证据/预算/技术详情、空错状态和 390px 测试通过。
- [ ] `cd backend && uv sync --frozen && uv run pytest`、`cd frontend && npm ci --include=dev && npm run lint && npm run test && npm run build` 和 `bash -n scripts/server/*.sh` 全部通过。
- [ ] 生产 API 的 `/api/health`、Research list/detail/events、Discovery detail、Space detail、数据库完整性、服务/Worker 和活动任务状态均通过验证。
- [ ] 代码 commit/push，生产工作树 clean；报告包含迁移备份路径/SHA-256、提交、部署命令、回滚注意事项和截图路径。

## Definition of Done

- 数据库、领域模型、仓储、服务、API、Worker、前端、测试、文档和部署影响均已闭环。
- 生产环境不出现 500、伪造数据、未验证平台成功暗示、残留浏览器状态或未提交生产专用修改。
- 阶段 8E 仅标记为未来主动监控，阶段 8F 仅标记为未来机会与行动；不创建或暗示 8G/8H。

## Out of Scope

- 无限递归发现、长期无人值守监控、自动周期运行、自动通知、自动发布、自动执行用户写操作。
- 完整知识图谱、复杂多 Agent、MCP、Notion 同步、多用户协作、规模化并发和商业化系统。
- 删除旧表/旧数据、重写 MediaCrawler 核心、修改 Cloudflare/Nginx/sudoers/系统网络或新增 root 权限。

## Technical approach

- 新建一个 8D closure migration（必要时拆分为 discovery/space 两个连续 revision），扩展候选与事件为统一 discovery record，并单独保存 seed、source、score、feedback、preference rule、run 和 space item 审计。
- 以 `ResearchTaskRepository` 为事务边界，Discovery service 负责 seed 收集、候选去重、来源独立性、事件聚合和评分；Runtime 在研究轮次结束后只进行一次受预算约束的深度 1 生成，不启动第二个 Worker。
- API 层复用 `require_owner_session`/CSRF 依赖和现有异常语义，所有 response 先通过本地 Pydantic model；继续研究复制为新任务并写入来源上下文。
- 前端以路由级页面和现有 UI primitives 渐进重构；真实 API hook 负责缓存失效，旧路由只做兼容重定向/迁移说明，历史实验移入工具中心。
- 先完成本地迁移/后端契约和 discovery service，再完成反馈/空间，再完成导航和页面重构，最后运行质量门、部署与真实验收。

## Decision (ADR-lite)

**Context**：现有 8D-0 已能理解研究目标并保存候选/记忆基础，但产品仍以旧采集/情报导航为主，缺少有限主动发现、用户反馈和跨对象研究空间。

**Decision**：沿用单一 Research Runtime 和 SQLite/Alembic，采用深度 1、显式生命周期和可解释确定性评分作为 8D MVP；把旧模块降级为工具/历史兼容层；所有 AI 选择必须经过 owner 判断。

**Consequences**：本阶段可形成真实可验收的“目标→研究→发现→反馈→记忆/空间”闭环，但不会提供长期监控或自动行动；未来 8E/8F 可在保存的 seed、preference 和 space 关联上演进。

## Technical notes

- Current baseline: migration `0014_research_intent_and_information_utility`, existing Research Runtime/API/frontend and 8D-0 specs.
- Relevant specs: `.trellis/spec/backend/research-runtime-8d0.md`, `.trellis/spec/frontend/research-center-8d0.md`, `.trellis/spec/backend/index.md`, `.trellis/spec/frontend/index.md`, `.trellis/spec/operations/index.md`.
- Existing paused task `08-02-ux` is preserved as unrelated prior bookkeeping; its narrower “backend out of scope” decision does not define this 8D closure task.
