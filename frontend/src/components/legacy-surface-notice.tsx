import { Link } from "react-router";

interface LegacySurfaceNoticeProps {
  surface: string;
  replacement: string;
  replacementPath?: string;
}

export function LegacySurfaceNotice({
  surface,
  replacement,
  replacementPath,
}: LegacySurfaceNoticeProps) {
  return (
    <aside
      role="note"
      className="rounded-2xl border border-warning/30 bg-warning/5 p-4 text-sm"
    >
      <p className="section-kicker text-warning-strong">历史兼容工具</p>
      <p className="mt-2 font-semibold">
        {surface}已停止作为核心产品继续开发，未来将由{replacement}替代。
      </p>
      <p className="mt-1 leading-6 text-muted">
        当前页面仅保留历史数据查看与审计用途，不会再创建、执行或修改自动化任务。
      </p>
      {replacementPath ? (
        <Link
          to={replacementPath}
          className="mt-3 inline-flex font-semibold text-signal-strong hover:underline"
        >
          前往{replacement} →
        </Link>
      ) : null}
    </aside>
  );
}
