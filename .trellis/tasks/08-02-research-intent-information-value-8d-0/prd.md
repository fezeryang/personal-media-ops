# 阶段 8D-0：研究意图理解与信息价值转化

## 目标

在不重开或重命名阶段 8C 的前提下，把 Research 从“用户目标作为平台查询 → 抓取 → 摘要”升级为可追溯的认知链：自然语言目标 → Intent Contract → Research Plan → Execution Query → Captured Content → Evidence / Discovery Seed / Memory / Action。保留 8B、8C 历史任务、Finding、查询和证据，不重新执行历史研究。

## 产品边界

- 新建独立的 Intent Interpreter Runtime；它只负责理解目标、识别多意图、已知/未知、时间范围、受众、证据要求、排除项、输出、置信度、歧义和假设。Research Planner 继续单独负责计划与执行查询。
- 第一版稳定意图枚举：discovery、verification、comparison、trend_tracking、pain_point_research、competitor_scan、creator_scan、content_opportunity、market_mapping、product_opportunity、monitoring；允许额外语义标签但调度只依赖稳定枚举。
- 为每个新任务保存不可静默覆盖的 Intent Contract；保存 original request、interpreted goal、primary/secondary intents、subject、known entities/constraints、unknowns、time scope、platform preferences、audience、证据/反证要求、exclusions、desired output、success criteria、confidence、ambiguities、assumptions、created_at、version。
- User Goal 与 Execution Query 完全分离。User Goal 只做空/安全/能力边界校验，不能因“工具、平台、趋势、竞品、有哪些、最近”等泛化词拒绝；Execution Query 才做规范化、重复、具体性、噪音、平台、预算和边际收益判断。
- 查询决策支持 allow、transform、hold、reject；Execution Query 保存 query_role（seed_discovery、entity_expansion、cross_platform_validation、counterevidence、competitor_scan、trend_probe、creator_scan、pain_point_probe）、状态和理由。转换必须绑定 Intent Contract、平台、时间、数量和执行预算。
- 识别 unknowns_to_discover，探索计划采用类目扫描 → 主题聚类 → 实体抽取 → 代表内容 → 跨平台验证；不要求用户预先知道产品或创作者。
- 在任务完成前运行 Intent Alignment Review，保存 alignment_score、covered_requirements、missing_requirements、scope_drift、recommended_next_step；对齐不足且预算允许时继续补关键缺口，耗尽时以 partial_completion 进入人工审核。
- 每条新内容评估可多选 information_utility：core_evidence、discovery_seed、background_context、event_signal、counterevidence、memory_update、action_trigger、noise、duplicate，并细分“未作为证据采用”的原因。候选实体进入 candidate_discovery，不自动监控；事件进入 event_candidate 并保留来源。
- 建立基础长期研究记忆：确认实体、事实、推测、反证、未解决问题、查询/失败查询、高价值来源、低价值来源、反馈和变化；再次研究时区分已知、新变化、重复和待验证问题。
- 创建任务后先展示“研究理解卡”：意图、未知项、时间默认、计划平台、证据/反证、排除和预期输出，允许直接开始、修改理解、补充要求。confidence >= .75 直接开始；.45–.75 展示假设并继续；低于 .45 只提出一个最高价值澄清问题，模型失败时使用合理默认而不永久阻塞。
- 记录 original_intent、current_research_hypothesis、intent_revisions；范围漂移只展示建议或创建分支，不静默替换原始目标。

## 数据与兼容

- 添加正式 Alembic forward migration（建议 `0014_research_intent_and_information_utility`，以实际 head 为准），不得以启动时 DDL 代替。迁移前备份生产 SQLite；旧任务生成只读 `legacy_migrated` intent，不修改旧 Finding；历史错误查询标记为 `record_type=user_goal`、`gate_status=not_applicable`，保留审计。
- 按真实读写创建/扩展 intent、intent versions/assumptions、unknowns、alignment reviews、content utilities、entity candidates、event candidates、memory 相关表；不创建空表。保证从 0013 升级保留所有任务、查询、Finding、证据和原始 JSONL，`PRAGMA integrity_check` 为 ok；downgrade 对已有数据 fail-closed。
- 通过现有 ModelGateway 调用低上下文、低温度、结构化 Intent Interpreter；降级顺序为原生结构化 → tool schema → 严格 JSON → 一次修复 → 合理默认 Intent。不得直接接入厂商 SDK、硬编码密钥或把 prompt/output 写入 invocation 审计。

## API、Worker 与前端

- 扩展 Research 创建/详情/控制契约，明确返回 Intent Contract、Plan、Execution Queries、价值分布、候选实体、事件和 Alignment Review；兼容缺少新字段的历史详情。Worker 仍保持单并发、既有 Pause/Resume/Cancel、故障恢复和平台能力矩阵；意图理解不得绕过质量闸门或提交未验证平台。
- 创建页以自然语言目标和理解卡为主；详情页增加原始目标、契约、计划、执行查询、价值分布、发现实体、事件候选和 Alignment Review；所有数字来自 API 真实数据，390px 下可读，无 mock。
- 前端 API 使用 Zod，组件不使用 `any`、不读数据库字段、错误不被吞掉；查询 hook 传 AbortSignal，服务端错误可见。

## 验收与质量门禁

后端覆盖意图解析、多意图、未知项、时间默认、置信度/单问题澄清、User Goal 闸门隔离、查询 transform/角色/hold、历史兼容、价值分类、seed、反证、事件、记忆、对齐、漂移、部分完成、模型降级和迁移；前端覆盖理解卡、修改/假设、契约、价值、实体、事件、对齐、探索/验证差异和 390px。

必须跑：

```text
cd backend && uv sync --frozen && uv run pytest
cd frontend && npm ci --include=dev && npm run lint && npm run test && npm run build
bash -n scripts/server/*.sh
```

至少用两个真实研究任务验收：

1. `最近有哪些值得关注的个人AI工具？`：目标接受、识别 discovery 与 unknowns、生成多个具体 Execution Query、发现至少两个真实实体，且有 discovery_seed、core_evidence、Alignment Review。
2. `比较Codex与WorkBuddy在长期记忆、Skills和自动化任务方面的差异。`：识别 comparison，实体为已知项，查询更具体，直接证据绑定且不被其他产品带偏。

最终报告必须记录初始/最终 commit、迁移、备份路径与 SHA-256、架构和字段、两项任务 ID/结果、价值分类计数、记忆/对齐、模型调用/token/降级、测试覆盖率、服务/Worker/爬虫状态、commit/push/worktree、部署命令与回滚注意事项，并明确 8D-1 只建议有限 Discovery Engine，不在本阶段实现完整自动遍历、关系图谱、知识图谱、多 Agent、MCP、Notion 同步或自动动作。
