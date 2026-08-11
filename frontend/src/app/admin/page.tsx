"use client";

import { useCallback, useEffect, useState } from "react";
import { Leaderboard, type LeaderboardRow } from "@/components/Leaderboard";
import { apiGet, apiPatch, apiPost, apiUrl, getApiBaseUrl } from "@/lib/api";

type MarketStatus = {
  server_time_utc?: string;
  session_status?: string;
  market_online?: boolean;
  stocks_halted?: number;
  stocks_total?: number;
  ai_agents?: number;
  ai_agents_enabled?: number;
};

type SectorRow = {
  id: number;
  slug: string;
  name: string;
  stock_count?: number | null;
};

type SectorSummary = {
  sector_id: number;
  name: string;
  stock_count: number;
  sector_change_pct: string;
  top_gainer: { ticker: string; percent_change: string } | null;
  top_loser: { ticker: string; percent_change: string } | null;
  stocks: Array<{ ticker: string; percent_change: string }>;
};

type StockRow = {
  id: number;
  ticker: string;
  sector_id?: number | null;
  sector_name?: string | null;
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
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);
  const [leaderboardLoading, setLeaderboardLoading] = useState(true);
  const [sectors, setSectors] = useState<SectorRow[]>([]);
  const [sectorSummaries, setSectorSummaries] = useState<SectorSummary[]>([]);
  const [adminStocks, setAdminStocks] = useState<StockRow[]>([]);
  const [assignStockId, setAssignStockId] = useState<number | "">("");
  const [assignSectorId, setAssignSectorId] = useState<number | "">("");
  const [finImpact, setFinImpact] = useState("-8");
  const [techImpact, setTechImpact] = useState("-2");
  const [simSettings, setSimSettings] = useState<Record<string, unknown> | null>(null);
  const [ipoTicker, setIpoTicker] = useState("FTECH");
  const [ipoName, setIpoName] = useState("FutureTech Ltd");
  const [ipoPrice, setIpoPrice] = useState("100");
  const [ipoLot, setIpoLot] = useState("50");
  const [ipoTotal, setIpoTotal] = useState("1000");
  const [ipoWin, setIpoWin] = useState("250");
  const [ipoList, setIpoList] = useState<Array<Record<string, unknown>>>([]);

  const refreshOverview = useCallback(async (silent = false) => {
    try {
      await apiGet("/health");
      setApiOk(true);
      const [ov, lb, sec, sum, stk, sim, ipos] = await Promise.all([
        apiGet<Record<string, unknown>>("/admin/overview"),
        apiGet<LeaderboardRow[]>("/leaderboard"),
        apiGet<SectorRow[]>("/sectors"),
        apiGet<SectorSummary[]>("/market/sectors"),
        apiGet<StockRow[]>("/stocks"),
        apiGet<Record<string, unknown>>("/admin/simulation-settings").catch(() => null),
        apiGet<Array<Record<string, unknown>>>("/ipos").catch(() => []),
      ]);
      setOverview(ov);
      setMarketStatus(ov as MarketStatus);
      setLeaderboard(lb);
      setSectors(sec);
      setSectorSummaries(sum);
      setAdminStocks(stk);
      setSimSettings(sim);
      setIpoList(ipos);
      setLeaderboardLoading(false);
      if (!silent) setMsg("");
    } catch (e) {
      setApiOk(false);
      setOverview(null);
      setMarketStatus(null);
      setLeaderboardLoading(false);
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
      label: "Start AI scheduler",
      run: () => apiPost("/admin/ai/scheduler/start"),
    },
    {
      label: "Stop AI scheduler",
      run: () => apiPost("/admin/ai/scheduler/stop"),
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
          <input
            className="border border-line bg-background px-2 py-2"
            value={finImpact}
            onChange={(e) => setFinImpact(e.target.value)}
            placeholder="Financials impact %"
          />
          <input
            className="border border-line bg-background px-2 py-2"
            value={techImpact}
            onChange={(e) => setTechImpact(e.target.value)}
            placeholder="Technology impact %"
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
                  duration_minutes: 30,
                  decay_rate: 0.02,
                  fundamental_impact_pct: direction * Number(impact) * 8,
                  sector_impacts: {
                    financials: Number(finImpact),
                    technology: Number(techImpact),
                  },
                });
                return apiPost(`/admin/news/${created.id}/release`);
              },
              `Release news "${newsTitle}"?`,
            )
          }
        >
          {activeAction === "News" ? "Releasing news…" : "Create & release"}
        </button>
      </section>

      <section className="mt-8 border border-line bg-panel p-4">
        <h2 className="font-mono text-sm uppercase text-muted">Simulation settings</h2>
        {simSettings && (
          <pre className="mt-2 overflow-auto font-mono text-xs text-muted">
            {JSON.stringify(simSettings, null, 2)}
          </pre>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className="border border-line px-3 py-2 font-mono text-xs hover:border-accent"
            disabled={isBusy || apiOk === false}
            onClick={() =>
              runAction("Save sim settings", () =>
                apiPatch("/admin/simulation-settings", {
                  ai_tick_min_sec: 15,
                  ai_tick_max_sec: 30,
                  news_impact_tolerance_pct: 0.5,
                  ai_aggressiveness: 1.2,
                  news_reaction_strength: 1.2,
                }),
              )
            }
          >
            Reset defaults (15–30s AI)
          </button>
        </div>
      </section>

      <section className="mt-8 border border-line bg-panel p-4">
        <h2 className="font-mono text-sm uppercase text-muted">IPO management</h2>
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          <input className="border border-line bg-background px-2 py-2" value={ipoName} onChange={(e) => setIpoName(e.target.value)} placeholder="Company" />
          <input className="border border-line bg-background px-2 py-2" value={ipoTicker} onChange={(e) => setIpoTicker(e.target.value)} placeholder="Ticker" />
          <input className="border border-line bg-background px-2 py-2" value={ipoPrice} onChange={(e) => setIpoPrice(e.target.value)} placeholder="Issue price" />
          <input className="border border-line bg-background px-2 py-2" value={ipoLot} onChange={(e) => setIpoLot(e.target.value)} placeholder="Lot size" />
          <input className="border border-line bg-background px-2 py-2" value={ipoTotal} onChange={(e) => setIpoTotal(e.target.value)} placeholder="Total lots" />
          <input className="border border-line bg-background px-2 py-2" value={ipoWin} onChange={(e) => setIpoWin(e.target.value)} placeholder="Winning lots" />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className="bg-accent px-3 py-2 font-mono text-xs text-black disabled:opacity-50"
            disabled={isBusy || apiOk === false}
            onClick={() =>
              runAction("Create IPO", async () => {
                const tech = sectors.find((s) => s.slug === "technology");
                const created = await apiPost<Record<string, unknown>>("/admin/ipos", {
                  company_name: ipoName,
                  ticker: ipoTicker,
                  sector_id: tech?.id,
                  issue_price: ipoPrice,
                  lot_size: Number(ipoLot),
                  total_lots: Number(ipoTotal),
                  winning_lots: Number(ipoWin),
                  maximum_lots_per_user: 2,
                  status: "draft",
                });
                await apiPost(`/admin/ipos/${created.id}/open`);
                return created;
              })
            }
          >
            Create & open IPO
          </button>
        </div>
        <ul className="mt-3 space-y-2 font-mono text-xs">
          {ipoList.map((ipo) => (
            <li key={String(ipo.id)} className="flex flex-wrap items-center gap-2 border-t border-line/50 py-2">
              <span>
                {String(ipo.ticker)} · {String(ipo.status)} · ₹{String(ipo.issue_price)}
              </span>
              <button type="button" className="border border-line px-2 py-1" onClick={() => runAction("Close IPO", () => apiPost(`/admin/ipos/${ipo.id}/close`))}>Close</button>
              <button type="button" className="border border-line px-2 py-1" onClick={() => runAction("Allot IPO", () => apiPost(`/admin/ipos/${ipo.id}/allot`))}>Allot</button>
              <button type="button" className="border border-line px-2 py-1" onClick={() => runAction("List IPO", () => apiPost(`/admin/ipos/${ipo.id}/list`))}>List</button>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-8 border border-line bg-panel p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-mono text-sm uppercase text-muted">Sectors</h2>
          <button
            type="button"
            disabled={isBusy || apiOk === false}
            className="border border-line px-3 py-1 font-mono text-xs hover:border-accent disabled:opacity-50"
            onClick={() =>
              runAction("Seed sectors", () => apiPost("/admin/sectors/seed"))
            }
          >
            Seed / link sectors
          </button>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full font-mono text-xs">
            <thead>
              <tr className="text-left text-muted">
                <th className="pb-2 pr-3">Sector</th>
                <th className="pb-2 pr-3 text-right">Stocks</th>
                <th className="pb-2 pr-3 text-right">Change</th>
                <th className="pb-2 pr-3">Top gainer</th>
                <th className="pb-2">Top loser</th>
              </tr>
            </thead>
            <tbody>
              {sectorSummaries.map((row) => (
                <tr key={row.sector_id} className="border-t border-line/60">
                  <td className="py-2 pr-3">{row.name}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{row.stock_count}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {Number(row.sector_change_pct) > 0 ? "+" : ""}
                    {Number(row.sector_change_pct).toFixed(2)}%
                  </td>
                  <td className="py-2 pr-3 text-accent">
                    {row.top_gainer
                      ? `${row.top_gainer.ticker} ${Number(row.top_gainer.percent_change) > 0 ? "+" : ""}${Number(row.top_gainer.percent_change).toFixed(2)}%`
                      : "—"}
                  </td>
                  <td className="py-2 text-warn">
                    {row.top_loser
                      ? `${row.top_loser.ticker} ${Number(row.top_loser.percent_change).toFixed(2)}%`
                      : "—"}
                  </td>
                </tr>
              ))}
              {!sectorSummaries.length && (
                <tr>
                  <td colSpan={5} className="py-3 text-muted">
                    Bootstrap market or seed sectors to populate.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="mt-4 grid gap-2 md:grid-cols-3">
          <select
            className="border border-line bg-background px-2 py-2 font-mono text-xs"
            value={assignStockId}
            onChange={(e) =>
              setAssignStockId(e.target.value ? Number(e.target.value) : "")
            }
          >
            <option value="">Select stock…</option>
            {adminStocks.map((s) => (
              <option key={s.id} value={s.id}>
                {s.ticker}
                {s.sector_name ? ` (${s.sector_name})` : ""}
              </option>
            ))}
          </select>
          <select
            className="border border-line bg-background px-2 py-2 font-mono text-xs"
            value={assignSectorId}
            onChange={(e) =>
              setAssignSectorId(e.target.value ? Number(e.target.value) : "")
            }
          >
            <option value="">Assign sector…</option>
            {sectors.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={
              isBusy || apiOk === false || !assignStockId || !assignSectorId
            }
            className="border border-line bg-panel px-3 py-2 font-mono text-xs hover:border-accent disabled:opacity-50"
            onClick={() =>
              runAction("Assign sector", async () => {
                const result = await apiPatch(
                  `/admin/stocks/${assignStockId}/sector`,
                  { sector_id: assignSectorId },
                );
                await refreshOverview(true);
                return result;
              })
            }
          >
            Assign sector
          </button>
        </div>
      </section>

      <section className="mt-8 border border-line bg-panel p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-mono text-sm uppercase text-muted">Leaderboard</h2>
          <p className="font-mono text-xs text-muted">
            {leaderboard.length} human traders · ranked by return %
          </p>
        </div>
        <Leaderboard
          rows={leaderboard}
          variant="admin"
          loading={leaderboardLoading}
          maxRows={20}
        />
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
