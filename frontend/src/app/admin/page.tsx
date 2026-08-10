"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiUrl, getApiBaseUrl } from "@/lib/api";

type MarketStatus = {
  server_time_utc?: string;
  session_status?: string;
  market_online?: boolean;
  stocks_halted?: number;
  stocks_total?: number;
  ai_agents?: number;
  ai_agents_enabled?: number;
};

type AdminAction = {
  label: string;
  run: () => Promise<unknown>;
  confirm?: string;
  variant?: "danger" | "default";
};

const BTN_BASE =
  "border px-3 py-4 text-left font-mono text-sm transition-all duration-150 touch-manipulation active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50";

export default function AdminPage() {
  const [overview, setOverview] = useState<Record<string, unknown> | null>(null);
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null);
  const [clock, setClock] = useState("");
  const [msg, setMsg] = useState("");
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [newsTitle, setNewsTitle] = useState("TechNova wins contract");
  const [newsBody, setNewsBody] = useState("Government awards ₹500cr deal.");
  const [tickers, setTickers] = useState("TECHNOVA");
  const [direction, setDirection] = useState(1);
  const [impact, setImpact] = useState("0.75");

  const refreshOverview = useCallback(async (silent = false) => {
    try {
      await apiGet("/health");
      setApiOk(true);
      const ov = await apiGet<Record<string, unknown>>("/admin/overview");
      setOverview(ov);
      setMarketStatus(ov as MarketStatus);
      if (!silent) setMsg("");
    } catch (e) {
      setApiOk(false);
      setOverview(null);
      setMarketStatus(null);
      if (!silent) {
        setMsg(e instanceof Error ? e.message : "Cannot reach API");
      }
    }
  }, []);

  useEffect(() => {
    refreshOverview(true);
    const poll = window.setInterval(() => refreshOverview(true), 5000);
    return () => window.clearInterval(poll);
  }, [refreshOverview]);

  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleString());
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);

  async function runAction(label: string, fn: () => Promise<unknown>, confirm?: string) {
    if (confirm && !window.confirm(confirm)) return;

    setActiveAction(label);
    setMsg(`Running: ${label}…`);
    try {
      const result = await fn();
      setMsg(`${label}: ${JSON.stringify(result)}`);
      await refreshOverview(true);
    } catch (e) {
      setMsg(`${label} failed: ${e instanceof Error ? e.message : "error"}`);
    } finally {
      setActiveAction(null);
    }
  }

  const actions: AdminAction[] = [
    {
      label: "Bootstrap market",
      confirm: "Bootstrap the market (seed stocks, AI agents, and open a session)?",
      run: () => apiPost("/admin/bootstrap"),
    },
    {
      label: "Start session",
      run: () => apiPost("/admin/session/start"),
    },
    {
      label: "Pause",
      confirm: "Pause the market? New orders will be rejected until resumed.",
      variant: "danger",
      run: () => apiPost("/admin/session/pause"),
    },
    {
      label: "Resume",
      run: () => apiPost("/admin/session/resume"),
    },
    {
      label: "Seed AI agents",
      run: () => apiPost("/admin/ai/seed"),
    },
    {
      label: "Run AI tick",
      run: () => apiPost("/admin/ai/tick"),
    },
    {
      label: "Halt all",
      confirm: "Halt all stocks? Trading will stop on every ticker.",
      variant: "danger",
      run: () => apiPost("/admin/halt", { market_wide: true, halted: true }),
    },
    {
      label: "Clear halt",
      run: () => apiPost("/admin/halt", { market_wide: true, halted: false }),
    },
  ];

  const marketOnline = marketStatus?.market_online === true;
  const sessionStatus = marketStatus?.session_status ?? "unknown";
  const showMarketAlert = apiOk === false || !marketOnline || sessionStatus === "paused";
  const isBusy = activeAction !== null;

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-4 py-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
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
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={isBusy}
            className="border border-line bg-panel px-3 py-2 font-mono text-xs hover:border-accent disabled:opacity-50"
            onClick={() => refreshOverview()}
          >
            Refresh status
          </button>
          <a href="/terminal" className="font-mono text-sm text-accent underline">
            Trading terminal
          </a>
        </div>
      </div>

      <section className="mt-6 grid gap-3 border border-line bg-panel p-4 sm:grid-cols-3">
        <div>
          <p className="font-mono text-xs uppercase text-muted">Exchange clock</p>
          <p className="mt-1 font-mono text-lg">{clock}</p>
        </div>
        <div>
          <p className="font-mono text-xs uppercase text-muted">Market status</p>
          <p className={`mt-1 font-mono text-lg ${marketOnline ? "text-accent" : "text-warn"}`}>
            {apiOk === false ? "OFFLINE (API)" : marketOnline ? "ONLINE" : `NOT TRADING (${sessionStatus})`}
          </p>
          <p className="font-mono text-xs text-muted">
            Session: {sessionStatus} · AI bots: {marketStatus?.ai_agents_enabled ?? "—"}/
            {marketStatus?.ai_agents ?? "—"}
          </p>
        </div>
        <div>
          <p className="font-mono text-xs uppercase text-muted">Stocks</p>
          <p className="mt-1 font-mono text-lg">
            {marketStatus?.stocks_total ?? "—"} total · {marketStatus?.stocks_halted ?? "—"} halted
          </p>
        </div>
      </section>

      {showMarketAlert && (
        <div className="mt-4 border border-warn bg-panel p-3 text-sm text-warn">
          {apiOk === false ? (
            <>
              Cannot reach backend at <strong>{getApiBaseUrl()}</strong>. Use Refresh status after
              starting the API.
            </>
          ) : sessionStatus === "paused" ? (
            <>
              Market session is <strong>paused</strong>. Resume or start a session — orders will be
              rejected.
            </>
          ) : (
            <>
              Market is <strong>not online</strong>. Bootstrap market or start a session, and clear
              halt if needed.
            </>
          )}
        </div>
      )}

      {apiOk === false && (
        <div className="mt-4 border border-warn bg-panel p-3 text-sm text-warn">
          Start the API with:
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
        {actions.map(({ label, run, confirm, variant }) => {
          const loading = activeAction === label;
          const disabled = isBusy || apiOk === false;
          return (
            <button
              key={label}
              type="button"
              disabled={disabled}
              className={`${BTN_BASE} ${
                variant === "danger"
                  ? "border-warn/60 bg-panel hover:border-warn"
                  : "border-line bg-panel hover:border-accent"
              } ${loading ? "border-accent ring-1 ring-accent/40" : ""}`}
              onClick={() => runAction(label, run, confirm)}
            >
              {loading ? `Running ${label}…` : label}
            </button>
          );
        })}
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
          disabled={isBusy || apiOk === false}
          className={`mt-3 bg-accent px-4 py-3 font-mono text-sm text-black transition active:scale-[0.98] disabled:opacity-50 ${activeAction === "News" ? "opacity-70" : ""}`}
          onClick={() =>
            runAction(
              "News",
              async () => {
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
              },
              `Release news "${newsTitle}" for ${tickers}?`,
            )
          }
        >
          {activeAction === "News" ? "Releasing news…" : "Create & release"}
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
