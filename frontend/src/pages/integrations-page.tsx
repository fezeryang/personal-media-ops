import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  Check,
  Copy,
  FileJson,
  KeyRound,
  Network,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { type FormEvent, useState } from "react";

import {
  createApiKey,
  listApiKeys,
  revokeApiKey,
  type CreatedApiKey,
} from "../api/auth";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { formatDateTime } from "../lib/utils";

const scopes = [
  ["library:read", "读取资料库"],
  ["intelligence:read", "读取趋势与简报"],
  ["tasks:read", "读取采集任务"],
  ["tasks:write", "创建和管理采集任务"],
  ["subscriptions:read", "读取订阅状态"],
  ["subscriptions:write", "创建和管理订阅"],
] as const;

export function IntegrationsPage() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>([
    "library:read",
    "intelligence:read",
  ]);
  const [createdKey, setCreatedKey] = useState<CreatedApiKey | null>(null);
  const [copied, setCopied] = useState(false);
  const keys = useQuery({
    queryKey: ["api-keys"],
    queryFn: ({ signal }) => listApiKeys(signal),
  });
  const create = useMutation({
    mutationFn: () =>
      createApiKey({ name: name.trim(), scopes: selectedScopes }),
    onSuccess: async (result) => {
      setCreatedKey(result);
      setCreating(false);
      setName("");
      setCopied(false);
      await queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });
  const revoke = useMutation({
    mutationFn: revokeApiKey,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    create.mutate();
  }

  async function copyKey() {
    if (!createdKey) return;
    await navigator.clipboard.writeText(createdKey.api_key);
    setCopied(true);
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Agent-ready interfaces"
        title="Agent 与集成"
        description="管理仅显示一次的 Scoped API Key，并查看稳定 REST API。MCP 与 Notion 当前未连接外部服务。"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" /> 创建 API Key
          </Button>
        }
      />

      {createdKey ? (
        <Card className="overflow-hidden border-warning/30 bg-[#fffaf2]">
          <CardHeader className="flex flex-row items-start justify-between border-b border-warning/15 pb-5">
            <div>
              <p className="section-kicker text-warning-strong">
                One-time secret
              </p>
              <h2 className="mt-1 font-display text-xl font-semibold">
                立即保存完整 API Key
              </h2>
              <p className="mt-2 text-sm text-muted">
                关闭后系统无法再次读取，只会保留哈希和前缀。
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              aria-label="关闭完整 API Key"
              onClick={() => setCreatedKey(null)}
            >
              <X className="size-4" />
            </Button>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-3 sm:flex-row">
              <code className="min-w-0 flex-1 overflow-x-auto rounded-xl border border-warning/20 bg-white px-4 py-3 font-mono text-sm">
                {createdKey.api_key}
              </code>
              <Button variant="secondary" onClick={() => void copyKey()}>
                {copied ? (
                  <Check className="size-4" />
                ) : (
                  <Copy className="size-4" />
                )}
                {copied ? "已复制" : "复制"}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {creating ? (
        <Card className="border-signal/25">
          <CardContent>
            <form onSubmit={submit} className="space-y-5">
              <div className="flex items-center justify-between">
                <h2 className="font-display text-xl font-semibold">
                  新 API Key
                </h2>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => setCreating(false)}
                >
                  <X className="size-4" />
                </Button>
              </div>
              <label className="block text-sm font-semibold">
                名称
                <Input
                  className="mt-2"
                  value={name}
                  onChange={(event) => setName(event.currentTarget.value)}
                  placeholder="例如：本地 Codex 只读"
                  required
                />
              </label>
              <fieldset>
                <legend className="text-sm font-semibold">Scope</legend>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {scopes.map(([scope, description]) => (
                    <label
                      key={scope}
                      className="flex items-start gap-3 rounded-xl border border-line bg-paper/60 p-3"
                    >
                      <input
                        className="mt-1"
                        type="checkbox"
                        checked={selectedScopes.includes(scope)}
                        onChange={(event) =>
                          setSelectedScopes(
                            event.currentTarget.checked
                              ? [...selectedScopes, scope]
                              : selectedScopes.filter(
                                  (item) => item !== scope,
                                ),
                          )
                        }
                      />
                      <span>
                        <code className="text-xs font-semibold">{scope}</code>
                        <span className="mt-1 block text-xs text-muted">
                          {description}
                        </span>
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>
              {create.isError ? <ErrorState error={create.error} /> : null}
              <div className="flex justify-end">
                <Button
                  disabled={
                    create.isPending ||
                    !name.trim() ||
                    !selectedScopes.length
                  }
                >
                  生成一次性 Key
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <p className="section-kicker">Credentials</p>
                <h2 className="mt-1 font-display text-xl font-semibold">
                  API Key
                </h2>
              </div>
              <KeyRound className="size-5 text-signal" />
            </div>
          </CardHeader>
          <CardContent className="space-y-3 pt-4">
            {(keys.data ?? []).map((key) => (
              <div
                key={key.id}
                className="rounded-xl border border-line bg-paper/50 p-4"
              >
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold">{key.name}</p>
                      <Badge variant={key.revoked_at ? "neutral" : "success"}>
                        {key.revoked_at ? "已撤销" : "可用"}
                      </Badge>
                    </div>
                    <code className="mt-2 block text-xs text-muted">
                      {key.prefix}…
                    </code>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {key.scopes.map((scope) => (
                        <Badge key={scope} variant="info">
                          {scope}
                        </Badge>
                      ))}
                    </div>
                    <p className="mt-3 text-[11px] text-muted">
                      创建 {formatDateTime(key.created_at)} · 最近使用{" "}
                      {key.last_used_at
                        ? formatDateTime(key.last_used_at)
                        : "从未"}
                    </p>
                  </div>
                  {!key.revoked_at ? (
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`撤销 ${key.name}`}
                      onClick={() => revoke.mutate(key.id)}
                    >
                      <Trash2 className="size-4 text-danger" />
                    </Button>
                  ) : null}
                </div>
              </div>
            ))}
            {!keys.data?.length ? (
              <p className="py-10 text-center text-sm text-muted">
                尚未创建 API Key。
              </p>
            ) : null}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardContent className="flex items-start gap-4">
              <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-[#e7f5f1] text-signal-strong">
                <FileJson className="size-5" />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold">REST API v1</h2>
                  <Badge variant="success">可用</Badge>
                </div>
                <p className="mt-2 text-sm leading-6 text-muted">
                  稳定 DTO、统一分页、来源溯源与 Scope 已启用。
                </p>
                <a
                  className="mt-3 inline-flex text-xs font-bold text-signal-strong"
                  href="/docs"
                  target="_blank"
                  rel="noreferrer"
                >
                  打开 OpenAPI 文档 →
                </a>
              </div>
            </CardContent>
          </Card>
          {[
            {
              title: "MCP Server",
              text: "后续可映射只读工具；写操作需要单独 Scope 与确认。",
              icon: Network,
            },
            {
              title: "Notion",
              text: "当前没有 OAuth 或外部同步。",
              icon: Bot,
            },
          ].map((item) => (
            <Card key={item.title}>
              <CardContent className="flex items-start gap-4">
                <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-paper text-muted">
                  <item.icon className="size-5" />
                </span>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="font-semibold">{item.title}</h2>
                    <Badge>规划中</Badge>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    {item.text}
                  </p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
