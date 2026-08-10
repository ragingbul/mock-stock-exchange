export type LeaderboardRow = {
  rank: number;
  trader_id: number;
  name: string;
  portfolio_value: string;
  return_pct: string;
  trade_count: number;
};

function fmtMoney(v: string): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return v;
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function fmtPct(v: string): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return v;
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
}

type LeaderboardProps = {
  rows: LeaderboardRow[];
  variant: "admin" | "terminal";
  highlightTraderId?: number | null;
  loading?: boolean;
  maxRows?: number;
};

export function Leaderboard({
  rows,
  variant,
  highlightTraderId,
  loading = false,
  maxRows = 15,
}: LeaderboardProps) {
  const shown = rows.slice(0, maxRows);

  if (variant === "terminal") {
    return (
      <div className="border border-white/15 p-3">
        <p className="text-xs text-white/40">Leaderboard</p>
        {loading && !shown.length ? (
          <p className="mt-2 text-xs text-white/30">Loading…</p>
        ) : !shown.length ? (
          <p className="mt-2 text-xs text-white/30">No traders yet</p>
        ) : (
          <table className="mt-2 w-full text-xs tabular-nums">
            <thead>
              <tr className="text-white/40">
                <th className="pb-2 text-left">#</th>
                <th className="pb-2 text-left">Trader</th>
                <th className="pb-2 text-right">Return</th>
                <th className="pb-2 text-right">Value</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((row) => {
                const isYou = highlightTraderId != null && row.trader_id === highlightTraderId;
                const ret = Number(row.return_pct);
                const retCls = ret > 0 ? "text-[#22c55e]" : ret < 0 ? "text-[#ef4444]" : "text-white";
                return (
                  <tr
                    key={row.trader_id}
                    className={isYou ? "bg-white/10" : undefined}
                  >
                    <td className="py-1 pr-2">{row.rank}</td>
                    <td className="py-1 pr-2 truncate max-w-[8rem]">
                      {row.name}
                      {isYou ? <span className="text-white/50"> · you</span> : null}
                    </td>
                    <td className={`py-1 text-right ${retCls}`}>{fmtPct(row.return_pct)}</td>
                    <td className="py-1 text-right text-white/70">₹{fmtMoney(row.portfolio_value)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    );
  }

  return (
    <div>
      {loading && !shown.length ? (
        <p className="mt-2 font-mono text-xs text-muted">Loading leaderboard…</p>
      ) : !shown.length ? (
        <p className="mt-2 font-mono text-xs text-muted">No human traders yet</p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full font-mono text-xs">
            <thead>
              <tr className="text-left text-muted">
                <th className="pb-2 pr-3">Rank</th>
                <th className="pb-2 pr-3">Trader</th>
                <th className="pb-2 pr-3 text-right">Return %</th>
                <th className="pb-2 pr-3 text-right">Portfolio</th>
                <th className="pb-2 text-right">Trades</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((row) => {
                const ret = Number(row.return_pct);
                const retCls =
                  ret > 0 ? "text-accent" : ret < 0 ? "text-warn" : "text-muted";
                return (
                  <tr key={row.trader_id} className="border-t border-line/60">
                    <td className="py-2 pr-3 tabular-nums">{row.rank}</td>
                    <td className="py-2 pr-3">
                      <span className="text-white">{row.name}</span>
                      <span className="ml-2 text-muted">#{row.trader_id}</span>
                    </td>
                    <td className={`py-2 pr-3 text-right tabular-nums ${retCls}`}>
                      {fmtPct(row.return_pct)}
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums text-muted">
                      ₹{fmtMoney(row.portfolio_value)}
                    </td>
                    <td className="py-2 text-right tabular-nums text-muted">{row.trade_count}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
