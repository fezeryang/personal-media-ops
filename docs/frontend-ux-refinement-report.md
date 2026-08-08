# 前端产品体验收敛报告

日期：2026-08-08
基线：`b75215d4279e6eb7a65b7024b3838bca63601593` 以及其后的文档/Trellis记录提交
范围：现有 8D–8F 前端体验收敛；不新增产品阶段、业务模块、Runtime、Prompt、监控算法或机会算法。

## 当前状态

| 维度 | 状态 |
| --- | --- |
| implementation_status | passed |
| local_test_status | passed |
| local_visual_status | passed |
| release_candidate_status | in_progress |
| deployment_status | not_started |
| production_smoke_status | not_started |
| production_business_status | not_started |
| user_product_review_status | awaiting_owner_review |

## 1. 修改前主要 UX 问题

审计记录见 [`frontend-ux-audit.md`](frontend-ux-audit.md)。主要问题是：

- 页面首屏同时堆叠教学、摘要、创建表单、列表和详情，用户很难先找到下一步。
- 桌面侧栏固定 272px；移动端一级导航横向滚动，主操作依赖页面级横向空间。
- Research、Discovery、Space、Memory 的列表不能收起；长详情始终和列表争抢宽度。
- Discovery、Monitoring、Opportunity 缺少完整的业务筛选/排序；列表无法应对 20–50 条数据。
- 技术字段、内部状态、对象 ID、分数解释与用户判断混在一起。
- 反馈、验证、归档、取消、放弃等动作层级不清，危险状态变化缺少确认。
- 高级设置、运行轨迹、原始证据、预算和历史信息默认展开，纵向认知负担过高。

## 2. AppShell 变化

- 主导航仍只有 AI 研究、发现收件箱、研究空间、记忆与证据、监控任务、工具中心、设置。
- 桌面侧栏支持 272px 展开和 76px 收起；收起后保留 Logo、图标、active 状态、title/label 提示。
- 侧栏状态保存在 `localStorage`；读取或写入失败不会阻塞布局。
- 移动端改为当前页面 Top bar + 菜单按钮，不再显示全部一级导航胶囊。
- 导航使用 Radix Dialog 抽屉，支持焦点管理、Esc 关闭，点击链接后自动关闭。

## 3. Sidebar 变化

侧栏收起按钮使用 `aria-expanded` 和可访问名称“收起侧栏/展开侧栏”。内容区通过对应的
`padding-left` 同步移动，避免收起时页面溢出或跳动。

## 4. Mobile navigation 变化

移动抽屉展示七个正式工作区入口，机会、Action、通知不提升为一级导航。筛选器在手机上
收敛为搜索 + “筛选”按钮，条件在抽屉中选择，避免五个 select 横向挤压。

## 5. PageHeader 变化

`PageHeader` 现在默认只呈现标题、可选的一行说明和动作。历史阶段名、长产品哲学说明不再
出现在页面眉头；旧 `eyebrow` 参数保持兼容但不再渲染。移动端由紧凑布局承载必要动作。

## 6. Research 变化

- 首屏以“先说你想知道什么”的自然语言 composer 为主。
- “研究是如何工作的？”改为默认收起的说明区。
- Today/Focus 合并为“研究焦点”，只显示运行中、待确认、发现和机会中实际有内容的组。
- 研究创建的高级平台、预算和 coverage 字段默认收起。
- 研究任务列表增加搜索、业务状态分组和排序，并使用可收起的 Master/Detail 布局。
- 详情保持总览、过程、发现、证据、查询、预算、技术详情等 Tabs；查询与轨迹默认折叠。
- 暂停、继续、确认完成保留为上下文主动作；重新研究、取消等放入“更多”，取消使用确认框。
- 研究内容中的对象标识、采集任务标识和原始上下文移入技术详情。

## 7. Discovery 变化

- 增加搜索、状态、类型、平台、来源、重要度、推荐/最新/证据/独立来源排序。
- 筛选条件显示为可删除 chips，并在有条件时提供清除筛选。
- 列表卡只展示标题、摘要、类型、来源、推荐原因和重要程度；内容数、转载数、平台数与原始分数移入详情。
- 详情使用概览、证据、为什么推荐、相关对象、后续动作、技术详情 Tabs。
- 顶部只保留“继续研究”主动作；反馈统一进入“判断”菜单，并保留撤销最近反馈。

## 8. Monitoring 变化

- 监控列表增加搜索、状态、任务类型、频率、平台状态和排序。
- Mission 卡片收敛为标题、目标摘要、状态、频率、最近运行和是否有重要变化；预算与完整平台信息不放列表。
- “新建监控”改为 Dialog；自然语言目标在前，平台/频率/预算在高级设置中收起。
- 通知从长期占据概览的面板变为 header 图标/数量和 Drawer；详情仍可通过通知 Tab 访问。
- 详情使用概览、重要变化、运行记录、已知基线、监控范围、通知、资源、技术详情 Tabs。
- 单次运行默认显示摘要，查询、平台、新增数据、资源和失败原因通过“运行详情”展开。
- 归档移入“更多”并使用 AlertDialog 确认。

