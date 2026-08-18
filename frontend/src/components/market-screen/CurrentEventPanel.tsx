"use client";

import { fmtPct, signClass } from "@/lib/marketFormat";
import { impactForColumn, SECTOR_COLUMNS } from "@/lib/sectorImpactUtils";

type Props = {
  title: string;
  description?: string;
  sectorImpacts?: Record<string, number>;
};

export function CurrentEventPanel({ title, description, sectorImpacts }: Props) {
  const impacts = SECTOR_COLUMNS.map((col) => ({
    name: col.name,
    value: impactForColumn(sectorImpacts, col),
  })).filter((x) => x.value != null);

  return (
    <section className="border border-[#ef4444]/30 bg-[#ef4444]/5 p-6">
      <p className="text-xs uppercase tracking-widest text-[#ef4444]">Current market event</p>
      <h2 className="mt-2 text-2xl font-bold md:text-3xl">{title}</h2>
      {description && <p className="mt-2 max-w-3xl text-base text-white/60 md:text-lg">{description}</p>}
      {impacts.length > 0 && (
        <ul className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-4">
          {impacts.map(({ name, value }) => (
            <li key={name} className="font-mono text-sm md:text-base">
              <span className="text-white/60">{name}</span>{" "}
              <span className={signClass(value)}>{fmtPct(value)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
