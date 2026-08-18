"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { BreakingNewsAlert } from "@/components/BreakingNewsAlert";
import type { NewsItem } from "@/components/NewsPanel";
import { Leaderboard, type LeaderboardRow } from "@/components/Leaderboard";
import { StockSidebar, type SectorGroup, type SidebarStock } from "@/components/StockSidebar";
import { TradePanel } from "@/components/TradePanel";
import { WalletBar } from "@/components/WalletBar";
import { useMarketWebSocket } from "@/hooks/useMarketWebSocket";
import { usePriceChart, type PriceUpdatePayload } from "@/hooks/usePriceChart";
import { apiGet, apiPost, fetchSessionBootstrap, joinSession } from "@/lib/api";

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

type SimulationState = {
  status?: string;
  trading_enabled?: boolean;
};

export default function TerminalPage() {
  const [traderId, setTraderId] = useState<number | null>(null);
  const [traderName, setTraderName] = useState("Trader");
  const [stocks, setStocks] = useState<SidebarStock[]>([]);
  const [sectors, setSectors] = useState<SectorGroup[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [breaking, setBreaking] = useState<NewsItem | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);
  const [showLb, setShowLb] = useState(false);
  const [ipos, setIpos] = useState<IPO[]>([]);
  const [ipoLots, setIpoLots] = useState(1);
  const [qty, setQty] = useState(10);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [confirmSide, setConfirmSide] = useState<"buy" | "sell" | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [tradingEnabled, setTradingEnabled] = useState(false);
  const [wsStatus, setWsStatus] = useState<"LIVE" | "OFF" | "Reconnecting">("OFF");

  const selected = useMemo(
    () => stocks.find((s) => s.id === selectedId) ?? null,
    [stocks, selectedId],
  );

  const { priceSeries, chartLoading, handlePriceUpdate } = usePriceChart(
    selectedId,
    selected?.last_traded_price,
  );

  const holdingQty = useMemo(() => {
    if (!selected || !portfolio) return 0;
    return portfolio.holdings.find((h) => h.ticker === selected.ticker)?.quantity ?? 0;
  }, [selected, portfolio]);

  const dissolvedStocks = useMemo(
    () => stocks.filter((s) => s.is_open === false),
    [stocks],
  );

  const patchStockPrice = useCallback((stockId: number, ltp: string) => {
    setStocks((prev) =>
      prev.map((s) => (s.id === stockId ? { ...s, last_traded_price: ltp } : s)),
    );
    setSectors((prev) =>
      prev.map((sector) => ({
        ...sector,
        stocks: sector.stocks.map((s) =>
          s.stock_id === stockId ? { ...s, last_traded_price: ltp } : s,
        ),
      })),
    );
  }, []);

  const applySimulationState = useCallback((sim: SimulationState | undefined) => {
    if (!sim) return;
    if (typeof sim.trading_enabled === "boolean") {
      setTradingEnabled(sim.trading_enabled);
    } else if (sim.status) {
      setTradingEnabled(sim.status === "running");
    }
  }, []);

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

  const applyBootstrap = useCallback(
    (data: Awaited<ReturnType<typeof fetchSessionBootstrap>>) => {
      setTraderId(data.trader_id);
      setWallet({
        available_cash: data.wallet.available_cash,
        portfolio_value: data.wallet.portfolio_value,
        total_pnl: data.wallet.total_pnl ?? "0",
        return_pct: data.wallet.return_pct ?? "0",
      });
      setPortfolio(data.portfolio);
      applySimulationState(data.simulation as SimulationState);
      if (data.stocks?.length) {
        setStocks(
          data.stocks.map((s) => ({
            id: s.id,
            ticker: s.ticker,
            company_name: s.company_name ?? s.ticker,
            last_traded_price: s.ltp ?? s.last_traded_price ?? "0",
            percent_change: s.percent_change ?? null,
            is_open: s.is_open ?? true,
          })),
        );
        if (!selectedId) {
          setSelectedId(data.stocks.find((s) => s.is_open !== false)?.id ?? data.stocks[0].id);
        }
      }
      if (data.sectors?.length) setSectors(data.sectors);
      if (data.leaderboard?.length) setLeaderboard(data.leaderboard);
      if (data.open_ipos?.length) setIpos(data.open_ipos);
    },
    [selectedId, applySimulationState],
  );

  const resyncBootstrap = useCallback(async () => {
    const token = localStorage.getItem("mse_access_token");
    if (!token) return;
    try {
      const data = await fetchSessionBootstrap();
      applyBootstrap(data);
    } catch {
      /* token may be stale; user can re-join */
    }
  }, [applyBootstrap]);

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

  const refresh = useCallback(async () => {
    try {
      await refreshStocks();
      await refreshSectors();
      const openIpos = await apiGet<IPO[]>("/ipos/open").catch(() => [] as IPO[]);
      setIpos(openIpos);
      if (traderId) await refreshWallet();
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load data");
    }
  }, [refreshStocks, refreshSectors, refreshWallet, traderId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const saved = localStorage.getItem("mse_trader_id");
    const token = localStorage.getItem("mse_access_token");
    if (saved && token) {
      setTraderId(Number(saved));
      void resyncBootstrap();
    }
  }, [resyncBootstrap]);

  const { connected, reconnecting } = useMarketWebSocket({
    onOpen: () => setWsStatus("LIVE"),
    onClose: () => setWsStatus("Reconnecting"),
    onReconnect: () => {
      setWsStatus("LIVE");
      void resyncBootstrap();
    },
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
      }
      if (msg.event === "SIMULATION_CLOCK" || msg.event === "SIMULATION_STATUS") {
        applySimulationState((msg.payload ?? msg) as SimulationState);
      }
      if (msg.event === "PRICE_UPDATED") {
        const payload = (msg.payload ?? msg) as PriceUpdatePayload;
        handlePriceUpdate(payload);
        const stockId = payload.stock_id;
        if (stockId) {
          const ltp =
            payload.ltp ??
            (payload.trades?.length ? payload.trades[payload.trades.length - 1].price : undefined);
          if (ltp) patchStockPrice(stockId, ltp);
        }
      }
      if (msg.event === "TRADE_EXECUTED") {
        void refreshWallet();
      }
      if (msg.event === "WALLET_UPDATED" || msg.event === "PORTFOLIO_UPDATED") {
        void refreshWallet();
      }
      if (msg.event === "LEADERBOARD_UPDATE") {
        apiGet<LeaderboardRow[]>("/leaderboard").then(setLeaderboard).catch(() => {});
      }
      if (msg.event === "IPO_OPENED" || msg.event === "IPO_RESULT" || msg.event === "IPO_LISTED") {
        apiGet<IPO[]>("/ipos/open").then(setIpos).catch(() => []);
        void refreshWallet();
      }
    },
  });

  useEffect(() => {
    if (reconnecting) setWsStatus("Reconnecting");
  }, [reconnecting]);

  useEffect(() => {
    if (connected) return;
    const id = window.setInterval(() => void refresh(), 12000);
    return () => window.clearInterval(id);
  }, [connected, refresh]);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(id);
  }, [toast]);

  async function join() {
    try {
      const created = await joinSession(traderName || "Trader");
      setTraderId(created.trader_id);
      await resyncBootstrap();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not join session");
    }
  }

  function openConfirm(side: "buy" | "sell") {
    setConfirmError(null);
    setConfirmSide(side);
  }

  function closeConfirm() {
    if (confirmLoading) return;
    setConfirmSide(null);
    setConfirmError(null);
  }

  async function executeOrder() {
    if (!traderId || !selectedId || !confirmSide) return;
    setConfirmLoading(true);
    setConfirmError(null);
    try {
      const res = await apiPost<{
        execution_summary?: { executed: boolean; message: string };
      }>("/orders", {
        trader_id: traderId,
        stock_id: selectedId,
        side: confirmSide,
        order_type: "market",
        quantity: qty,
        price: null,
      });
      if (res.execution_summary && !res.execution_summary.executed) {
        setConfirmError(res.execution_summary.message);
        return;
      }
      setToast(res.execution_summary?.message ?? `${confirmSide.toUpperCase()} order placed`);
      setConfirmSide(null);
      await refreshWallet();
    } catch (e) {
      setConfirmError(e instanceof Error ? e.message : "Order failed");
    } finally {
      setConfirmLoading(false);
    }
  }

  async function applyIpo() {
    if (!traderId || !ipos[0]) return;
    try {
      await apiPost(`/ipos/${ipos[0].id}/apply`, { trader_id: traderId, requested_lots: ipoLots });
      setToast("IPO applied");
      await refreshWallet();
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

      <BreakingNewsAlert news={breaking} onDismiss={() => setBreaking(null)} />

      <div className="grid flex-1 grid-cols-1 gap-0 lg:grid-cols-[240px_1fr]">
        <StockSidebar
          sectors={sectors}
          dissolved={dissolvedStocks}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        <TradePanel
          stock={selected}
          priceSeries={priceSeries}
          chartLoading={chartLoading}
          qty={qty}
          onQtyChange={setQty}
          holdingQty={holdingQty}
          tradingEnabled={tradingEnabled}
          onBuy={() => openConfirm("buy")}
          onSell={() => openConfirm("sell")}
          confirmSide={confirmSide}
          confirmLoading={confirmLoading}
          confirmError={confirmError}
          onConfirm={() => void executeOrder()}
          onCancelConfirm={closeConfirm}
          ipo={ipos[0] ?? null}
          ipoLots={ipoLots}
          onIpoLotsChange={setIpoLots}
          onIpoApply={ipos[0] ? applyIpo : undefined}
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
    </div>
  );
}