## 9. Opportunity 变化

- 列表增加搜索、类型、成熟度、状态和“最值得判断/最新更新/证据最强/可验证优先”排序。
- 卡片收敛为类型、成熟度、标题、机会说明、证据状态和建议下一步，不展示黑箱总分。
- 详情使用概览、证据、验证计划、相关研究、行动与结果、技术详情 Tabs。
- 顶部只保留一个创建/继续验证主动作；反馈统一进入“判断”菜单。
- 验证结果、行动编辑、行动结果均默认收起；拒绝机会、放弃行动使用 AlertDialog 确认。

## 10. Research Space 变化

- 空间列表增加搜索、active/archived 筛选、排序和可收起列表。
- 移除普通流程中的手工对象 ID 输入。
- “添加材料”改为 Picker Dialog，按搜索和类型从现有研究任务、发现、证据、结论、机会、Validation Plan、Action、Outcome、Memory 中选择。
- 选择项展示标题、类型、来源和更新时间；对象 ID 只在技术详情出现。
- 当前空间使用概览、研究、发现、机会、证据、行动 Tabs，各类型列表独立展示。
- 后端只增加 owner-scoped 的只读 lookup endpoint，没有重设计 Research Space 后端或新增数据库表。

## 11. Memory 变化

- 研究记录列表增加搜索、状态筛选和排序，并支持收起列表。
- 详情使用概览、结论、证据、未解决、记忆 Tabs。
- 概览只显示主题、结论/证据/未解决/记忆数量和继续入口。
- Evidence 增加标题/说明搜索、直接/反向/背景用途筛选、平台筛选。
- Memory 增加当前/历史/全部与事实/推测/变化类型筛选；完整来源标识进入技术详情。

## 12. Filter 体系

新增共享 `FilterBar`、`SearchInput`、`FilterChip`。桌面筛选器单行可换行，手机只保留搜索和
筛选入口；活动条件有 chip 和清除筛选。实际接入 Research、Discovery、Monitoring、Opportunity、
Research Space、Memory 以及 Memory 的 Evidence/Memory 子列表。

## 13. Collapse 体系

共享 `CollapsibleSection` 用于说明、advanced settings、验证/行动表单、运行详情和原始内容；
`MasterDetailLayout` 用于 Research、Discovery、Space、Memory，列表展开/收起状态按页面
保存在 `localStorage`。长查询、证据、历史运行、预算内部和技术字段不默认展开。

## 14. Button audit

审计清单按页面、可见标签、预期结果和分类维护在实现与测试中：

| 页面 | 代表性动作 | 分类 | 验证结果 |
| --- | --- | --- | --- |
| AppShell | 导航、退出、收起侧栏、移动菜单 | navigation / mutation / toggle / drawer | 真实导航、状态变化、localStorage 和抽屉行为已测 |
| Research | 创建、暂停、继续、确认、重新研究、取消 | mutation / menu / dialog | 真实 API mutation；取消有确认框 |
| Discovery | 继续研究、判断、反馈撤销、分析机会、加入空间 | mutation / menu | 菜单项、反馈参数和撤销已测 |
| Monitoring | 新建、立即运行、暂停/恢复、归档、通知 | dialog / mutation / menu | 归档确认、筛选、详情和运行展开已测 |
| Opportunity | 验证、判断、创建行动、批准/开始/完成、放弃 | mutation / menu / dialog | 拒绝和放弃确认；列表/详情测试已覆盖 |
| Space | 创建、选择空间、打开 picker、选择材料、加入 | mutation / selection / dialog | picker 使用现有列表结果，不暴露 ID 工作流 |
| Memory | 选择记录、Tabs、Evidence/Memory 筛选 | selection / toggle | Tab 和筛选行为已测 |

未发现产品级无 handler 的装饰性按钮。原先“所有动作同时平铺”的语义问题通过主动作、
更多菜单和折叠区收敛；不真实可用的能力没有伪造为 Enabled 按钮。

## 15. 被移除的伪按钮

本次没有发现需要保留的无 handler 按钮；被移除/降级的是开发者式“手工输入对象 ID”流程，
以及不应占据主层级的多组反馈、技术说明和表单入口。它们分别改为 Picker、Action Menu、
Collapsible Section 或技术详情。

## 16. 被补全的真实按钮

补全了侧栏收起/展开、移动端菜单、筛选面板、列表收起/显示、Tab 键盘切换、研究空间
材料选择、研究取消、监控归档、机会拒绝、行动放弃等动作的可访问名称、状态反馈和确认语义。

## 17. 技术字段降级

