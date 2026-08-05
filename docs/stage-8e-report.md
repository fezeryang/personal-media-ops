# 阶段 8E 验收报告（工作记录）

本文件在本地门禁、Release Candidate、部署、生产冒烟和最小真实业务验收完成后更新为最终报告。所有“未验证”字段必须保留，不得用演示数据代替。

## 基线与提交

- 初始生产 Commit：`ac0e322`
- 8D 归档：`11007d9`
- Trellis 日志：`ad2e494`
- 8E 最终 Commit：待 Release Candidate
- 审计报告：已移动到 `docs/audits/AI_ARCHITECTURE_AUDIT_REPORT.md`
- 未跟踪用户附件 `愿景.svg`：保留，未纳入 8E 代码提交

## 交付范围

- 数据库：迁移 `0017_stage_8e`，包含 Prompt/Eval、Monitoring Mission、运行/查询、基线、变化来源、Memory Update、通知表；downgrade 在存在数据时 fail-closed。
- Backend：AI Registry、Replay、Context Builder/Compactor、查询语义审计、有限 Alignment 回流、Monitoring Service、调度锁/退避、变化与来源独立性、事件合并、记忆更新、通知 API。
- Frontend：监控任务主导航、两步创建、理解卡、详情标签页、运行/变化/基线/通知、发现收件箱 `monitoring` 来源、AI 工作台摘要、Prompt 治理面板。
- Worker：复用现有单 Worker；Monitoring Mission 指定平台时桥接到现有 Research Runtime，不建立第二套采集运行时。
- 旧数据：订阅和创作者观察保持只读历史审计，不删除、不伪造迁移。

## 质量证据

- 固定 Eval Dataset：12 个场景；无 golden answer。
- 历史 Replay：由 `AIRepository.replay_recorded_task()` 离线运行，未重新抓取平台；实际运行数和结果待最终门禁记录。
- 优化前基线：审计发现 Compactor 未接入、缺少固定评测和 Prompt Registry；没有完整生产计量的字段保持 `not_instrumented`。
- 优化后：Gateway 记录 Prompt/Context/Tool 版本；Runtime 记录分层/压缩上下文和 stats；监控记录资源和变化来源。

## 分阶段状态（最终门禁前）

```text
implementation_status: in_progress
local_test_status: in_progress
local_visual_status: not_run
release_candidate_status: not_started
deployment_status: not_started
production_smoke_status: not_started
production_business_status: not_started
user_product_review_status: not_started
```

## 最终报告必须补齐

1. 初始/最终 Commit、push 结果；
2. 迁移、备份路径与 SHA-256、回滚警告；
3. Eval/Replay、基线与 candidate 对比、Token/调用变化；
4. Context Builder/Compactor/Alignment/early stopping 证据；
5. Prompt、Constitution、角色、Tool Contract、激活/回滚证据；
6. Monitoring Mission、旧数据处理、调度资源与安全边界；
7. Baseline、Change/Event/Memory、Attention/Notification、Inbox/Workbench；
8. 桌面/移动视觉证据、后端/前端测试、Build；
9. 生产任务、平台限制、服务/Worker/DB 状态、SSH 状态、工作树；
10. 八个分维度状态和可复制到 Notion 的产品更新。
