import {
  FileSearch,
  LoaderCircle,
  MessageCircle,
  MessagesSquare,
  Plus,
  Search,
  UserRoundSearch,
} from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router";

import type {
  CreateCrawlerTaskInput,
  CrawlerModeCapability,
  CrawlerTaskMode,
} from "../../../api/crawler";
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
import {
  capabilityStatusLabel,
  modeCapabilityStatusLabel,
} from "../lib/task";

const MODE_ICONS = {
  search: Search,
  detail: FileSearch,
  creator: UserRoundSearch,
  comments: MessageCircle,
  sub_comments: MessagesSquare,
} satisfies Record<CrawlerTaskMode, typeof Search>;

function isHttpUrl(value: string): boolean {
  try {
    const protocol = new URL(value).protocol;
    return protocol === "http:" || protocol === "https:";
  } catch {
    return false;
  }
}

function countCapability(mode: CrawlerModeCapability) {
  if (mode.mode === "comments" && mode.requested_comment_count) {
    return mode.requested_comment_count;
  }
  if (mode.mode === "sub_comments" && mode.requested_sub_comment_count) {
    return mode.requested_sub_comment_count;
  }
  return mode.requested_count;
}

export function CreateTaskDialog() {
  const [open, setOpen] = useState(false);
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null);
  const [selectedMode, setSelectedMode] = useState<CrawlerTaskMode | null>(null);
  const [primaryInput, setPrimaryInput] = useState("");
  const [parentCommentId, setParentCommentId] = useState("");
  const [requestedCount, setRequestedCount] = useState<number | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const capabilitiesQuery = useCrawlerCapabilitiesQuery();
  const createTask = useCreateCrawlerTaskMutation();
  const navigate = useNavigate();
  const platforms = useMemo(
    () => capabilitiesQuery.data?.platforms ?? [],
    [capabilitiesQuery.data?.platforms],
  );

  const selectedCapability = useMemo(
    () =>
      platforms.find(
        (capability) =>
          capability.platform === selectedPlatform &&
          capability.modes.some((mode) => mode.enabled),
      ) ??
      platforms.find((capability) =>
        capability.modes.some((mode) => mode.enabled),
      ),
    [platforms, selectedPlatform],
  );
  const selectedModeCapability =
    selectedCapability?.modes.find(
      (mode) => mode.mode === selectedMode && mode.enabled,
    ) ?? selectedCapability?.modes.find((mode) => mode.enabled);
  const countRules = selectedModeCapability
    ? countCapability(selectedModeCapability)
    : { minimum: 1, maximum: 20, default: 5 };
  const effectiveRequestedCount = requestedCount ?? countRules.default;
  const ModeIcon = selectedModeCapability
    ? MODE_ICONS[selectedModeCapability.mode]
    : Search;

  const resetFields = () => {
    setPrimaryInput("");
    setParentCommentId("");
    setRequestedCount(null);
    setValidationError(null);
  };

  const handleOpenChange = (nextOpen: boolean) => {
    if (createTask.isPending) return;
    setOpen(nextOpen);
    if (!nextOpen) {
      resetFields();
      createTask.reset();
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (createTask.isPending) return;
    if (!selectedCapability || !selectedModeCapability) {
      setValidationError("当前没有可提交的采集模式");
      return;
    }
    const normalizedInput = primaryInput.trim();
    const normalizedParentCommentId = parentCommentId.trim();
    if (!normalizedInput) {
      setValidationError(
        selectedModeCapability.mode === "search"
          ? "请输入要采集的关键词"
          : "请输入当前模式要求的目标 ID 或 URL",
      );
      return;
    }
    if (
      selectedModeCapability.mode === "sub_comments" &&
      !normalizedParentCommentId
    ) {
      setValidationError("请输入父评论 ID");
      return;
    }
    if (
      !Number.isInteger(effectiveRequestedCount) ||
      effectiveRequestedCount < countRules.minimum ||
      effectiveRequestedCount > countRules.maximum
    ) {
      setValidationError(
        `请求数量必须在 ${countRules.minimum} 到 ${countRules.maximum} 之间`,
      );
      return;
    }

    const mode = selectedModeCapability.mode;
    const input: CreateCrawlerTaskInput = {
      platform: selectedCapability.platform,
      mode,
      requested_count:
        mode === "comments" || mode === "sub_comments"
          ? 1
          : effectiveRequestedCount,
    };
    if (mode === "search") {
      input.keywords = normalizedInput;
    } else if (mode === "creator") {
      if (isHttpUrl(normalizedInput)) {
        input.creator_urls = [normalizedInput];
      } else {
        input.creator_ids = [normalizedInput];
      }
    } else if (mode === "comments" || mode === "sub_comments") {
      if (isHttpUrl(normalizedInput)) {
        input.target_urls = [normalizedInput];
      } else {
        input.parent_content_id = normalizedInput;
      }
      if (mode === "comments") {
        input.requested_comment_count = effectiveRequestedCount;
      } else {
        input.parent_comment_id = normalizedParentCommentId;
        input.requested_sub_comment_count = effectiveRequestedCount;
      }
    } else if (isHttpUrl(normalizedInput)) {
      input.target_urls = [normalizedInput];
    } else {
      input.target_ids = [normalizedInput];
    }

    setValidationError(null);
    createTask.mutate(input, {
      onSuccess: (task) => {
        setOpen(false);
        void navigate(`/crawler/tasks/${encodeURIComponent(task.id)}`);
      },
    });
  };

  const mode = selectedModeCapability?.mode ?? "search";
  const primaryLabel = {
    search: "关键词",
    detail: "内容 URL 或 ID",
    creator: "创作者 URL 或 ID",
    comments: "内容 URL 或 ID",
    sub_comments: "内容 URL 或 ID",
  }[mode];
  const primaryPlaceholder = {
    search: "例如：AI Agent",
    detail: "粘贴内容链接或输入平台内容 ID",
    creator: "粘贴创作者主页链接或输入创作者 ID",
    comments: "一次只允许一个内容目标",
    sub_comments: "输入父评论所属的内容目标",
  }[mode];

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
          平台与模式来自生产能力矩阵。评论任务严格限量并始终单任务串行执行。
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
                    (capability) => capability.platform === nextPlatform,
                  );
                  setSelectedPlatform(nextPlatform);
                  setSelectedMode(
                    nextCapability?.modes.find((modeItem) => modeItem.enabled)
                      ?.mode ?? null,
                  );
                  resetFields();
                }}
              >
                {capabilitiesQuery.isPending ? (
                  <option value="">正在加载平台能力</option>
                ) : null}
                {platforms.map((capability) => (
                  <option
                    key={capability.platform}
                    value={capability.platform}
                    disabled={!capability.modes.some((modeItem) => modeItem.enabled)}
                  >
                    {capability.display_name}
                    {capabilityStatusLabel(capability)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                className="mb-2 block text-xs font-semibold text-muted"
                htmlFor="crawler-mode"
              >
                采集模式
              </label>
              <div className="relative">
                <ModeIcon className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
                <select
                  id="crawler-mode"
                  className="h-10 w-full rounded-lg border border-line bg-white pl-9 pr-3 text-sm font-medium text-ink outline-none focus:border-signal focus:ring-2 focus:ring-signal/12"
                  value={selectedModeCapability?.mode ?? ""}
                  disabled={!selectedCapability || createTask.isPending}
                  onChange={(event) => {
                    setSelectedMode(event.currentTarget.value as CrawlerTaskMode);
                    resetFields();
                  }}
                >
                  {(selectedCapability?.modes ?? []).map((modeItem) => (
                    <option
                      key={modeItem.mode}
                      value={modeItem.mode}
                      disabled={!modeItem.enabled}
                    >
                      {modeItem.label}
                      {modeCapabilityStatusLabel(modeItem)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="sm:col-span-2">
              <label
                className="mb-2 block text-xs font-semibold text-muted"
                htmlFor="crawler-primary-input"
              >
                {primaryLabel}
              </label>
              <Input
                id="crawler-primary-input"
                value={primaryInput}
                onChange={(event) => setPrimaryInput(event.currentTarget.value)}
                placeholder={primaryPlaceholder}
                maxLength={2000}
                autoComplete="off"
                autoFocus
                disabled={!selectedModeCapability || createTask.isPending}
              />
            </div>
            {mode === "sub_comments" ? (
              <div>
                <label
                  className="mb-2 block text-xs font-semibold text-muted"
                  htmlFor="parent-comment-id"
                >
                  父评论 ID
                </label>
                <Input
                  id="parent-comment-id"
                  value={parentCommentId}
                  onChange={(event) =>
                    setParentCommentId(event.currentTarget.value)
                  }
                  maxLength={500}
                  disabled={createTask.isPending}
                />
              </div>
            ) : null}
            <div>
              <label
                className="mb-2 block text-xs font-semibold text-muted"
                htmlFor="requested-count"
              >
                {mode === "comments"
                  ? "一级评论数量"
                  : mode === "sub_comments"
                    ? "二级评论数量"
                    : "采集数量"}
              </label>
              <Input
                id="requested-count"
                type="number"
                min={countRules.minimum}
                max={countRules.maximum}
                value={effectiveRequestedCount}
                disabled={!selectedModeCapability || createTask.isPending}
                onChange={(event) =>
                  setRequestedCount(event.currentTarget.valueAsNumber)
                }
              />
            </div>
          </div>

          {mode === "comments" || mode === "sub_comments" ? (
            <p className="rounded-lg border border-warning/25 bg-warning/5 px-3 py-2 text-xs leading-5 text-warning-strong">
              评论采集请求量较高：当前任务只处理一个内容，一级评论最多 10
              条、二级评论最多 5 条，不会隐式递归抓取全部回复。
            </p>
          ) : null}
          {selectedModeCapability?.reason ? (
            <p className="text-xs leading-5 text-muted">
              模式说明：{selectedModeCapability.reason}
            </p>
          ) : null}
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
              disabled={!selectedModeCapability || createTask.isPending}
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
