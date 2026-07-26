# End-to-End Agent Workflow

## How to Request Work

用户负责描述产品目标、约束和验收结果。无需把需求拆成“前端任务”和“后端任务”；
Codex 会从真实代码和接口出发，识别需要完成的数据库、领域模型、后端服务、API、
Worker、前端、测试、文档和部署工作。

一个有效请求可以写成：

```text
目标：任务详情支持重新执行失败任务。
约束：仍只允许单 Worker，不复用旧输出目录。
验收：API、页面、测试和部署说明都完成。
```

尚未实现的能力不会用 Mock 数据或静默降级伪装完成。

## Repository Rules

根目录 `AGENTS.md` 是整个仓库的工程事实来源。开始修改前，Agent 必须：

1. 阅读相关代码、测试、文档和 Trellis 规则；
2. 以当前 OpenAPI、数据模型和实现确认契约；
3. 判断数据库迁移、Worker 和生产部署影响；
4. 给出简短实施计划；
5. 在本地完成与风险相称的验证。

Git 是代码唯一事实来源。生产中的临时修改必须回到仓库、通过验证并提交；不得直接
编辑生产源码或构建后的静态文件。

## Quality and Delivery

基础质量门：

```bash
cd backend
uv sync --frozen
uv run pytest

cd ../frontend
npm ci --include=dev
npm run lint
npm run test
npm run build
```

数据库结构变化必须有正式迁移和生产备份。当前项目尚无迁移工具，因此第一次结构
变化前必须先建立迁移基础设施。

完成报告必须说明实现内容、主要文件、数据库/后端/前端/Worker/部署影响、测试和
构建结果、遗留事项、提交哈希、push 状态、工作树状态、生产命令和回滚注意事项。

## Production Responsibility

仓库级 `$mediaops-server` Skill 和 `scripts/server/` 负责只读诊断、日志、备份及
受控部署。Agent 默认先定位证据，再执行最小修复。没有 root 权限时不会要求交互式
密码或绕过权限，而是提供管理员需要执行的精确命令并明确上线仍待完成。
