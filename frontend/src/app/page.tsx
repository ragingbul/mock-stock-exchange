"use client";

import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
  service: string;
  env: string;
  phase: number;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_PREFIX = process.env.NEXT_PUBLIC_API_PREFIX ?? "/api/v1";

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadHealth() {
      try {
        const response = await fetch(`${API_URL}${API_PREFIX}/health`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = (await response.json()) as HealthResponse;
        if (!cancelled) {
          setHealth(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setHealth(null);
          setError(err instanceof Error ? err.message : "Backend unreachable");
        }
      }
    }

    loadHealth();
    const id = window.setInterval(loadHealth, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-16">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-accent">
        Phase 0 · Foundation
      </p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-5xl">
        Mock Stock Exchange
      </h1>
      <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted">
        Multiplayer trading simulation. Orders go through an order book and
        matching engine — executed trades set the market price. News and models
        influence behaviour, not last traded price.
      </p>

      <section className="mt-10 border border-line bg-panel p-5">
        <div className="flex items-center justify-between gap-4">
          <h2 className="font-mono text-sm uppercase tracking-wider text-muted">
            Backend health
          </h2>
          <span
            className={`font-mono text-xs ${
              health ? "text-accent" : "text-warn"
            }`}
          >
            {health ? "CONNECTED" : "WAITING"}
          </span>
        </div>

        {health ? (
          <dl className="mt-4 grid gap-2 font-mono text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted">Status</dt>
              <dd>{health.status}</dd>
            </div>
            <div>
              <dt className="text-muted">Service</dt>
              <dd>{health.service}</dd>
            </div>
            <div>
              <dt className="text-muted">Environment</dt>
              <dd>{health.env}</dd>
            </div>
            <div>
              <dt className="text-muted">Phase</dt>
              <dd>{health.phase}</dd>
            </div>
          </dl>
        ) : (
          <p className="mt-4 text-sm text-muted">
            {error
              ? `Cannot reach API at ${API_URL}${API_PREFIX}/health (${error}). Start the backend with uvicorn.`
              : "Checking API…"}
          </p>
        )}
      </section>

      <p className="mt-8 font-mono text-xs text-muted">
        Next: Phase 1 — database models and core entities.
      </p>
    </main>
  );
}
