"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiUrl, getApiBaseUrl } from "@/lib/api";

export default function AdminPage() {
  const [overview, setOverview] = useState<Record<string, unknown> | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [newsTitle, setNewsTitle] = useState("TechNova wins contract");
  const [newsBody, setNewsBody] = useState("Government awards ₹500cr deal.");
  const [tickers, setTickers] = useState("TECHNOVA");
  const [direction, setDirection] = useState(1);
  const [impact, setImpact] = useState("0.75");

  const refresh = useCallback(async () => {
    try {
      await apiGet("/health");
      setApiOk(true);
      setOverview(await apiGet("/admin/overview"));
      setMsg("");
    } catch (e) {
      setApiOk(false);
      setOverview(null);
      setMsg(e instanceof Error ? e.message : "Cannot reach API");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function run(label: string, fn: () => Promise<unknown>) {
    setBusy(true);
    setMsg(`Running: ${label}…`);
    try {
      const result = await fn();
      setMsg(`${label}: ${JSON.stringify(result)}`);
      setBusy(false);
      try {
        await apiGet("/health");
        setApiOk(true);
        setOverview(await apiGet("/admin/overview"));
      } catch (e) {
        setMsg(
          `${label}: ${JSON.stringify(result)} (overview refresh failed: ${
            e instanceof Error ? e.message : "error"
          })`,
        );
      }
    } catch (e) {
      setMsg(`${label} failed: ${e instanceof Error ? e.message : "error"}`);
      setBusy(false);
    }
  }

  const buttons: Array<[string, () => Promise<unknown>]> = [
    ["Bootstrap market", () => apiPost("/admin/bootstrap")],
    ["Start session", () => apiPost("/admin/session/start")],
    ["Pause", () => apiPost("/admin/session/pause")],
    ["Resume", () => apiPost("/admin/session/resume")],
    ["Seed AI agents", () => apiPost("/admin/ai/seed")],
    ["Run AI tick", () => apiPost("/admin/ai/tick")],
    ["Halt all", () => apiPost("/admin/halt", { market_wide: true, halted: true })],
    ["Clear halt", () => apiPost("/admin/halt", { market_wide: true, halted: false })],
  ];

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-4 py-8">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">
            Exchange Control
          </p>
          <h1 className="text-3xl font-semibold">Admin / NSE Panel</h1>
          <p className="mt-2 font-mono text-xs text-muted">
            API: {apiUrl("/health")} ·{" "}
            {apiOk === null ? "checking…" : apiOk ? "connected" : "disconnected"}
          </p>
        </div>
        <a href="/terminal" className="font-mono text-sm text-accent underline">
          Trading terminal
        </a>
      </div>

      {apiOk === false && (
        <div className="mt-4 border border-warn bg-panel p-3 text-sm text-warn">
          Cannot reach backend at <strong>{getApiBaseUrl()}</strong>. Start the API with:
          <code className="ml-1 block mt-1 font-mono text-xs">
            cd backend &amp; .\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
          </code>
        </div>
      )}

      {msg && (
        <div className="mt-4 border border-line bg-panel p-3 font-mono text-xs text-accent">
          {msg}
        </div>
      )}

      <section className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {buttons.map(([label, fn]) => (
          <button
            key={label}
            type="button"
            disabled={busy || apiOk === false}
            className="border border-line bg-panel px-3 py-4 text-left hover:border-accent disabled:opacity-50"
            onClick={() => run(label, fn)}
          >
            {busy ? "…" : label}
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
          type="button"
          disabled={busy || apiOk === false}
          className="mt-3 bg-accent px-4 py-2 font-mono text-sm text-black disabled:opacity-50"
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
      </section>
    </main>
  );
}
