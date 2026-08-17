"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type SimStatus = {
  status: string;
  elapsed: string;
  duration: string;
  elapsed_sec: number;
  current_phase: string;
  current_event?: { headline: string; checkpoint_id?: number } | null;
  next_event?: { headline: string } | null;
  seconds_to_next_event?: number | null;
  completed_checkpoint_count: number;
  total_checkpoint_count: number;
  checkpoints?: Array<{
    checkpoint_id: number;
    headline: string;
    status: string;
    timestamp: string;
    type: string;
  }>;
};

function fmtCountdown(sec: number | null | undefined) {
  if (sec == null) return "—";
  const s = Math.max(0, Math.floor(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

export default function AdminPage() {
  const [status, setStatus] = useState<SimStatus | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await apiGet<SimStatus>("/admin/simulation/status");
      setStatus(data);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed to load status");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 2000);
    return () => clearInterval(id);
  }, [refresh]);

  async function act(action: "start" | "stop" | "reset") {
    setBusy(true);
    setMsg("");
    try {
      await apiPost(`/admin/simulation/${action}`);
      setMsg(`${action.toUpperCase()} OK`);
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : `${action} failed`);
    } finally {
      setBusy(false);
    }
  }

  const cp = status?.checkpoints ?? [];
  const currentId = status?.current_event?.checkpoint_id;

  return (
    <main className="min-h-screen bg-black text-white p-8 max-w-2xl mx-auto font-mono">
      <h1 className="text-2xl font-bold tracking-widest mb-8 text-center">TRADEVERSE ADMIN</h1>

      <div className="flex gap-4 justify-center mb-8">
        <button
          disabled={busy}
          onClick={() => act("start")}
          className="px-8 py-3 bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded"
        >
          ▶ START
        </button>
        <button
          disabled={busy}
          onClick={() => act("stop")}
          className="px-8 py-3 bg-yellow-700 hover:bg-yellow-600 disabled:opacity-50 rounded"
        >
          ⏸ STOP
        </button>
        <button
          disabled={busy}
          onClick={() => act("reset")}
          className="px-8 py-3 bg-red-800 hover:bg-red-700 disabled:opacity-50 rounded"
        >
          ↻ RESET
        </button>
      </div>

      {msg && <p className="text-center text-sm text-yellow-300 mb-4">{msg}</p>}

      {status && (
        <section className="border border-neutral-700 rounded p-4 space-y-3 mb-6">
          <p className="text-xl text-center">
            {status.elapsed} / {status.duration}
          </p>
          <p className="text-center text-neutral-300">{status.current_phase}</p>
          <p>
            <span className="text-neutral-500">CURRENT: </span>
            {status.current_event?.headline ?? "—"}
          </p>
          <p>
            <span className="text-neutral-500">NEXT: </span>
            {status.next_event?.headline ?? "—"}
          </p>
          <p>
            <span className="text-neutral-500">IN: </span>
            {fmtCountdown(status.seconds_to_next_event)}
          </p>
          <p className="text-sm text-neutral-400">
            Checkpoints {status.completed_checkpoint_count}/{status.total_checkpoint_count} · Status: {status.status}
          </p>
        </section>
      )}

      <section className="border border-neutral-700 rounded p-4 max-h-96 overflow-y-auto">
        <h2 className="text-sm text-neutral-500 mb-3">CHECKPOINTS (read-only)</h2>
        <ul className="space-y-1 text-sm">
          {cp.map((c) => {
            const mark =
              c.status === "executed"
                ? currentId === c.checkpoint_id
                  ? "●"
                  : "✓"
                : "○";
            return (
              <li key={c.checkpoint_id} className={c.status === "executed" ? "text-green-400" : "text-neutral-500"}>
                {mark} {c.timestamp} {c.headline}
              </li>
            );
          })}
        </ul>
      </section>

      <p className="text-center text-xs text-neutral-600 mt-8">
        Simulation runs on the server. Closing this tab does not stop the movie.
      </p>
    </main>
  );
}
