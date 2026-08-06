# 阶段 8E 验收报告

更新时间：2026-08-06（Asia/Shanghai）

## 结论

阶段 8E 的代码、质量门禁、发布和核心真实监控闭环已经完成。生产中已通过
一个用户确认的 Monitoring Mission：第二次运行完成真实研究、建立新基线，
结果为 `no_meaningful_change`，没有伪造变化、通知或独立来源。

阶段暂不归档为 fully complete，原因是以下生产验收必须由 Owner 在正常前端
确认后才能继续，Codex 不得绕过长期监控确认或管理员 Prompt 操作：具体产品
监控、负向反馈监控、产生高价值变化后的通知动作矩阵，以及生产 Candidate Eval
对比。它们不是代码失败，状态明确记录为 `not_run_pending_owner_action`。

## 1. 初始和最终 Commit

- 8D 生产基线：`ac0e322`
- 8D 归档：`11007d9`
- 8E 初始交付：`d423ab5765ebcae7f57a3c1dd79bc57059df7999`
- 8E Intent Contract 修复：`12a673d6fbe68734dfd15c05be3845140ace0ae2`
- 8E Summary 响应契约修复：`d439fb74143dd21b7765b79ed13391ee5fcf17a4`
- 8E Research `AwaitingReview` 结算修复：`8dceb61eb30fd10b0c9c6883a5099c8afaba43f3`
- 当前生产运行 Commit：`8dceb61eb30fd10b0c9c6883a5099c8afaba43f3`
- 所有代码 Commit 已 push 到 `origin/main`。

## 2. 数据库迁移、备份与回滚

- 迁移：`0017_stage_8e` 已部署，后续两个修复均为 code-only，无新迁移。
- 最初 8E 迁移备份：`/var/backups/mediaops/20260806T011925Z`，SHA-256
  `fdec8bd966c4284b2b577b873b7e04ebd7bb3e1e25c1ada9295e57fdeb98b289`。
- Intent 修复备份：`/var/backups/mediaops/20260806T013825Z`，SHA-256
  `7b2f6da05149af1dfee714af9053825e4797c5414aece7d6b2bc638fca7bef5f`。
- Summary 修复备份：`/var/backups/mediaops/20260806T020041Z`，SHA-256
  `e6aabfa7ea53d6e3ab5289aca89a41c1af2703279713f664e721ce41bd10af54`。
- 当前生产备份：`/var/backups/mediaops/20260806T021921Z`，SHA-256
  `ef391889d374f79b2614f96a56b511c0353e18fa69671f0c1543cd5e6a242292`。
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
- 生产数据库当前有 12 个 Eval case、0 个生产 Eval run；生产 Prompt 全部仍为
  `v1`，没有未经 Owner 操作激活 Candidate。

## 5. AI 行为基线与优化对比

- 优化前：审计确认 Context Compactor 名义存在但未进入 Runtime，缺少固定 Eval
  和 Prompt Registry；没有持久化依据的比例统一标记为 `not_instrumented`。
- 优化后：Gateway、Research Runtime 和 Monitoring Run 持久化 Prompt/Context/
  Tool 版本、模型调用、Token、耗时、采集和平台资源字段。
- 生产本次真实运行记录：4 次模型调用、输入 Token 14074、输出 Token 3223、
  采集内容 0；这些是事实记录，不将抓取数量当作研究价值。
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
- 生产默认 `active_version=v1`，Candidate 只允许明确 Owner Session + CSRF 操作；
  激活和回滚均有本地测试，生产 Candidate 对比仍为 `not_run_pending_owner_action`。

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

- 生产 Mission：`58c5e2fa-3bd5-4155-9f1e-fc430bde61b3`。
- 第一次历史运行 `4b7d24df…` 因旧 planner 契约缺陷 degraded，历史保留；修复后
  新运行 `8e005649-dd73-46a5-bebc-e47c5b66db54` 成功完成。
- 新运行建立/更新 Baseline，当前 Baseline 记录数为 2；与基线比较结果为
  `no_meaningful_change`。
