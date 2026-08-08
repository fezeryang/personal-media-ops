# 阶段 8F：Opportunity & Action 阶段报告

> 本报告记录 8F 的工程实现、质量门禁、发布和生产验收。生产验收不为了展示机会而写入合成 Opportunity、Validation、Action、Outcome 或 Memory。

## 1. 阶段范围与基线

| 项目 | 记录 |
| --- | --- |
| 阶段 | 8F Opportunity & Action；不创建 8G/8H |
| 初始代码 Commit | `9b555d2afd29b3a38df1dc2b957aa9fff8750ba4` |
| 8E 生产基线 | `3faffc416577cc24f5710aa98065b3151b03fb7c` |
| 当前 Prompt 基线 | `v1 active` / `v2 candidate` |
| 8E 状态 | `completed_with_data_limitation`；没有真实高价值变化时保持 `no_meaningful_change` |
| 8F Release Candidate | `b75215d4279e6eb7a65b7024b3838bca63601593`；已推送，manifest 为 `.release/rc.env` |
| 生产 Commit | `b75215d4279e6eb7a65b7024b3838bca63601593`；已部署 |

8F 收敛到产品愿景中的 Action Assistant：Evidence → Signal → Opportunity → Validation → Action → Outcome → Memory。没有把旧订阅、创作者观察或抓取数量重新包装成机会产品，也没有增加新的一级导航。

## 2. 数据库迁移、备份与回滚

新增 Alembic revision `0018_stage_8f`，down revision 为 `0017_stage_8e`。迁移实际创建并使用：

- `opportunity_signals`、`opportunities`、`opportunity_versions`、`opportunity_sources`、`opportunity_scores`、`opportunity_feedback`；
- `validation_plans`、`validation_results`、`opportunity_actions`、`action_outcomes`；
- 为既有 `research_memory_items` 增加可空的 `source_opportunity_id`、`source_action_id`、`source_outcome_id`，并允许 Outcome Memory 不绑定 `research_task_id`；
- 扩展 `research_space_items` 的类型检查，支持 `opportunity`、`validation_plan`、`action`、`outcome`。

已验证：空库从 `0001` 升至 `0018_stage_8f`；已有测试数据库通过现有数据迁移测试；空库从 `0018_stage_8f` 降回 `0017_stage_8e`，8F 表被移除、`research_memory_items.research_task_id` 恢复非空。含 8F 数据时 downgrade 会拒绝，避免不可逆丢失。

```text
backup_path_and_sha256: `/var/backups/mediaops/20260808T091409Z`; `1d5fcf057a0af78839a3e0d05b611620dbade455aa3422a5ff0864ca50c3257b`
database_integrity_check: `ok`; `alembic_head=0018_stage_8f`
rollback_caution: 先保留 SQLite 备份；0018 含 8F 数据时不允许 downgrade，回滚优先恢复兼容代码或经确认的数据迁移方案。
```

## 3. Opportunity 架构

### 3.1 Signal

Signal 是轻量、可追踪的证据层，支持：`pain_point`、`unmet_need`、`workflow_friction`、`repeated_complaint`、`behavior_shift`、`new_tool_category`、`product_gap`、`feature_request`、`switching_signal`、`pricing_friction`、`complexity_friction`、`trust_issue`、`content_gap`、`knowledge_gap`、`emerging_interest`。

每条 Signal 保留 `evidence_id`/`content_id`/`finding_id`、Research/Discovery/Monitoring 来源、平台、URL、实体/事件、观察时间和聚合键。AI 不能绕过已有证据创建高置信 Signal；人工来源没有证据引用时也会被拒绝。

### 3.2 Opportunity 类型与生命周期

支持 `product_opportunity`、`business_opportunity`、`content_opportunity`、`research_opportunity`。Opportunity 与 Discovery Candidate 分开，只有独立来源达到最低门槛时才物化候选；单来源或转载只返回 `needs_more_evidence`，无证据时返回 `no_opportunity_identified`。

生命周期为：

```text
weak_signal → evidence_building → candidate → review_ready → validation_ready
→ accepted / rejected / deferred → validating → validated / invalidated
→ converted_to_action → archived
```

Opportunity 每次变化追加 `opportunity_versions` 和 `opportunity_scores`，保留 `readiness_before`、`readiness_after`、变更原因和完整快照，不覆盖旧判断。

### 3.3 透明评分与 Readiness

评分维度为 `problem_severity`、`evidence_strength`、`source_independence`、`signal_frequency`、`cross_platform_support`、`novelty`、`urgency`、`actionability`、`validation_cost`、`competition_or_saturation`、`counterevidence`、`user_relevance` 和 `confidence`。评分只用于解释和排序，不等同于“好生意”。`user_relevance` 只使用用户明确目标、Research Space、Monitoring Mission 或反馈。

