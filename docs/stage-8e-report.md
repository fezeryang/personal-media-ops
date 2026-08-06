# 阶段 8E 验收报告

更新时间：2026-08-06（Asia/Shanghai）

## 结论

阶段 8E 的实现、质量门禁、发布、核心真实监控闭环和 Prompt/Eval 生产闭环已经完成。
生产中已通过三条用户确认的 Monitoring Mission：个人 AI 工具、CodeBuddy、AI 工具
负向反馈。三次最新运行均完成真实受控研究并明确返回 `no_meaningful_change`，没有
伪造变化、通知或独立来源；CodeBuddy 与负向反馈任务还通过了成功 B 站采集及完整
研究详情模型验收。

Owner 已在生产前端完成 `intent_interpreter` 的 v1/v2 Recorded Eval 对比，并完成
候选激活/回滚验证。最新正确对比的两次运行各有 12 个固定案例、2 个 `passed`、
10 个 `not_instrumented`、0 个 `failed`；`not_instrumented` 是固定夹具没有覆盖
的指标，不是伪造分数。当前真实数据没有产生可合法触发通知的高价值变化，因此通知
的“已读/稍后/忽略/继续研究/加入研究空间”动作矩阵没有被人为制造；这项状态诚实
保留为业务观测限制，而不是把无变化任务伪装成变化。小红书验证码限制仍单独记录
为 `blocked_by_platform`。

## 1. 初始和最终 Commit

- 8D 生产基线：`ac0e322`
- 8D 归档：`11007d9`
- 8E 初始交付：`d423ab5765ebcae7f57a3c1dd79bc57059df7999`
- 8E Intent Contract 修复：`12a673d6fbe68734dfd15c05be3845140ace0ae2`
- 8E Summary 响应契约修复：`d439fb74143dd21b7765b79ed13391ee5fcf17a4`
- 8E Research `AwaitingReview` 结算修复：`8dceb61eb30fd10b0c9c6883a5099c8afaba43f3`
- 8E 负向反馈查询边界修复：`0850b23c1a02c64b56bda07dc591f56fe8fcbf7a`
- 8E 前端测试稳定性修复：`7a721b57c0fae712d56b579b81a28630373012f5`
- 8E AI Governance/Recorded Eval：`8f20534141551d47746e3ffec038c638ea08a005`
- 8E Prompt Eval 按钮可辨识性修复：`3faffc416577cc24f5710aa98065b3151b03fb7c`
- 当前生产运行 Commit：`3faffc416577cc24f5710aa98065b3151b03fb7c`
- 所有代码 Commit 已 push 到 `origin/main`。

## 2. 数据库迁移、备份与回滚

- 迁移：`0017_stage_8e` 已部署，后续两个修复均为 code-only，无新迁移。
- 最初 8E 迁移备份：`/var/backups/mediaops/20260806T011925Z`，SHA-256
  `fdec8bd966c4284b2b577b873b7e04ebd7bb3e1e25c1ada9295e57fdeb98b289`。
- Intent 修复备份：`/var/backups/mediaops/20260806T013825Z`，SHA-256
  `7b2f6da05149af1dfee714af9053825e4797c5414aece7d6b2bc638fca7bef5f`。
- Summary 修复备份：`/var/backups/mediaops/20260806T020041Z`，SHA-256
  `e6aabfa7ea53d6e3ab5289aca89a41c1af2703279713f664e721ce41bd10af54`。
- 当前生产备份：`/var/backups/mediaops/20260806T030545Z`，SHA-256
  `11176babdc79631a81c2ca1118d93abd475ebd815560656e2c81c277786ed3e5`。
- AI Governance 发布备份：`/var/backups/mediaops/20260806T043205Z`，SHA-256
  `71c2197c9026bf81050440fe20902156c5fac9d886ef81f3df30428e4a87016f`。
- Prompt UI 修复发布备份：`/var/backups/mediaops/20260806T054429Z`，SHA-256
  `e74d7c39443e49aa38b25ee1295540bde3570f9b00ea1e476dbec621388459ea`。
- 两次后续发布均为 code-only；最后一次没有 Alembic migration，数据库 head 仍为
  `0017_stage_8e`。
- 回滚只允许使用保留备份和经过审核的 Git 回滚；不得 `git reset --hard`、
  删除数据库或覆盖生产数据。

## 3. 8D 基线冻结与审计报告

- 8D implementation/local/visual/release/deployment/smoke/user review 均按既有
  归档记录冻结；小红书验证码限制继续是 `blocked_by_platform`，不是 8D 或 8E
  整体失败。
