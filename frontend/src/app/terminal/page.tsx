"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiDelete, apiGet, apiPost, wsUrl } from "@/lib/api";

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

  const selected = useMemo(
    () => stocks.find((s) => s.id === selectedId) ?? null,
    [stocks, selectedId]
  );

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
    const id = window.setInterval(refresh, 4000);
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
    await apiPost("/orders", {
      trader_id: traderId,
      stock_id: selectedId,
      side,
      order_type: orderType,
      quantity: qty,
      price: orderType === "limit" ? price : null,
    });
    await refresh();
  }

  async function cancelOrder(id: number) {
    await apiDelete(`/orders/${id}?trader_id=${traderId}`);
    await refresh();
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-line px-4 py-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">
            Mock Stock Exchange
          </p>
          <h1 className="text-lg font-semibold">Trading Terminal</h1>
        </div>
        <div className="flex flex-wrap items-center gap-4 font-mono text-xs">
          <span>STATUS {status}</span>
          <span>VALUE {portfolio?.portfolio_value ?? "—"}</span>
          <span>CASH {portfolio?.cash ?? "—"}</span>
          <span>P&L {portfolio?.total_pnl ?? "—"}</span>
          <a className="text-accent underline" href="/admin">
            Admin
          </a>
        </div>
      </header>

      {!traderId ? (
        <div className="mx-auto max-w-md px-4 py-16">
          <h2 className="text-xl font-semibold">Join session</h2>
          <input
            className="mt-4 w-full border border-line bg-panel px-3 py-2"
            value={traderName}
            onChange={(e) => setTraderName(e.target.value)}
            placeholder="Display name"
          />
          <button
            className="mt-4 bg-accent px-4 py-2 font-mono text-sm text-black"
            onClick={join}
          >
            Create trader
          </button>
          {error && <p className="mt-3 text-sm text-warn">{error}</p>}
        </div>
      ) : (
        <div className="grid gap-3 p-3 lg:grid-cols-[220px_1fr_280px]">
          <aside className="border border-line bg-panel p-3">
            <h2 className="font-mono text-xs uppercase text-muted">Watchlist</h2>
            <ul className="mt-2 space-y-1">
              {stocks.map((s) => (
                <li key={s.id}>
                  <button
                    className={`w-full px-2 py-1 text-left font-mono text-sm ${
                      selectedId === s.id ? "bg-line" : ""
                    }`}
                    onClick={() => {
                      setSelectedId(s.id);
                      setPrice(s.last_traded_price);
                    }}
                  >
                    <div className="flex justify-between">
                      <span>{s.ticker}</span>
                      <span>{Number(s.last_traded_price).toFixed(2)}</span>
                    </div>
                    <div className="text-xs text-muted">
                      {s.percent_change ?? "0"}%
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          <section className="space-y-3">
            <div className="border border-line bg-panel p-3">
              <div className="flex items-end justify-between">
                <div>
                  <h2 className="text-2xl font-semibold">{selected?.ticker ?? "—"}</h2>
                  <p className="text-sm text-muted">{selected?.company_name}</p>
                </div>
                <p className="font-mono text-3xl">
                  {selected ? Number(selected.last_traded_price).toFixed(2) : "—"}
                </p>
              </div>
              <div className="mt-4 h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={priceSeries}>
                    <XAxis dataKey="t" hide />
                    <YAxis domain={["auto", "auto"]} width={50} />
                    <Tooltip />
                    <Line type="monotone" dataKey="px" stroke="#3ecf8e" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div className="border border-line bg-panel p-3">
                <h3 className="font-mono text-xs uppercase text-muted">Order ticket</h3>
                <div className="mt-2 flex gap-2">
                  <button
                    className={`flex-1 py-2 ${side === "buy" ? "bg-accent text-black" : "bg-line"}`}
                    onClick={() => setSide("buy")}
                  >
                    Buy
                  </button>
                  <button
                    className={`flex-1 py-2 ${side === "sell" ? "bg-warn text-black" : "bg-line"}`}
                    onClick={() => setSide("sell")}
                  >
                    Sell
                  </button>
                </div>
                <div className="mt-2 flex gap-2">
                  <button
                    className={`flex-1 py-1 text-sm ${orderType === "limit" ? "bg-line" : ""}`}
                    onClick={() => setOrderType("limit")}
                  >
                    Limit
                  </button>
                  <button
                    className={`flex-1 py-1 text-sm ${orderType === "market" ? "bg-line" : ""}`}
                    onClick={() => setOrderType("market")}
                  >
                    Market
                  </button>
                </div>
                <label className="mt-3 block text-xs text-muted">Quantity</label>
                <input
                  type="number"
                  className="w-full border border-line bg-background px-2 py-1"
                  value={qty}
                  onChange={(e) => setQty(Number(e.target.value))}
                />
                {orderType === "limit" && (
                  <>
                    <label className="mt-2 block text-xs text-muted">Price</label>
                    <input
                      className="w-full border border-line bg-background px-2 py-1"
                      value={price}
                      onChange={(e) => setPrice(e.target.value)}
                    />
                  </>
                )}
                <button
                  className="mt-3 w-full bg-accent py-2 font-mono text-sm text-black"
                  onClick={submitOrder}
                >
                  Submit {side.toUpperCase()}
                </button>
              </div>

              <div className="border border-line bg-panel p-3">
                <h3 className="font-mono text-xs uppercase text-muted">Order book</h3>
                <p className="mt-1 font-mono text-xs text-muted">
                  Spread {book?.spread ?? "—"} · Bid {book?.best_bid ?? "—"} · Ask{" "}
                  {book?.best_ask ?? "—"}
                </p>
                <div className="mt-2 grid grid-cols-2 gap-2 font-mono text-xs">
                  <div>
                    <p className="text-muted">Bids</p>
                    {(book?.bids ?? []).slice(0, 8).map((l) => (
                      <div key={`b-${l.price}`} className="flex justify-between text-accent">
                        <span>{l.price}</span>
                        <span>{l.quantity}</span>
                      </div>
                    ))}
                  </div>
                  <div>
                    <p className="text-muted">Asks</p>
                    {(book?.asks ?? []).slice(0, 8).map((l) => (
                      <div key={`a-${l.price}`} className="flex justify-between text-warn">
                        <span>{l.price}</span>
                        <span>{l.quantity}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div className="border border-line bg-panel p-3">
                <h3 className="font-mono text-xs uppercase text-muted">Positions</h3>
                <ul className="mt-2 space-y-1 font-mono text-xs">
                  {(portfolio?.holdings ?? []).map((h, i) => (
                    <li key={i} className="flex justify-between">
                      <span>
                        {h.ticker} × {h.quantity}
                      </span>
                      <span>{h.unrealized_pnl}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="border border-line bg-panel p-3">
                <h3 className="font-mono text-xs uppercase text-muted">Open orders</h3>
                <ul className="mt-2 space-y-1 font-mono text-xs">
                  {orders
                    .filter((o) => o.status === "open" || o.status === "partially_filled")
                    .map((o) => (
                      <li key={String(o.id)} className="flex items-center justify-between gap-2">
                        <span>
                          {String(o.side)} {String(o.remaining_quantity)} @ {String(o.price)}
                        </span>
                        <button
                          className="text-warn"
                          onClick={() => cancelOrder(Number(o.id))}
                        >
                          Cancel
                        </button>
                      </li>
                    ))}
                </ul>
              </div>
              <div className="border border-line bg-panel p-3">
                <h3 className="font-mono text-xs uppercase text-muted">Trades</h3>
                <ul className="mt-2 space-y-1 font-mono text-xs">
                  {trades.slice(0, 12).map((t) => (
                    <li key={String(t.id)}>
                      {String(t.quantity)} @ {String(t.price)}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>

          <aside className="space-y-3">
            <div className="border border-line bg-panel p-3">
              <h2 className="font-mono text-xs uppercase text-muted">News</h2>
              <ul className="mt-2 space-y-2 text-sm">
                {news.slice(0, 8).map((n) => (
                  <li key={n.id}>
                    <p className="font-medium">{n.title}</p>
                    <p className="text-xs text-muted">{n.description}</p>
                  </li>
                ))}
                {!news.length && <p className="text-xs text-muted">No released news yet.</p>}
              </ul>
            </div>
            <div className="border border-line bg-panel p-3">
              <h2 className="font-mono text-xs uppercase text-muted">Leaderboard</h2>
              <ul className="mt-2 space-y-1 font-mono text-xs">
                {leaders.slice(0, 10).map((r) => (
                  <li key={r.rank} className="flex justify-between">
                    <span>
                      #{r.rank} {r.name}
                    </span>
                    <span>{r.return_pct}%</span>
                  </li>
                ))}
              </ul>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