Readiness 单独判断：证据不足为 `insufficient_evidence`/`needs_more_evidence`；独立来源、证据强度和反向证据达到门槛时才可到 `review_ready`/`validation_ready`；Validation Result 后才可能为 `validated`。高严重度而证据弱的输入不会被升级为已验证机会。

## 4. Evidence Pack、来源独立性与反向证据

Opportunity Detail 保留 `Core Evidence`、`Supporting Evidence`、`Counterevidence`、`Background` 和 `Unknowns`。每个来源标记 `direct`、`inference`、`estimate` 或 `unknown`，并保留 evidence/content/finding ID、平台、独立来源组和转载标记。

聚合时以独立来源组和平台去重；同作者同步发布、转载和同源营销稿不会增加独立性。解释中同时显示内容数量、独立来源数量、平台数量、转载数量和反向证据是否存在。当前实现的自动聚合是确定性的、有限预算的，后续模型角色只能在这个证据契约内工作。

## 5. Opportunity Feedback

支持：有价值、不相关、证据不足、已经知道、稍后、拒绝、继续研究、创建验证计划、加入研究空间、降低同类优先级。反馈是可追踪用户信号，但不会把 Opportunity 直接变成 `validated`；反馈写入 `opportunity_feedback` 并保留撤销字段。

## 6. Validation Plan 与 Follow-up Research

Validation Plan 包含 hypothesis、target user、problem/value hypothesis、critical assumptions、unknowns、validation questions、evidence needed、cheapest next test、success/failure criteria、effort、risk 和 next decision。默认建议最低成本的研究、竞品/独立反馈/替代方案验证，不自动执行现实世界动作。

Owner 明确批准后才可：

```text
Validation Plan → 独立 Research Task → 新 Intent Contract → 独立预算 → 后续结果
```

Follow-up Research 引用 `opportunity_id` 与 `validation_plan_id`，使用独立 bounded budget、查询和完成标准，不无限扩展原研究。结果支持 `supported`、`partially_supported`、`not_supported`、`inconclusive`，写入 `validation_results` 并使 Opportunity 追加版本；历史 Evidence 和旧成熟度仍然可查看。

## 7. Content Opportunity

Content Opportunity 复用 `opportunity_type=content_opportunity`，描述用户正在困惑、抱怨、争论或缺少案例而现有内容没有回答清楚的问题。卡片包含受众、内容缺口、Evidence、反向证据、当前研究样本的饱和度说明、差异化角度、时效性和风险，最多给出教程型、反常识型、案例型三个证据驱动角度。

系统只说“当前研究样本中重复出现/同质化”，不把样本证据伪装成“全网热点”，也不自动发布内容。

## 8. Action、Outcome 与 Memory

Action 类型为 `research`、`validate`、`prototype`、`interview`、`compare`、`write`、`review`、`monitor`、`manual_other`；状态为 `proposed`、`approved`、`in_progress`、`completed`、`abandoned`。AI 只可提出 Action，Owner 必须批准；只有完成 Action 后才能记录 Outcome。

Outcome 保存 what happened、result、evidence、可选 metrics、lesson、next step，以及手工内容 URL/views/engagement/observation。Outcome 会追加 `research_memory_items` 的 `opportunity_outcome` 记录，绑定 Opportunity/Action/Outcome，先把同一 memory key 的旧记录标为非当前，再写入新值，因此可追溯、可解释、可保留历史，不静默覆盖重要事实。

## 9. Prompt、角色、Tool Contract 与 Eval

新增 Prompt Registry 角色：`opportunity_analyst`、`validation_planner`、`action_assistant`。它们的职责分别是证据绑定的 Signal/Opportunity 分析、最小验证计划和 Action/Outcome 辅助；Report Composer 和 Opportunity Analyst 均不能创造没有 Evidence ID 的事实。现有 `v1 active / v2 candidate` 版本机制、管理员 Owner Session + CSRF 的激活/回滚边界保持不变，AI 不能自行激活 Prompt。

Product Constitution 新增：证据绑定、推测标记、缺证据不补写、优先已有证据、范围漂移承认、重复/转载不计独立来源、最低成本验证、Owner 批准和历史记忆保留等规则。

Tool Contract 新增 `identify_opportunity`、`create_validation_plan`、`propose_action`，明确用途、输入输出、前置条件、预算、异步性、失败和重试边界；不是模糊的“搜索内容”。

