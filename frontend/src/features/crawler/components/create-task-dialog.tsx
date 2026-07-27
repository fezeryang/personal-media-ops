import { LoaderCircle, LockKeyhole, Plus, QrCode, Search } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router";

import type { CrawlerPlatformCapability } from "../../../api/crawler";
import { Button } from "../../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "../../../components/ui/dialog";
import { Input } from "../../../components/ui/input";
import { errorMessage } from "../../../lib/utils";
import {
  useCrawlerCapabilitiesQuery,
  useCreateCrawlerTaskMutation,
} from "../hooks/use-crawler-queries";

interface FixedFieldProps {
  label: string;
  value: string;
  icon: typeof Search;
}

function FixedField({ label, value, icon: Icon }: FixedFieldProps) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold text-muted">{label}</p>
      <div className="flex h-10 items-center gap-2 rounded-lg border border-line bg-paper px-3 text-sm font-medium text-ink">
        <Icon className="size-4 text-muted" />
        {value}
        <LockKeyhole className="ml-auto size-3.5 text-muted/60" />
      </div>
    </div>
  );
}

function capabilityStatusLabel(
  enabled: boolean,
  verificationStatus: CrawlerPlatformCapability["verification_status"],
) {
  if (verificationStatus === "verified") {
    return enabled ? "（已验证）" : "（已验证，未启用）";
  }
  return enabled ? "（代码就绪）" : "（代码就绪，未启用）";
}

export function CreateTaskDialog() {
  const [open, setOpen] = useState(false);
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null);
  const [keywords, setKeywords] = useState("");
  const [requestedCount, setRequestedCount] = useState<number | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const capabilitiesQuery = useCrawlerCapabilitiesQuery();
  const createTask = useCreateCrawlerTaskMutation();
  const navigate = useNavigate();
  const platforms = capabilitiesQuery.data?.platforms ?? [];
  const selectedCapability =
    platforms.find(
      (capability) =>
        capability.platform === selectedPlatform && capability.enabled,
    ) ?? platforms.find((capability) => capability.enabled);
  const effectiveRequestedCount =
    requestedCount ?? selectedCapability?.requested_count.default ?? 20;

  const handleOpenChange = (nextOpen: boolean) => {
    if (createTask.isPending) return;
    setOpen(nextOpen);
    if (!nextOpen) {
      setValidationError(null);
      createTask.reset();
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (createTask.isPending) return;

    const normalizedKeywords = keywords.trim();
    if (!selectedCapability) {
      setValidationError("当前没有可用的采集平台");
      return;
    }
    if (!normalizedKeywords) {
      setValidationError("请输入要采集的关键词");
      return;
    }
    if (
      !Number.isInteger(effectiveRequestedCount) ||
      effectiveRequestedCount < selectedCapability.requested_count.minimum ||
      effectiveRequestedCount > selectedCapability.requested_count.maximum
    ) {
      setValidationError(
        `采集数量必须在 ${selectedCapability.requested_count.minimum} 到 ${selectedCapability.requested_count.maximum} 之间`,
      );
      return;
    }

    setValidationError(null);
    createTask.mutate(
      {
        platform: selectedCapability.platform,
        crawler_type: selectedCapability.crawler_types[0].value,
        keywords: normalizedKeywords,
        requested_count: effectiveRequestedCount,
      },
      {
        onSuccess: (task) => {
          setOpen(false);
          void navigate(`/crawler/tasks/${encodeURIComponent(task.id)}`);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button size="lg">
          <Plus className="size-4" />
          创建采集任务
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>创建采集任务</DialogTitle>
        <DialogDescription>
          平台选项由后端真实能力注册表提供。任务进入执行后，请按提示使用对应平台客户端扫码登录。
        </DialogDescription>

        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label
                className="mb-2 block text-xs font-semibold text-muted"
                htmlFor="crawler-platform"
              >
                平台
              </label>
              <select
                id="crawler-platform"
                className="h-10 w-full rounded-lg border border-line bg-white px-3 text-sm font-medium text-ink outline-none focus:border-signal focus:ring-2 focus:ring-signal/12 disabled:bg-paper disabled:text-muted"
                value={selectedCapability?.platform ?? ""}
                disabled={
                  capabilitiesQuery.isPending ||
                  capabilitiesQuery.isError ||
                  createTask.isPending
                }
                onChange={(event) => {
                  const nextPlatform = event.currentTarget.value;
                  const nextCapability = platforms.find(
                    (capability) =>
                      capability.platform === nextPlatform &&
                      capability.enabled,
                  );
                  setSelectedPlatform(nextPlatform);
                  if (nextCapability) {
                    setRequestedCount(nextCapability.requested_count.default);
                  }
                }}
              >
                {capabilitiesQuery.isPending ? (
                  <option value="">正在加载平台能力</option>
                ) : null}
                {platforms.map((capability) => (
                  <option
                    key={capability.platform}
                    value={capability.platform}
                    disabled={!capability.enabled}
                  >
                    {capability.display_name}
                    {capabilityStatusLabel(
                      capability.enabled,
                      capability.verification_status,
                    )}
                  </option>
                ))}
              </select>
            </div>
            <FixedField
              label="采集类型"
              value={
                selectedCapability?.crawler_types[0]?.label ?? "关键词搜索"
              }
              icon={Search}
            />
            <FixedField
              label="登录方式"
              value={
                selectedCapability?.login_types[0]?.label ?? "二维码登录"
              }
              icon={QrCode}
            />
            <div>
              <label
                className="mb-2 block text-xs font-semibold text-muted"
                htmlFor="requested-count"
              >
                采集数量
              </label>
              <Input
                id="requested-count"
                type="number"
                min={selectedCapability?.requested_count.minimum ?? 1}
                max={selectedCapability?.requested_count.maximum ?? 20}
                value={effectiveRequestedCount}
                disabled={!selectedCapability || createTask.isPending}
                onChange={(event) =>
                  setRequestedCount(event.currentTarget.valueAsNumber)
                }
              />
            </div>
          </div>

          <div>
            <label
              className="mb-2 block text-xs font-semibold text-muted"
              htmlFor="crawler-keywords"
            >
              关键词
            </label>
            <Input
              id="crawler-keywords"
              value={keywords}
              onChange={(event) => setKeywords(event.currentTarget.value)}
              placeholder="例如：AI Agent"
              maxLength={200}
              autoComplete="off"
              autoFocus
              disabled={createTask.isPending}
            />
            <div className="mt-2 flex justify-between text-[11px] text-muted">
              <span>可输入一个关键词或短语</span>
              <span className="tabular-nums">{keywords.length} / 200</span>
            </div>
          </div>

          {capabilitiesQuery.isError ? (
            <p
              className="rounded-lg border border-danger/20 bg-danger/5 px-3 py-2 text-sm text-danger"
              role="alert"
            >
              平台能力加载失败：{errorMessage(capabilitiesQuery.error)}
            </p>
          ) : null}

          {validationError || createTask.error ? (
            <p
              className="rounded-lg border border-danger/20 bg-danger/5 px-3 py-2 text-sm text-danger"
              role="alert"
            >
              {validationError ?? errorMessage(createTask.error)}
            </p>
          ) : null}

          <div className="flex flex-col-reverse gap-3 border-t border-line pt-5 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="secondary"
              onClick={() => handleOpenChange(false)}
              disabled={createTask.isPending}
            >
              取消
            </Button>
            <Button
              type="submit"
              disabled={!selectedCapability || createTask.isPending}
            >
              {createTask.isPending ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Plus className="size-4" />
              )}
              {createTask.isPending ? "正在创建" : "创建并进入任务"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