- 变化类型、独立来源、转载合并、反向证据、事件指纹、Memory Update 和注意力等级
  均由代码和本地测试覆盖；本次无真实变化，因此变化、来源、通知和 Memory Update
  数均为 0，没有伪造高价值变化。
- 同 fingerprint、同源转载、低置信、已知内容和冷却窗口会被抑制；高价值变化才会
  写入现有发现收件箱并生成站内通知。

## 10. 前端与产品体验

- 一级主导航增加“监控任务”；旧订阅中心和创作者观察没有恢复为独立核心入口。
- 创建流程为自然语言目标 → AI 理解卡 → Owner 确认；详情固定为概览、重要变化、
  运行记录、已知基线、监控范围、预算、技术详情。
- 监控列表响应已修复为只返回 `MonitoringMissionSummary` 字段，详情字段不会再造成
  HTTP 500；“立即运行”按钮在任务详情页。
- 发现收件箱使用 `monitoring` 来源；AI 工作台显示重要变化、待处理发现、异常和
  需要登录的平台，不显示抓取数量大屏。
- 本地截图证据：
  [`local-fixtures-1440x900.png`](evidence/local-fixtures-1440x900.png)、
  [`local-fixtures-1280x720.png`](evidence/local-fixtures-1280x720.png)、
  [`local-fixtures-390x844.png`](evidence/local-fixtures-390x844.png)。

## 11. 测试、Release、部署与生产状态

- 后端：`453 passed`。
- 前端：30 个测试文件、72 个测试通过；lint、TypeScript build、Vite build 通过。
- 本地门禁：通过；迁移、Shell/release-script、安全边界和三视口视觉检查通过。
- Release Candidate：`8dceb61eb30fd10b0c9c6883a5099c8afaba43f3`，已 push。
- 部署：通过 `scripts/server/deploy.sh --target-ref ... --release-candidate .release/rc.env --execute`。
- 服务：`mediaops-api=active`、`mediaops-crawler-worker=active`；数据库
  `integrity_check=ok`、Alembic head=`0017_stage_8e`、活动 crawler=0、活动执行型
  research=0、活动 monitoring run=0、browser residue=0、生产工作树 clean。
- `.user.ini` rsync 权限告警触发了已知 marker-verified fallback，随后 restart、Nginx
  检查/重载、内部和公网 health 均通过；不是 SSH transport failure。
- 生产公网健康：frontend 200、`/api/health` 200、crawler route 200。

## 12. 真实生产验收边界

- 已完成：用户创建并确认“持续关注值得关注的个人 AI 工具”的 Mission，点击详情页
  “立即运行”，真实 Research Runtime 完成，最终为 `no_meaningful_change`；没有变化
  时保持静默。
- 尚未运行：具体产品 Mission、AI 工具负向反馈 Mission、产生真实变化后的通知已读/
  稍后/忽略/继续研究/加入研究空间全动作矩阵、生产 Candidate Eval 对比。这些操作
  需要 Owner 在生产前端确认创建任务或确认管理员操作，不能由 Codex 绕过。
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
production_business_status: partial (core mission verified; additional Owner-confirmed matrix pending)
user_product_review_status: partial (list/detail/immediate-run path verified; change-action matrix pending)
```

阶段尚未执行归档；待上述 Owner-confirmed production matrix 完成后，才能把最后两个
状态提升并生成最终归档提交。

## 14. 可复制到 Notion 的产品更新

Personal Media Ops 现在把“持续关注一个目标”建模为 Monitoring Mission：AI 先理解
用户真正想知道的变化，用户确认后按受控预算运行，检索已有记忆和证据，比较上次已知
状态，过滤转载/重复/低价值噪音，并把真正值得关注的变化送入现有发现收件箱。

当前生产闭环已经验证“没有真实变化时明确显示 `no_meaningful_change` 且不通知”。
下一步只补 Owner 必须确认的具体产品、负向反馈、通知操作矩阵和 Candidate Eval 对比；
不恢复旧订阅后台，不把抓取数量当作主动智能，不伪造平台验证码结果。
