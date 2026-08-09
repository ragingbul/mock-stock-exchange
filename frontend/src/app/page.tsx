"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

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
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-16">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-accent">
        Mock Stock Exchange
      </p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-5xl">
        Trade the book, not the formula.
      </h1>
      <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted">
        Orders hit an order book. The matching engine discovers price. News and
        models move agents — never last traded price directly.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <Link
          href="/terminal"
          className="bg-accent px-5 py-3 font-mono text-sm text-black"
        >
          Open terminal
        </Link>
        <Link
          href="/admin"
          className="border border-line px-5 py-3 font-mono text-sm"
        >
          Admin panel
        </Link>
      </div>
      <p className="mt-8 font-mono text-xs text-muted">
        API {health ? `phase ${health.phase} · ${health.status}` : "offline"} ·{" "}
        <a className="underline" href="http://localhost:8000/docs">
          docs
        </a>
      </p>
    </main>
  );
}
