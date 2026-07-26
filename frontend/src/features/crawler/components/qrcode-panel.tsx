import { CheckCircle2, LoaderCircle, QrCode } from "lucide-react";
import { useEffect, useState } from "react";

import type { CrawlerTask } from "../../../api/crawler";
import { ErrorState } from "../../../components/error-state";
import { Card, CardContent, CardHeader } from "../../../components/ui/card";
import { useCrawlerTaskQrcodeQuery } from "../hooks/use-crawler-queries";

function QrcodeImage({ image }: { image: Blob }) {
  const [imageUrl] = useState(() => URL.createObjectURL(image));

  useEffect(
    () => () => {
      URL.revokeObjectURL(imageUrl);
    },
    [imageUrl],
  );

  return (
    <img
      src={imageUrl}
      alt="哔哩哔哩登录二维码"
      className="size-44 object-contain"
    />
  );
}

export function QrcodePanel({ task }: { task: CrawlerTask }) {
  const waitingForLogin = task.status === "waiting_login";
  const qrcodeQuery = useCrawlerTaskQrcodeQuery(task.id, waitingForLogin);

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b border-line pb-4">
        <div className="flex items-center gap-2">
          <QrCode className="size-4 text-signal" />
          <h2 className="font-display text-lg font-semibold">二维码登录</h2>
        </div>
      </CardHeader>
      <CardContent>
        {!waitingForLogin ? (
          <div className="flex min-h-52 flex-col items-center justify-center text-center">
            <div className="grid size-11 place-items-center rounded-xl bg-paper text-muted">
              {task.status === "pending" ? (
                <LoaderCircle className="size-5" />
              ) : (
                <CheckCircle2 className="size-5 text-success" />
              )}
            </div>
            <p className="mt-3 text-sm font-semibold text-ink">
              {task.status === "pending"
                ? "等待任务进入登录阶段"
                : "当前无需扫码"}
            </p>
            <p className="mt-1 max-w-xs text-xs leading-5 text-muted">
              {task.status === "pending"
                ? "Worker 领取任务后，二维码会自动出现在这里。"
                : "任务已离开等待登录状态，二维码提示已隐藏。"}
            </p>
          </div>
        ) : qrcodeQuery.isError ? (
          <ErrorState
            title="二维码检查失败"
            error={qrcodeQuery.error}
            onRetry={() => void qrcodeQuery.refetch()}
          />
        ) : qrcodeQuery.data ? (
          <div className="flex min-h-52 flex-col items-center justify-center text-center">
            <div className="rounded-2xl border border-line bg-white p-3 shadow-sm">
              <QrcodeImage
                key={qrcodeQuery.dataUpdatedAt}
                image={qrcodeQuery.data}
              />
            </div>
            <p className="mt-4 text-sm font-semibold text-ink">
              使用哔哩哔哩客户端扫码
            </p>
            <p className="mt-1 text-xs text-muted">
              登录完成后，任务状态会自动恢复为采集中。
            </p>
          </div>
        ) : (
          <div className="flex min-h-52 flex-col items-center justify-center text-center">
            <LoaderCircle className="size-7 animate-spin text-signal" />
            <p className="mt-4 text-sm font-semibold text-ink">
              正在等待二维码生成
            </p>
            <p className="mt-1 text-xs text-muted">
              页面会持续检查，请保持此页面打开。
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
