/** Sector columns aligned with backend TRADEVERSE_SECTORS catalogue. */
export const SECTOR_COLUMNS = [
  { slug: "financials", name: "Financials", aliases: ["financials", "finance"] },
  { slug: "it", name: "IT", aliases: ["it", "technology", "tech", "data"] },
  { slug: "automobiles", name: "Automobiles", aliases: ["automobiles", "auto", "automotive"] },
  { slug: "energy", name: "Energy", aliases: ["energy"] },
  { slug: "industrials", name: "Industrials", aliases: ["industrials", "industrial"] },
  { slug: "infrastructure", name: "Infrastructure", aliases: ["infrastructure", "infra"] },
  { slug: "real_estate", name: "Real Estate", aliases: ["real estate", "real_estate"] },
  { slug: "metals", name: "Metals", aliases: ["metals", "metal"] },
  { slug: "consumer", name: "Consumer", aliases: ["consumer", "retail", "food", "healthcare"] },
] as const;

export type NewsImpactRow = {
  id: number;
  title: string;
  sector_impacts?: Record<string, number>;
};

export function impactForColumn(
  impacts: Record<string, number> | undefined,
  column: (typeof SECTOR_COLUMNS)[number],
): number | null {
  if (!impacts) return null;
  const normalized = Object.entries(impacts).map(([k, v]) => [k.toLowerCase().trim(), v] as const);
  for (const [key, value] of normalized) {
    if (key === "broad market" || key === "market-wide") continue;
    if (column.aliases.some((a) => key === a || key.includes(a))) return value;
    if (key === column.name.toLowerCase()) return value;
  }
  return null;
}

export function intensityDots(value: number | null): { count: number; tone: "up" | "down" | "neutral" } {
  if (value == null || Math.abs(value) < 0.5) return { count: 0, tone: "neutral" };
  const count = Math.min(5, Math.max(1, Math.round(Math.abs(value))));
  return { count, tone: value > 0 ? "up" : "down" };
}

export function renderDots(count: number, tone: "up" | "down" | "neutral"): string {
  if (count === 0) return "—";
  const ch = tone === "up" ? "🟢" : tone === "down" ? "🔴" : "⚪";
  return ch.repeat(count);
}
