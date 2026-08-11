"use client";

/**
 * Simple participant terminal — old simplicity + new features.
 * Wallet / P&L / price panel are always visible after login.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Leaderboard, type LeaderboardRow } from "@/components/Leaderboard";
import { apiDelete, apiGet, apiPost, wsUrl } from "@/lib/api";

const UP = "#22c55e";
const DOWN = "#ef4444";

type Stock = {
  id: number;
  ticker: string;
  company_name: string;
  last_traded_price: string;
  percent_change: string | null;
  sector_id?: number | null;
  sector_name?: string | null;
};

type SectorInfo = { id: number; name: string; stock_count?: number | null };

type Wallet = {
  available_cash: string;
  cash_blocked_ipo: string;
  invested: string;
  portfolio_value: string;
  total_pnl: string;
  return_pct: string;
};

type Portfolio = {
  cash: string;
  available_cash?: string;
  cash_blocked_ipo?: string;
  invested?: string;
  portfolio_value: string;
  total_pnl: string;
  holdings: Array<{
    ticker: string | null;
    quantity: number;
    unrealized_pnl: string | null;
  }>;
};

type News = { id: number; title: string; description: string; effective_impact?: string };
type Conditional = {
  id: number;
  stock_id: number;
  condition_type: string;
  quantity: number;
  trigger_price: string;
  status: string;
};
type IPO = {
  id: number;
  company_name: string;
  ticker: string;
  issue_price: string;
  lot_size: number;
  maximum_lots_per_user: number;
  status: string;
};
type ExecutionSummary = { executed: boolean; message: string };

function num(v: string | number | null | undefined): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}
function signClass(v: string | number | null | undefined): string {
  const n = num(v);
  if (n > 0) return "text-[#22c55e]";
  if (n < 0) return "text-[#ef4444]";
  return "text-white";
}
function fmtPct(v: string | null | undefined): string {
  const n = num(v);
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
}
function fmtMoney(v: string | number | null | undefined): string {
  return `₹${num(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export default function TerminalPage() {
  const [traderId, setTraderId] = useState<number | null>(null);
  const [traderName, setTraderName] = useState("Trader");
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [news, setNews] = useState<News[]>([]);
  const [trades, setTrades] = useState<Array<Record<string, unknown>>>([]);
  const [qty, setQty] = useState(10);
  const [status, setStatus] = useState("—");
  const [priceSeries, setPriceSeries] = useState<Array<{ t: string; px: number }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [resultMsg, setResultMsg] = useState<string | null>(null);
  const [confirmSide, setConfirmSide] = useState<"buy" | "sell" | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [extrasOpen, setExtrasOpen] = useState(false);
  const [limitPrice, setLimitPrice] = useState("100");
  const [limitSide, setLimitSide] = useState<"buy" | "sell">("buy");
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);
  const [sectors, setSectors] = useState<SectorInfo[]>([]);
  const [sectorFilter, setSectorFilter] = useState<number | "all">("all");
  const [conditionals, setConditionals] = useState<Conditional[]>([]);
  const [slPrice, setSlPrice] = useState("");
  const [tpPrice, setTpPrice] = useState("");
  const [slQty, setSlQty] = useState(10);
  const [tpQty, setTpQty] = useState(10);
  const [ipos, setIpos] = useState<IPO[]>([]);
  const [ipoLots, setIpoLots] = useState(1);
  const [breaking, setBreaking] = useState<News | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const selected = useMemo(
    () => stocks.find((s) => s.id === selectedId) ?? null,
    [stocks, selectedId],
  );

  const visibleStocks = useMemo(() => {
    if (sectorFilter === "all") return stocks;
    return stocks.filter((s) => s.sector_id === sectorFilter);
  }, [stocks, sectorFilter]);

  const chartStroke = useMemo(() => {
    if (priceSeries.length < 2) return UP;
    return priceSeries[priceSeries.length - 1].px >= priceSeries[0].px ? UP : DOWN;
  }, [priceSeries]);

  const holdingQty = useMemo(() => {
    if (!selected || !portfolio) return 0;
    return portfolio.holdings.find((h) => h.ticker === selected.ticker)?.quantity ?? 0;
  }, [selected, portfolio]);

  const cash = wallet?.available_cash ?? portfolio?.available_cash ?? portfolio?.cash;
  const pnl = wallet?.total_pnl ?? portfolio?.total_pnl;
  const invested = wallet?.invested ?? portfolio?.invested;
  const portValue = wallet?.portfolio_value ?? portfolio?.portfolio_value;
  const blocked = wallet?.cash_blocked_ipo ?? portfolio?.cash_blocked_ipo ?? "0";
  const ret = wallet?.return_pct;

  const refresh = useCallback(async () => {
    try {
      const [s, n, lb, sec, openIpos] = await Promise.all([
        apiGet<Stock[]>("/stocks"),
        apiGet<News[]>("/news"),
        apiGet<LeaderboardRow[]>("/leaderboard"),
        apiGet<SectorInfo[]>("/sectors"),
        apiGet<IPO[]>("/ipos/open").catch(() => [] as IPO[]),
      ]);
      setStocks(s);
      setNews(n);
      setLeaderboard(lb);
      setSectors(sec);
      setIpos(openIpos);

      if (!selectedId && s.length) {
        setSelectedId(s[0].id);
        setLimitPrice(s[0].last_traded_price);
      }

      if (traderId) {
        const [p, w, cond, t] = await Promise.all([
          apiGet<Portfolio>(`/traders/${traderId}/portfolio`),
          apiGet<Wallet>(`/traders/${traderId}/wallet`).catch(() => null),
          apiGet<Conditional[]>(`/traders/${traderId}/conditionals`).catch(() => []),
          apiGet<Array<Record<string, unknown>>>(`/trades?trader_id=${traderId}`).catch(() => []),
        ]);
        setPortfolio(p);
        if (w) setWallet(w);
        setConditionals(cond);
        setTrades(t);
      }

      if (selectedId) {
        const stockTrades = await apiGet<Array<{ id: number; price: string; executed_at?: string }>>(
          `/trades?stock_id=${selectedId}&limit=120`,
        );
        const sorted = [...stockTrades].sort((a, b) =>
          String(a.executed_at ?? a.id).localeCompare(String(b.executed_at ?? b.id)),
        );
        const stock = s.find((x) => x.id === selectedId);
        if (sorted.length > 0) {
          setPriceSeries(
            sorted.map((tr) => ({
              t: tr.executed_at
                ? new Date(tr.executed_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })
                : `#${tr.id}`,
              px: num(tr.price),
            })),
          );
        } else if (stock) {
          setPriceSeries([{ t: "now", px: num(stock.last_traded_price) }]);
        }
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load market data");
    }
  }, [selectedId, traderId]);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 5000);
    return () => window.clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(wsUrl());
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          setStatus(msg.event ?? "EVENT");
          if (msg.event === "NEWS_RELEASED") setBreaking(msg as News);
          if (msg.event === "STOP_LOSS_TRIGGERED" || msg.event === "TAKE_PROFIT_TRIGGERED") {
            setToast(msg.message ?? msg.event);
          }
          if (
            [
              "TRADE_EXECUTED",
              "PRICE_UPDATED",
              "NEWS_RELEASED",
              "PORTFOLIO_UPDATED",
              "WALLET_UPDATED",
              "CONDITIONAL_UPDATED",
              "IPO_APPLICATION_UPDATED",
              "IPO_ALLOTMENT",
              "IPO_LISTED",
              "STOP_LOSS_TRIGGERED",
              "TAKE_PROFIT_TRIGGERED",
            ].includes(msg.event)
          ) {
            refresh();
          }
        } catch {
          /* ignore */
        }
      };
      ws.onopen = () => setStatus("LIVE");
      ws.onclose = () => setStatus("OFF");
    } catch {
      setStatus("OFF");
    }
    return () => ws?.close();
  }, [refresh]);

  useEffect(() => {
    const saved = localStorage.getItem("mse_trader_id");
    if (saved) setTraderId(Number(saved));
  }, []);

  async function join() {
    const created = await apiPost<{ id: number }>("/traders", { name: traderName || "Trader" });
    setTraderId(created.id);
    localStorage.setItem("mse_trader_id", String(created.id));
  }

  async function executeMarketOrder(side: "buy" | "sell") {
    if (!traderId || !selectedId) return;
    setSubmitting(true);
    setError(null);
    setResultMsg(null);
    try {
      const res = await apiPost<{
        rejected?: boolean;
        execution_summary?: ExecutionSummary;
        detail?: string;
      }>("/orders", {
        trader_id: traderId,
        stock_id: selectedId,
        side,
        order_type: "market",
        quantity: qty,
        price: null,
      });
      if (res.execution_summary) {
        setResultMsg(res.execution_summary.message);
        if (!res.execution_summary.executed) setError(res.execution_summary.message);
      } else if (res.rejected) {
        setError(res.detail ?? "Order could not be completed");
      }
      setConfirmSide(null);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Order failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function setConditional(type: "stop_loss" | "take_profit") {
    if (!traderId || !selectedId) return;
    try {
      await apiPost("/conditionals", {
        trader_id: traderId,
        stock_id: selectedId,
        condition_type: type,
        quantity: type === "stop_loss" ? slQty : tpQty,
        trigger_price: type === "stop_loss" ? slPrice : tpPrice,
      });
      setToast(type === "stop_loss" ? "Stop loss set" : "Take profit set");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not set condition");
    }
  }

  const panel = "border border-white/15";
  const inputCls =
    "w-full border border-white/25 bg-black px-2 py-2 text-white outline-none focus:border-white";

  return (
    <div className="min-h-screen bg-black font-mono text-sm text-white">
      <header className={`${panel} flex flex-wrap items-center justify-between gap-2 border-x-0 border-t-0 px-4 py-2 text-xs`}>
        <span>MSE · {status}</span>
        <a className="underline" href="/admin">Admin</a>
      </header>

      {!traderId ? (
        <div className="mx-auto max-w-sm px-4 py-16">
          <p className="text-white/50">Enter your name to start trading</p>
          <input className={`${inputCls} mt-3`} value={traderName} onChange={(e) => setTraderName(e.target.value)} />
          <button type="button" className="mt-4 w-full border border-[#22c55e] py-2 text-[#22c55e]" onClick={join}>
            Start
          </button>
          {error && <p className="mt-3 text-[#ef4444]">{error}</p>}
        </div>
      ) : (
        <div className="mx-auto max-w-3xl px-4 py-4">
          {/* WALLET — always visible */}
          <section className={`${panel} p-3`}>
            <p className="text-[10px] uppercase tracking-wider text-white/40">Wallet</p>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs md:grid-cols-3">
              <div>
                <p className="text-white/40">Available cash</p>
                <p className="mt-1 text-base">{fmtMoney(cash)}</p>
              </div>
              <div>
                <p className="text-white/40">Invested</p>
                <p className="mt-1 text-base">{fmtMoney(invested)}</p>
              </div>
              <div>
                <p className="text-white/40">Portfolio value</p>
                <p className="mt-1 text-base">{fmtMoney(portValue)}</p>
              </div>
              <div>
                <p className="text-white/40">Current profit/loss</p>
                <p className={`mt-1 text-base ${signClass(pnl)}`}>{fmtMoney(pnl)}</p>
              </div>
              <div>
                <p className="text-white/40">Return</p>
                <p className={`mt-1 text-base ${signClass(ret)}`}>{ret != null ? fmtPct(ret) : "—"}</p>
              </div>
              <div>
                <p className="text-white/40">IPO blocked</p>
                <p className="mt-1 text-base">{fmtMoney(blocked)}</p>
              </div>
            </div>
            <p className="mt-3 truncate text-xs text-white/50">
              Holdings:{" "}
              {(portfolio?.holdings ?? [])
                .filter((h) => h.quantity > 0)
                .map((h) => `${h.ticker} ${h.quantity}`)
                .join(" · ") || "None"}
            </p>
          </section>

          {/* Sector chips (simple) */}
          <div className="mt-4 flex flex-wrap gap-1">
            <button
              type="button"
              className={`px-3 py-1 text-xs ${sectorFilter === "all" ? "bg-white text-black" : "border border-white/20"}`}
              onClick={() => setSectorFilter("all")}
            >
              All
            </button>
            {sectors
              .filter((s) => (s.stock_count ?? 0) > 0)
              .map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`px-3 py-1 text-xs ${sectorFilter === s.id ? "bg-white text-black" : "border border-white/20"}`}
                  onClick={() => setSectorFilter(s.id)}
                >
                  {s.name}
                </button>
              ))}
          </div>

          {/* Stock picker */}
          <div className="mt-3 flex flex-wrap gap-1">
            {visibleStocks.map((s) => (
              <button
                key={s.id}
                type="button"
                className={`px-3 py-1 text-xs ${selectedId === s.id ? "bg-white text-black" : "border border-white/20"}`}
                onClick={() => {
                  setSelectedId(s.id);
                  setLimitPrice(s.last_traded_price);
                  setPriceSeries([]);
                }}
              >
                {s.ticker}
              </button>
            ))}
          </div>

          {/* PRICE PANEL */}
          <section className={`${panel} mt-4 p-4`}>
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-[10px] uppercase tracking-wider text-white/40">Price</p>
                <h1 className="mt-1 text-xl">{selected?.company_name ?? "—"}</h1>
                <p className="text-xs text-white/50">
                  {selected?.ticker}
                  {selected?.sector_name ? ` · ${selected.sector_name}` : ""}
                </p>
              </div>
              <div className="text-right">
                <p className="text-[10px] uppercase text-white/40">Current price</p>
                <p className={`text-3xl tabular-nums ${signClass(selected?.percent_change)}`}>
                  {selected ? num(selected.last_traded_price).toFixed(2) : "—"}
                </p>
                <p className={`text-sm ${signClass(selected?.percent_change)}`}>
                  {selected ? fmtPct(selected.percent_change) : "—"}
                </p>
              </div>
            </div>
            <div className="mt-4 h-40 border border-white/10 p-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={priceSeries}>
                  <XAxis dataKey="t" hide />
                  <YAxis
                    domain={["auto", "auto"]}
                    width={52}
                    tick={{ fill: "#888", fontSize: 10 }}
                    tickFormatter={(v) => Number(v).toFixed(2)}
                  />
                  <Tooltip contentStyle={{ background: "#000", border: "1px solid #333", fontSize: 11 }} />
                  <Line type="monotone" dataKey="px" stroke={chartStroke} strokeWidth={1.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>

          {/* Trade */}
          <div className={`${panel} mt-4 p-4`}>
            <label className="text-xs text-white/40">Quantity</label>
            <input
              type="number"
              className={`${inputCls} mt-1`}
              value={qty}
              min={1}
              onChange={(e) => setQty(Number(e.target.value))}
            />
            <p className="mt-1 text-[10px] text-white/40">Your holding in this stock: {holdingQty}</p>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <button
                type="button"
                disabled={submitting}
                className="bg-[#22c55e] py-3 text-black disabled:opacity-40"
                onClick={() => setConfirmSide("buy")}
              >
                BUY NOW
              </button>
              <button
                type="button"
                disabled={submitting}
                className="bg-[#ef4444] py-3 text-black disabled:opacity-40"
                onClick={() => setConfirmSide("sell")}
              >
                SELL NOW
              </button>
            </div>
          </div>

          {resultMsg && (
            <pre className="mt-4 whitespace-pre-wrap border border-white/20 p-3 text-xs text-white/90">{resultMsg}</pre>
          )}
          {error && <p className="mt-2 text-xs text-[#ef4444]">{error}</p>}

          {/* Recent trades */}
          <div className={`${panel} mt-4 p-3`}>
            <p className="text-xs text-white/40">Your recent trades</p>
            <ul className="mt-2 space-y-1 text-xs">
              {trades.slice(0, 8).map((t) => (
                <li key={String(t.id)}>
                  {String(t.quantity)} shares @ ₹{String(t.price)}
                </li>
              ))}
              {!trades.length && <li className="text-white/30">No trades yet</li>}
            </ul>
          </div>

          {/* News */}
          <div className={`${panel} mt-4 p-3`}>
            <p className="text-xs text-white/40">News</p>
            <ul className="mt-2 space-y-2 text-xs">
              {news.slice(0, 5).map((n) => (
                <li key={n.id}>
                  <p className={signClass(n.effective_impact)}>{n.title}</p>
                  <p className="text-white/50">{n.description}</p>
                </li>
              ))}
              {!news.length && <li className="text-white/30">No news</li>}
            </ul>
          </div>

          <div className="mt-4">
            <Leaderboard rows={leaderboard} variant="terminal" highlightTraderId={traderId} maxRows={10} />
          </div>

          {/* Extra features — collapsed by default */}
          <button
            type="button"
            className="mt-6 text-xs text-white/50 underline"
            onClick={() => setExtrasOpen((v) => !v)}
          >
            {extrasOpen ? "Hide stop loss / take profit / IPO" : "Stop loss, take profit & IPO"}
          </button>

          {extrasOpen && (
            <div className={`${panel} mt-3 space-y-4 p-4`}>
              {holdingQty > 0 && selected && (
                <div className="grid gap-3 md:grid-cols-2">
                  <div>
                    <p className="text-xs text-white/40">Stop loss</p>
                    <input className={`${inputCls} mt-1`} placeholder="Trigger ₹" value={slPrice} onChange={(e) => setSlPrice(e.target.value)} />
                    <input type="number" className={`${inputCls} mt-1`} value={slQty} onChange={(e) => setSlQty(Number(e.target.value))} />
                    <button type="button" className="mt-2 w-full border border-[#ef4444] py-2 text-xs text-[#ef4444]" onClick={() => setConditional("stop_loss")}>
                      SET STOP LOSS
                    </button>
                  </div>
                  <div>
                    <p className="text-xs text-white/40">Take profit</p>
                    <input className={`${inputCls} mt-1`} placeholder="Target ₹" value={tpPrice} onChange={(e) => setTpPrice(e.target.value)} />
                    <input type="number" className={`${inputCls} mt-1`} value={tpQty} onChange={(e) => setTpQty(Number(e.target.value))} />
                    <button type="button" className="mt-2 w-full border border-[#22c55e] py-2 text-xs text-[#22c55e]" onClick={() => setConditional("take_profit")}>
                      SET TAKE PROFIT
                    </button>
                  </div>
                </div>
              )}

              <div>
                <p className="text-xs text-white/40">Active conditions</p>
                <ul className="mt-2 space-y-1 text-xs">
                  {conditionals
                    .filter((c) => c.status === "active")
                    .map((c) => {
                      const st = stocks.find((x) => x.id === c.stock_id);
                      return (
                        <li key={c.id} className="flex justify-between gap-2">
                          <span>
                            {st?.ticker ?? c.stock_id} · {c.condition_type === "stop_loss" ? "SL" : "TP"}{" "}
                            {c.quantity} @ ₹{c.trigger_price}
                          </span>
                          <button
                            type="button"
                            className="text-[#ef4444]"
                            onClick={async () => {
                              await apiDelete(`/conditionals/${c.id}?trader_id=${traderId}`);
                              await refresh();
                            }}
                          >
                            Cancel
                          </button>
                        </li>
                      );
                    })}
                  {!conditionals.some((c) => c.status === "active") && (
                    <li className="text-white/30">None</li>
                  )}
                </ul>
              </div>

              {ipos.length > 0 && (
                <div>
                  <p className="text-xs text-white/40">Open IPOs</p>
                  {ipos.map((ipo) => (
                    <div key={ipo.id} className="mt-2 border-t border-white/10 pt-2 text-xs">
                      <p>
                        {ipo.company_name} ({ipo.ticker}) · ₹{ipo.issue_price} · lot {ipo.lot_size}
                      </p>
                      <div className="mt-2 flex gap-2">
                        <input
                          type="number"
                          className={inputCls}
                          value={ipoLots}
                          min={1}
                          max={ipo.maximum_lots_per_user}
                          onChange={(e) => setIpoLots(Number(e.target.value))}
                        />
                        <button
                          type="button"
                          className="border border-white/30 px-3"
                          onClick={async () => {
                            try {
                              await apiPost(`/ipos/${ipo.id}/apply`, {
                                trader_id: traderId,
                                requested_lots: ipoLots,
                              });
                              setToast("IPO applied");
                              await refresh();
                            } catch (e) {
                              setError(e instanceof Error ? e.message : "IPO failed");
                            }
                          }}
                        >
                          APPLY
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <button
            type="button"
            className="mt-4 text-xs text-white/50 underline"
            onClick={() => setAdvancedOpen((v) => !v)}
          >
            {advancedOpen ? "Hide advanced" : "Advanced orders & order book"}
          </button>
          {advancedOpen && (
            <div className={`${panel} mt-3 space-y-3 p-4`}>
              <div className="flex gap-2">
                <button
                  type="button"
                  className={`flex-1 py-1 text-xs ${limitSide === "buy" ? "bg-[#22c55e] text-black" : "border border-white/20"}`}
                  onClick={() => setLimitSide("buy")}
                >
                  Buy
                </button>
                <button
                  type="button"
                  className={`flex-1 py-1 text-xs ${limitSide === "sell" ? "bg-[#ef4444] text-black" : "border border-white/20"}`}
                  onClick={() => setLimitSide("sell")}
                >
                  Sell
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <input type="number" className={inputCls} value={qty} onChange={(e) => setQty(Number(e.target.value))} />
                <input className={inputCls} value={limitPrice} onChange={(e) => setLimitPrice(e.target.value)} />
              </div>
              <button
                type="button"
                className="w-full border border-white/30 py-2 text-xs"
                onClick={async () => {
                  if (!traderId || !selectedId) return;
                  await apiPost("/orders", {
                    trader_id: traderId,
                    stock_id: selectedId,
                    side: limitSide,
                    order_type: "limit",
                    quantity: qty,
                    price: limitPrice,
                  });
                  await refresh();
                }}
              >
                Place limit order
              </button>
            </div>
          )}
        </div>
      )}

      {breaking && (
        <div className="fixed bottom-4 right-4 z-50 w-full max-w-sm border border-[#ef4444]/60 bg-black p-4">
          <p className="text-xs text-[#ef4444]">BREAKING NEWS</p>
          <p className="mt-2 text-sm">{breaking.title}</p>
          <p className="mt-1 text-xs text-white/60">{breaking.description}</p>
          <button type="button" className="mt-3 text-xs text-white/50" onClick={() => setBreaking(null)}>
            Dismiss
          </button>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-4 left-4 z-50 max-w-sm whitespace-pre-wrap border border-white/25 bg-black p-3 text-xs">
          {toast}
          <button type="button" className="ml-3 text-white/40" onClick={() => setToast(null)}>
            ×
          </button>
        </div>
      )}

      {confirmSide && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4">
          <div className="w-full max-w-sm border border-white/25 bg-black p-4">
            <p className="text-xs text-white/40">Confirm</p>
            <p className="mt-2 text-lg">
              {confirmSide === "buy" ? "Buy" : "Sell"} {qty} shares of {selected.ticker}
            </p>
            <p className="mt-1 text-xs text-white/50">
              Current price ₹{num(selected.last_traded_price).toFixed(2)}
            </p>
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                className="flex-1 border border-white/25 py-2 text-xs"
                disabled={submitting}
                onClick={() => setConfirmSide(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className={`flex-1 py-2 text-xs text-black ${confirmSide === "buy" ? "bg-[#22c55e]" : "bg-[#ef4444]"}`}
                disabled={submitting}
                onClick={() => executeMarketOrder(confirmSide)}
              >
                {submitting ? "…" : "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
