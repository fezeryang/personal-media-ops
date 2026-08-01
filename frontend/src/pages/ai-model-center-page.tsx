import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Boxes,
  Cable,
  CheckCircle2,
  CircleDollarSign,
  FlaskConical,
  Gauge,
  KeyRound,
  Pencil,
  Plus,
  Power,
  RefreshCw,
  Route,
  ServerCog,
  ShieldCheck,
  Trash2,
  XCircle,
} from "lucide-react";
import {
  type FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  type AiModel,
  type AiProvider,
  type DebugInput,
  type GatewayResponse,
  type ModelCandidate,
  type ModelInput,
  type ProviderInput,
  type ProviderCheckKind,
  type ProviderTemplate,
  type RouteRole,
  createAiProvider,
  createModel,
  debugModel,
  deleteAiProvider,
  deleteModel,
  getAiHealth,
  getUsage,
  listAiModels,
  listAiProviders,
  listProviderTemplates,
  listRoutes,
  refreshProviderModels,
  routeRoles,
  streamDebugModel,
  testAiProvider,
  updateAiProvider,
  updateModel,
  updateRoutes,
} from "../api/ai";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "../components/ui/dialog";
import { Input } from "../components/ui/input";

type Tab = "providers" | "models" | "routes" | "usage" | "debug";
const tabs: { id: Tab; label: string; icon: typeof Cable }[] = [
  { id: "providers", label: "服务商", icon: Cable },
  { id: "models", label: "模型", icon: Boxes },
  { id: "routes", label: "路由", icon: Route },
  { id: "usage", label: "用量", icon: Gauge },
  { id: "debug", label: "调试测试", icon: FlaskConical },
];
const roleLabels: Record<RouteRole, string> = {
  default: "默认模型",
  fast: "快速模型",
  deep: "深度模型",
  tool_calling: "工具调用模型",
  final_report: "最终报告模型",
  fallback: "备用模型",
};
const capabilityLabels: Record<string, string> = {
  supports_streaming: "流式",
  supports_tools: "工具",
  supports_thinking: "思考",
  supports_vision: "视觉",
  supports_files: "文件",
  supports_structured_output: "结构化输出",
};

function healthVariant(status: string | null) {
  if (status === "healthy") return "success" as const;
  if (status === "degraded" || status === "rate_limited") return "warning" as const;
  if (status) return "danger" as const;
  return "neutral" as const;
}

function healthLabel(status: string | null) {
  return (
    {
      healthy: "健康",
      degraded: "降级",
      unreachable: "不可达",
      authentication_failed: "认证失败",
      model_not_found: "模型不存在",
      rate_limited: "限流",
      protocol_error: "协议错误",
      disabled: "已停用",
    }[status ?? ""] ?? "未检查"
  );
}

interface ProviderDraft extends ProviderInput {
  id?: string;
  template_id: ProviderTemplate["id"];
}

function emptyProviderDraft(templates: ProviderTemplate[]): ProviderDraft {
  const template = templates[0];
  return {
    template_id: template?.id ?? "custom_openai",
    name: "",
    provider_type: template?.id ?? "custom_openai",
    protocol: template?.protocol ?? "openai_compatible",
    base_url: template?.base_url ?? "",
    enabled: false,
    timeout_seconds: 60,
    max_retries: 1,
    concurrency_limit: 1,
    api_key: "",
  };
}

function providerDraft(provider: AiProvider): ProviderDraft {
  return {
    id: provider.id,
    template_id: provider.provider_type,
    name: provider.name,
    provider_type: provider.provider_type,
    protocol: provider.protocol,
    base_url: provider.base_url,
    enabled: provider.enabled,
    timeout_seconds: provider.timeout_seconds,
    max_retries: provider.max_retries,
    concurrency_limit: provider.concurrency_limit,
    api_key: "",
  };
}

interface ModelDraft {
  id?: string;
  provider_id: string;
  model_id: string;
  display_name: string;
  enabled: boolean;
  context_window: string;
  max_output_tokens: string;
  supports_streaming: "unknown" | "yes" | "no";
  supports_tools: "unknown" | "yes" | "no";
  supports_thinking: "unknown" | "yes" | "no";
  supports_vision: "unknown" | "yes" | "no";
  supports_files: "unknown" | "yes" | "no";
  supports_structured_output: "unknown" | "yes" | "no";
  input_price_per_million: string;
  output_price_per_million: string;
  cached_input_price_per_million: string;
  price_currency: string;
  price_effective_at: string;
  capabilities_source: ModelInput["capabilities_source"];
}

function triState(value: boolean | null): "unknown" | "yes" | "no" {
  return value === null ? "unknown" : value ? "yes" : "no";
}

function emptyModelDraft(providerId = ""): ModelDraft {
  return {
    provider_id: providerId,
    model_id: "",
    display_name: "",
    enabled: false,
    context_window: "",
    max_output_tokens: "",
    supports_streaming: "unknown",
    supports_tools: "unknown",
    supports_thinking: "unknown",
    supports_vision: "unknown",
    supports_files: "unknown",
    supports_structured_output: "unknown",
    input_price_per_million: "",
    output_price_per_million: "",
    cached_input_price_per_million: "",
    price_currency: "",
    price_effective_at: "",
    capabilities_source: "user",
  };
}

function candidateDraft(candidate: ModelCandidate, providerId: string): ModelDraft {
  return {
    ...emptyModelDraft(providerId),
    model_id: candidate.model_id,
    display_name: candidate.display_name ?? candidate.model_id,
    supports_streaming: triState(candidate.capabilities.supports_streaming),
    supports_tools: triState(candidate.capabilities.supports_tools),
    supports_thinking: triState(candidate.capabilities.supports_thinking),
    supports_vision: triState(candidate.capabilities.supports_vision),
    supports_files: triState(candidate.capabilities.supports_files),
    supports_structured_output: triState(
      candidate.capabilities.supports_structured_output,
    ),
    capabilities_source: "provider",
  };
}

