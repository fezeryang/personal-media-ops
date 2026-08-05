# 阶段 8E：AI 行为系统与主动监控

本文件记录阶段 8E 的可执行契约。它服务于当前单 Owner 产品，不引入第二套研究 Runtime，也不把旧订阅或创作者观察重新提升为核心产品。

## 产品闭环

```text
长期关注目标
→ Intent / 监控理解卡
→ 用户确认
→ Monitoring Mission
→ 现有 Research Runtime（库优先、质量闸门、单 Worker）
→ 基线比较
→ 变化/事件/记忆更新
→ 注意力过滤
→ 发现收件箱 + 站内通知
→ 用户反馈、继续研究、加入研究空间
```

监控核心输出是“与上次已知状态相比发生了什么”，不是抓取数量。第一次运行只建立基线；没有真实变化时输出 `no_meaningful_change`，不生成合成候选。

## AI 质量基线与 Replay

固定评测集由 `backend/app/services/ai/evals.py` 定义，包含产品探索、用户痛点、产品比较、趋势变化、事实验证、创作者监控、产品更新监控、事件追踪、负向反馈变化、内容信号、证据不足和平台不可用 12 类场景。评测任务只保存 Intent、关键 unknown、必要证据、范围禁区、最低来源和 partial completion 条件，不保存完整答案。

指标只能从 Recorded Response、Research Task 和 Model Gateway 的持久记录中计算；缺少数据时统一写入 `not_instrumented`，不会用估算比例填充。指标包括 Intent 一致性、目标覆盖、范围漂移、查询接受、查询语义保持、新增信息、独立证据、重复、背景/噪音、事实绑定、错误推测、候选采纳、调用/token/耗时，以及监控专属的真实变化准确率、静默率、重复通知率、变化证据完整率和通知采纳率。

`AIRepository.replay_recorded_task()` 对已记录的任务做离线评估：只读 Recorded Response，不重新抓取平台、不覆盖原任务、不改变生产历史。Prompt Registry 的 `ai_eval_runs` / `ai_eval_results` 保存比较所用的 Prompt、Context 和每个 case 的结果。

8E 的优化前基线来自 2026-08-03 的只读审计 `docs/audits/AI_ARCHITECTURE_AUDIT_REPORT.md`：Context Compactor 名义存在但未进入 Runtime、缺少固定 Eval Dataset 和 Prompt 版本治理；审计记录的“平均调用次数/目标覆盖/噪音占比”是代码审计观察，不是完整生产计量，在没有 Replay 数据前保持 `not_instrumented`。优化后的可比较字段从本阶段开始由 Model Gateway、Research Task 资源和 Eval Replay 持久化。

## Context Engineering

`ContextBuilder` 使用 `ctx-v1` 组织六层上下文：

1. 用户目标、Intent、成功标准；
2. 已确认 Finding 与证据卡；
3. unknown、反向证据和未解决问题；
4. 实体、事件、长期记忆；
5. 带 parent goal/unknown、角色、生成原因和 scope distance 的查询轨迹；
6. 只在必要时加载的原始内容片段。

随后调用原有 `compact_research_context()`。压缩后的证据卡保留 `content_id`、`evidence_id`、source、URL、时间、事实/推测类型和实体关系；查询保留父目标、父 unknown、查询角色、生成原因和范围距离。每次 Builder 调用把 `tiered_context`、`compacted_context` 和 compaction stats 写入 Runtime context，确保 Compactor 是实际调用链的一部分。

Execution Query 必须记录 `parent_goal`、`parent_unknown`、`query_role`、`generation_reason` 和 `scope_distance`。查询质量闸门拒绝泛化、重复和高噪音查询。连续低新增、无独立证据、查询重复、预算接近上限、目标完成或平台饱和时停止。Alignment Review 默认最多一次补充研究回流，超出后保留缺口并进入 partial completion。

## Product Constitution、角色与工具

Product Constitution 位于 `backend/app/services/ai/constitution.py`，要求事实绑定证据 ID、推测显式标记、优先使用长期记忆、查询必须具体、研究价值不由抓取/候选数量决定、单一来源不代表共识、重要写操作需确认，且发现范围漂移要承认。

