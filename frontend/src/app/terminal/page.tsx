"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
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
  trader_id: number;
  name: string;
  cash: string;
  portfolio_value: string;
  total_pnl: string;
  realized_pnl: string;
  unrealized_pnl: string;
  holdings: Array<{
    ticker: string | null;
    quantity: number;
    avg_cost: string;
    market_price: string | null;
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
type Leader = { rank: number; name: string; return_pct: string; portfolio_value: string };

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
  const [leaders, setLeaders] = useState<Leader[]>([]);
  const [orders, setOrders] = useState<Array<Record<string, unknown>>>([]);
  const [trades, setTrades] = useState<Array<Record<string, unknown>>>([]);
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [orderType, setOrderType] = useState<"limit" | "market">("limit");
  const [qty, setQty] = useState(10);
  const [price, setPrice] = useState("100");
  const [status, setStatus] = useState("IDLE");
  const [priceSeries, setPriceSeries] = useState<Array<{ t: string; px: number }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [orderConfirmOpen, setOrderConfirmOpen] = useState(false);
  const [submittingOrder, setSubmittingOrder] = useState(false);

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
      const [s, n, l] = await Promise.all([
        apiGet<Stock[]>("/stocks"),
        apiGet<News[]>("/news"),
        apiGet<Leader[]>("/leaderboard"),
      ]);
      setStocks(s);
      setNews(n);
      setLeaders(l);
      if (!selectedId && s.length) {
        setSelectedId(s[0].id);
        setPrice(s[0].last_traded_price);
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
        const b = await apiGet<Book>(`/market/${selectedId}/book`);
        setBook(b);
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "refresh failed");
    }
  }, [selectedId, traderId]);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 8000);
    return () => window.clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    if (!selected) return;
    setPriceSeries((prev) => {
      const px = Number(selected.last_traded_price);
      const next = [...prev, { t: new Date().toLocaleTimeString(), px }];
      return next.slice(-40);
    });
  }, [selected?.last_traded_price, selected?.id]);

  useEffect(() => {
    let ws: WebSocket | null = null;
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
            msg.event === "PORTFOLIO_UPDATED"
          ) {
            refresh();
          }
        } catch {
          /* ignore */
        }
      };
      ws.onopen = () => setStatus("LIVE");
      ws.onclose = () => setStatus("WS CLOSED");
    } catch {
      setStatus("WS OFF");
    }
    return () => ws?.close();
  }, [refresh]);

  async function join() {
    const created = await apiPost<{ id: number; name: string }>("/traders", {
      name: traderName || "Trader",
    });
    setTraderId(created.id);
    localStorage.setItem("mse_trader_id", String(created.id));
    await refresh();
  }

  useEffect(() => {
    const saved = localStorage.getItem("mse_trader_id");
    if (saved) setTraderId(Number(saved));
  }, []);

  async function submitOrder() {
    if (!traderId || !selectedId) return;
    setSubmittingOrder(true);
    try {
      const result = await apiPost<{
        rejected?: boolean;
        detail?: string;
        order: { status: string };
        trades: unknown[];
      }>("/orders", {
        trader_id: traderId,
        stock_id: selectedId,
        side,
        order_type: orderType,
        quantity: qty,
        price: orderType === "limit" ? price : null,
      });
      if (result.rejected) {
        setError(result.detail ?? "Order rejected");
      } else {
        setError(null);
      }
      setOrderConfirmOpen(false);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "order failed");
    } finally {
      setSubmittingOrder(false);
    }
  }

  function openOrderConfirm() {
    if (!traderId || !selectedId || !selected) return;
    setOrderConfirmOpen(true);
  }

  const orderPriceLabel =
    orderType === "limit" ? `₹${price}` : `market (~₹${selected?.last_traded_price ?? "—"})`;

  async function cancelOrder(id: number) {
    await apiDelete(`/orders/${id}?trader_id=${traderId}`);
    await refresh();
  }

  const panel = "border border-white/15";
  const inputCls =
    "w-full border border-white/20 bg-black px-2 py-1.5 text-white outline-none focus:border-white";

  return (
    <div className="min-h-screen bg-black font-mono text-sm text-white">
      <header className={`${panel} flex flex-wrap items-center justify-between gap-3 border-x-0 border-t-0 px-4 py-2`}>
        <div className="flex items-center gap-4">
          <span className="text-xs tracking-widest">MSE</span>
          <span className="text-white/50">{status}</span>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <span>VAL {portfolio?.portfolio_value ?? "—"}</span>
          <span>CASH {portfolio?.cash ?? "—"}</span>
          <span className={signClass(portfolio?.total_pnl)}>P&L {portfolio?.total_pnl ?? "—"}</span>
          <a className="text-white underline underline-offset-2" href="/admin">Admin</a>
        </div>
      </header>

      {!traderId ? (
        <div className="mx-auto max-w-sm px-4 py-20">
          <p className="text-xs text-white/50">JOIN</p>
          <input
            className={`${inputCls} mt-3`}
            value={traderName}
            onChange={(e) => setTraderName(e.target.value)}
            placeholder="Name"
          />
          <button
            type="button"
            className="mt-4 w-full border border-[#22c55e] py-2 text-[#22c55e] transition active:scale-[0.98]"
            onClick={join}
          >
            Enter market
          </button>
          {error && <p className="mt-3 text-xs text-[#ef4444]">{error}</p>}
        </div>
      ) : (
        <div className="grid gap-0 lg:grid-cols-[11rem_1fr_12rem]">
          <aside className={`${panel} border-l-0 border-t-0 p-2 lg:min-h-[calc(100vh-2.5rem)]`}>
            <p className="mb-2 text-[10px] text-white/40">WATCH</p>
            <ul className="space-y-0">
              {stocks.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    className={`w-full px-1 py-1.5 text-left text-xs transition ${
                      selectedId === s.id ? "bg-white text-black" : "hover:bg-white/10"
                    }`}
                    onClick={() => {
                      setSelectedId(s.id);
                      setPrice(s.last_traded_price);
                    }}
                  >
                    <div className="flex justify-between gap-2">
                      <span>{s.ticker}</span>
                      <span>{num(s.last_traded_price).toFixed(2)}</span>
                    </div>
                    <div className={`text-[10px] ${selectedId === s.id ? "text-black/60" : signClass(s.percent_change)}`}>
                      {fmtPct(s.percent_change)}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          <section className="border-b border-white/15 lg:border-r">
            <div className="flex items-baseline justify-between gap-4 border-b border-white/15 px-4 py-3">
              <div>
                <p className="text-2xl font-semibold tracking-tight">{selected?.ticker ?? "—"}</p>
                <p className={`text-sm ${signClass(selected?.percent_change)}`}>
                  {selected ? fmtPct(selected.percent_change) : "—"}
                </p>
              </div>
              <p className={`text-3xl tabular-nums ${signClass(selected?.percent_change)}`}>
                {selected ? num(selected.last_traded_price).toFixed(2) : "—"}
              </p>
            </div>

            <div className="h-36 border-b border-white/15 px-2 py-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={priceSeries}>
                  <XAxis dataKey="t" hide />
                  <YAxis domain={["auto", "auto"]} hide />
                  <Tooltip
                    contentStyle={{
                      background: "#000",
                      border: "1px solid rgba(255,255,255,0.2)",
                      fontSize: 11,
                      color: "#fff",
                    }}
                    labelStyle={{ color: "rgba(255,255,255,0.5)" }}
                  />
                  <Line type="monotone" dataKey="px" stroke={chartStroke} strokeWidth={1.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="grid md:grid-cols-2">
              <div className="border-b border-white/15 p-3 md:border-r">
                <p className="text-[10px] text-white/40">ORDER</p>
                <div className="mt-2 flex gap-1">
                  <button
                    type="button"
                    className={`flex-1 py-1.5 text-xs ${
                      side === "buy" ? "bg-[#22c55e] text-black" : "border border-white/20 text-white"
                    }`}
                    onClick={() => setSide("buy")}
                  >
                    BUY
                  </button>
                  <button
                    type="button"
                    className={`flex-1 py-1.5 text-xs ${
                      side === "sell" ? "bg-[#ef4444] text-black" : "border border-white/20 text-white"
                    }`}
                    onClick={() => setSide("sell")}
                  >
                    SELL
                  </button>
                </div>
                <div className="mt-2 flex gap-1 text-[10px]">
                  <button
                    type="button"
                    className={`flex-1 py-1 ${orderType === "limit" ? "bg-white text-black" : "text-white/50"}`}
                    onClick={() => setOrderType("limit")}
                  >
                    LMT
                  </button>
                  <button
                    type="button"
                    className={`flex-1 py-1 ${orderType === "market" ? "bg-white text-black" : "text-white/50"}`}
                    onClick={() => setOrderType("market")}
                  >
                    MKT
                  </button>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-white/40">QTY</label>
                    <input
                      type="number"
                      className={inputCls}
                      value={qty}
                      onChange={(e) => setQty(Number(e.target.value))}
                    />
                  </div>
                  {orderType === "limit" && (
                    <div>
                      <label className="text-[10px] text-white/40">PRICE</label>
                      <input className={inputCls} value={price} onChange={(e) => setPrice(e.target.value)} />
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  className={`mt-3 w-full py-2 text-xs transition active:scale-[0.98] disabled:opacity-40 ${
                    side === "buy"
                      ? "bg-[#22c55e] text-black"
                      : "bg-[#ef4444] text-black"
                  }`}
                  disabled={submittingOrder}
                  onClick={openOrderConfirm}
                >
                  {side.toUpperCase()}
                </button>
                {error && <p className="mt-2 text-[10px] text-[#ef4444]">{error}</p>}
              </div>

              <div className="border-b border-white/15 p-3">
                <p className="text-[10px] text-white/40">
                  BOOK · {book?.spread ?? "—"}
                </p>
                <div className="mt-2 grid grid-cols-2 gap-3 text-[11px] tabular-nums">
                  <div>
                    <p className="mb-1 text-[10px] text-[#22c55e]">BID</p>
                    {(book?.bids ?? []).slice(0, 6).map((l) => (
                      <div key={`b-${l.price}`} className="flex justify-between text-[#22c55e]">
                        <span>{l.price}</span>
                        <span className="text-white/50">{l.quantity}</span>
                      </div>
                    ))}
                  </div>
                  <div>
                    <p className="mb-1 text-[10px] text-[#ef4444]">ASK</p>
                    {(book?.asks ?? []).slice(0, 6).map((l) => (
                      <div key={`a-${l.price}`} className="flex justify-between text-[#ef4444]">
                        <span>{l.price}</span>
                        <span className="text-white/50">{l.quantity}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="grid text-[11px] md:grid-cols-3">
              <div className="border-b border-white/15 p-3 md:border-r">
                <p className="text-[10px] text-white/40">POSITIONS</p>
                <ul className="mt-2 space-y-1">
                  {(portfolio?.holdings ?? []).map((h, i) => (
                    <li key={i} className="flex justify-between gap-2">
                      <span>{h.ticker} {h.quantity}</span>
                      <span className={signClass(h.unrealized_pnl)}>{h.unrealized_pnl}</span>
                    </li>
                  ))}
                  {!portfolio?.holdings?.length && <li className="text-white/30">—</li>}
                </ul>
              </div>
              <div className="border-b border-white/15 p-3 md:border-r">
                <p className="text-[10px] text-white/40">OPEN</p>
                <ul className="mt-2 space-y-1">
                  {orders
                    .filter((o) => o.status === "open" || o.status === "partially_filled")
                    .map((o) => (
                      <li key={String(o.id)} className="flex justify-between gap-2">
                        <span className={String(o.side) === "buy" ? "text-[#22c55e]" : "text-[#ef4444]"}>
                          {String(o.side)} {String(o.remaining_quantity)} @{String(o.price)}
                        </span>
                        <button
                          type="button"
                          className="text-[#ef4444]"
                          onClick={() => cancelOrder(Number(o.id))}
                        >
                          ×
                        </button>
                      </li>
                    ))}
                  {!orders.filter((o) => o.status === "open" || o.status === "partially_filled").length && (
                    <li className="text-white/30">—</li>
                  )}
                </ul>
              </div>
              <div className="border-b border-white/15 p-3">
                <p className="text-[10px] text-white/40">FILLS</p>
                <ul className="mt-2 space-y-1">
                  {trades.slice(0, 8).map((t) => (
                    <li key={String(t.id)}>{String(t.quantity)} @ {String(t.price)}</li>
                  ))}
                  {!trades.length && <li className="text-white/30">—</li>}
                </ul>
              </div>
            </div>
          </section>

          <aside className={`${panel} border-r-0 border-t-0 p-2 lg:min-h-[calc(100vh-2.5rem)]`}>
            <p className="mb-2 text-[10px] text-white/40">NEWS</p>
            <ul className="space-y-2 text-[11px]">
              {news.slice(0, 5).map((n) => (
                <li key={n.id} className="border-b border-white/10 pb-2">
                  <p className={signClass(n.effective_impact)}>{n.title}</p>
                </li>
              ))}
              {!news.length && <li className="text-white/30">—</li>}
            </ul>
            <p className="mb-2 mt-4 text-[10px] text-white/40">RANK</p>
            <ul className="space-y-1 text-[11px]">
              {leaders.slice(0, 8).map((r) => (
                <li key={r.rank} className="flex justify-between gap-2">
                  <span className="text-white/70">{r.rank} {r.name}</span>
                  <span className={signClass(r.return_pct)}>{r.return_pct}%</span>
                </li>
              ))}
            </ul>
          </aside>
        </div>
      )}

      {orderConfirmOpen && selected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="order-confirm-title"
        >
          <div className="w-full max-w-sm border border-white/25 bg-black p-4">
            <p id="order-confirm-title" className="text-[10px] text-white/40">CONFIRM</p>
            <p className="mt-2 text-lg">
              <span className={side === "buy" ? "text-[#22c55e]" : "text-[#ef4444]"}>
                {side.toUpperCase()}
              </span>
              {" "}{qty} {selected.ticker}
            </p>
            <div className="mt-3 space-y-1 text-xs text-white/70">
              <p>{orderType.toUpperCase()} · {orderPriceLabel}</p>
              <p>Cash {portfolio?.cash ?? "—"}</p>
            </div>
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                className="flex-1 border border-white/25 py-2 text-xs"
                disabled={submittingOrder}
                onClick={() => setOrderConfirmOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className={`flex-1 py-2 text-xs text-black disabled:opacity-40 ${
                  side === "buy" ? "bg-[#22c55e]" : "bg-[#ef4444]"
                }`}
                disabled={submittingOrder}
                onClick={submitOrder}
              >
                {submittingOrder ? "…" : "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
