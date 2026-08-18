"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, getApiBaseUrl } from "@/lib/api";

type HealthResponse = {
  status: string;
  service: string;
  env: string;
  phase: number;
};

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    apiGet<HealthResponse>("/health")
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-16 bg-black text-white">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-[#22c55e]">
        TRADEVERSE
      </p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-5xl">
        Three hours. One market. Your call.
      </h1>
      <p className="mt-4 max-w-2xl text-base leading-relaxed text-white/60">
        A cinematic stock simulation driven by a preloaded timeline. Trade live
        news, IPOs, and a crash — while admins run START, STOP, and RESET.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <Link
          href="/terminal"
          className="bg-[#22c55e] px-5 py-3 font-mono text-sm text-black"
        >
          Open terminal
        </Link>
        <Link
          href="/admin"
          className="border border-white/25 px-5 py-3 font-mono text-sm"
        >
          Admin panel
        </Link>
        <Link
          href="/market-screen"
          className="border border-white/25 px-5 py-3 font-mono text-sm"
        >
          Market screen
        </Link>
      </div>
      <p className="mt-8 font-mono text-xs text-white/40">
        API {health ? `${health.status}` : "offline"} ·{" "}
        <a className="underline" href={`${getApiBaseUrl()}/docs`}>
          docs
        </a>
      </p>
    </main>
  );
}
