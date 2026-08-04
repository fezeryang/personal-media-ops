import { Activity, ArrowUpRight, Bot, Database, Gauge, Radar, Wrench } from "lucide-react";
import { Link } from "react-router";

import { PageHeader } from "../components/page-header";
import { Card, CardContent, CardHeader } from "../components/ui/card";

const tools = [
  { title: "采集任务", description: "查看单 Worker 运行中的采集任务、登录状态和真实错误。", to: "/tools/crawls", icon: Activity },
  { title: "平台能力", description: "检查平台 × mode 的独立能力事实，不把搜索能力外推到其他模式。", to: "/tools/capabilities", icon: Gauge },
  { title: "运行总览", description: "查看服务健康、活跃研究、采集队列、平台能力、模型健康和资源用量。", to: "/tools/overview", icon: Radar },
  { title: "旧版趋势工具", description: "仅保留历史查看与审计；趋势工具已停止作为核心产品继续开发。", to: "/tools/legacy-trends", icon: Database },
  { title: "旧版自动化工具", description: "仅保留订阅与创作者观察的历史审计；未来由统一监控模块替代。", to: "/tools/legacy-automation/subscriptions", icon: Wrench },
  { title: "Agent 与集成", description: "查看 Agent API、集成和外部调用配置。", to: "/settings/integrations", icon: Bot },
];

export function ToolsPage() {
  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Low-level operations"
        title="工具中心"
        description="这里承载采集、能力、系统和兼容工具。主工作流从 AI 研究、发现收件箱、研究空间和记忆证据开始。"
      />
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {tools.map((tool) => (
          <Link key={tool.to} to={tool.to} className="group">
            <Card className="h-full transition group-hover:-translate-y-0.5 group-hover:border-signal/30">
              <CardHeader><div className="flex items-center justify-between"><tool.icon className="size-5 text-signal" /><ArrowUpRight className="size-4 text-muted transition group-hover:text-signal" /></div><h2 className="mt-4 font-display text-xl font-semibold">{tool.title}</h2></CardHeader>
              <CardContent><p className="text-sm leading-6 text-muted">{tool.description}</p></CardContent>
            </Card>
          </Link>
        ))}
      </section>
    </div>
  );
}
