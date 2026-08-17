export function num(v: string | number | null | undefined): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

export function signClass(v: string | number | null | undefined): string {
  const n = num(v);
  if (n > 0.05) return "text-[#22c55e]";
  if (n < -0.05) return "text-[#ef4444]";
  return "text-white/70";
}

export function fmtPct(v: string | number | null | undefined): string {
  const n = num(v);
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
}

export function fmtMoney(v: string | number | null | undefined): string {
  return `₹${num(v).toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`;
}
