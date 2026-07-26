import { Ban, LoaderCircle } from "lucide-react";
import { useState } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "../../../components/ui/alert-dialog";
import { Button } from "../../../components/ui/button";
import { errorMessage } from "../../../lib/utils";
import { useCancelCrawlerTaskMutation } from "../hooks/use-crawler-queries";

export function CancelTaskDialog({ taskId }: { taskId: string }) {
  const [open, setOpen] = useState(false);
  const cancelTask = useCancelCrawlerTaskMutation();

  return (
    <AlertDialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!cancelTask.isPending) setOpen(nextOpen);
        if (!nextOpen) cancelTask.reset();
      }}
    >
      <AlertDialogTrigger asChild>
        <Button variant="danger">
          <Ban className="size-4" />
          取消任务
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogTitle>确认取消这个采集任务？</AlertDialogTitle>
        <AlertDialogDescription>
          Worker 会终止对应的采集进程。已经写入的日志和结果不会由此页面删除。
        </AlertDialogDescription>
        {cancelTask.error ? (
          <p
            className="mt-4 rounded-lg border border-danger/20 bg-danger/5 px-3 py-2 text-sm text-danger"
            role="alert"
          >
            {errorMessage(cancelTask.error)}
          </p>
        ) : null}
        <div className="mt-6 flex justify-end gap-3">
          <AlertDialogCancel asChild>
            <Button variant="secondary" disabled={cancelTask.isPending}>
              返回
            </Button>
          </AlertDialogCancel>
          <AlertDialogAction asChild>
            <Button
              variant="danger"
              disabled={cancelTask.isPending}
              onClick={(event) => {
                event.preventDefault();
                cancelTask.mutate(taskId, {
                  onSuccess: () => setOpen(false),
                });
              }}
            >
              {cancelTask.isPending ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Ban className="size-4" />
              )}
              {cancelTask.isPending ? "正在取消" : "确认取消"}
            </Button>
          </AlertDialogAction>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
}
