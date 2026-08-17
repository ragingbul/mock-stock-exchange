"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Leaderboard, type LeaderboardRow } from "@/components/Leaderboard";
import { NewsPanel, type NewsItem } from "@/components/NewsPanel";
import { StockSidebar, type SectorGroup, type SidebarStock } from "@/components/StockSidebar";
import { TradePanel } from "@/components/TradePanel";
import { WalletBar } from "@/components/WalletBar";
import { useMarketWebSocket } from "@/hooks/useMarketWebSocket";
import { apiGet, apiPost } from "@/lib/api";
import { num } from "@/lib/marketFormat";

type Wallet = {
  available_cash: string;
  portfolio_value: string;
  total_pnl: string;
  return_pct: string;
};

type Portfolio = {
  holdings: Array<{ ticker: string | null; quantity: number }>;
};

type IPO = {
  id: number;
  company_name: string;
  ticker: string;
  issue_price: string;
  lot_size: number;
  maximum_lots_per_user: number;
};

export default function TerminalPage() {
  const [traderId, setTraderId] = useState<number | null>(null);
  const [traderName, setTraderName] = useState("Trader");
  const [stocks, setStocks] = useState<SidebarStock[]>([]);
  const [sectors, setSectors] = useState<SectorGroup[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [breaking, setBreaking] = useState<NewsItem | null>(null);
  const [selectedNews, setSelectedNews] = useState<NewsItem | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);
  const [showLb, setShowLb] = useState(false);
  const [ipos, setIpos] = useState<IPO[]>([]);
  const [ipoLots, setIpoLots] = useState(1);
  const [qty, setQty] = useState(10);
  const [priceSeries, setPriceSeries] = useState<Array<{ t: string; px: number }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [confirmSide, setConfirmSide] = useState<"buy" | "sell" | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [wsStatus, setWsStatus] = useState<"LIVE" | "OFF" | "Reconnecting">("OFF");

  const selected = useMemo(
    () => stocks.find((s) => s.id === selectedId) ?? null,
    [stocks, selectedId],
  );

  const holdingQty = useMemo(() => {
    if (!selected || !portfolio) return 0;
    return portfolio.holdings.find((h) => h.ticker === selected.ticker)?.quantity ?? 0;
  }, [selected, portfolio]);

  const refreshStocks = useCallback(async () => {
    const s = await apiGet<SidebarStock[]>("/stocks");
    setStocks(s);
    if (!selectedId && s.length) setSelectedId(s[0].id);
    return s;
  }, [selectedId]);

  const refreshSectors = useCallback(async () => {
    const data = await apiGet<SectorGroup[]>("/market/sectors");
    setSectors(data);
    return data;
  }, []);

  const refreshNews = useCallback(async () => {
    const n = await apiGet<NewsItem[]>("/news");
    setNews(n);
  }, []);

  const refreshWallet = useCallback(async () => {
    if (!traderId) return;
    const [w, p, lb] = await Promise.all([
      apiGet<Wallet>(`/traders/${traderId}/wallet`),
      apiGet<Portfolio>(`/traders/${traderId}/portfolio`),
      apiGet<LeaderboardRow[]>("/leaderboard"),
    ]);
    setWallet(w);
    setPortfolio(p);
    setLeaderboard(lb);
  }, [traderId]);

  const refreshChart = useCallback(async (stockId: number, stockList?: SidebarStock[]) => {
    const list = stockList ?? stocks;
    const stockTrades = await apiGet<Array<{ id: number; price: string; executed_at?: string }>>(
      `/trades?stock_id=${stockId}&limit=120`,
    );
    const sorted = [...stockTrades].sort((a, b) =>
      String(a.executed_at ?? a.id).localeCompare(String(b.executed_at ?? b.id)),
    );
    const stock = list.find((x) => x.id === stockId);
    if (sorted.length > 0) {
      setPriceSeries(
        sorted.map((tr) => ({
          t: tr.executed_at
            ? new Date(tr.executed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
            : `#${tr.id}`,
          px: num(tr.price),
        })),
      );
    } else if (stock) {
      setPriceSeries([{ t: "now", px: num(stock.last_traded_price) }]);
    }
  }, [stocks]);

  const refreshMarket = useCallback(async () => {
    await Promise.all([refreshStocks(), refreshSectors()]);
  }, [refreshStocks, refreshSectors]);

  const refresh = useCallback(async () => {
    try {
      const s = await refreshStocks();
      await refreshSectors();
      await refreshNews();
      const openIpos = await apiGet<IPO[]>("/ipos/open").catch(() => [] as IPO[]);
      setIpos(openIpos);
      if (traderId) await refreshWallet();
      if (selectedId) await refreshChart(selectedId, s);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load data");
    }
  }, [refreshStocks, refreshSectors, refreshNews, refreshWallet, refreshChart, traderId, selectedId]);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 12000);
    return () => window.clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    if (selectedId) refreshChart(selectedId);
  }, [selectedId, refreshChart]);

  useEffect(() => {
    const saved = localStorage.getItem("mse_trader_id");
    if (saved) setTraderId(Number(saved));
  }, []);

  const { connected } = useMarketWebSocket({
    onOpen: () => setWsStatus("LIVE"),
    onClose: () => setWsStatus("OFF"),
    onMessage: (msg) => {
      if (msg.event === "NEWS_RELEASED") {
        const payload = msg.payload as NewsItem | undefined;
        if (payload?.title) {
          setBreaking({
            id: payload.id ?? 0,
            title: payload.title,
            description: payload.description ?? "",
            released_at: payload.released_at,
          });
        }
        refreshNews();
      }
      if (msg.event === "PRICE_UPDATED" || msg.event === "TRADE_EXECUTED") {
        refreshMarket();
        if (selectedId) refreshChart(selectedId);
      }
      if (msg.event === "WALLET_UPDATED" || msg.event === "PORTFOLIO_UPDATED") {
        refreshWallet();
      }
      if (msg.event === "LEADERBOARD_UPDATE") {
        apiGet<LeaderboardRow[]>("/leaderboard").then(setLeaderboard).catch(() => {});
      }
      if (msg.event === "IPO_OPENED" || msg.event === "IPO_RESULT" || msg.event === "IPO_LISTED") {
        apiGet<IPO[]>("/ipos/open").then(setIpos).catch(() => []);
        refreshWallet();
      }
    },
  });

  async function join() {
    const created = await apiPost<{ id: number }>("/traders", { name: traderName || "Trader" });
    setTraderId(created.id);
    localStorage.setItem("mse_trader_id", String(created.id));
  }

  async function executeOrder(side: "buy" | "sell") {
    if (!traderId || !selectedId) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await apiPost<{ execution_summary?: { executed: boolean; message: string } }>("/orders", {
        trader_id: traderId,
        stock_id: selectedId,
        side,
        order_type: "market",
        quantity: qty,
        price: null,
      });
      if (res.execution_summary && !res.execution_summary.executed) {
        setError(res.execution_summary.message);
      }
      setConfirmSide(null);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Order failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function applyIpo() {
    if (!traderId || !ipos[0]) return;
    try {
      await apiPost(`/ipos/${ipos[0].id}/apply`, { trader_id: traderId, requested_lots: ipoLots });
      setToast("IPO applied");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "IPO failed");
    }
  }

  const inputCls = "w-full border border-white/25 bg-black px-2 py-2 text-white outline-none";

  if (!traderId) {
    return (
      <div className="min-h-screen bg-black font-mono text-white">
        <div className="mx-auto max-w-sm px-4 py-16">
          <h1 className="text-lg tracking-widest">TRADEVERSE</h1>
          <p className="mt-2 text-white/50">Enter your name to join the simulation</p>
          <input className={`${inputCls} mt-4`} value={traderName} onChange={(e) => setTraderName(e.target.value)} />
          <button type="button" className="mt-4 w-full border border-[#22c55e] py-2 text-[#22c55e]" onClick={join}>
            Start
          </button>
          {error && <p className="mt-3 text-[#ef4444]">{error}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-black font-mono text-sm text-white">
      <WalletBar
        cash={wallet?.available_cash}
        portfolio={wallet?.portfolio_value}
        pnl={wallet?.total_pnl}
        ret={wallet?.return_pct}
        onLeaderboard={() => setShowLb((v) => !v)}
        showLeaderboard={showLb}
      />
      <p className="border-x border-white/15 px-4 py-1 text-[10px] text-white/40">
        {wsStatus}
        {!connected && wsStatus === "OFF" ? " · fallback poll 12s" : ""}
      </p>

      <div className="grid flex-1 grid-cols-1 gap-0 lg:grid-cols-[240px_1fr_240px]">
        <StockSidebar
          sectors={sectors}
          selectedId={selectedId}
          onSelect={(id) => {
            setSelectedId(id);
            setPriceSeries([]);
          }}
        />
        <TradePanel
          stock={selected}
          priceSeries={priceSeries}
          qty={qty}
          onQtyChange={setQty}
          holdingQty={holdingQty}
          onBuy={() => setConfirmSide("buy")}
          onSell={() => setConfirmSide("sell")}
          submitting={submitting}
          ipo={ipos[0] ?? null}
          ipoLots={ipoLots}
          onIpoLotsChange={setIpoLots}
          onIpoApply={ipos[0] ? applyIpo : undefined}
        />
        <NewsPanel
          news={news}
          breaking={breaking}
          onDismissBreaking={() => setBreaking(null)}
          onSelectNews={setSelectedNews}
          selectedNews={selectedNews}
        />
      </div>

      {showLb && (
        <div className="border-t border-white/15 p-4">
          <Leaderboard rows={leaderboard} variant="terminal" highlightTraderId={traderId} maxRows={15} />
        </div>
      )}

      {error && <p className="px-4 py-2 text-xs text-[#ef4444]">{error}</p>}

      {toast && (
        <div className="fixed bottom-4 left-4 border border-white/25 bg-black p-3 text-xs">
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
              {confirmSide === "buy" ? "Buy" : "Sell"} {qty} {selected.ticker}
            </p>
            <div className="mt-4 flex gap-2">
              <button type="button" className="flex-1 border border-white/25 py-2" onClick={() => setConfirmSide(null)}>
                Cancel
              </button>
              <button
                type="button"
                className={`flex-1 py-2 text-black ${confirmSide === "buy" ? "bg-[#22c55e]" : "bg-[#ef4444]"}`}
                disabled={submitting}
                onClick={() => executeOrder(confirmSide)}
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
