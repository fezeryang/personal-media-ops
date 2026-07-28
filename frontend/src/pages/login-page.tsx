import { ArrowRight, KeyRound, Radar, ShieldCheck } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";

import { ApiError } from "../api/client";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { useAuth } from "../features/auth/auth-context";

function requestedPath(state: unknown): string {
  if (
    typeof state === "object" &&
    state !== null &&
    "from" in state &&
    typeof state.from === "string"
  ) {
    return state.from;
  }
  return "/";
}

export function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (auth.session?.authenticated) {
    return <Navigate to="/" replace />;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await auth.login(username, password);
      const destination = requestedPath(location.state as unknown);
      void navigate(destination, { replace: true });
    } catch (caught: unknown) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "登录失败，请稍后重试",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-canvas min-h-screen px-5 py-8 sm:grid sm:place-items-center">
      <section className="mx-auto grid w-full max-w-5xl overflow-hidden rounded-[28px] border border-white/70 bg-white shadow-[0_32px_100px_rgba(31,55,56,0.14)] lg:grid-cols-[1.08fr_0.92fr]">
        <div className="relative hidden min-h-[620px] overflow-hidden bg-[#153c3d] p-12 text-white lg:block">
          <div className="absolute -right-28 -top-28 size-96 rounded-full border border-white/10" />
          <div className="absolute -right-10 top-20 size-64 rounded-full border border-[#80d6ca]/30" />
          <div className="relative">
            <div className="flex items-center gap-3">
              <span className="grid size-11 place-items-center rounded-2xl bg-[#dff7ee] text-[#153c3d]">
                <Radar className="size-5" />
              </span>
              <div>
                <p className="font-display text-lg font-semibold">
                  Personal Media Ops
                </p>
                <p className="text-xs tracking-[0.18em] text-[#9fc4bf]">
                  INTELLIGENCE LAB
                </p>
              </div>
            </div>
            <h1 className="mt-24 max-w-md font-display text-5xl font-semibold leading-[1.08] tracking-[-0.04em]">
              把分散的信息，
              <br />
              变成持续积累的判断。
            </h1>
            <p className="mt-6 max-w-md text-base leading-7 text-[#bdd4d0]">
              订阅主题、观察创作者、识别趋势，并用可追溯证据生成每日情报简报。
            </p>
            <div className="mt-20 grid grid-cols-2 gap-3">
              {["单一所有者", "证据可追溯", "确定性分析", "Agent API"].map(
                (label) => (
                  <div
                    key={label}
                    className="rounded-2xl border border-white/10 bg-white/[0.05] px-4 py-3 text-sm text-[#d8e7e4]"
                  >
                    {label}
                  </div>
                ),
              )}
            </div>
          </div>
        </div>

        <div className="flex min-h-[560px] flex-col justify-center p-7 sm:p-12">
          <span className="grid size-12 place-items-center rounded-2xl bg-[#e7f5f1] text-signal-strong">
            <ShieldCheck className="size-5" />
          </span>
          <p className="mt-9 text-xs font-bold uppercase tracking-[0.2em] text-signal-strong">
            Owner access
          </p>
          <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight">
            登录情报工作台
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted">
            本系统不开放注册。使用服务器上安全初始化的所有者账户登录。
          </p>

          <form
            className="mt-9 space-y-5"
            onSubmit={(event) => void submit(event)}
          >
            <label className="block text-sm font-semibold">
              用户名
              <Input
                className="mt-2 h-12"
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.currentTarget.value)}
                required
              />
            </label>
            <label className="block text-sm font-semibold">
              密码
              <div className="relative mt-2">
                <KeyRound className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
                <Input
                  className="h-12 pl-10"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.currentTarget.value)}
                  required
                />
              </div>
            </label>
            {error ? (
              <p
                role="alert"
                className="rounded-xl border border-danger/20 bg-danger/5 px-4 py-3 text-sm text-danger"
              >
                {error}
              </p>
            ) : null}
            <Button className="h-12 w-full" disabled={submitting}>
              {submitting ? "正在验证…" : "进入工作台"}
              <ArrowRight className="size-4" />
            </Button>
          </form>
          <p className="mt-8 text-xs leading-5 text-muted">
            会话保存在 HttpOnly Cookie 中；密码和会话令牌不会写入浏览器存储。
          </p>
        </div>
      </section>
    </main>
  );
}