普通视图不再主动展示 UUID、对象 ID、内部 enum、raw query lifecycle、model/token budget、
version integer、scope distance、generation reason、crawler task id 等。它们只在技术详情、
运行详情、原始上下文或 API/Tools 边界出现。技术详情本身仍保留审计能力。

## 18. Mobile overflow 验证

`html/body` 增加横向裁剪保护，组件使用 `min-w-0`、换行、移动筛选 Drawer 和内部 Tab/代码/日志
viewport。`local-visual.sh` 对所有六个核心 UX fixture 在 1440×900、1280×720、1024×768、
390×844 执行 `document.documentElement.scrollWidth <= clientWidth` 检查；内部 Tab strip、
table、code/log viewer 仍可按规则独立滚动。

## 19. Desktop 截图

视觉证据目录为 `docs/evidence/`（ignored，不提交生产数据）。核心页面截图：

- `frontend-ux-research-1440x900.png`、`frontend-ux-research-1280x720.png`、`frontend-ux-research-1024x768.png`
- `frontend-ux-discovery-1440x900.png`、`frontend-ux-monitoring-1440x900.png`
- `frontend-ux-spaces-1440x900.png`、`frontend-ux-memory-1440x900.png`、`frontend-ux-opportunities-1440x900.png`
- Research/Discovery/Space/Memory 列表收起版 1440×900 截图

## 20. Mobile 截图

- 六个核心页面各有 `390x844` 截图。
- Research/Discovery/Space/Memory 另有列表收起版 `390x844` 截图。
- 手机筛选通过“筛选”按钮打开 Drawer，不依赖页面级横向滚动。

## 21. 测试

已执行的局部回归：

- 前端 Vitest：35 个测试文件、85 个测试通过。
- 前端 lint：通过。
- TypeScript/Vite build：通过。
- 后端 pytest：460 项通过。
- 本地视觉脚本：核心 fixture 在 1440×900、1280×720、1024×768、390×844 及收起状态通过。
- `npm ci --include=dev` 报告依赖审计中已有 3 项 vulnerability（1 moderate、2 high）；本次未升级依赖，也未用配置掩盖该提示。

新增/更新测试覆盖侧栏收起、移动抽屉、FilterBar/清除筛选、移动筛选面板、Tabs、Master/Detail
收起、研究空间 picker、真实反馈/取消/归档/拒绝/放弃动作、Mutation pending 语义和密集
20+条 fixture。

## 22. Release Commit

状态：`local_gate=passed; release_candidate=in_progress`。最终 Release Candidate 将记录完整 40 位
commit、local gate、视觉证据和任务外既有 dirty 文件排除情况。

## 23. Production Commit

状态：`pending deployment`。生产只能接收 push 后的 Release Candidate commit；不直接在生产
服务器编辑仓库或生成 CSS/JS。

## 24. Production Smoke

状态：`pending deployment`。部署后将验证生产 commit、服务、Nginx、`/api/health`、登录入口、
`/api/research/tasks`、每个验收研究任务的 detail/events；本任务没有创建真实 crawler login
任务，因此不虚构 QR 验证结果。

## 25. 尚需 Owner 真实体验判断的问题

- Owner 需要在 Windows Chrome 的生产前端确认：桌面侧栏收起/展开是否符合日常工作习惯。
- Owner 需要确认移动端从 Top bar 打开导航、筛选 Drawer 和列表收起后的返回路径是否自然。
- Owner 需要实际浏览 Research、Discovery、Monitoring、Space、Memory、Opportunity 六个页面，
  判断首屏是否能在 5 秒内回答“我在哪里、最重要看什么、下一步点哪里”。
- Owner review 是产品体验验收，不用 WSL 临时浏览器登录，不读取或导出浏览器 Cookie；在 Owner
  真实反馈前，不把工程门禁通过写成最终用户验收通过。

## Completion report

- 实现内容：信息架构、渐进披露、导航、筛选、动作语义、响应式布局、技术字段降级、研究空间 picker。
- 主要文件：`frontend/src/components/`、六个核心页面、`frontend/src/dev/local-ux-fixtures-page.tsx`、
  `backend/app/api/research.py`、`backend/app/repositories/discovery.py`、本报告和审计文档。
- 数据库：未改表、未新增 migration；picker 使用只读查询。
- Backend：有最小 owner-scoped lookup API 和对应 Pydantic/repository/test；没有改变 8D–8F 业务算法。
- Frontend：已修改。
- Worker：未受影响。
- Deployment：受影响；前后端需要随 RC 发布，生产 helper/部署流程不改变。
- 生产构建：本地 Vite production build 已通过；部署后补记 release helper 的生产构建结果。
- 剩余工作：RC/push、生产部署/冒烟、Owner 产品体验 review。
- 回滚 cautions：保留生产旧 commit；本次无 schema migration，不能用数据库恢复替代代码回滚；生产只用
  reviewed release helper，禁止手工改静态目录或服务配置。
