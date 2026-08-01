# 阶段 8C-1：研究质量地基（单平台 · 不改平台配置）

## Goal

在不恢复新平台、不修改 `MEDIAOPS_ENABLED_PLATFORMS`、不触碰登录态的前提下，
让研究任务能够精确回答：本次带回多少原本不存在的信息；结论的具体证据是否
支撑结论；Agent 生成的查询中哪些是噪声以及为何被拒绝。开发前置诊断必须先
完成，并以 8B 真实任务为基线事实。

## 前置诊断（0.1–0.5，已完成）

诊断对象：研究任务
`f496000c-742e-42c2-91c2-e7218e6961b2`。生产数据库只读核对时间为
2026-08-01；生产应用 commit 为
`2ca748b24db08681da6a5ddb9d8c7c15e800f60c`，API/Worker 均 active。

### 0.1 两条关联采集任务

`actual_count` 是当前解析器交给入库层的条数，不等于上游搜索候选数。上游候选
数由任务日志中实际尝试的视频详情 ID（成功 JSONL 记录 + 详情错误）核对；落库前
条数由 JSONL 记录经当前解析器 `requested_count` 截断后的数量核对；去重命中按
采集开始前是否已有 `bili + source_content_id` 判断。最终“新内容写入”与“已有
内容 upsert”分开报告，避免把更新已有行误称为新增。

| crawler task | platform / query | requested / status | started → finished (UTC) | 实际耗时 | 上游候选 / 可用 JSONL | 落库前 | 去重命中 | 新内容写入 / 已有行 upsert |
|---|---|---:|---|---:|---:|---:|---:|---:|
| `19252928-60df-42b6-9304-baf4965216fd` | `bili` / `寻找当前值得关注的个人 AI 工作台产品，分析其解决的需求、产品形态与可能机会。` | 5 / `succeeded` | `10:02:01.859450` → `10:03:10.512423` | 68.653 s | 20 候选（17 条 JSONL，3 条详情错误） | 5 | 5 | 0 / 5 |
| `22437093-11a1-47ae-b29f-be02e34043a7` | `bili` / `codex workbuddy app agent agentic api` | 5 / `succeeded` | `10:03:12.617900` → `10:04:17.779042` | 65.161 s | 20 候选（19 条 JSONL，1 条详情错误） | 5 | 5 | 0 / 5 |

两条任务的 `actual_count` 都是 5；每条都向 `crawl_task_entities` 写入 5 条内容
发现记录，但 5 条均是已有 `library_contents` 的 upsert，不是新增内容。第一条
完整 JSONL 的第 7、10–15、17 条（共 8 条）当时尚无库记录；第二条第 8–10、
12–14、16–19 条（共 10 条）当时尚无库记录。它们被 `requested_count=5` 的解析
截断排除，证明候选池中存在可能新增的内容。

### 0.2 新增 0 的判定

主判定：**(c) `requested_count` 过小，采样量不足**。其直接表现同时满足
**(a) 对已执行子集的去重命中**：两条任务实际进入入库的 10 条内容全部在采集
开始前已有同平台同 `source_content_id` 记录；因此新增为 0。完整上游可用池中
仍有 8 + 10 条当时无库记录的候选，说明不能把 0 简化成“B站没有新结果”。

排除依据：

* **(b) 不成立**：两条任务均 `succeeded`，各有 17/19 条有效 JSONL，Worker
  完成解析和入库；不是空结果或提前失败。
* **(d) 不成立**：第二条实际参数与任务持久化的 `derived_keywords` 和 trace
  中 `submit_crawl` 参数完全一致；没有发现 API/Worker/Adapter 改写参数的证据。
  但 `app`、`agent`、`api` 等泛词是查询质量噪声，属于 8C-1 要修复的质量问题。

### 0.3 三条 inference 抽查

研究库共有 3 条 inference、11 条关联记录、7 个独立内容；所有 21 条 Finding
证据关联对应的 10 个独立内容，其 `first_collected_at` 均早于研究开始时间。
当前 `save_finding` 只校验 content_id 存在，不校验正文是否支持结论，因此以下
是人工抽查判定，不代表旧实现已有自动保证。

#### `9dc55c05-cb0d-4f42-b6e5-924beedccbbf`

结论原文：个人 AI 工作台类产品正在收敛出一组共同特征：(1) 三种交互模式（执行
Craft / 问答 Ask / 规划 Plan），(2) 长期记忆与全局规则使 AI 越来越懂用户，
(3) Skills/MCP/连接器构成的插件生态，(4) 定时任务与自动化执行。

绑定内容与正文片段：

