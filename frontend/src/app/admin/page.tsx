"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

export default function AdminPage() {
  const [overview, setOverview] = useState<Record<string, unknown> | null>(null);
  const [msg, setMsg] = useState("");
  const [newsTitle, setNewsTitle] = useState("TechNova wins contract");
  const [newsBody, setNewsBody] = useState("Government awards ₹500cr deal.");
  const [tickers, setTickers] = useState("TECHNOVA");
  const [direction, setDirection] = useState(1);
  const [impact, setImpact] = useState("0.75");

  async function refresh() {
    try {
      setOverview(await apiGet("/admin/overview"));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "failed");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function run(label: string, fn: () => Promise<unknown>) {
    try {
      const result = await fn();
      setMsg(`${label}: ${JSON.stringify(result)}`);
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "error");
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-4 py-8">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">
            Exchange Control
          </p>
          <h1 className="text-3xl font-semibold">Admin / NSE Panel</h1>
        </div>
        <a href="/terminal" className="font-mono text-sm text-accent underline">
          Trading terminal
        </a>
      </div>

      <section className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Bootstrap market", () => apiPost("/admin/bootstrap")],
          ["Start session", () => apiPost("/admin/session/start")],
          ["Pause", () => apiPost("/admin/session/pause")],
          ["Resume", () => apiPost("/admin/session/resume")],
          ["Seed AI agents", () => apiPost("/admin/ai/seed")],
          ["Run AI tick", () => apiPost("/admin/ai/tick")],
          ["Halt all", () => apiPost("/admin/halt", { market_wide: true, halted: true })],
          ["Clear halt", () => apiPost("/admin/halt", { market_wide: true, halted: false })],
        ].map(([label, fn]) => (
          <button
            key={String(label)}
            className="border border-line bg-panel px-3 py-4 text-left hover:border-accent"
            onClick={() => run(String(label), fn as () => Promise<unknown>)}
          >
            {label}
          </button>
        ))}
      </section>

      <section className="mt-8 border border-line bg-panel p-4">
        <h2 className="font-mono text-sm uppercase text-muted">Release news</h2>
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          <input
            className="border border-line bg-background px-2 py-2"
            value={newsTitle}
            onChange={(e) => setNewsTitle(e.target.value)}
            placeholder="Title"
          />
          <input
            className="border border-line bg-background px-2 py-2"
            value={tickers}
            onChange={(e) => setTickers(e.target.value)}
            placeholder="Tickers"
          />
          <textarea
            className="border border-line bg-background px-2 py-2 md:col-span-2"
            value={newsBody}
            onChange={(e) => setNewsBody(e.target.value)}
          />
          <input
            type="number"
            className="border border-line bg-background px-2 py-2"
            value={direction}
            onChange={(e) => setDirection(Number(e.target.value))}
            placeholder="direction -1/0/1"
          />
          <input
            className="border border-line bg-background px-2 py-2"
            value={impact}
            onChange={(e) => setImpact(e.target.value)}
            placeholder="impact 0-1"
          />
        </div>
        <button
          className="mt-3 bg-accent px-4 py-2 font-mono text-sm text-black"
          onClick={() =>
            run("News", async () => {
              const created = await apiPost<{ id: number }>("/admin/news", {
                title: newsTitle,
                description: newsBody,
                affected_tickers: tickers,
                direction,
                impact,
                confidence: 0.9,
                duration_minutes: 20,
                decay_rate: 0.05,
                fundamental_impact_pct: direction * Number(impact) * 8,
              });
              return apiPost(`/admin/news/${created.id}/release`);
            })
          }
        >
          Create & release
        </button>
      </section>

      <section className="mt-8 border border-line bg-panel p-4">
        <h2 className="font-mono text-sm uppercase text-muted">Overview</h2>
        <pre className="mt-3 overflow-auto font-mono text-xs text-muted">
          {overview ? JSON.stringify(overview, null, 2) : "Loading…"}
        </pre>
        {msg && <p className="mt-3 font-mono text-xs text-accent">{msg}</p>}
      </section>
    </main>
  );
}