function editModelDraft(model: AiModel): ModelDraft {
  return {
    id: model.id,
    provider_id: model.provider_id,
    model_id: model.model_id,
    display_name: model.display_name,
    enabled: model.enabled,
    context_window: model.context_window?.toString() ?? "",
    max_output_tokens: model.max_output_tokens?.toString() ?? "",
    supports_streaming: triState(model.supports_streaming),
    supports_tools: triState(model.supports_tools),
    supports_thinking: triState(model.supports_thinking),
    supports_vision: triState(model.supports_vision),
    supports_files: triState(model.supports_files),
    supports_structured_output: triState(model.supports_structured_output),
    input_price_per_million: model.input_price_per_million ?? "",
    output_price_per_million: model.output_price_per_million ?? "",
    cached_input_price_per_million: model.cached_input_price_per_million ?? "",
    price_currency: model.price_currency ?? "",
    price_effective_at: model.price_effective_at?.slice(0, 16) ?? "",
    capabilities_source: model.capabilities_source,
  };
}

function decodedTriState(value: "unknown" | "yes" | "no") {
  return value === "unknown" ? null : value === "yes";
}

function modelInput(draft: ModelDraft): ModelInput {
  const priced = Boolean(
    draft.input_price_per_million ||
      draft.output_price_per_million ||
      draft.cached_input_price_per_million,
  );
  return {
    provider_id: draft.provider_id,
    model_id: draft.model_id.trim(),
    display_name: draft.display_name.trim(),
    enabled: draft.enabled,
    context_window: draft.context_window ? Number(draft.context_window) : null,
    max_output_tokens: draft.max_output_tokens
      ? Number(draft.max_output_tokens)
      : null,
    supports_streaming: decodedTriState(draft.supports_streaming),
    supports_tools: decodedTriState(draft.supports_tools),
    supports_thinking: decodedTriState(draft.supports_thinking),
    supports_vision: decodedTriState(draft.supports_vision),
    supports_files: decodedTriState(draft.supports_files),
    supports_structured_output: decodedTriState(
      draft.supports_structured_output,
    ),
    capabilities_source: draft.capabilities_source,
    input_price_per_million: draft.input_price_per_million || null,
    output_price_per_million: draft.output_price_per_million || null,
    cached_input_price_per_million:
      draft.cached_input_price_per_million || null,
    price_currency: priced ? draft.price_currency.trim().toUpperCase() : null,
    price_effective_at: priced
      ? new Date(draft.price_effective_at).toISOString()
      : null,
  };
}

function editableModelInput(
  input: ModelInput,
): Omit<ModelInput, "provider_id" | "model_id"> {
  return {
    display_name: input.display_name,
    enabled: input.enabled,
    context_window: input.context_window,
    max_output_tokens: input.max_output_tokens,
    supports_streaming: input.supports_streaming,
    supports_tools: input.supports_tools,
    supports_thinking: input.supports_thinking,
    supports_vision: input.supports_vision,
    supports_files: input.supports_files,
    supports_structured_output: input.supports_structured_output,
    capabilities_source: input.capabilities_source,
    input_price_per_million: input.input_price_per_million,
    output_price_per_million: input.output_price_per_million,
    cached_input_price_per_million: input.cached_input_price_per_million,
    price_currency: input.price_currency,
    price_effective_at: input.price_effective_at,
  };
}