- 未跟踪的 `AI_ARCHITECTURE_AUDIT_REPORT.md` 属于有效审计报告，已移动并提交
  到 [`docs/audits/AI_ARCHITECTURE_AUDIT_REPORT.md`](audits/AI_ARCHITECTURE_AUDIT_REPORT.md)。
- 用户附件 `愿景.svg` 及其 Zone.Identifier 未纳入代码提交，原样保留。

## 4. Eval Dataset 与历史 Replay

- 固定 Eval Dataset 共 12 类：产品探索、用户痛点、产品比较、趋势变化、事实
  验证、创作者监控、产品更新监控、事件追踪、负向反馈变化、内容信号、证据
  不足、平台不可用。
- 每个 case 保存 Intent、关键 unknown、证据类型、范围禁区、最低来源和
  partial completion 条件，不保存完整答案或 golden answer。
- `AIRepository.replay_recorded_task()` 只读 Recorded Response，不重新抓取平台、
  不覆盖原任务、不修改生产历史；本地 API 测试已验证 12 case 回放和 partial /
  `not_instrumented` 结果。
- 生产数据库当前有 12 个 Eval case、6 个 Eval run、72 个 Eval result、9 个 Prompt
  定义和 10 个 Prompt version。正确的最终对比为：v1 run
  `4fc63934-ce6c-48e9-a42e-50d00ef20b14`、v2 run
  `713cfada-4810-4bee-92ba-45269750e9e7`，两者均为 12 case / 2 passed /
  10 not_instrumented / 0 failed。另有早期错误角色运行和重复 v2 运行，均保留为
  审计记录，没有删除生产历史。

## 5. AI 行为基线与优化对比

- 优化前：审计确认 Context Compactor 名义存在但未进入 Runtime，缺少固定 Eval
  和 Prompt Registry；没有持久化依据的比例统一标记为 `not_instrumented`。
- 优化后：Gateway、Research Runtime 和 Monitoring Run 持久化 Prompt/Context/
  Tool 版本、模型调用、Token、耗时、采集和平台资源字段。
- 三次最新真实运行记录分别为：个人 AI 工具 4 次模型调用、输入 14121、输出
  3342、采集内容 0；CodeBuddy 5 次、输入 15602、输出 3528、采集内容 10；
  负向反馈 5 次、输入 14964、输出 3623、采集内容 9。这些是事实记录，不将
  抓取数量当作研究价值。
- 未有真实持久化依据的质量比例仍为 `not_instrumented`，没有用估算数补齐。

## 6. Context Builder、Compactor、Alignment 与 Early Stopping

- Context Builder 按 Tier 1 用户目标/Intent、Tier 2 已确认 Finding/证据、Tier 3
  unknown/反向证据、Tier 4 实体/事件/长期记忆、Tier 5 查询/工具轨迹、Tier 6
  必要原文构建角色上下文。
- Compactor 已进入生产 Runtime 调用链，保留 `content_id`、`evidence_id`、来源、
  时间、实体关系、事实/推测标记、未解决问题和反向证据，并压缩重复轨迹与低价值
  背景。
- Execution Query 保存 `parent_goal`、`parent_unknown`、`query_role`、
  `generation_reason`、`scope_distance`，质量闸门控制语义漂移。
- 连续低新增、独立证据不增加、查询重复、预算接近上限、目标完成或平台饱和时
  Early Stopping；生产研究任务记录了 `query_candidates_exhausted_after_quality_gate`。
- Alignment Review 默认最多一次有限回流，受查询、平台、Token、运行时间和回流次数
  上限约束；不足时进入 partial completion，不无限循环。

## 7. Prompt Registry、Constitution、角色和 Tool Contract

- Product Constitution 已固定：事实绑定证据 ID、推测显式标记、优先已有记忆、具体
  Query 对应 unknown、转载不增加独立来源、单一来源不代表共识、报告组织器不能
  创造事实、重要写操作需要 Owner 确认。
- Registry 现有 9 个角色 Prompt：Intent Interpreter、Research Planner、Query
  Strategist、Evidence Judge、Information Utility Classifier、Discovery Analyst、
  Change Analyst、Alignment Reviewer、Report Composer。
- 每个 Prompt 记录 key、role、version、status、model family、system/task template、
  input/output schema、temperature、max tokens、change reason、激活时间。
- Tool Contract 明确用途/禁用范围、输入输出 schema、前置条件、预算、异步性、失败
  类型、重试规则和状态变化；工具不再只写“搜索内容”。
- 生产最终为 `active_version=v1`、`candidate_version=v2`；Owner 已通过
  Owner Session + CSRF 完成激活和回滚验证。Prompt 卡片已显示 Prompt key，避免不同
  角色的 Recorded Eval 操作产生歧义；AI 不会自行激活或回滚版本。

## 8. Monitoring Mission 模型、旧数据和调度