* `165c3b6b-bcf9-403d-9165-21a666dd431f` — 《我用 Codex 做了一个 AI 邮箱助理：自动巡检多邮箱、总结重点、提醒回复》；正文称“让它定时读取多个邮箱……自动整理成每日简报……提醒我哪些邮件需要关注、哪些需要回复”，支持定时执行/自动化。
* `1b64924d-c2db-4ca1-9cc3-c2783690f341` — 《帮你定制AI个人工作台的Skill！效率MAX》；正文称“不是没有计划——而是会持续忘记该干嘛”，并称拥有“可视化的定制工作台”、根据长期数据推进目标，支持记忆/规划场景。
* `8bc1667a-ff85-4ea3-9621-2b8468c501fa` — 《【终极保姆教程】WorkBuddy官方都没想到？我把10节付费级课程全开源了……》；课程大纲明确列出 Craft/Ask/Plan、技能/MCP/连接器、记忆与全局规则、飞书文档周报、自动化定时任务，直接支持四类特征在 WorkBuddy 中存在。
* `e01469f4-7fd7-4b8e-91ba-4f47bba1d018` — 《【Codex实战】手摸手教你多Agent协同开发》；正文仅为“Codex多Agent协同开发”，不能支撑上述四项。

判定：**部分支撑**。正文支持若干产品/工作流具备这些特征，但只有一条
WorkBuddy 课程完整列出四项，其他材料是单点场景，不能仅凭这些内容推出“产品类
正在收敛”的跨产品趋势。

#### `963d2bd0-892f-406b-a553-eaab65ce1f3d`

结论原文：个人 AI 工作台产品瞄准的真实需求不是单点问答，而是个人/小团队层面的
「执行力外包」：把日常重复任务（多邮箱巡检、办公文档、电商运营、素材生产、研究
检索）交给一个长期可调用的 AI 员工，并补足人脑的执行遗忘与多线程瓶颈。

绑定内容与正文片段：

* `165c3b6b-bcf9-403d-9165-21a666dd431f` — 《我用 Codex 做了一个 AI 邮箱助理：自动巡检多邮箱、总结重点、提醒回复》；正文直接描述多邮箱巡检、分类、日报、回复提醒，并说查邮件/汇总/写报告/整理客户信息等重复工作可逐步交给 AI。
* `1b64924d-c2db-4ca1-9cc3-c2783690f341` — 《帮你定制AI个人工作台的Skill！效率MAX》；正文直接说“会持续忘记该干嘛”，工作台通过提醒、记录、规划和长期数据推进目标。
* `4a4c6809-28b3-4771-be8b-c607f02036b0` — 《电商人狂喜！Codex+skills一个人成一个团队》；正文描述为“-”，只有标题支持“一个人成一个团队”的表述，正文没有独立支撑。

判定：**部分支撑**。这三项证据能推出“若干用户场景体现执行自动化、遗忘和多
线程痛点”，所以该句不是凭空由预训练知识补挂 content_id；但从三个同平台教程/案例
外推到“真实核心需求”及广泛产品定位，证据跨度过大，且第三条没有正文支撑。

#### `c3eb743e-f7a9-4c97-bd7d-0e329a975827`

结论原文：可能的产品机会点：(1) 面向 C 端的「AI 员工即服务」订阅，借鉴 WorkBuddy
模式整合国内办公生态（飞书/钉钉/企微/微信）做差异化；(2) 面向 Codex/Skills
生态做「工作台模板商店」或垂直场景 Skill；(3) 借鉴 Codex Harness Engineering
套路做「零代码 Harness Builder」，让小白可视化拼装多 CLI + 多 API 自动化工作流并
自带风控/反封号策略。

绑定内容与正文片段：

* `1b64924d-c2db-4ca1-9cc3-c2783690f341` — 标题/正文是自建“赛博AI副驾 Skill”和可视化个人工作台，支持个性化 Skill 场景，但不支持模板商店或付费意愿。
* `8bc1667a-ff85-4ea3-9621-2b8468c501fa` — WorkBuddy 课程正文明确是“腾讯云 AI 桌面工作台”，并列出办公 MCP/飞书周报、定时任务，支持被借鉴的产品形态，但不支持订阅商业模式或市场规模。
* `e7667220-fc97-44ed-8b42-3fe66b2f322a` — 《AI 工作流实战！Codex app 搭建某书 Web 工作台 📕》；正文列出 Harness Engineering、Codex CLI、DeepSeek API、外部 CLI、插件修复和自动化生成，支持 Harness 工作流的事实基础，但不支持“零代码”或商业机会成立。
* `fc9d7f03-795b-414d-8ed0-eadf14169a9f` — 《【2026最新Codex】Codex保姆级完整教程……》；正文是 Codex App 与 Claude Code 的功能/额度比较，不能支撑订阅、模板商店或 Harness Builder。

