# 研究任务UX优化：查询轨迹展示与质量闸门改进

## Goal

优化研究任务页面的查询轨迹和执行轨迹展示，解决当前"步数过多窗口太长"、"空内容浪费空间"的展示问题，并改进质量闸门的用户体验，让探索性研究不被固定规则限制。

## What I already know

* 前端研究任务页面位于 `frontend/src/pages/research-tasks-page.tsx`
* 查询轨迹组件 `QueryTrajectoryCard` 展示所有查询，分为"已执行"和"已拒绝"两组
* 执行轨迹组件 `TraceCard` 用 `<details>` 折叠所有步骤，步数多时窗口过长
* 后端质量闸门使用固定规则判断泛化词（`backend/app/services/ai/research_quality.py`）
* 后端查询状态包括：`generated`, `rejected_generic`, `rejected_duplicate`, `rejected_low_relevance`, `rejected_low_value`, `approved_pending`, `executing`, `completed`
* 用户反馈："AI工具推荐"等探索性查询被拒绝，但用户正是因为不知道具体产品才来研究
* 当前实现基于 8C-1 质量基础和 8C-2 跨平台完成（`0013_cross_platform_research_completion`）

## Requirements

### 查询轨迹展示优化

* **分组折叠**：将"已执行"和"已拒绝"两组默认折叠，只显示计数和关键指标
* **优先级排序**：已执行查询按 `expected_value_score` 降序排列，重要查询优先显示
* **空内容过滤**：工具参数为空、原因为空、token为0的步骤标记为"空步骤"，默认隐藏
* **状态图标**：用颜色区分状态（completed=绿色、rejected=红色、pending=黄色），添加图标
* **关键信息突出**：查询文本、拒绝原因、结果计数用不同字体大小和颜色突出显示

### 执行轨迹展示优化

* **智能分组**：按步骤类型分组（Planning/Query/Tool/Evidence/Report），每组显示关键指标
* **默认折叠**：每组默认折叠，显示"X步 - 总耗时Y秒"，点击展开查看详情
* **空步骤隐藏**：`tool_arguments` 为空且 `reason` 为空的步骤默认隐藏
* **错误步骤突出**：状态为 `Failed` 的步骤用红色边框和图标突出显示
* **搜索过滤**：提供搜索框，可按事件名称/步骤名称/工具名称过滤

### 质量闸门UX改进

* **探索模式 vs 验证模式**：创建研究任务时让用户选择模式
  - **探索模式**：放宽限制，允许泛化词和探索性查询
  - **验证模式**：严格质量检查，避免浪费预算
* **智能建议**：当查询被拒绝时，提供"如何改写查询"的建议
  - 例如："AI工具推荐" → 被拒绝 → 建议："分析当前值得关注的AI工具类别和代表性产品"
* **拒绝原因可视化**：用颜色和图标区分拒绝原因（泛化词=黄色、重复=蓝色、低相关性=灰色）
* **实时预览**：创建任务时提供"查询质量预判"，实时显示查询可能的结果

### 前端契约保持

* 保持所有现有 API 契约不变
* 不修改 `frontend/src/api/research.ts` 的 schema 定义
* 新增功能通过可选参数和渐进增强实现
* 确保 390px 宽度下的响应式布局

## Acceptance Criteria

* [ ] 查询轨迹默认折叠，显示关键指标，点击展开查看详情
* [ ] 执行轨迹按类型分组，空步骤默认隐藏，错误步骤突出显示
* [ ] 用户可选择"探索模式"或"验证模式"，探索模式允许泛化词
* [ ] 被拒绝查询显示改写建议，用颜色区分拒绝原因
* [ ] 前端 lint/test/build 全部通过
* [ ] 响应式布局在 390px 宽度下正常显示
* [ ] 不影响现有研究任务的创建和执行

## Definition of Done

* 前端组件修改、测试用例、API 契约兼容性验证全部完成
* 前端 lint/test/build 通过，无 console 错误
* 在现有研究任务上验证新 UI 不影响功能
* 代码已提交，文档已更新

## Out of Scope

* 后端质量闸门的规则修改（这是独立任务，需要评估成本和架构）
* 数据库 schema 变更
* 后端 API 接口变更
* 自动执行用户动作
* Redis/Kafka/Elasticsearch 等新基础设施

## Technical Approach

### 前端组件重构
* 重构 `QueryTrajectoryCard`：添加折叠/分组/排序功能
* 重构 `TraceCard`：添加分组/搜索/空内容过滤
* 新建 `ResearchCreateForm` 扩展：添加模式选择和质量预览
* 新建 `QueryQualityIndicator` 组件：显示查询质量评分和建议

### 状态管理
* 使用 React `useState` 管理折叠状态
* 使用 `useMemo` 优化分组和排序计算
* 保持现有的 TanStack Query 数据获取逻辑

### 样式和动画
* 使用 Tailwind 4 实现响应式布局
* 添加 CSS transition 实现折叠动画
* 使用现有 Badge 组件的 variant 系统

## Decision (ADR-lite)

**Context**：当前查询轨迹和执行轨迹展示信息密度过高，用户难以快速找到关键信息；质量闸门的固定规则限制了探索性研究。

**Decision**：优先优化前端展示（折叠、分组、过滤），并通过"探索模式 vs 验证模式"的UX设计来缓解质量闸门的限制，暂不修改后端规则。

**Consequences**：用户体验立即改善，探索性研究可以通过选择"探索模式"绕过泛化词限制；后端质量闸门的架构问题留待后续任务解决。

## Technical Notes

* 相关前端 spec：`.trellis/spec/frontend/intelligence-workbench.md`
* 相关后端 spec：`.trellis/spec/backend/research-runtime-8c.md`
* 现有 UI 组件库：`frontend/src/components/ui/`
* 现有样式系统：Tailwind 4 + 自定义 theme