- Monitoring Mission 统一替代旧关键词订阅、创作者观察和零散定时采集；旧数据保留
  只读历史，不删除、不伪造批量迁移。
- 任务对象支持 topic、entity、creator、event、research_question、query；长期任务
  只有在自然语言理解卡经 Owner 确认后才进入 active。
- 复用 Research Task、Evidence、Finding、Entity、Event、Memory、Model Gateway、
  Budget 和现有单 Worker，不创建第二套 Research Runtime。
- 运行状态与任务状态分离，支持锁、幂等、暂停/恢复、失败退避、错过运行恢复、重复
  触发保护和 bounded budget；全局单浏览器约束未改变。
- 资源环境仍为 2 vCPU、约 1.6 GiB RAM、SQLite、1 GiB swap；没有 Redis、Kafka、
  Celery 集群、Elasticsearch、图数据库或 Kubernetes。

## 9. Baseline、Change、Event、Memory、Attention 和通知

- 生产 Mission：个人 AI 工具 `58c5e2fa-3bd5-4155-9f1e-fc430bde61b3`、CodeBuddy
  `ef17be25-6ca2-48dd-91c3-3244fbcfc62d`、AI 工具负向反馈
  `b0851446-fffc-4f03-b0d2-1da736e5283a`。
- 第一次历史运行 `4b7d24df…` 因旧 planner 契约缺陷 degraded，历史保留；修复后
  新运行 `8e005649-dd73-46a5-bebc-e47c5b66db54` 成功完成。生产共保留 7 次
  Monitoring Run，其中 5 次 `no_meaningful_change`、2 次 `degraded`。
- 最新运行分别为 `6b138533-27ff-47ba-8f8f-e10fd1bc6a57`、
  `c7cc2356-64a3-4d71-840b-316d7641cbe6`、
  `16932a3f-c8f4-402f-bcf7-dfe63b08a0e5`，均为 `no_meaningful_change`。
  三条任务合计保留 7 个版本化 Baseline；每次运行均有 Research Task 关联，
  没有覆盖原历史记录。
- 变化类型、独立来源、转载合并、反向证据、事件指纹、Memory Update 和注意力等级
  均由代码和本地测试覆盖；本次无真实变化，因此生产变化、变化来源、通知和 Memory
  Update 数均为 0，没有伪造高价值变化。无事件也意味着无法诚实地声称生产已完成
  通知的已读、稍后、忽略、继续研究和加入研究空间动作矩阵。
- 同 fingerprint、同源转载、低置信、已知内容和冷却窗口会被抑制；高价值变化才会
  写入现有发现收件箱并生成站内通知。

## 10. 前端与产品体验

- 一级主导航增加“监控任务”；旧订阅中心和创作者观察没有恢复为独立核心入口。
- 创建流程为自然语言目标 → AI 理解卡 → Owner 确认；详情固定为概览、重要变化、
  运行记录、已知基线、监控范围、预算、技术详情。
- 监控列表响应已修复为只返回 `MonitoringMissionSummary` 字段，详情字段不会再造成
  HTTP 500（`d439fb7`）；“立即运行”按钮在任务详情页，三条真实任务均从该入口
  发起。没有变化的详情页显示明确的静默空状态。
- 发现收件箱使用 `monitoring` 来源；AI 工作台显示重要变化、待处理发现、异常和
  需要登录的平台，不显示抓取数量大屏。
- 本地截图证据：
  [`local-fixtures-1440x900.png`](evidence/local-fixtures-1440x900.png)、
  [`local-fixtures-1280x720.png`](evidence/local-fixtures-1280x720.png)、
  [`local-fixtures-390x844.png`](evidence/local-fixtures-390x844.png)。

## 11. 测试、Release、部署与生产状态

- 后端：`455 passed`。
- 前端：30 个测试文件、73 个测试通过；lint、TypeScript build、Vite build 通过。
- 本地门禁：通过；迁移、Shell/release-script、安全边界和三视口视觉检查通过。
- 最终 Release Candidate：`3faffc416577cc24f5710aa98065b3151b03fb7c`，已 push；
  AI Governance 版本 `8f20534141551d47746e3ffec038c638ea08a005` 也已先行部署。
- 部署：两次均通过 `scripts/server/deploy.sh --target-ref ... --release-candidate
  .release/rc.env --execute`，生产最终运行 `3faffc4`。
- 服务：`mediaops-api=active`、`mediaops-crawler-worker=active`；数据库
  `integrity_check=ok`、Alembic head=`0017_stage_8e`、活动 crawler=0、活动执行型
  research=0、活动 monitoring run=0、browser residue=0、生产工作树 clean。