判定：**部分支撑**。证据支持被借鉴的产品/工作流事实和机会假设的来源，但没有
市场、定价、用户付费、竞品或需求规模证据，不能把三个机会写成已验证机会。

### 0.4 requested_count 缺陷处理门

0.2 判定包含 (c)，所以 8C-1 的第一个实现交付物必须修复研究采集的默认/边界
参数，使真实验证任务使用 `requested_count=10–15`，并保持单任务最多 4 次采集、
单 Worker/全局浏览器锁与异步挂起唤醒不变。修复后必须在 `bili` 单平台重跑一次，
确认完整候选池可进入质量统计并产生真实新增或如实证明无新增；不得制造数据。

### 0.5 支持类型提前判断

三条 inference 均为“部分支撑”，没有判为“不支撑”；因此没有因 0.5 触发把
4.5 提前到 4.1 的额外门禁。但 4.5 仍是本阶段必做项：旧 `save_finding` 的
content_id 绑定是形式校验，必须增加支持类型、强度、解释、反证/未找到反证和事实
型 direct 约束。

## 架构审查（实现前门禁）

### 1. `research_queries` 关联

`research_queries.research_task_id` 作为任务内查询轨迹主键；首轮查询允许无父查询，
后续查询必须通过 `parent_query_id`，且至少一个 `source_content_id` 或
`source_finding_id` 非空。`crawler_tasks` 继续用已有 `research_task_id` 关联采集
任务；采集完成通过 `research_queries.executed_at/result_count/new_content_count`
回写，不把 crawler 行复制成查询行。`source_content_id` 外键指向
`library_contents`，`source_finding_id` 外键指向 `findings`；同任务来源链可在 SQL
和 API 中完整展开。

### 2. 质量闸门职责切分

确定性、零 token 规则放在后端纯函数/服务并单元测试：规范化、泛化词单独拒绝、
实体词/长度/停用词 specificity、hash/精确匹配与受控近似历史去重、noise risk、
来源链完整性和平台能力适配。模型只批量评估候选 relevance；expected value 由
`relevance × specificity × novelty` 确定性计算。每个候选先落库再执行/拒绝，拒绝
必须带原因；不允许模型逐候选调用，不允许绕过 Model Gateway。这样能在不消耗 token
的情况下测试“app/工具/话题/agent/api/人工智能/AI/软件/产品”等泛词规则。

### 3. 四类内容判定落点

以现有 `LibraryRepository.ingest_task()` 的 `(platform, source_content_id)` upsert
为幂等事实源，但收紧语义：

* `new_content`：入库前不存在的标准化内容；
* `existing_content`：已存在且 title/description/author 无变化；
* `updated_content`：仅 title/description/author 至少一项实质变化；
* `duplicate_evidence`：结果/查询/任务重复指向同一标准化 content_id，不增加独立证据。

互动指标变化只写现有 `content_metric_snapshots`（EngagementSnapshot 语义），不计入
updated。建议让 ingestion 返回完整分类 DTO，并在 research query/occurrence 事务
中记录，避免研究层再次猜测 upsert 结果。

### 4. `evidence_occurrences` 与 `finding_contents`

保留现有 `finding_contents` 作为“结论—独立证据”去重关联，扩展其支持字段：
`support_type`、`support_strength`、`support_explanation`、必要的推导/反证字段。
新增 `evidence_occurrences` 作为发现事实日志，一行代表某研究任务/查询/采集任务
命中某标准化 content_id，带 `first_seen_at`、`last_seen_at`、`occurrence_count`。
同一 finding 的 evidence API 只返回去重后的 content_id，再展开 occurrences；不
把 occurrence 当独立证据。迁移 0012 从 0011 保留所有 finding_contents 关联，并以
既有 `crawl_task_entities`/finding 关联回填历史 occurrences，无法确定原始查询时
明确标记为历史回填而不伪造 query_id。

### 5. 上下文增量与 token 预算

查询评分元数据为标量，默认不进入模型上下文；批量 relevance 只发送候选文本、类型
和必要来源摘要，目标控制在每批 20–50 候选、每候选约 30–80 token，约 600–4,000
输入 token/批次。证据 occurrences 只在摘要阶段按去重 content_id 展开，默认传
标题 + 受限正文片段 + 支持类型/强度，不传重复命中记录；预计每独立证据增加约
20–60 token，20 条证据约 400–1,200 token。API/前端可完整显示 occurrences，不能
让展示字段无界地进入模型上下文。

## Requirements