export function AiModelCenterPage() {
  const client = useQueryClient();
  const [tab, setTab] = useState<Tab>("providers");
  const [providerEditor, setProviderEditor] = useState<ProviderDraft | null>(null);
  const [modelEditor, setModelEditor] = useState<ModelDraft | null>(null);
  const [candidateProviderId, setCandidateProviderId] = useState("");
  const [candidates, setCandidates] = useState<ModelCandidate[]>([]);
  const [notice, setNotice] = useState<string | null>(null);

  const providers = useQuery({ queryKey: ["ai", "providers"], queryFn: ({ signal }) => listAiProviders(signal) });
  const templates = useQuery({ queryKey: ["ai", "templates"], queryFn: ({ signal }) => listProviderTemplates(signal) });
  const models = useQuery({ queryKey: ["ai", "models"], queryFn: ({ signal }) => listAiModels(signal) });
  const routes = useQuery({ queryKey: ["ai", "routes"], queryFn: ({ signal }) => listRoutes(signal) });
  const usage = useQuery({ queryKey: ["ai", "usage"], queryFn: ({ signal }) => getUsage(signal), enabled: tab === "usage" });
  const health = useQuery({ queryKey: ["ai", "health"], queryFn: ({ signal }) => getAiHealth(signal), enabled: tab === "providers" });

  const selectedCandidateProviderId =
    candidateProviderId || providers.data?.[0]?.id || "";

  const invalidateConfiguration = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["ai", "providers"] }),
      client.invalidateQueries({ queryKey: ["ai", "models"] }),
      client.invalidateQueries({ queryKey: ["ai", "routes"] }),
      client.invalidateQueries({ queryKey: ["ai", "health"] }),
      client.invalidateQueries({ queryKey: ["ai", "usage"] }),
    ]);
  };
  const providerSave = useMutation({
    mutationFn: async (draft: ProviderDraft) => {
      const input: ProviderInput = {
        name: draft.name.trim(),
        provider_type: draft.provider_type,
        protocol: draft.protocol,
        base_url: draft.base_url.trim(),
        enabled: draft.enabled,
        timeout_seconds: Number(draft.timeout_seconds),
        max_retries: Number(draft.max_retries),
        concurrency_limit: Number(draft.concurrency_limit),
        ...(draft.api_key ? { api_key: draft.api_key } : {}),
      };
      return draft.id ? updateAiProvider(draft.id, input) : createAiProvider(input);
    },
    onSuccess: async () => {
      setProviderEditor(null);
      setNotice("服务商配置已保存");
      await invalidateConfiguration();
    },
  });
  const modelSave = useMutation({
    mutationFn: async (draft: ModelDraft) => {
      const input = modelInput(draft);
      if (draft.id) {
        return updateModel(draft.id, editableModelInput(input));
      }
      return createModel(input);
    },
    onSuccess: async () => {
      setModelEditor(null);
      setNotice("模型配置已保存；新候选默认保持停用");
      await invalidateConfiguration();
    },
  });

  const queryError = providers.error ?? templates.error ?? models.error ?? routes.error;

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="AI Runtime · Phase 8A"
        title="AI 模型中心"
        description="集中管理兼容服务商、模型能力、角色路由和真实调用审计。业务功能只通过统一 Model Gateway 使用模型。"
        action={
          <div className="flex items-center gap-2 rounded-xl border border-success/20 bg-success/8 px-3 py-2 text-xs font-semibold text-success">
            <ShieldCheck className="size-4" /> Secret 仅服务端解密
          </div>
        }
      />

      <div className="flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="模型中心分区">
        {tabs.map((item) => (
          <Button
            key={item.id}
            role="tab"
            aria-selected={tab === item.id}
            variant={tab === item.id ? "primary" : "secondary"}
            className="shrink-0"
            onClick={() => setTab(item.id)}
          >
            <item.icon className="size-4" /> {item.label}
          </Button>
        ))}
      </div>

      {notice ? (
        <div className="flex items-center justify-between rounded-xl border border-success/20 bg-success/8 px-4 py-3 text-sm text-success" role="status">
          <span className="flex items-center gap-2"><CheckCircle2 className="size-4" /> {notice}</span>
          <button aria-label="关闭提示" onClick={() => setNotice(null)}><XCircle className="size-4" /></button>
        </div>
      ) : null}
      {queryError ? <ErrorState error={queryError} onRetry={() => void invalidateConfiguration()} /> : null}

      {tab === "providers" ? (
        <ProvidersPanel
          providers={providers.data ?? []}
          models={models.data ?? []}
          healthRecords={health.data ?? []}
          pending={providers.isPending || models.isPending}
          onAdd={() => setProviderEditor(emptyProviderDraft(templates.data ?? []))}
          onEdit={(provider) => setProviderEditor(providerDraft(provider))}
          onChanged={invalidateConfiguration}
          onNotice={setNotice}
        />
      ) : null}
      {tab === "models" ? (
        <ModelsPanel
          providers={providers.data ?? []}
          models={models.data ?? []}
          candidates={candidates}
          candidateProviderId={selectedCandidateProviderId}
          onCandidateProviderChange={(id) => { setCandidateProviderId(id); setCandidates([]); }}
          onCandidates={setCandidates}
          onAdd={() => setModelEditor(emptyModelDraft(selectedCandidateProviderId))}
          onEdit={(model) => setModelEditor(editModelDraft(model))}
          onImport={(candidate) =>
            setModelEditor(candidateDraft(candidate, selectedCandidateProviderId))
          }
          onChanged={invalidateConfiguration}
          onNotice={setNotice}
        />
      ) : null}
      {tab === "routes" ? (
        <RoutesPanel
          key={(routes.data ?? []).map((route) => `${route.role}:${route.model_record_id ?? ""}`).join("|")}
          routes={routes.data ?? []}
          models={models.data ?? []}
          onChanged={invalidateConfiguration}
          onNotice={setNotice}
        />
      ) : null}
      {tab === "usage" ? <UsagePanel usage={usage.data} pending={usage.isPending} error={usage.error} /> : null}
      {tab === "debug" ? <DebugPanel models={models.data ?? []} /> : null}

      <ProviderDialog
        draft={providerEditor}
        templates={templates.data ?? []}
        pending={providerSave.isPending}
        error={providerSave.error}
        onChange={setProviderEditor}
        onClose={() => setProviderEditor(null)}
        onSave={(draft) => providerSave.mutate(draft)}
      />
      <ModelDialog
        draft={modelEditor}
        providers={providers.data ?? []}
        pending={modelSave.isPending}
        error={modelSave.error}
        onChange={setModelEditor}
        onClose={() => setModelEditor(null)}
        onSave={(draft) => modelSave.mutate(draft)}
      />
    </div>
  );
}