Eval 复用 8E 的 Fixed Eval Dataset 与 Recorded Replay，当前固定数据集共 20 个案例（12 个 8E 场景 + 8 个 8F 场景）：强痛点多来源、单一营销来源、转载噪音、证据不足、高竞争、 新颖弱需求、强 Counterevidence、Content Gap。回放不重新抓取、不改生产历史、不覆盖原结果。

指标包含 Intent、覆盖、范围漂移、查询、信息率、独立证据、重复、事实绑定、推测、候选采纳、调用/Token/时间，以及 8F 的 Evidence Coverage、Source Independence、Counterevidence、Opportunity→Validation、Validation Completion、Action Completion 和 Content Opportunity 接受率。缺少真实计算依据的值为 `not_instrumented`，不补写比例。Candidate 版本未自动激活；基线与 candidate 的对比只允许在固定任务上进行，并以质量门禁决定是否激活。

## 10. API 与安全

新增 `/api/opportunities`、`/api/opportunities/{id}`、`/api/opportunities/analyze`、feedback、validation-plan、follow-up research、validation result、`/api/actions`、Action transition/outcome，以及 Research Space 加入机会的现有 API 集成。所有写操作复用 Owner Session、CSRF、Origin 和 owner-scope 查询；Pydantic `extra=forbid` 与前端 Zod schema 拒绝越权字段和未知结构。没有自动发布、外联、付款、第三方表单、注册、合同、投资或 Prompt 自修改。

## 11. 产品整合

- AI 工作台/研究入口显示少量最高优先 Opportunity、Validation In Progress、待处理发现、重要变化和下一步；不显示抓取量、Token 或 Worker 指标。
- Discovery Inbox 提供“分析是否形成机会”，仍保留原 Candidate，不自动升级所有候选。
- Research Space 复用 typed items，可加入 Opportunity、Validation Plan、Action、Outcome；不创建第二套 Runtime。
- Opportunity Detail 使用 sticky summary + `概览 / 证据 / 验证计划 / 相关研究 / 行动与结果 / 技术详情` 标签页。
- 空状态明确说明如何继续研究以形成候选；`needs_more_evidence`、反向证据和错误状态均有用户语言。
- 主导航保持产品愿景结构，不新增“机会大屏”或项目管理入口。

## 12. 本地 Fixture 与视觉证据

本地 fixture 覆盖强/弱 Opportunity、Evidence 不足、Counterevidence、Content Opportunity、Validation Plan、Validation 完成、Action/Outcome、No Opportunity。专用本地路线 `__local/opportunities` 用于视觉验收，不访问生产 API。

已通过 1440×900、1280×720、390×844；脚本还保留 8E 综合状态截图。证据文件在本机 `docs/evidence/`（该目录按仓库规则忽略，不携带生产数据）：

- [`local-opportunity-1440x900.png`](evidence/local-opportunity-1440x900.png)
- [`local-opportunity-1280x720.png`](evidence/local-opportunity-1280x720.png)
- [`local-opportunity-390x844.png`](evidence/local-opportunity-390x844.png)
- [`local-fixtures-1440x900.png`](evidence/local-fixtures-1440x900.png)
- [`local-fixtures-1280x720.png`](evidence/local-fixtures-1280x720.png)
- [`local-fixtures-390x844.png`](evidence/local-fixtures-390x844.png)

桌面端和移动端未发现横向溢出；首屏包括 Opportunity Card、Evidence、Validation Plan、Content Opportunity、Action/Outcome 和空状态。

## 13. 测试与 Release Gate

最终本地门禁命令：

```bash
scripts/test/local-gate.sh
```

结果：`local_gate=passed`；后端 `459 passed`；前端 `32 passed files / 76 passed tests`；前端 lint、TypeScript/Vite build、Alembic blank upgrade/current-head、Shell/release-script checks、六张视觉截图均通过。`npm ci` 报告现有依赖审计为 `3 vulnerabilities (1 moderate, 2 high)`；本阶段未使用 `npm audit fix` 自动改依赖，避免超出 8F 范围，需作为后续依赖维护事项跟踪。

Release Candidate 和 manifest 在本地门禁后生成，记录完整 Commit、迁移状态、上一生产 Commit、视觉证据和回滚要求。正式部署使用以下固定 Commit，并先完成 SQLite 备份：

```text
scripts/server/deploy.sh \
  --target-ref b75215d4279e6eb7a65b7024b3838bca63601593 \
  --release-candidate .release/rc.env \
  --allow-migrations --execute

release_candidate_status: passed
release_commit: b75215d4279e6eb7a65b7024b3838bca63601593
previous_production_commit: 3faffc416577cc24f5710aa98065b3151b03fb7c
production_deploy_result: passed
```

