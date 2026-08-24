"use client";

import { fmtMoney, fmtPct, signClass } from "@/lib/marketFormat";

type Props = {
  cash?: string | null;
  portfolio?: string | null;
  pnl?: string | null;
  ret?: string | null;
  onLeaderboard: () => void;
  showLeaderboard: boolean;
  onWallet: () => void;
  showWallet: boolean;
};

export function WalletBar({
  cash,
  portfolio,
  pnl,
  ret,
  onLeaderboard,
  showLeaderboard,
  onWallet,
  showWallet,
}: Props) {
  return (
    <header className="sticky top-0 z-30 border-b border-white/15 bg-black/95 px-3 py-2 backdrop-blur sm:px-4">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 sm:gap-3">
        <span className="text-sm font-bold tracking-widest">TRADEVERSE</span>
        <div className="flex flex-1 flex-wrap items-center justify-end gap-x-3 gap-y-1 text-[11px] sm:gap-x-4 sm:text-xs">
          <span className="whitespace-nowrap">
            <span className="text-white/40">Cash </span>
            <span className="tabular-nums">{fmtMoney(cash)}</span>
          </span>
          <span className="whitespace-nowrap">
            <span className="text-white/40">Portfolio </span>
            <span className="tabular-nums">{fmtMoney(portfolio)}</span>
          </span>
          <span className={`whitespace-nowrap ${signClass(pnl)}`}>
            <span className="text-white/40">P&L </span>
            <span className="tabular-nums">{fmtMoney(pnl)}</span>
          </span>
          <span className={`whitespace-nowrap ${signClass(ret)}`}>
            <span className="text-white/40">Return </span>
            <span className="tabular-nums">{ret != null ? fmtPct(ret) : "—"}</span>
          </span>
          <button
            type="button"
            onClick={onWallet}
            className={`border px-2.5 py-1 text-[10px] uppercase hover:bg-white/10 ${
              showWallet ? "border-[#22c55e] text-[#22c55e]" : "border-white/25"
            }`}
          >
            {showWallet ? "Hide Wallet" : "Wallet"}
          </button>
          <button
            type="button"
            onClick={onLeaderboard}
            className="border border-white/25 px-2.5 py-1 text-[10px] uppercase hover:bg-white/10"
          >
            {showLeaderboard ? "Hide LB" : "Leaderboard"}
          </button>
        </div>
      </div>
    </header>
  );
}