function ProvidersPanel({
  providers,
  models,
  healthRecords,
  pending,
  onAdd,
  onEdit,
  onChanged,
  onNotice,
}: {
  providers: AiProvider[];
  models: AiModel[];
  healthRecords: Awaited<ReturnType<typeof getAiHealth>>;
  pending: boolean;
  onAdd: () => void;
  onEdit: (provider: AiProvider) => void;
  onChanged: () => Promise<void>;
  onNotice: (message: string) => void;
}) {
  const [actionError, setActionError] = useState<unknown>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [checkKinds, setCheckKinds] = useState<
    Partial<Record<string, ProviderCheckKind>>
  >({});
  async function runTest(provider: AiProvider) {
    const model = models.find((item) => item.provider_id === provider.id && item.enabled);
    if (!model) { setActionError(new Error("请先为该服务商添加并启用一个模型")); return; }
    setTesting(provider.id); setActionError(null);
    try {
      const checkKind = checkKinds[provider.id] ?? "text";
      const checkLabel = {
        text: "文本",
        streaming: "流式",
        tools: "工具调用",
        thinking: "思考模式",
      }[checkKind];
      const result = await testAiProvider(provider.id, {
        model_record_id: model.id,
        check_kind: checkKind,
      });
      onNotice(result.status === "healthy" ? `${checkLabel}检查通过 · ${result.latency_ms ?? "—"} ms` : `${checkLabel}检查结果：${healthLabel(result.status)}`);
      await onChanged();
    } catch (error) { setActionError(error); } finally { setTesting(null); }
  }
  async function toggle(provider: AiProvider) {
    setActionError(null);
    try {
      await updateAiProvider(provider.id, {
        name: provider.name, provider_type: provider.provider_type, protocol: provider.protocol,
        base_url: provider.base_url, enabled: !provider.enabled,
        timeout_seconds: provider.timeout_seconds, max_retries: provider.max_retries,
        concurrency_limit: provider.concurrency_limit,
      });
      await onChanged();
    } catch (error) { setActionError(error); }
  }
  async function remove(provider: AiProvider) {
    if (!window.confirm(`确认删除服务商“${provider.name}”？存在路由或调用历史时服务器会拒绝。`)) return;
    try { await deleteAiProvider(provider.id); await onChanged(); } catch (error) { setActionError(error); }
  }
  return (
    <section className="space-y-5" aria-label="服务商">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div><p className="section-kicker">Provider registry</p><h2 className="mt-1 text-xl font-semibold">服务商与凭证</h2></div>
        <Button onClick={onAdd}><Plus className="size-4" /> 添加服务商</Button>
      </div>
      {actionError ? <ErrorState error={actionError} title="服务商操作失败" /> : null}
      {pending ? <p className="text-sm text-muted">正在加载服务商…</p> : null}
      {!pending && providers.length === 0 ? (
        <Card><CardContent className="py-12 text-center"><ServerCog className="mx-auto size-8 text-muted/50" /><p className="mt-3 font-semibold">还没有服务商</p><p className="mt-1 text-sm text-muted">可以先创建未配置凭证的服务商，稍后在网页内安全填写 API Key。</p></CardContent></Card>
      ) : null}
      <div className="grid gap-4 xl:grid-cols-2">
        {providers.map((provider) => {
          const last = healthRecords.find((item) => item.provider_id === provider.id);
          return (
            <Card key={provider.id} className="overflow-hidden">
              <CardHeader className="border-b border-line pb-4">
                <div className="flex items-start justify-between gap-3">
                  <div><div className="flex flex-wrap items-center gap-2"><h3 className="font-display text-lg font-semibold">{provider.name}</h3><Badge variant={provider.enabled ? "success" : "neutral"}>{provider.enabled ? "启用" : "停用"}</Badge></div><p className="mt-1 break-all font-mono text-xs text-muted">{provider.base_url}</p></div>
                  <Badge variant={healthVariant(provider.last_health_status)}>{healthLabel(provider.last_health_status)}</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                  <Metric label="协议" value={provider.protocol === "openai_compatible" ? "OpenAI" : "Anthropic"} />
                  <Metric label="凭证" value={provider.credentials_configured ? "凭证已配置" : "未配置"} icon={provider.credentials_configured ? KeyRound : undefined} />
                  <Metric label="模型" value={`${provider.model_count} 个`} />
                  <Metric label="最近延迟" value={provider.last_health_latency_ms === null ? "—" : `${provider.last_health_latency_ms} ms`} />
                </div>
                {last?.error_summary ? <p className="rounded-lg bg-danger/5 px-3 py-2 text-xs text-danger">{last.error_summary}</p> : null}
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="secondary" aria-label={`编辑 ${provider.name}`} onClick={() => onEdit(provider)}><Pencil className="size-3.5" /> 编辑</Button>
                  <select
                    className="form-select h-8 w-auto min-w-28 py-0"
                    aria-label={`测试能力 ${provider.name}`}
                    value={checkKinds[provider.id] ?? "text"}
                    onChange={(event) =>
                      setCheckKinds({
                        ...checkKinds,
                        [provider.id]: event.currentTarget
                          .value as ProviderCheckKind,
                      })
                    }
                  >
                    <option value="text">基础文本</option>
                    <option value="streaming">流式输出</option>
                    <option value="tools">工具调用</option>
                    <option value="thinking">思考模式</option>
                  </select>
                  <Button size="sm" variant="secondary" aria-label={`测试 ${provider.name}`} disabled={testing === provider.id || !provider.enabled || !provider.credentials_configured} onClick={() => void runTest(provider)}><Activity className="size-3.5" /> {testing === provider.id ? "测试中…" : "测试"}</Button>
                  <Button size="sm" variant="ghost" onClick={() => void toggle(provider)}><Power className="size-3.5" /> {provider.enabled ? "停用" : "启用"}</Button>
                  <Button size="sm" variant="danger" onClick={() => void remove(provider)}><Trash2 className="size-3.5" /> 删除</Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </section>
  );
}

function ModelsPanel({ providers, models, candidates, candidateProviderId, onCandidateProviderChange, onCandidates, onAdd, onEdit, onImport, onChanged, onNotice }: {
  providers: AiProvider[]; models: AiModel[]; candidates: ModelCandidate[]; candidateProviderId: string;
  onCandidateProviderChange: (id: string) => void; onCandidates: (items: ModelCandidate[]) => void;
  onAdd: () => void; onEdit: (model: AiModel) => void; onImport: (candidate: ModelCandidate) => void;
  onChanged: () => Promise<void>; onNotice: (message: string) => void;
}) {
  const [loading, setLoading] = useState(false); const [error, setError] = useState<unknown>(null);
  async function refresh() { if (!candidateProviderId) return; setLoading(true); setError(null); try { const result = await refreshProviderModels(candidateProviderId); onCandidates(result.filter((candidate) => !models.some((model) => model.provider_id === candidateProviderId && model.model_id === candidate.model_id))); onNotice("候选模型已拉取，尚未自动启用任何模型"); } catch (value) { setError(value); } finally { setLoading(false); } }
  async function remove(model: AiModel) { if (!window.confirm(`确认删除模型“${model.display_name}”？存在路由或调用历史时服务器会拒绝。`)) return; try { await deleteModel(model.id); await onChanged(); } catch (value) { setError(value); } }
  return (
    <section className="space-y-5" aria-label="模型">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div><p className="section-kicker">Model catalog</p><h2 className="mt-1 text-xl font-semibold">模型与能力</h2><p className="mt-1 text-sm text-muted">兼容协议不代表能力一致；未知、服务商声明和实测结果保持可区分。</p></div>
        <div className="flex flex-col gap-2 sm:flex-row"><select className="form-select min-w-52" aria-label="候选服务商" value={candidateProviderId} onChange={(event) => onCandidateProviderChange(event.currentTarget.value)}><option value="">选择服务商</option>{providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name}</option>)}</select><Button variant="secondary" disabled={!candidateProviderId || loading} onClick={() => void refresh()}><RefreshCw className="size-4" /> {loading ? "正在拉取…" : "拉取候选模型"}</Button><Button onClick={onAdd}><Plus className="size-4" /> 手动添加</Button></div>
      </div>
      {error ? <ErrorState error={error} title="模型操作失败" /> : null}
      {candidates.length > 0 ? <Card className="border-signal/25"><CardHeader><p className="section-kicker">Provider candidates</p><h3 className="mt-1 font-semibold">待确认候选</h3></CardHeader><CardContent className="grid gap-2 sm:grid-cols-2">{candidates.map((candidate) => <div key={candidate.model_id} className="flex items-center justify-between gap-3 rounded-xl border border-line bg-paper p-3"><div className="min-w-0"><p className="truncate font-mono text-sm font-semibold">{candidate.model_id}</p><p className="text-xs text-muted">导入后默认停用</p></div><Button size="sm" variant="secondary" aria-label={`加入候选模型 ${candidate.model_id}`} onClick={() => onImport(candidate)}><Plus className="size-3.5" /> 加入</Button></div>)}</CardContent></Card> : null}
      {models.length === 0 ? <Card><CardContent className="py-12 text-center"><Boxes className="mx-auto size-8 text-muted/50" /><p className="mt-3 font-semibold">还没有模型</p><p className="mt-1 text-sm text-muted">拉取候选或手动添加；模型不会被自动启用。</p></CardContent></Card> : null}
      <div className="grid gap-4 xl:grid-cols-2">{models.map((model) => <Card key={model.id}><CardHeader className="flex flex-row items-start justify-between gap-3"><div><p className="text-xs font-semibold text-muted">{model.provider_name}</p><h3 className="mt-1 font-display text-lg font-semibold">{model.display_name}</h3><p className="mt-1 break-all font-mono text-xs text-muted">{model.model_id}</p></div><div className="flex gap-2"><Badge variant={healthVariant(model.last_health_status)}>{healthLabel(model.last_health_status)}</Badge><Badge variant={model.enabled ? "success" : "neutral"}>{model.enabled ? "启用" : "停用"}</Badge></div></CardHeader><CardContent className="space-y-4"><div className="flex flex-wrap gap-2">{Object.entries(capabilityLabels).map(([field, label]) => { const value = model[field as keyof AiModel]; return <Badge key={field} variant={value === true ? "info" : value === false ? "neutral" : "warning"}>{label} · {value === true ? "是" : value === false ? "否" : "未知"}</Badge>; })}</div><div className="grid grid-cols-2 gap-3 text-sm"><Metric label="上下文" value={model.context_window?.toLocaleString() ?? "未配置"} /><Metric label="输出上限" value={model.max_output_tokens?.toLocaleString() ?? "未配置"} /><Metric label="能力来源" value={model.capabilities_source} /><Metric label="价格" value={model.input_price_per_million === null && model.output_price_per_million === null ? "未配置" : model.price_currency ?? "已配置"} /></div><div className="flex gap-2"><Button size="sm" variant="secondary" aria-label={`编辑模型 ${model.display_name}`} onClick={() => onEdit(model)}><Pencil className="size-3.5" /> 编辑能力</Button><Button size="sm" variant="danger" onClick={() => void remove(model)}><Trash2 className="size-3.5" /> 删除</Button></div></CardContent></Card>)}</div>
    </section>
  );
}

function RoutesPanel({ routes, models, onChanged, onNotice }: { routes: Awaited<ReturnType<typeof listRoutes>>; models: AiModel[]; onChanged: () => Promise<void>; onNotice: (message: string) => void }) {
  const initial = useMemo(() => Object.fromEntries(routeRoles.map((role) => [role, routes.find((item) => item.role === role)?.model_record_id ?? ""])) as Record<RouteRole, string>, [routes]);
  const [draft, setDraft] = useState(initial); const [error, setError] = useState<unknown>(null); const [saving, setSaving] = useState(false);
  const enabled = models.filter((model) => model.enabled && model.provider_enabled);
  async function save() { setSaving(true); setError(null); try { await updateRoutes(Object.fromEntries(routeRoles.map((role) => [role, draft[role] || null]))); onNotice("模型路由已保存；只影响此后创建的新 AI 任务"); await onChanged(); } catch (value) { setError(value); } finally { setSaving(false); } }
  return <section className="space-y-5" aria-label="路由"><div><p className="section-kicker">Route snapshot</p><h2 className="mt-1 text-xl font-semibold">模型角色路由</h2><p className="mt-1 max-w-2xl text-sm text-muted">正在运行的任务保留启动时快照。备用模型仅在有限重试失败后使用，流式输出开始后不透明续写。</p></div>{error ? <ErrorState error={error} title="路由保存失败" /> : null}<Card><CardContent className="grid gap-5 pt-6 md:grid-cols-2">{routeRoles.map((role) => <label key={role} className="text-sm font-semibold">{roleLabels[role]}<select className="form-select mt-2" aria-label={roleLabels[role]} value={draft[role] ?? ""} onChange={(event) => setDraft({ ...draft, [role]: event.currentTarget.value })}><option value="">未配置</option>{enabled.map((model) => <option key={model.id} value={model.id}>{model.provider_name} · {model.display_name}</option>)}</select><span className="mt-1 block text-xs font-normal text-muted">{role === "fallback" ? "失败后备用，不用于流式中途续写" : "新任务启动时固化此选择"}</span></label>)}</CardContent></Card><Button disabled={saving} onClick={() => void save()}>{saving ? "正在保存…" : "保存路由"}</Button></section>;
}

function UsagePanel({ usage, pending, error }: { usage: Awaited<ReturnType<typeof getUsage>> | undefined; pending: boolean; error: unknown }) {
  if (pending) return <p className="text-sm text-muted">正在读取调用审计…</p>;
  if (error) return <ErrorState error={error} title="用量读取失败" />;
  if (!usage || usage.totals.invocation_count === 0) return <Card><CardContent className="py-14 text-center"><CircleDollarSign className="mx-auto size-9 text-muted/40" /><p className="mt-3 font-semibold">还没有模型调用记录</p><p className="mt-1 text-sm text-muted">完成连接测试或调试调用后，这里会展示真实 Token、延迟与成本语义。</p></CardContent></Card>;
  const total = usage.totals;
  return <section className="space-y-5" aria-label="用量"><div><p className="section-kicker">Invocation ledger</p><h2 className="mt-1 text-xl font-semibold">真实调用用量</h2></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Summary label="调用次数" value={total.invocation_count.toLocaleString()} /><Summary label="成功率" value={total.success_rate === null ? "—" : `${(total.success_rate * 100).toFixed(1)}%`} /><Summary label="平均延迟" value={total.average_latency_ms === null ? "—" : `${Math.round(total.average_latency_ms)} ms`} /><Summary label="估算成本" value={total.estimated_cost === null ? "未配置 / 不完整" : `${total.estimated_cost} ${total.price_currency}`} /><Summary label="输入 Token" value={total.input_tokens.toLocaleString()} /><Summary label="输出 Token" value={total.output_tokens.toLocaleString()} /><Summary label="缓存 Token" value={total.cached_tokens.toLocaleString()} /><Summary label="未计价调用" value={total.uncosted_invocation_count.toLocaleString()} /></div>{usage.by_provider.length > 0 ? <UsageTable title="按服务商" groups={usage.by_provider} /> : null}{usage.by_model.length > 0 ? <UsageTable title="按模型" groups={usage.by_model} /> : null}{usage.by_role.length > 0 ? <UsageTable title="按角色" groups={usage.by_role} /> : null}</section>;
}

function UsageTable({ title, groups }: { title: string; groups: Awaited<ReturnType<typeof getUsage>>["by_provider"] }) { return <Card><CardHeader><h3 className="font-semibold">{title}</h3></CardHeader><CardContent className="overflow-x-auto"><table className="w-full min-w-[620px] text-left text-sm"><thead className="text-xs text-muted"><tr><th className="pb-2">名称</th><th>调用</th><th>成功率</th><th>延迟</th><th>输入 / 输出 / 缓存</th></tr></thead><tbody>{groups.map((group) => <tr key={group.key} className="border-t border-line"><td className="py-3 font-semibold">{group.label}</td><td>{group.invocation_count}</td><td>{group.success_rate === null ? "—" : `${(group.success_rate * 100).toFixed(1)}%`}</td><td>{group.average_latency_ms === null ? "—" : `${Math.round(group.average_latency_ms)} ms`}</td><td>{group.input_tokens.toLocaleString()} / {group.output_tokens.toLocaleString()} / {group.cached_tokens.toLocaleString()}</td></tr>)}</tbody></table></CardContent></Card>; }

function DebugPanel({ models }: { models: AiModel[] }) {
  const [message, setMessage] = useState(""); const [role, setRole] = useState<RouteRole>("default"); const [modelId, setModelId] = useState(""); const [stream, setStream] = useState(false); const [result, setResult] = useState<GatewayResponse | null>(null); const [content, setContent] = useState(""); const [pending, setPending] = useState(false); const [error, setError] = useState<unknown>(null); const abortRef = useRef<AbortController | null>(null);
  useEffect(() => () => abortRef.current?.abort(), []);
  async function run(event: FormEvent) { event.preventDefault(); setPending(true); setError(null); setContent(""); setResult(null); const input: DebugInput = { message: message.trim(), route_role: modelId ? null : role, model_record_id: modelId || null, stream }; try { if (stream) { const controller = new AbortController(); abortRef.current = controller; let accumulated = ""; for await (const item of streamDebugModel(input, controller.signal)) { if (item.content_delta) { accumulated += item.content_delta; setContent(accumulated); } if (item.response && item.final_provider_id && item.initial_provider_id && item.initial_model_id && item.final_model_id && item.request_correlation_id && item.fallback_used !== null && item.fallback_used !== undefined) setResult({ response: item.response, route_role: modelId ? null : role, fallback_used: item.fallback_used, request_correlation_id: item.request_correlation_id, initial_provider_id: item.initial_provider_id, initial_model_id: item.initial_model_id, final_provider_id: item.final_provider_id, final_model_id: item.final_model_id }); } } else { const response = await debugModel(input); setResult(response); setContent(response.response.content ?? ""); } } catch (value) { setError(value); } finally { abortRef.current = null; setPending(false); } }
  return <section className="grid gap-5 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]" aria-label="调试测试"><Card><CardHeader><p className="section-kicker">Bounded diagnostic</p><h2 className="mt-1 text-xl font-semibold">网关调试请求</h2><p className="mt-2 text-sm text-muted">单条短消息，最多 256 输出 Token；不是完整聊天产品。</p></CardHeader><CardContent><form className="space-y-4" onSubmit={(event) => void run(event)}><label className="block text-sm font-semibold">短消息<textarea className="mt-2 min-h-28 w-full resize-y rounded-lg border border-line bg-white p-3 text-sm outline-none focus:border-signal focus:ring-2 focus:ring-signal/12" value={message} maxLength={2000} required onChange={(event) => setMessage(event.currentTarget.value)} /></label><label className="block text-sm font-semibold">路由角色<select className="form-select mt-2" value={role} disabled={Boolean(modelId)} onChange={(event) => setRole(event.currentTarget.value as RouteRole)}>{routeRoles.map((item) => <option key={item} value={item}>{roleLabels[item]}</option>)}</select></label><label className="block text-sm font-semibold">指定模型（可选）<select className="form-select mt-2" value={modelId} onChange={(event) => setModelId(event.currentTarget.value)}><option value="">按路由选择</option>{models.filter((model) => model.enabled && model.provider_enabled).map((model) => <option key={model.id} value={model.id}>{model.provider_name} · {model.display_name}</option>)}</select></label><label className="flex items-center gap-2 text-sm font-semibold"><input type="checkbox" checked={stream} onChange={(event) => setStream(event.currentTarget.checked)} /> 流式输出</label><Button type="submit" disabled={pending}>{pending ? "正在调用…" : "执行测试"}</Button></form></CardContent></Card><Card className="min-h-80"><CardHeader><div className="flex items-center justify-between"><h2 className="text-xl font-semibold">响应</h2>{result ? <Badge variant={result.fallback_used ? "warning" : "success"}>{result.fallback_used ? "发生 fallback" : "未发生 fallback"}</Badge> : null}</div></CardHeader><CardContent>{error ? <ErrorState error={error} title="模型调用失败" /> : !content && !pending ? <div className="grid min-h-52 place-items-center text-center text-sm text-muted">请求后显示模型、服务商、Token 与实际 fallback 状态。</div> : <><pre className="min-h-36 whitespace-pre-wrap break-words rounded-xl bg-[#122928] p-4 font-mono text-sm leading-6 text-[#d9f2ec]">{content || "正在等待首个增量…"}</pre>{result ? <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4"><Metric label="服务商" value={result.response.provider} /><Metric label="模型" value={result.response.model ?? result.final_model_id} /><Metric label="耗时" value={result.response.latency_ms === null ? "—" : `${result.response.latency_ms} ms`} /><Metric label="Token" value={result.response.usage?.total_tokens?.toString() ?? "未返回"} /></div> : null}</>}</CardContent></Card></section>;
}

function ProviderDialog({ draft, templates, pending, error, onChange, onClose, onSave }: { draft: ProviderDraft | null; templates: ProviderTemplate[]; pending: boolean; error: unknown; onChange: (draft: ProviderDraft | null) => void; onClose: () => void; onSave: (draft: ProviderDraft) => void }) {
  function templateChanged(id: string) { if (!draft) return; const template = templates.find((item) => item.id === id); if (!template) return; onChange({ ...draft, template_id: template.id, provider_type: template.id, protocol: template.protocol, base_url: template.base_url ?? "", name: draft.name || template.display_name }); }
  return <Dialog open={draft !== null} onOpenChange={(open) => { if (!open) onClose(); }}>{draft ? <DialogContent><DialogTitle>{draft.id ? "编辑服务商" : "添加服务商"}</DialogTitle><DialogDescription>API Key 通过认证加密保存，保存后不会回填到浏览器。</DialogDescription>{error ? <div className="mt-4"><ErrorState error={error} title="保存失败" /></div> : null}<form className="mt-5 grid gap-4 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); onSave(draft); }}><label className="text-sm font-semibold sm:col-span-2">模板<select className="form-select mt-2" value={draft.template_id} disabled={Boolean(draft.id)} onChange={(event) => templateChanged(event.currentTarget.value)}>{templates.map((template) => <option key={template.id} value={template.id}>{template.display_name}</option>)}</select></label><label className="text-sm font-semibold sm:col-span-2">服务商名称<Input className="mt-2" aria-label="服务商名称" value={draft.name} required onChange={(event) => onChange({ ...draft, name: event.currentTarget.value })} /></label><label className="text-sm font-semibold sm:col-span-2">Base URL<Input className="mt-2" aria-label="Base URL" type="url" value={draft.base_url} required onChange={(event) => onChange({ ...draft, base_url: event.currentTarget.value })} /></label><label className="text-sm font-semibold sm:col-span-2">API Key<Input className="mt-2" aria-label="API Key" type="password" autoComplete="new-password" value={draft.api_key ?? ""} onChange={(event) => onChange({ ...draft, api_key: event.currentTarget.value })} />{draft.id ? <span className="mt-1 block text-xs font-normal text-muted">留空以保留现有凭证</span> : null}</label><label className="text-sm font-semibold">超时（秒）<Input className="mt-2" type="number" min={1} max={600} value={draft.timeout_seconds} onChange={(event) => onChange({ ...draft, timeout_seconds: Number(event.currentTarget.value) })} /></label><label className="text-sm font-semibold">有限重试<Input className="mt-2" type="number" min={0} max={5} value={draft.max_retries} onChange={(event) => onChange({ ...draft, max_retries: Number(event.currentTarget.value) })} /></label><label className="text-sm font-semibold">并发上限<Input className="mt-2" type="number" min={1} max={20} value={draft.concurrency_limit} onChange={(event) => onChange({ ...draft, concurrency_limit: Number(event.currentTarget.value) })} /></label><label className="flex items-end gap-2 pb-2 text-sm font-semibold"><input type="checkbox" checked={draft.enabled} onChange={(event) => onChange({ ...draft, enabled: event.currentTarget.checked })} /> 启用服务商</label><div className="flex justify-end gap-2 sm:col-span-2"><Button type="button" variant="ghost" onClick={onClose}>取消</Button><Button type="submit" disabled={pending}>{pending ? "正在保存…" : "保存服务商"}</Button></div></form></DialogContent> : null}</Dialog>;
}

function ModelDialog({ draft, providers, pending, error, onChange, onClose, onSave }: { draft: ModelDraft | null; providers: AiProvider[]; pending: boolean; error: unknown; onChange: (draft: ModelDraft | null) => void; onClose: () => void; onSave: (draft: ModelDraft) => void }) {
  const priced = Boolean(draft && (draft.input_price_per_million || draft.output_price_per_million || draft.cached_input_price_per_million));
  return <Dialog open={draft !== null} onOpenChange={(open) => { if (!open) onClose(); }}>{draft ? <DialogContent className="max-w-3xl"><DialogTitle>{draft.id ? "编辑模型能力" : "添加模型"}</DialogTitle><DialogDescription>模型能力可人工校正；成本为空表示“未配置”，不会记为 0。</DialogDescription>{error ? <div className="mt-4"><ErrorState error={error} title="保存失败" /></div> : null}<form className="mt-5 grid gap-4 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); onSave(draft); }}><label className="text-sm font-semibold">服务商<select className="form-select mt-2" value={draft.provider_id} disabled={Boolean(draft.id)} required onChange={(event) => onChange({ ...draft, provider_id: event.currentTarget.value })}><option value="">选择服务商</option>{providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name}</option>)}</select></label><label className="text-sm font-semibold">模型 ID<Input className="mt-2" value={draft.model_id} disabled={Boolean(draft.id)} required onChange={(event) => onChange({ ...draft, model_id: event.currentTarget.value })} /></label><label className="text-sm font-semibold sm:col-span-2">显示名称<Input className="mt-2" value={draft.display_name} required onChange={(event) => onChange({ ...draft, display_name: event.currentTarget.value })} /></label><label className="text-sm font-semibold">上下文长度<Input className="mt-2" type="number" min={1} value={draft.context_window} onChange={(event) => onChange({ ...draft, context_window: event.currentTarget.value })} /></label><label className="text-sm font-semibold">输出限制<Input className="mt-2" type="number" min={1} value={draft.max_output_tokens} onChange={(event) => onChange({ ...draft, max_output_tokens: event.currentTarget.value })} /></label><fieldset className="grid gap-3 rounded-xl border border-line p-4 sm:col-span-2 sm:grid-cols-3"><legend className="px-1 text-sm font-semibold">能力</legend>{Object.entries(capabilityLabels).map(([field, label]) => <label key={field} className="text-xs font-semibold">{label}<select className="form-select mt-1" value={draft[field as keyof ModelDraft] as string} onChange={(event) => onChange({ ...draft, [field]: event.currentTarget.value })}><option value="unknown">未知</option><option value="yes">支持</option><option value="no">不支持</option></select></label>)}</fieldset><label className="text-sm font-semibold">输入单价 / 百万 Token<Input className="mt-2" inputMode="decimal" value={draft.input_price_per_million} onChange={(event) => onChange({ ...draft, input_price_per_million: event.currentTarget.value })} /></label><label className="text-sm font-semibold">输出单价 / 百万 Token<Input className="mt-2" inputMode="decimal" value={draft.output_price_per_million} onChange={(event) => onChange({ ...draft, output_price_per_million: event.currentTarget.value })} /></label><label className="text-sm font-semibold">缓存输入单价 / 百万 Token<Input className="mt-2" inputMode="decimal" value={draft.cached_input_price_per_million} onChange={(event) => onChange({ ...draft, cached_input_price_per_million: event.currentTarget.value })} /></label><label className="text-sm font-semibold">币种<Input className="mt-2" placeholder="CNY / USD" value={draft.price_currency} required={priced} onChange={(event) => onChange({ ...draft, price_currency: event.currentTarget.value })} /></label><label className="text-sm font-semibold">价格生效时间<Input className="mt-2" type="datetime-local" value={draft.price_effective_at} required={priced} onChange={(event) => onChange({ ...draft, price_effective_at: event.currentTarget.value })} /></label><label className="flex items-end gap-2 pb-2 text-sm font-semibold"><input type="checkbox" checked={draft.enabled} onChange={(event) => onChange({ ...draft, enabled: event.currentTarget.checked })} /> 启用模型</label><div className="flex justify-end gap-2 sm:col-span-2"><Button type="button" variant="ghost" onClick={onClose}>取消</Button><Button type="submit" disabled={pending}>{pending ? "正在保存…" : "保存模型"}</Button></div></form></DialogContent> : null}</Dialog>;
}

function Metric({ label, value, icon: Icon }: { label: string; value: string; icon?: typeof KeyRound }) { return <div><p className="text-[11px] uppercase tracking-wide text-muted">{label}</p><p className="mt-1 flex items-center gap-1.5 break-words font-semibold">{Icon ? <Icon className="size-3.5 text-success" /> : null}{value}</p></div>; }
function Summary({ label, value }: { label: string; value: string }) { return <Card className="metric-card"><CardContent><p className="text-xs font-semibold text-muted">{label}</p><p className="mt-2 font-display text-2xl font-semibold tabular-nums">{value}</p></CardContent></Card>; }
