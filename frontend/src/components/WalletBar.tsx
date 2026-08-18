"use client";

import { fmtMoney, fmtPct, signClass } from "@/lib/marketFormat";

type Props = {
  cash?: string | null;
  portfolio?: string | null;
  pnl?: string | null;
  ret?: string | null;
  onLeaderboard: () => void;
  showLeaderboard: boolean;
};

export function WalletBar({ cash, portfolio, pnl, ret, onLeaderboard, showLeaderboard }: Props) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border border-white/15 px-4 py-2 text-xs">
      <span className="text-sm font-bold tracking-widest">TRADEVERSE</span>
      <div className="flex flex-wrap gap-4">
        <span>
          <span className="text-white/40">Cash </span>
          {fmtMoney(cash)}
        </span>
        <span>
          <span className="text-white/40">Portfolio </span>
          {fmtMoney(portfolio)}
        </span>
        <span className={signClass(pnl)}>
          <span className="text-white/40">P&L </span>
          {fmtMoney(pnl)}
        </span>
        <span className={signClass(ret)}>
          <span className="text-white/40">Return </span>
          {ret != null ? fmtPct(ret) : "—"}
        </span>
      </div>
      <button
        type="button"
        onClick={onLeaderboard}
        className="border border-white/25 px-3 py-1 text-[10px] uppercase hover:bg-white/10"
      >
        {showLeaderboard ? "Hide leaderboard" : "Leaderboard"}
      </button>
    </div>
  );
}