- `.user.ini` rsync 权限告警触发了已知 marker-verified fallback，随后 restart、Nginx
  检查/重载、内部和公网 health 均通过；不是 SSH transport failure。
- 生产公网健康：frontend 200、`/api/health` 200、crawler route 200。

## 12. 真实生产验收边界

- 已完成：用户创建并确认三条 Mission，分别点击详情页“立即运行”；三次真实
  Research Runtime 均完成，最终为 `no_meaningful_change`，没有变化时保持静默。
  CodeBuddy 与负向反馈任务各有成功 B 站采集，详情模型验证有效；请求的知乎没有
  被冒充为已验证平台。
- 已完成：生产 Candidate Eval 对比，以及 Candidate 激活/回滚后回到
  `v1 active / v2 candidate` 的状态验证。正确 v1/v2 对比各 12 case、2 passed、
  10 not_instrumented、0 failed。
- 未产生可合法触发通知的真实高价值变化，因此通知已读/稍后/忽略/继续研究/加入研究
  空间全动作矩阵没有被人为制造；这是业务数据边界，不是把无变化结果伪装成成功。
- 小红书验证码限制仍记录为 `blocked_by_platform`，不可描述成小红书业务成功，也不
  否定已通过的 Bilibili/Research Runtime 监控闭环。

## 13. 八个分维度状态

```text
implementation_status: passed
local_test_status: passed
local_visual_status: passed
release_candidate_status: passed
deployment_status: passed
production_smoke_status: passed
production_business_status: partial (core mission and Prompt/Eval verified; no legitimate high-value event existed for action-matrix observation)
user_product_review_status: partial (mission creation/run and Prompt governance verified; notification action matrix intentionally not fabricated)
```

阶段以 `completed_with_data_limitation` 归档：代码、质量门禁、生产部署、核心监控闭环
和 Prompt/Eval 闭环均已通过；两个 partial 状态仅表示当前真实数据没有提供可验证通知
事件，且小红书仍受平台验证码限制。不会为了抬高状态而创建合成变化或通知。

## 14. 可复制到 Notion 的产品更新

Personal Media Ops 现在把“持续关注一个目标”建模为 Monitoring Mission：AI 先理解
用户真正想知道的变化，用户确认后按受控预算运行，检索已有记忆和证据，比较上次已知
状态，过滤转载/重复/低价值噪音，并把真正值得关注的变化送入现有发现收件箱。

当前生产闭环已经验证三条真实 Mission 在没有真实变化时明确显示
`no_meaningful_change` 且不通知，并验证了成功采集、研究详情、Baseline、资源和平台
状态的真实记录。`intent_interpreter` 的 v1/v2 Recorded Eval 已完成，最终保持
`v1 active / v2 candidate`，可在后续真实变化出现时继续观测通知动作。产品不恢复旧
订阅后台，不把抓取数量当作主动智能，不伪造平台验证码结果。

## 15. 最终报告索引（对应用户要求的 45 项）

1. 初始和最终 Commit：§1。
2. 数据库迁移：§2。
3. 备份路径与 SHA-256：§2。
4. 8D 基线冻结结果：§3。
5. 审计报告文件处理：§3。
6. Eval Dataset：§4。
7. 历史任务 Replay：§4。
8. 优化前基线：§5。
9. 优化后对比：§5。
10. Context Builder：§6。
11. Compactor 真实调用链：§6。
12. Token 与调用变化：§5、§11。
13. Alignment 回流：§6。
14. Early Stopping：§6。
15. Prompt Registry：§7。
16. Product Constitution：§7。
17. 角色边界：§7。
18. Tool Contract：§7。
19. Prompt 激活和回滚：§7、§12。
20. Monitoring Mission 模型：§8。
21. 旧订阅与创作者观察处理：§8。
22. 调度与资源限制：§8。
23. Baseline 建立：§9。
24. Change Detection：§9。
25. 来源独立性：§9。
26. 转载识别：§9。
27. Event Update：§9。
28. Memory Update：§9。
29. Attention Management：§9。
30. 站内通知：§9、§10。
31. 发现收件箱监控来源：§10。
32. AI 工作台变化摘要：§10。
33. 监控任务前端：§10。
34. 本地桌面与移动端截图：§10。
35. 真实生产验收任务：§12。
36. 平台限制：§12。
37. 后端测试：§11。
38. 前端测试、lint 和 build：§11。
39. Release 与部署：§11。
40. SSH 问题状态：§11。
41. 服务和数据库状态：§11。
42. push 结果：§1、§11。
43. 工作树状态：§11 及最终交接记录。
44. 当前 8E 分维度状态：§13。
45. 可复制到 Notion 的产品文档更新：§14 及 `docs/stage-8e-notion-update.md`。
