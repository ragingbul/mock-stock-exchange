"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { BreakingNewsAlert } from "@/components/BreakingNewsAlert";
import { LatestNewsPanel } from "@/components/LatestNewsPanel";
import type { NewsItem } from "@/components/NewsPanel";
import { Leaderboard, type LeaderboardRow } from "@/components/Leaderboard";
import { StockSidebar, type SectorGroup, type SidebarStock } from "@/components/StockSidebar";
import { TradePanel, MAX_POSITION_PER_STOCK } from "@/components/TradePanel";
import { WalletBar } from "@/components/WalletBar";
import { WalletPanel } from "@/components/WalletPanel";
import { useMarketWebSocket } from "@/hooks/useMarketWebSocket";
import {
  usePriceChart,
  type MarketPulseStock,
  type PriceUpdatePayload,
} from "@/hooks/usePriceChart";
import {
  apiGet,
  apiPost,
  fetchOrders,
  fetchPortfolio,
  fetchSessionBootstrap,
  fetchTrades,
  joinSession,
  mergeTransactions,
  type PortfolioDetail,
  type TransactionRow,
} from "@/lib/api";
import {
  markHoldingsToMarket,
  markWalletToMarket,
  type PortfolioSnapshot,
  type WalletSnapshot,
} from "@/lib/portfolioValuation";

type Wallet = WalletSnapshot;
type Portfolio = PortfolioSnapshot;

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

function asMoney(v: unknown): string {
  if (v == null) return "0";
  return String(v);
}

function newsFromPayload(raw: Record<string, unknown> | undefined): NewsItem | null {
  if (!raw) return null;
  const title = String(raw.title ?? raw.headline ?? "").trim();
  if (!title) return null;
  const briefRaw = raw.brief_points;
  const brief_points = Array.isArray(briefRaw)
    ? briefRaw.map((p) => String(p))
    : undefined;
  return {
    id: Number(raw.id ?? 0),
    title,
    description: String(raw.description ?? ""),
    brief_points,
    released_at: raw.released_at ? String(raw.released_at) : undefined,
  };
}

