import { opportunityFixtureStates } from "./opportunity-fixtures";

export function LocalOpportunityFixturesPage() {
  const strong = opportunityFixtureStates[0];
  const content = opportunityFixtureStates[3];
  const validation = opportunityFixtureStates[4];
  const outcome = opportunityFixtureStates[6];

  return (
    <main className="min-h-screen bg-canvas px-4 py-8 text-ink sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="rounded-3xl bg-[#184b4b] p-7 text-white shadow-sm sm:p-10">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#9de1d2]">Local-only opportunity harness</p>
          <h1 className="mt-3 font-display text-3xl font-semibold sm:text-4xl">机会与行动</h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-[#d9f2ec]">
            证据 → 信号 → 机会 → 验证 → 行动 → Outcome → 记忆。所有状态来自本地 fixture，不调用模型、爬虫或生产 API。
          </p>
        </header>

        <section className="mt-8" aria-labelledby="opportunity-card-heading">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="section-kicker">Opportunity inbox · local states</p>
              <h2 id="opportunity-card-heading" className="mt-2 text-2xl font-semibold">机会卡与证据成熟度</h2>
            </div>
            <span className="rounded-full bg-[#e6f4ef] px-3 py-1 text-xs font-semibold text-[#126d69]">no fabricated business result</span>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {opportunityFixtureStates.map((item) => (
              <article key={item.key} className={`rounded-3xl border p-5 ${item.key === "empty" ? "border-line bg-white" : item.key === "counterevidence" ? "border-amber-200 bg-amber-50" : "border-[#9de1d2] bg-[#f1fbf7]"}`}>
                <div className="flex items-start justify-between gap-2">
                  <p className="section-kicker">{item.label}</p>
                  <span className="text-[11px] font-mono text-muted">{item.readiness}</span>
                </div>
                <h3 className="mt-2 text-lg font-semibold">{item.title}</h3>
                <p className="mt-3 text-xs font-semibold text-[#126d69]">{item.evidence}</p>
                <p className="mt-2 text-sm leading-6 text-muted">{item.detail}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]" aria-labelledby="opportunity-detail-heading">
          <article className="rounded-3xl border border-line bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="section-kicker">Opportunity Card · detail</p>
                <h2 id="opportunity-detail-heading" className="mt-2 text-2xl font-semibold">{strong.title}</h2>
              </div>
              <span className="rounded-full bg-[#126d69] px-3 py-1 text-xs font-semibold text-white">validation_ready</span>
            </div>
            <p className="mt-4 text-sm leading-7 text-muted">存在一个可被最低成本验证的工作流摩擦，但这不是已验证的商业结论。</p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              {[["问题严重度", "高"], ["独立来源", "3 个 / 2 平台"], ["验证成本", "低"]].map(([label, value]) => (
                <div key={label} className="rounded-2xl bg-[#f4f5f2] p-4"><p className="text-xs text-muted">{label}</p><p className="mt-2 font-semibold">{value}</p></div>
              ))}
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-[#9de1d2] bg-[#f1fbf7] p-4"><p className="text-xs font-bold uppercase tracking-[0.14em] text-[#126d69]">Core Evidence</p><p className="mt-2 text-sm leading-6">3 条直接反馈，保留 evidence_id、平台、时间和实体关系。</p></div>
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4"><p className="text-xs font-bold uppercase tracking-[0.14em] text-amber-800">Counterevidence</p><p className="mt-2 text-sm leading-6">熟练用户认为配置成本可接受；反向证据不会被静默覆盖。</p></div>
            </div>
          </article>

          <article className="rounded-3xl border border-line bg-white p-6 shadow-sm" aria-labelledby="validation-plan-heading">
            <p className="section-kicker">Validation Plan</p>
            <h2 id="validation-plan-heading" className="mt-2 text-xl font-semibold">{validation.title}</h2>
            <div className="mt-4 space-y-3 text-sm">
              <p><span className="font-semibold">最小验证动作：</span>继续寻找 3 个独立用户反馈，比较替代方案。</p>
              <p><span className="font-semibold">成功标准：</span>问题在不同来源持续出现，且用户描述了当前解决成本。</p>
              <p><span className="font-semibold">失败标准：</span>只有营销材料，或反向证据解释了全部信号。</p>
            </div>
            <div className="mt-5 flex flex-wrap gap-2"><span className="rounded-full bg-[#e6f4ef] px-3 py-1 text-xs text-[#126d69]">用户确认后创建研究</span><span className="rounded-full bg-[#f4f5f2] px-3 py-1 text-xs text-muted">不自动执行现实行动</span></div>
          </article>
        </section>

        <section className="mt-6 grid gap-6 md:grid-cols-2" aria-labelledby="content-opportunity-heading">
          <article className="rounded-3xl border border-blue-200 bg-blue-50 p-6">
            <p className="section-kicker">Content Opportunity</p>
            <h2 id="content-opportunity-heading" className="mt-2 text-xl font-semibold">{content.title}</h2>
            <p className="mt-3 text-sm leading-6 text-muted">目标受众：正在第一次部署个人 AI 工具、但被配置细节卡住的人。</p>
            <div className="mt-4 grid gap-2 text-sm"><p><span className="font-semibold">内容缺口：</span>现有教程说明步骤，却没有解释失败原因。</p><p><span className="font-semibold">差异化角度：</span>教程型 · 反常识型 · 真实案例型。</p><p><span className="font-semibold">饱和度说明：</span>当前研究样本中已有同质教程，不能推断全网热点。</p></div>
          </article>
          <article className="rounded-3xl border border-[#9de1d2] bg-[#f1fbf7] p-6" aria-labelledby="action-outcome-heading">
            <p className="section-kicker">Action &amp; Outcome</p>
            <h2 id="action-outcome-heading" className="mt-2 text-xl font-semibold">{outcome.title}</h2>
            <div className="mt-4 space-y-3 text-sm"><p><span className="font-semibold">行动：</span>完成一轮用户问题频率研究。</p><p><span className="font-semibold">结果：</span>支持部分假设，证据和用户备注已绑定。</p><p><span className="font-semibold">Memory Update：</span>提高重复痛点置信度，保留旧判断和可撤回历史。</p></div>
            <span className="mt-5 inline-flex rounded-full bg-[#126d69] px-3 py-1 text-xs font-semibold text-white">用户批准 → 手工记录 → 回流记忆</span>
          </article>
        </section>
      </div>
    </main>
  );
}
