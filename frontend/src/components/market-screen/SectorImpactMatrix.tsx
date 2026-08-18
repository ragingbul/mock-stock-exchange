"use client";

import {
  impactForColumn,
  intensityDots,
  renderDots,
  SECTOR_COLUMNS,
  type NewsImpactRow,
} from "@/lib/sectorImpactUtils";

type Props = {
  news: NewsImpactRow[];
};

export function SectorImpactMatrix({ news }: Props) {
  const rows = [...news].reverse();

  return (
    <section className="flex min-h-0 flex-1 flex-col border border-white/15 p-4">
      <p className="mb-3 text-xs uppercase tracking-widest text-white/40">Released event impact matrix</p>
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full min-w-[900px] border-collapse text-left text-sm md:text-base">
          <thead>
            <tr className="border-b border-white/20 text-[10px] uppercase tracking-wider text-white/50 md:text-xs">
              <th className="sticky left-0 z-10 bg-black px-3 py-2">Event</th>
              {SECTOR_COLUMNS.map((col) => (
                <th key={col.slug} className="px-2 py-2 text-center">
                  {col.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.id} className="border-b border-white/10 hover:bg-white/5">
                <td className="sticky left-0 z-10 max-w-[220px] bg-black px-3 py-2 text-xs md:text-sm">
                  {item.title}
                </td>
                {SECTOR_COLUMNS.map((col) => {
                  const val = impactForColumn(item.sector_impacts, col);
                  const { count, tone } = intensityDots(val);
                  return (
                    <td key={col.slug} className="px-2 py-2 text-center font-mono text-lg md:text-xl">
                      {renderDots(count, tone)}
                    </td>
                  );
                })}
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan={SECTOR_COLUMNS.length + 1} className="px-3 py-8 text-center text-white/40">
                  No released events yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