export default function TerminalPage() {
  const [traderId, setTraderId] = useState<number | null>(null);
  const [traderName, setTraderName] = useState("Trader");
  const [stocks, setStocks] = useState<SidebarStock[]>([]);
  const [sectors, setSectors] = useState<SectorGroup[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [breaking, setBreaking] = useState<NewsItem | null>(null);
  const [newsFeed, setNewsFeed] = useState<NewsItem[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);
  const [showLb, setShowLb] = useState(false);
  const [showWallet, setShowWallet] = useState(false);
  const [portfolioDetail, setPortfolioDetail] = useState<PortfolioDetail | null>(null);
  const [transactions, setTransactions] = useState<TransactionRow[]>([]);
  const [walletLoading, setWalletLoading] = useState(false);
  const [selectedNewsId, setSelectedNewsId] = useState<number | null>(null);
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

  const { priceSeries, chartLoading, handlePriceUpdate, handleMarketPulse } = usePriceChart(
    selectedId,
    selected?.last_traded_price,
  );

  const displayWallet = useMemo(
    () => markWalletToMarket(wallet, portfolio, stocks),
    [wallet, portfolio, stocks],
  );

  const liveHoldings = useMemo(
    () => markHoldingsToMarket(portfolioDetail?.holdings ?? [], stocks),
    [portfolioDetail, stocks],
  );

  const selectedNews = useMemo(() => {
    if (selectedNewsId != null) {
      return newsFeed.find((n) => n.id === selectedNewsId) ?? newsFeed[0] ?? breaking;
    }
    return newsFeed[0] ?? breaking;
  }, [newsFeed, breaking, selectedNewsId]);

  const holdingQty = useMemo(() => {
    if (!selected || !portfolio) return 0;
    return portfolio.holdings.find((h) => h.ticker === selected.ticker)?.quantity ?? 0;
  }, [selected, portfolio]);

  const dissolvedStocks = useMemo(
    () => stocks.filter((s) => s.is_open === false),
    [stocks],
  );

  const patchStockPrice = useCallback(
    (stockId: number, ltp: string, percentChange?: string) => {
      setStocks((prev) =>
        prev.map((s) =>
          s.id === stockId
            ? {
                ...s,
                last_traded_price: ltp,
                ...(percentChange != null ? { percent_change: percentChange } : {}),
              }
            : s,
        ),
      );
      setSectors((prev) =>
        prev.map((sector) => ({
          ...sector,
          stocks: sector.stocks.map((s) =>
            s.stock_id === stockId
              ? {
                  ...s,
                  last_traded_price: ltp,
                  ...(percentChange != null ? { percent_change: percentChange } : {}),
                }
              : s,
          ),
        })),
      );
    },
    [],
  );

  const applySimulationState = useCallback((sim: SimulationState | undefined) => {
    if (!sim) return;
    if (typeof sim.trading_enabled === "boolean") {
      setTradingEnabled(sim.trading_enabled);
    } else if (sim.status) {
      setTradingEnabled(sim.status === "running");
    }
  }, []);

  const showBreaking = useCallback((item: NewsItem) => {
    setBreaking(item);
    setNewsFeed((prev) => {
      const without = prev.filter((n) => n.id !== item.id);
      return [item, ...without].slice(0, 12);
    });
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
        available_cash: asMoney(data.wallet.available_cash),
        portfolio_value: asMoney(data.wallet.portfolio_value),
        total_pnl: asMoney(data.wallet.total_pnl ?? "0"),
        return_pct: asMoney(data.wallet.return_pct ?? "0"),
        starting_capital: data.wallet.starting_capital
          ? asMoney(data.wallet.starting_capital)
          : undefined,
      });
      setPortfolio({
        holdings: (data.portfolio.holdings ?? []).map((h) => ({
          ticker: h.ticker,
          quantity: h.quantity,
          avg_cost: h.avg_cost != null ? asMoney(h.avg_cost) : undefined,
        })),
        starting_capital:
          data.portfolio.starting_capital != null
            ? asMoney(data.portfolio.starting_capital)
            : undefined,
        realized_pnl:
          data.portfolio.realized_pnl != null ? asMoney(data.portfolio.realized_pnl) : undefined,
        cash_blocked_ipo:
          data.portfolio.cash_blocked_ipo != null
            ? asMoney(data.portfolio.cash_blocked_ipo)
            : undefined,
      });
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
      if (data.released_news?.length) {
        const items = data.released_news.map((n) => ({
          id: n.id,
          title: n.title,
          description: n.description ?? "",
          brief_points: n.brief_points,
          released_at: n.released_at,
        }));
        setNewsFeed(items);
        setBreaking((prev) => prev ?? items[0]);
      }
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
      localStorage.removeItem("mse_access_token");
      localStorage.removeItem("mse_trader_id");
      setTraderId(null);
      setWallet(null);
      setPortfolio(null);
    }
  }, [applyBootstrap]);

  const refreshWalletDetail = useCallback(async (explicitTraderId?: number) => {
    const id = explicitTraderId ?? traderId;
    if (!id) return;
    setWalletLoading(true);
    try {
      const [detail, orders, trades] = await Promise.all([
        fetchPortfolio(id),
        fetchOrders(),
        fetchTrades(),
      ]);
      setPortfolioDetail(detail);
      const tickerMap = new Map(stocks.map((s) => [s.id, s.ticker]));
      setTransactions(mergeTransactions(orders, trades, tickerMap));
    } catch {
      /* wallet panel is optional */
    } finally {
      setWalletLoading(false);
    }
  }, [traderId, stocks]);

  const refreshWallet = useCallback(async (explicitTraderId?: number) => {
    const id = explicitTraderId ?? traderId;
    if (!id) return;
    try {
      const [w, p, lb] = await Promise.all([
        apiGet<Wallet>(`/traders/${id}/wallet`),
        apiGet<Portfolio>(`/traders/${id}/portfolio`),
        apiGet<LeaderboardRow[]>("/leaderboard"),
      ]);
      setWallet({
        available_cash: asMoney(w.available_cash),
        portfolio_value: asMoney(w.portfolio_value),
        total_pnl: asMoney(w.total_pnl ?? "0"),
        return_pct: asMoney(w.return_pct ?? "0"),
        starting_capital: w.starting_capital ? asMoney(w.starting_capital) : undefined,
      });
      setPortfolio({
        holdings: (p.holdings ?? []).map((h) => ({
          ticker: h.ticker,
          quantity: h.quantity,
          avg_cost: h.avg_cost != null ? asMoney(h.avg_cost) : undefined,
        })),
        starting_capital: p.starting_capital != null ? asMoney(p.starting_capital) : undefined,
        realized_pnl: p.realized_pnl != null ? asMoney(p.realized_pnl) : undefined,
        cash_blocked_ipo: p.cash_blocked_ipo != null ? asMoney(p.cash_blocked_ipo) : undefined,
      });
      setLeaderboard(lb);
      if (showWallet) {
        void refreshWalletDetail(id);
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : "";
      if (message.toLowerCase().includes("401") || message.toLowerCase().includes("unauthor")) {
        localStorage.removeItem("mse_access_token");
        localStorage.removeItem("mse_trader_id");
        setTraderId(null);
      }
    }
  }, [traderId, showWallet, refreshWalletDetail]);

  const refresh = useCallback(async () => {
    try {
      await refreshStocks();
      await refreshSectors();
      const openIpos = await apiGet<IPO[]>("/ipos/open").catch(() => [] as IPO[]);
      setIpos(openIpos);
      if (traderId) await refreshWallet(traderId);
      const news = await apiGet<NewsItem[]>("/news").catch(() => [] as NewsItem[]);
      if (news.length) {
        setNewsFeed(
          news.slice(0, 12).map((n) => ({
            id: n.id,
            title: n.title,
            description: n.description ?? "",
            brief_points: n.brief_points,
            released_at: n.released_at,
          })),
        );
      }
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

  useEffect(() => {
    if (showWallet && traderId) {
      void refreshWalletDetail(traderId);
    }
  }, [showWallet, traderId, refreshWalletDetail]);

  useEffect(() => {
    if (!breaking) return;
    const id = window.setTimeout(() => setBreaking(null), 20_000);
    return () => window.clearTimeout(id);
  }, [breaking]);

  const { connected, reconnecting } = useMarketWebSocket({
    onOpen: () => setWsStatus("LIVE"),
    onClose: () => setWsStatus("Reconnecting"),
    onReconnect: () => {
      setWsStatus("LIVE");
      void resyncBootstrap();
    },
    onMessage: (msg) => {
      if (msg.event === "NEWS_RELEASED") {
        const raw = (msg.payload ?? msg) as Record<string, unknown>;
        const item = newsFromPayload(raw);
        if (item) showBreaking(item);
      }
      if (msg.event === "SIMULATION_CLOCK" || msg.event === "SIMULATION_STATUS") {
        applySimulationState((msg.payload ?? msg) as SimulationState);
      }
      if (msg.event === "MARKET_PULSE") {
        const payload = (msg.payload ?? msg) as { stocks?: MarketPulseStock[] };
        const rows = payload.stocks ?? [];
        handleMarketPulse(rows);
        for (const row of rows) {
          patchStockPrice(row.stock_id, row.ltp, row.percent_change);
        }
      }
      if (msg.event === "PRICE_UPDATED") {
        const payload = (msg.payload ?? msg) as PriceUpdatePayload & { percent_change?: string };
        handlePriceUpdate(payload);
        const stockId = payload.stock_id;
        if (stockId) {
          const ltp =
            payload.ltp ??
            (payload.trades?.length ? payload.trades[payload.trades.length - 1].price : undefined);
          if (ltp) patchStockPrice(stockId, ltp, payload.percent_change);
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
      await refreshWallet(created.trader_id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not join session");
    }
  }

  function openConfirm(side: "buy" | "sell") {
    setConfirmError(null);
    if (side === "buy" && holdingQty + qty > MAX_POSITION_PER_STOCK) {
      setToast(`Max ${MAX_POSITION_PER_STOCK} shares per stock (you hold ${holdingQty})`);
      return;
    }
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
      await refreshWallet(traderId);
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
      await refreshWallet(traderId);
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
        cash={displayWallet?.available_cash}
        portfolio={displayWallet?.portfolio_value}
        pnl={displayWallet?.total_pnl}
        ret={displayWallet?.return_pct}
        onWallet={() => setShowWallet((v) => !v)}
        showWallet={showWallet}
        onLeaderboard={() => setShowLb((v) => !v)}
        showLeaderboard={showLb}
      />
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 px-3 py-1.5 text-[10px] text-white/40 sm:px-4">
        <span>
          {wsStatus}
          {!connected && wsStatus === "OFF" ? " · fallback poll 12s" : ""}
        </span>
        <span className={tradingEnabled ? "text-[#22c55e]" : "text-yellow-400"}>
          {tradingEnabled ? "MARKET OPEN" : "MARKET CLOSED"}
        </span>
      </div>

      {selectedNews && (
        <LatestNewsPanel
          newsFeed={newsFeed}
          selected={selectedNews}
          onSelect={(item) => setSelectedNewsId(item.id)}
        />
      )}

      <BreakingNewsAlert news={breaking} onDismiss={() => setBreaking(null)} />

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-0 lg:grid-cols-[220px_1fr] xl:grid-cols-[260px_1fr]">
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

      {showWallet && (
        <WalletPanel
          portfolio={portfolioDetail}
          holdings={liveHoldings}
          transactions={transactions}
          loading={walletLoading}
        />
      )}

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
