import { ArrowUpRight, Bot, KeyRound, Sparkles } from "lucide-react";
import { Link } from "react-router";

import { PageHeader } from "../components/page-header";
import { Card, CardContent, CardHeader } from "../components/ui/card";

const settings = [
  { title: "AI 模型与路由", description: "管理 ModelGateway 路由、模型实例和预算可见性。", to: "/settings/models", icon: Sparkles },
  { title: "Agent 与集成", description: "查看稳定 Agent API v1 和外部集成入口。", to: "/settings/integrations", icon: Bot },
  { title: "安全会话", description: "当前工作台使用单所有者认证和同源请求保护。", to: "/settings/security", icon: KeyRound },
];

export function SettingsPage() {
  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Workspace configuration"
        title="设置"
        description="配置 AI 研究运行方式、Agent 集成和工作台安全边界。密钥不会在前端或页面中展示。"
      />
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {settings.map((item) => (
          <Link key={item.to} to={item.to} className="group">
            <Card className="h-full transition group-hover:-translate-y-0.5 group-hover:border-signal/30">
              <CardHeader><div className="flex items-center justify-between"><item.icon className="size-5 text-signal" /><ArrowUpRight className="size-4 text-muted transition group-hover:text-signal" /></div><h2 className="mt-4 font-display text-xl font-semibold">{item.title}</h2></CardHeader>
              <CardContent><p className="text-sm leading-6 text-muted">{item.description}</p></CardContent>
            </Card>
          </Link>
        ))}
      </section>
    </div>
  );
}
