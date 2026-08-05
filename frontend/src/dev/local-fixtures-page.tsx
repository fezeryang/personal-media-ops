import {
  researchFixtureCandidate,
  researchFixtureEvidence,
  researchFixtureMemory,
  researchFixtureSpace,
  researchFixtureTask,
  researchStatusFixtures,
} from "./research-fixtures";

const statusClass: Record<string, string> = {
  Draft: "border-line bg-white",
  Planning: "border-blue-200 bg-blue-50",
  Researching: "border-cyan-200 bg-cyan-50",
  WaitingCrawl: "border-amber-200 bg-amber-50",
  Partial: "border-orange-200 bg-orange-50",
  Done: "border-emerald-200 bg-emerald-50",
  Failed: "border-rose-200 bg-rose-50",
  BudgetExceeded: "border-amber-300 bg-amber-100",
};

export function LocalFixturesPage() {
  return (
    <main className="min-h-screen bg-canvas px-4 py-8 text-ink sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="rounded-3xl bg-[#184b4b] p-7 text-white shadow-sm sm:p-10">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#9de1d2]">
            Local-only fixture harness
          </p>
          <h1 className="mt-3 font-display text-3xl font-semibold sm:text-4xl">
            8D 研究与发现状态覆盖
          </h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-[#d9f2ec]">
            这是脱敏 Recorded Response 的本地产品验证入口。它不调用真实模型、爬虫或生产
            API，也不代表生产业务已经验收。
          </p>
        </header>

        <section className="mt-8" aria-labelledby="research-status-heading">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="section-kicker">Research lifecycle</p>
              <h2 id="research-status-heading" className="mt-2 text-2xl font-semibold">
                研究任务状态
              </h2>
            </div>
            <span className="rounded-full bg-[#e6f4ef] px-3 py-1 text-xs font-semibold text-[#126d69]">
              schema validated
            </span>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {researchStatusFixtures.map((item) => (
              <article key={item.status} className={`rounded-2xl border p-4 ${statusClass[item.status]}`}>
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-semibold">{item.label}</h3>
                  <span className="text-[11px] font-mono text-muted">{item.status}</span>
                </div>
                <p className="mt-3 text-sm leading-6 text-muted">{item.description}</p>
              </article>
            ))}
          </div>
        </section>

        <div className="mt-8 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <section className="rounded-3xl border border-line bg-white p-6 shadow-sm" aria-labelledby="candidate-heading">
            <p className="section-kicker">Discovery inbox</p>
            <h2 id="candidate-heading" className="mt-2 text-2xl font-semibold">
              {researchFixtureCandidate.title}
            </h2>
            <p className="mt-3 text-sm leading-7 text-muted">{researchFixtureCandidate.summary}</p>
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                ["最终评分", researchFixtureCandidate.final_score.toFixed(2)],
                ["独立来源", String(researchFixtureCandidate.independent_source_count)],
                ["平台数", String(researchFixtureCandidate.platform_count)],
                ["状态", researchFixtureCandidate.state],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl bg-[#f4f5f2] p-3">
                  <p className="text-xs text-muted">{label}</p>
                  <p className="mt-2 text-sm font-semibold">{value}</p>
                </div>
              ))}
            </div>
            <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6">
              <span className="font-semibold">反向证据：</span>
              {String(researchFixtureCandidate.score_explanation.counterevidence)}
            </div>
            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              <span className="rounded-full bg-[#e6f4ef] px-3 py-1.5 text-[#126d69]">反馈已撤销</span>
              <span className="rounded-full bg-[#f4f5f2] px-3 py-1.5 text-muted">可继续研究</span>
              <span className="rounded-full bg-[#f4f5f2] px-3 py-1.5 text-muted">可加入空间</span>
            </div>
          </section>

          <section className="rounded-3xl border border-line bg-white p-6 shadow-sm" aria-labelledby="space-heading">
            <p className="section-kicker">Research space</p>
            <h2 id="space-heading" className="mt-2 text-2xl font-semibold">{researchFixtureSpace.name}</h2>
            <p className="mt-3 text-sm leading-7 text-muted">{researchFixtureSpace.description}</p>
            <div className="mt-5 rounded-2xl bg-[#f4f5f2] p-4">
              <p className="text-xs text-muted">空间条目</p>
              <p className="mt-2 font-semibold">{researchFixtureSpace.items[0]?.note}</p>
            </div>
            <p className="mt-5 text-sm text-muted">
              任务：<span className="font-medium text-ink">{researchFixtureTask.objective}</span>
            </p>
          </section>
        </div>

        <div className="mt-6 grid gap-6 md:grid-cols-2">
          <section className="rounded-3xl border border-line bg-white p-6 shadow-sm" aria-labelledby="evidence-heading">
            <p className="section-kicker">Evidence</p>
            <h2 id="evidence-heading" className="mt-2 text-xl font-semibold">证据、Finding 与反例</h2>
            <div className="mt-4 space-y-3">
              {researchFixtureEvidence.map((item) => (
                <div key={item.type} className="rounded-2xl border border-line p-4">
                  <p className="font-semibold">{item.label}</p>
                  <p className="mt-1 text-sm text-muted">{item.detail}</p>
                </div>
              ))}
            </div>
          </section>
          <section className="rounded-3xl border border-line bg-white p-6 shadow-sm" aria-labelledby="memory-heading">
            <p className="section-kicker">Memory and follow-up</p>
            <h2 id="memory-heading" className="mt-2 text-xl font-semibold">记忆、事件与下一步</h2>
            <div className="mt-4 space-y-3">
              {researchFixtureMemory.map((item) => (
                <div key={item.type} className="rounded-2xl bg-[#f4f5f2] p-4">
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#126d69]">{item.type}</p>
                  <p className="mt-1 text-sm text-muted">{item.detail}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