部署已完成。已创建备份 `/var/backups/mediaops/20260808T091409Z`，数据库升级到 `0018_stage_8f`。BaoTa `.user.ini` 删除返回 code 23，但 published/build marker 一致，受限 helper fallback 已完成 restart、Nginx reload 和 verify；external observer=passed。

## 14. 生产冒烟与业务验收计划

部署后先验证：服务 active、Worker active、数据库 integrity/head、活动 crawler/research/monitoring_run 为 0、无浏览器残留、`/api/health` 和认证 API 正常、生产工作树 clean。

真实业务验收严格使用已有 Research/Discovery/Monitoring 数据：

1. 询问“当前证据里有没有真正值得验证的产品/商业机会”，允许 `no_opportunity_identified`；不写合成机会。
2. 围绕已有 AI 工具负向反馈分析重复痛点，单来源只能 `needs_more_evidence`，要求 Evidence Pack、独立来源、Counterevidence 和 Readiness。
3. 运行 Content Opportunity 分析，只接受有 Evidence 的内容缺口，不伪造热点。
4. 只有存在真实 `validation_ready` Opportunity 且用户明确确认时才创建 Validation Plan/Follow-up Research；否则记录 `production_validation_pending_real_candidate`。
5. 只有存在合法真实 Action 且用户实际完成后才记录 Outcome/Memory；否则记录 `user_outcome_observation_pending`。

小红书验证码/登录限制继续单独标记 `blocked_by_platform`，不把平台数据限制描述成整个 8F 失败，也不伪造结果。

生产冒烟结果：公网前端、`/api/health`、`/crawler/tasks` 均为 HTTP 200；生产 Git/静态发布 marker 均为 `b75215d...`；API 与 Worker active；数据库 `integrity_check=ok`、head 为 `0018_stage_8f`；活动 monitoring/research/crawler run 均为 0；浏览器残留为 0。未带 Owner Session 的 `GET /api/opportunities` 返回预期 401，`/opportunities` 返回 200，未出现 500。

真实业务验收保持证据边界：生产当前 `opportunities=0`、`opportunity_signals=0`，没有强行制造机会、验证计划、Action 或 Outcome；本次真实数据验收记录为 `completed_with_data_limitation`。用户已在正常 Owner 浏览器检查 `/opportunities` 和 AI 工作台空状态，确认页面可用、无 500、没有假机会列表。后续若真实证据分析仍不足，正确结果仍是 `no_opportunity_identified` 或 `needs_more_evidence`。

## 15. 阶段状态（当前真实状态）

```text
implementation_status: passed
local_test_status: passed
local_visual_status: passed
release_candidate_status: passed
deployment_status: passed
production_smoke_status: passed
production_business_status: completed_with_data_limitation
user_product_review_status: passed
```

```text
database_changed: yes
backend_changed: yes
frontend_changed: yes
worker_changed: no (复用现有 Research Runtime/队列；新增 Follow-up 通过既有 Runtime)
deployment_changed: yes (0018 migration + API/frontend release activated)
remaining_work: 观察真实 Research/Discovery/Monitoring 使用是否产生可验证机会；不伪造候选，不自动创建 8G/8H。
user_action_required: 仅在生产出现真实 Owner 确认或平台验证码时；普通工程步骤不要求用户协调。
```

## 16. 产品愿景结论

8F 只有在以下链路有真实数据后才算用户价值成立：AI 从证据形成可解释 Signal/Opportunity，用户拥有接受/拒绝/继续研究的控制权，Validation 进入独立研究，Action 需要 Owner 批准，Outcome 回到可撤销的 Memory。当前实现已把这条产品闭环落到统一 Runtime 和可测 API/UI，但生产真实商业价值、内容效果和现实行动结果不在没有用户行为时伪造；这些维度按数据情况记录 `production_observation_pending` 或 `not_instrumented`。

8F 完成后停止自动扩张，不创建 8G/8H，先观察真实使用再决定产品方向。

## 17. 最终补充项

```text
production_backup_path_and_sha256: `/var/backups/mediaops/20260808T091409Z`; `1d5fcf057a0af78839a3e0d05b611620dbade455aa3422a5ff0864ca50c3257b`
production_commit: b75215d4279e6eb7a65b7024b3838bca63601593
deployment_transport_status: passed
production_smoke: passed; database_integrity=ok; alembic_head=0018_stage_8f; active crawler/research/monitoring_run=0
production_business: completed_with_data_limitation；opportunities=0、signals=0，未伪造验收
user_product_review: passed；用户已完成生产空状态检查
final_report_commit: 本次最终验收文档提交记录于 Git log；生产代码 Commit 保持 b75215d...
```