Prompt Registry 位于 `prompt_definitions` / `prompt_versions`：当前版本只有 `active_version` 和可选 `candidate_version`，支持显式激活与回滚；普通用户没有 Prompt 编辑能力，API 写操作需要 Owner Session + CSRF。每次 Gateway 调用记录 Prompt key/version、Model、Context version 和 Tool Contract version。

角色边界为 Intent Interpreter、Research Planner、Query Strategist、Evidence Judge、Information Utility Classifier、Discovery Analyst、Change Analyst、Alignment Reviewer 和 Report Composer。Report Composer 只组织已确认结果，不重新创造事实。工具契约位于 `backend/app/services/ai/tool_contract.py`，明确用途、禁用范围、Schema、前置条件、预算、异步性、失败和重试行为。

## Monitoring Mission

`monitoring_missions` 是用户长期目标；`monitoring_targets` 支持 topic/entity/creator/event/research_question/query。任务只能在理解卡确认后进入 active。每次运行有模型调用、Token、采集次数、平台数、运行时间、每日/每周预算，并通过 SQLite `BEGIN IMMEDIATE` 任务锁和现有 Worker 保持全局单浏览器约束。

指定平台时，Monitoring Service 不新建 Agent 或采集链，而是创建一个受限的现有 Research Task，并把 `monitoring_runs.research_task_id` 关联到它。Research Runtime 负责 Intent、规划、查询质量、平台等待和现有 Crawler Worker；Worker 将终态任务回写到 Monitoring Mission。没有指定平台时，只使用已有证据库，清楚标记 `existing_library_baseline`。

任务长期状态和本次运行状态分离：一次平台失败进入 `waiting_platform` / `waiting_login` 或 scheduled `degraded`，不会永久删除或终止 Mission。scheduled 任务有指数退避和错过运行后的下一次安全时间；手动任务不会在失败后自动重试。

旧 `subscriptions` 和 `creator_watchlist` 数据保持不变。现有旧页面只读、从主导航隐藏，作为历史审计入口；因为旧记录的关键词、平台认证和业务语义不能总是可靠映射到长期目标，8E 不未经用户确认自动创建 Monitoring Mission。未来可靠映射时使用 `legacy_imported` 来源标记；当前不伪造迁移结果。

## 变化、事件、记忆

基线保存内容 ID、内容指纹和受限内容记录。比较器支持新实体、事件、功能、声明、用户痛点、正/负证据、更新事实和无变化等类型；同一 fingerprint 的相近实体/时间/变化在 `monitoring_changes` 合并为事件更新。变化中保存首次/最近出现、独立来源、平台、转载疑似数、证据、解释和未知项。

来源独立性按 independent group、作者+平台或 URL 统计；相同 URL、近重复文本和作者同步会留下合并理由，不重复增加置信度。高置信变化生成 `monitoring_memory_updates`，保存 old value、new value、evidence IDs、变化时间、来源、置信度和是否需要用户确认，不静默覆盖长期事实。

注意力等级为 `immediate_attention`、`daily_digest`、`normal_record`、`silent_memory`、`ignored`。低置信、已知或重复内容静默；通知以 change 唯一约束、事件 fingerprint、状态和稍后时间防止重复。高价值变化统一进入现有发现收件箱，来源为 `monitoring`；原始查询和工具轨迹只在 Mission 详情的运行/技术标签页中展示。

## 前端与边界

主导航增加“监控任务”，创建页采用“自然语言目标 → AI 理解卡 → Owner 确认”两步流程。详情页固定为概览、重要变化、运行记录、已知基线、监控范围、预算、技术详情。AI 模型中心增加 Prompt 治理只读/显式管理员操作面板。AI 工作台和发现收件箱只展示变化摘要，不恢复旧订阅中心或技术运维大屏。

本阶段不实现邮件、短信、外部推送、自动发布、商业行动、复杂多 Agent、知识图谱、Notion 同步、MCP 或机会卡。扫码、验证码和平台认证仍由现有生产前端与用户完成；系统不读取用户浏览器 Cookie。
