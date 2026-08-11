"use client";

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
};

type Portfolio = {
  cash: string;
  portfolio_value: string;
  total_pnl: string;
  holdings: Array<{
    ticker: string | null;
    quantity: number;
    unrealized_pnl: string | null;
  }>;
};

type Book = {
  best_bid: string | null;
  best_ask: string | null;
  spread: string | null;
  bids: Array<{ price: string; quantity: number }>;
  asks: Array<{ price: string; quantity: number }>;
};

type News = { id: number; title: string; description: string; effective_impact?: string };

type ExecutionSummary = {
  status: string;
  executed: boolean;
  filled_quantity: number;
  average_price: string | null;
  total_notional: string | null;
  ticker: string;
  side: string;
  message: string;
};

function num(v: string | number | null | undefined): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function signClass(value: string | number | null | undefined): string {
  const n = num(value);
  if (n > 0) return "text-[#22c55e]";
  if (n < 0) return "text-[#ef4444]";
  return "text-white";
}

function fmtPct(value: string | null | undefined): string {
  const n = num(value);
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
}

export default function TerminalPage() {
  const [traderId, setTraderId] = useState<number | null>(null);
  const [traderName, setTraderName] = useState("Trader");
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [book, setBook] = useState<Book | null>(null);
  const [news, setNews] = useState<News[]>([]);
  const [orders, setOrders] = useState<Array<Record<string, unknown>>>([]);
  const [trades, setTrades] = useState<Array<Record<string, unknown>>>([]);
  const [qty, setQty] = useState(10);
  const [status, setStatus] = useState("—");
  const [priceSeries, setPriceSeries] = useState<Array<{ t: string; px: number }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [resultMsg, setResultMsg] = useState<string | null>(null);
  const [confirmSide, setConfirmSide] = useState<"buy" | "sell" | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [limitPrice, setLimitPrice] = useState("100");
  const [limitSide, setLimitSide] = useState<"buy" | "sell">("buy");
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);

  const selected = useMemo(
    () => stocks.find((s) => s.id === selectedId) ?? null,
    [stocks, selectedId],
  );

  const chartStroke = useMemo(() => {
    if (priceSeries.length < 2) return UP;
    return priceSeries[priceSeries.length - 1].px >= priceSeries[0].px ? UP : DOWN;
  }, [priceSeries]);

  const refresh = useCallback(async () => {
    try {
      const [s, n, lb] = await Promise.all([
        apiGet<Stock[]>("/stocks"),
        apiGet<News[]>("/news"),
        apiGet<LeaderboardRow[]>("/leaderboard"),
      ]);
      setStocks(s);
      setNews(n);
      setLeaderboard(lb);
      if (!selectedId && s.length) {
        setSelectedId(s[0].id);
        setLimitPrice(s[0].last_traded_price);
      }
      if (traderId) {
        const [p, o, t] = await Promise.all([
          apiGet<Portfolio>(`/traders/${traderId}/portfolio`),
          apiGet<Array<Record<string, unknown>>>(`/orders?trader_id=${traderId}`),
          apiGet<Array<Record<string, unknown>>>(`/trades?trader_id=${traderId}`),
        ]);
        setPortfolio(p);
        setOrders(o);
        setTrades(t);
      }
      if (selectedId) {
        const [b, stockTrades] = await Promise.all([
          apiGet<Book>(`/market/${selectedId}/book`),
          apiGet<Array<{ id: number; price: string; executed_at?: string }>>(
            `/trades?stock_id=${selectedId}&limit=120`,
          ),
        ]);
        setBook(b);
        const stock = s.find((x) => x.id === selectedId);
        const sorted = [...stockTrades].sort((a, b) =>
          String(a.executed_at ?? a.id).localeCompare(String(b.executed_at ?? b.id)),
        );
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
    let reconnectTimer: number | null = null;
    let unmounted = false;
    let attempt = 0;

    function connect() {
      if (unmounted) return;
      try {
        ws = new WebSocket(wsUrl());
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            setStatus(msg.event ?? "EVENT");
            if (
              msg.event === "TRADE_EXECUTED" ||
              msg.event === "ORDER_BOOK_UPDATED" ||
              msg.event === "PRICE_UPDATED" ||
              msg.event === "NEWS_RELEASED" ||
              msg.event === "PORTFOLIO_UPDATED" ||
              msg.event === "MARKET_HALTED"
            ) {
              refresh();
            }
          } catch {
            /* ignore */
          }
        };
        ws.onopen = () => {
          attempt = 0;
          setStatus("LIVE");
        };
        ws.onclose = () => {
          setStatus("OFF");
          if (!unmounted) {
            const delay = Math.min(1000 * 2 ** attempt, 30_000);
            attempt += 1;
            reconnectTimer = window.setTimeout(connect, delay);
          }
        };
      } catch {
        setStatus("OFF");
        if (!unmounted) {
          reconnectTimer = window.setTimeout(connect, 5000);
        }
      }
    }

    connect();
    return () => {
      unmounted = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [refresh]);

  useEffect(() => {
    const saved = localStorage.getItem("mse_trader_id");
    if (saved) {
      const id = Number(saved);
      if (Number.isFinite(id) && id > 0) setTraderId(id);
    }
  }, []);

  async function join() {
    try {
      const created = await apiPost<{ id: number }>("/traders", {
        name: traderName || "Trader",
      });
      setTraderId(created.id);
      localStorage.setItem("mse_trader_id", String(created.id));
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not join");
    }
  }

  async function executeMarketOrder(side: "buy" | "sell") {
    if (!traderId || !selectedId) return;
    setSubmitting(true);
    setError(null);
    setResultMsg(null);
    try {
      const res = await apiPost<{
        rejected?: boolean;
        executed?: boolean;
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
      const summary = res.execution_summary;
      if (summary) {
        setResultMsg(summary.message);
        if (!summary.executed) setError(summary.message);
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

  async function submitLimitOrder() {
    if (!traderId || !selectedId) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await apiPost<{
        rejected?: boolean;
        execution_summary?: ExecutionSummary;
        detail?: string;
      }>("/orders", {
        trader_id: traderId,
        stock_id: selectedId,
        side: limitSide,
        order_type: "limit",
        quantity: qty,
        price: limitPrice,
      });
      if (res.execution_summary) {
        setResultMsg(res.execution_summary.message);
        if (!res.execution_summary.executed && res.rejected) {
          setError(res.execution_summary.message);
        }
      } else if (res.rejected) {
        setError(res.detail ?? "Limit order rejected");
      } else {
        setResultMsg("Limit order placed on the book");
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Limit order failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function cancelOrder(id: number) {
    try {
      await apiDelete(`/orders/${id}?trader_id=${traderId}`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not cancel order");
    }
  }

  function updateQty(raw: string) {
    const n = Number(raw);
    if (Number.isFinite(n) && n > 0) setQty(Math.floor(n));
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
          <button
            type="button"
            className="mt-4 w-full border border-[#22c55e] py-2 text-[#22c55e]"
            onClick={join}
          >
            Start
          </button>
          {error && <p className="mt-3 text-[#ef4444]">{error}</p>}
        </div>
      ) : (
        <div className="mx-auto max-w-3xl px-4 py-4">
          {/* Stock picker */}
          <div className="flex flex-wrap gap-1">
            {stocks.map((s) => (
              <button
                key={s.id}
                type="button"
                className={`px-3 py-1 text-xs ${
                  selectedId === s.id ? "bg-white text-black" : "border border-white/20"
                }`}
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

          {/* Price header */}
          <div className="mt-6 flex items-end justify-between">
            <div>
              <h1 className="text-xl">{selected?.company_name ?? selected?.ticker ?? "—"}</h1>
              <p className="text-xs text-white/50">{selected?.ticker}</p>
            </div>
            <div className="text-right">
              <p className={`text-3xl tabular-nums ${signClass(selected?.percent_change)}`}>
                {selected ? num(selected.last_traded_price).toFixed(2) : "—"}
              </p>
              <p className={`text-sm ${signClass(selected?.percent_change)}`}>
                {selected ? fmtPct(selected.percent_change) : "—"}
              </p>
            </div>
          </div>

          {/* Chart */}
            <div className="mt-4 h-40 border border-white/15 p-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={priceSeries}>
                  <XAxis dataKey="t" hide />
                  <YAxis
                    domain={["auto", "auto"]}
                    width={52}
                    tick={{ fill: "#888", fontSize: 10 }}
                    tickFormatter={(v) => Number(v).toFixed(2)}
                  />
                <Tooltip
                  contentStyle={{ background: "#000", border: "1px solid #333", fontSize: 11 }}
                />
                <Line type="monotone" dataKey="px" stroke={chartStroke} strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Portfolio strip */}
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
            <div className={`${panel} p-2`}>
              <p className="text-white/40">Available cash</p>
              <p className="mt-1">{portfolio?.cash ?? "—"}</p>
            </div>
            <div className={`${panel} p-2`}>
              <p className="text-white/40">Portfolio value</p>
              <p className="mt-1">{portfolio?.portfolio_value ?? "—"}</p>
            </div>
            <div className={`${panel} p-2`}>
              <p className="text-white/40">Current profit/loss</p>
              <p className={`mt-1 ${signClass(portfolio?.total_pnl)}`}>{portfolio?.total_pnl ?? "—"}</p>
            </div>
            <div className={`${panel} p-2`}>
              <p className="text-white/40">Holdings</p>
              <p className="mt-1 truncate">
                {(portfolio?.holdings ?? [])
                  .filter((h) => h.quantity > 0)
                  .map((h) => `${h.ticker} ${h.quantity}`)
                  .join(" · ") || "None"}
              </p>
            </div>
          </div>

          {/* Trade */}
          <div className={`${panel} mt-4 p-4`}>
            <label className="text-xs text-white/40">Quantity</label>
            <input
              type="number"
              className={`${inputCls} mt-1`}
              value={qty}
              min={1}
              onChange={(e) => updateQty(e.target.value)}
            />
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
            <pre className="mt-4 whitespace-pre-wrap border border-white/20 p-3 text-xs text-white/90">
              {resultMsg}
            </pre>
          )}
          {error && <p className="mt-2 text-xs text-[#ef4444]">{error}</p>}

          {/* Recent trades */}
          <div className={`${panel} mt-4 p-3`}>
            <p className="text-xs text-white/40">Your recent trades</p>
            <ul className="mt-2 space-y-1 text-xs">
              {trades.slice(0, 8).map((t) => (
                <li key={String(t.id)}>{String(t.quantity)} shares @ ₹{String(t.price)}</li>
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
            <Leaderboard
              rows={leaderboard}
              variant="terminal"
              highlightTraderId={traderId}
              maxRows={12}
            />
          </div>

          {/* Advanced */}
          <button
            type="button"
            className="mt-6 text-xs text-white/50 underline"
            onClick={() => setAdvancedOpen((v) => !v)}
          >
            {advancedOpen ? "Hide advanced" : "Advanced orders & order book"}
          </button>

          {advancedOpen && (
            <div className={`${panel} mt-3 space-y-4 p-4`}>
              <div>
                <p className="text-xs text-white/40">Limit order</p>
                <div className="mt-2 flex gap-2">
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
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <input type="number" className={inputCls} value={qty} onChange={(e) => updateQty(e.target.value)} />
                  <input className={inputCls} value={limitPrice} onChange={(e) => setLimitPrice(e.target.value)} />
                </div>
                <button
                  type="button"
                  disabled={submitting}
                  className="mt-2 w-full border border-white/30 py-2 text-xs"
                  onClick={submitLimitOrder}
                >
                  Place limit order
                </button>
              </div>

              <div>
                <p className="text-xs text-white/40">
                  Order book · spread {book?.spread ?? "—"}
                </p>
                <div className="mt-2 grid grid-cols-2 gap-3 text-xs tabular-nums">
                  <div>
                    <p className="text-[#22c55e]">Bids</p>
                    {(book?.bids ?? []).slice(0, 6).map((l) => (
                      <div key={`b-${l.price}`} className="flex justify-between text-[#22c55e]">
                        <span>{l.price}</span>
                        <span className="text-white/40">{l.quantity}</span>
                      </div>
                    ))}
                  </div>
                  <div>
                    <p className="text-[#ef4444]">Asks</p>
                    {(book?.asks ?? []).slice(0, 6).map((l) => (
                      <div key={`a-${l.price}`} className="flex justify-between text-[#ef4444]">
                        <span>{l.price}</span>
                        <span className="text-white/40">{l.quantity}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div>
                <p className="text-xs text-white/40">Open limit orders</p>
                <ul className="mt-2 space-y-1 text-xs">
                  {orders
                    .filter((o) => o.status === "open" || o.status === "partially_filled")
                    .map((o) => (
                      <li key={String(o.id)} className="flex justify-between gap-2">
                        <span>
                          {String(o.side)} {String(o.remaining_quantity)} @ {String(o.price)}
                        </span>
                        <button type="button" className="text-[#ef4444]" onClick={() => cancelOrder(Number(o.id))}>
                          Cancel
                        </button>
                      </li>
                    ))}
                </ul>
              </div>
            </div>
          )}
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
              Current price ₹{num(selected.last_traded_price).toFixed(2)} · executes immediately at market price
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
                className={`flex-1 py-2 text-xs text-black disabled:opacity-40 ${
                  confirmSide === "buy" ? "bg-[#22c55e]" : "bg-[#ef4444]"
                }`}
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
