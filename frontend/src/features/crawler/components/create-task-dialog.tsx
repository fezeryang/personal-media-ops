import { LoaderCircle, LockKeyhole, Plus, QrCode, Search } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router";

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
import { useCreateCrawlerTaskMutation } from "../hooks/use-crawler-queries";

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

export function CreateTaskDialog() {
  const [open, setOpen] = useState(false);
  const [keywords, setKeywords] = useState("");
  const [requestedCount, setRequestedCount] = useState(20);
  const [validationError, setValidationError] = useState<string | null>(null);
  const createTask = useCreateCrawlerTaskMutation();
  const navigate = useNavigate();

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
    if (!normalizedKeywords) {
      setValidationError("请输入要采集的关键词");
      return;
    }
    if (
      !Number.isInteger(requestedCount) ||
      requestedCount < 1 ||
      requestedCount > 20
    ) {
      setValidationError("采集数量必须在 1 到 20 之间");
      return;
    }

    setValidationError(null);
    createTask.mutate(
      {
        platform: "bili",
        crawler_type: "search",
        keywords: normalizedKeywords,
        requested_count: requestedCount,
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
        <DialogTitle>创建 B 站采集任务</DialogTitle>
        <DialogDescription>
          当前版本仅支持哔哩哔哩关键词搜索。任务进入执行后，请按提示使用客户端扫码登录。
        </DialogDescription>

        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FixedField label="平台" value="哔哩哔哩" icon={Search} />
            <FixedField label="采集类型" value="关键词搜索" icon={Search} />
            <FixedField label="登录方式" value="二维码登录" icon={QrCode} />
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
                min={1}
                max={20}
                value={requestedCount}
                disabled={createTask.isPending}
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
            <Button type="submit" disabled={createTask.isPending}>
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