* 修复研究采集 `requested_count` 过小导致候选池截断的缺陷；真实验收使用 bili、
  `requested_count=10–15`，最多 4 次采集，不改平台配置。
* 新增 `research_queries`，记录候选、来源链、五项评分、执行/拒绝状态、拒绝原因、
  结果计数和新增计数；拒绝不得静默丢弃。
* 质量闸门按“规范化 → 实体识别 → 确定性评分/历史去重 → 批量模型 relevance →
  期望价值计算 → 平台适配 → 执行或拒绝”顺序运行。
* 研究结果精确报告 new/existing/updated/duplicate_evidence 四类计数；互动指标
  变化只进入 `EngagementSnapshot`，不算 updated。
* 新增 `evidence_occurrences`（或等价结构）区分独立证据与重复发现，扩展
  `finding_contents` 支持类型、强度、解释；事实型 finding 必须有 direct 证据，
  inference 必须有推导依据和反证或“未找到反证”说明。
* 迁移 revision `0012_research_quality_foundation` 从 `0011_ai_runtime_research`
  安全升级；新库/旧库、既有研究任务与证据关联、`PRAGMA integrity_check` 均测试。
* 只增强既有研究任务页：查询轨迹/评分/拒绝原因、四类计数、合并证据及 occurrences、
  支持类型标识和事实/推测/反证/数据不足区分；390px 通过。
* 保持 AI Runtime → Model Gateway → Provider Adapter、异步 submit_crawl、单并发
  Worker、propose_action 人工确认边界和 DeepSeek/GLM tool-routing 约束不变。

## Acceptance Criteria

* [ ] 0.1–0.5 诊断记录、架构审查与本 PRD/开发日志保持一致。
* [ ] requested_count 缺陷修复后，bili 真实验证任务使用 10–15 条且最多 4 次采集。
* [ ] 后端覆盖率 ≥86%；迁移新旧库、既有证据兼容和 integrity_check 通过。
* [ ] 查询规范化、泛化词、来源链、评分、去重、四类计数、occurrences、支持类型约束有测试。
* [ ] 前端研究页展示查询、拒绝、评分、四类计数、独立证据/发现次数和支持类型，390px 通过。
* [ ] 真实任务的所有后续查询有 parent_query_id 与 source_content_id/source_finding_id；至少一条泛词被拒绝且可见。
* [ ] 真实任务所有事实型 Finding 有 direct 证据；inference 显式标记并展示推导依据及反证状态。
* [ ] 未执行任何用户动作；平台配置、登录态和 Worker 并发限制未改变。

## Definition of Done

* 后端、前端、迁移、Worker/部署影响均完成端到端核对；原始 JSONL 不改写。
* 运行 backend pytest（含覆盖率）、frontend lint/test/build、shell syntax；ShellCheck
  若存在则运行。
* 生产部署使用独立 SSH 阶段、marker、受限 helper、迁移备份和完整复核；记录备份
  路径与 SHA-256。
* 报告初始/最终 commit、push、工作树、真实任务 ID、查询/计数/证据/实体/耗时/token、
  服务状态、部署命令与 rollback cautions。

## Out of Scope

平台恢复与跨平台研究、8C-3 token/成本/fallback/故障注入、MCP/Notion、多 Agent、
完整 Discovery Engine、知识图谱、候选审核学习队列、自动发布/执行、导航 IA 重构、
Redis/Celery/PostgreSQL/S3/WebSocket/Kafka/Elasticsearch/Docker，以及任何 MediaCrawler
核心修改。

## Decision (ADR-lite)

**Context**：8B 能完成机械流程，但 `requested_count=5` 截断了真实候选池，且旧 Finding
证据绑定只证明 content_id 存在。

**Decision**：先修复采样量缺陷并以真实 bili 任务复核，再以 SQLite/Alembic 新增查询轨迹
和 occurrence 日志；finding_contents 保持独立证据主表，occurrences 独立记录重复发现；
规则与模型判断严格分工。

**Consequences**：研究报告计数会从“任务实际处理 5 条”升级为可解释的四类计数；历史
8B 任务需要兼容展示并标注旧数据缺少 occurrence/support 元数据，不能回填不存在的
查询来源。

## Implementation Plan

1. 修复 requested_count 截断/默认参数与相关测试；在 bili 生产完成一次真实验证并记录结果。
2. 实现 0012 迁移、查询闸门、四类 ingestion 统计和 evidence occurrences/support 约束。
3. 接入 Research Runtime/API/Worker，保持异步等待和 Model Gateway 边界。
4. 扩展既有研究任务页与前端契约测试；完成全量质量门禁、生产发布与验收报告。
