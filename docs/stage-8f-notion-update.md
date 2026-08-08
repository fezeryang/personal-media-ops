# 个人 AI 研究与机会发现工作台：8F 产品文档更新

## 这次产品增加了什么

8F 把已有的 Research、Discovery、Monitoring 和 Memory 连接成一个可控的行动闭环：

```text
Evidence → Signal → Opportunity → Validation → Action → Outcome → Memory
```

机会不是热点列表，也不是模型随手生成的创意。它必须说明问题是谁遇到的、证据来自哪里、来源是否独立、有哪些反向证据、还不知道什么，以及最低成本如何验证。

## Opportunity

第一版支持四类机会：产品机会、商业机会、内容机会、研究机会。商业机会只表示“值得继续验证的需求或价值空间”，不表示市场规模、收入或商业模式已经成立。

Opportunity Card 首屏展示：机会描述、目标用户/场景、核心痛点、关注原因、证据强度、独立来源、成熟度和下一步。详情可以查看 Evidence Pack、反向证据、版本历史、验证计划、相关研究和行动结果。

没有足够证据时，系统会显示 `no_opportunity_identified` 或 `needs_more_evidence`。一篇营销文章、一组转载或模型想象不会直接形成高置信机会。

## Validation

用户接受一个候选后，可以创建 Validation Plan。计划会把问题假设、关键假设、最大未知、验证问题、证据需求、成功/失败标准和最便宜的下一步写清楚。只有用户确认后，系统才会创建独立的 Follow-up Research；不会无限扩展原研究，也不会自动联系用户、发布内容或执行商业动作。

验证结果支持：支持、部分支持、不支持、无法判断。结果会产生 Opportunity 新版本，旧版本和历史证据继续保留。

## Content Opportunity

Content Opportunity 关注的是“用户正在困惑，但现有内容没有回答好什么”，不是播放量、热度或全网趋势。系统只会基于当前研究样本说明重复问题、内容缺口、受众和差异化角度，并明确样本边界；不会自动发布文章。

## Action 与 Outcome

Action 是轻量下一步，不是项目管理工具。AI 可以提出 research、validate、prototype、interview、compare、write、review、monitor 或 manual action，但用户必须先批准。Action 完成后，用户手工记录发生了什么、结果、证据、教训和下一步。

Outcome 会形成可追溯的长期记忆更新：旧判断不被静默覆盖，新记忆绑定 Opportunity、Action 和 Outcome，未来可以解释和撤回。没有真实用户结果时，系统不会假装验证成功。

## 产品入口

机会主要出现在：

- AI 工作台：少量最高优先机会、正在验证、待处理发现、重要变化和下一步；
- 发现收件箱：从 Candidate 发起证据绑定的机会分析；
- Research Space：把 Research、Discovery、Evidence、Opportunity、Validation、Action、Outcome 放在同一个长期主题空间。

没有增加新的“机会大屏”，也没有恢复订阅中心或创作者观察为核心产品。

## 用户控制与边界

- 反馈“有价值”不等于已验证；
- 机会不自动变成商业项目；
- Action 不会自动执行外部现实动作；
- 不自动发布、外联、付款、注册、投放广告、提交第三方表单或修改系统 Prompt；
- 平台验证码/登录限制会原样显示，不生成合成变化或合成机会。

## 8F 之后

8F 是当前预定义路线的最后一个阶段。接下来不自动创建 8G/8H，也不继续扩张基础设施。需要先观察：Research 是否带来新认知、Monitoring 是否减少主动搜索、Opportunity 是否帮助找到值得验证的方向、Validation 是否促成行动，以及 Outcome 是否让长期记忆越来越有用。

## 当前发布状态

8F Release Candidate `b75215d4279e6eb7a65b7024b3838bca63601593` 已通过完整门禁并部署。生产已完成备份 `/var/backups/mediaops/20260808T091409Z` 和 `0018_stage_8f` 迁移，API/Worker active，数据库 integrity=ok，活动 crawler/research/monitoring run 为 0。用户已在正常 Owner 浏览器完成 `/opportunities` 和 AI 工作台空状态检查。当前生产尚无 Opportunity/Signal 数据，因此本阶段业务状态为 `completed_with_data_limitation`，没有伪造 Opportunity、Validation、Action 或 Outcome；后续证据不足时保持 `no_opportunity_identified` 或 `needs_more_evidence`。
