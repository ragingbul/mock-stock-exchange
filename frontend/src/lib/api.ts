/**
 * Frontend API helpers.
 * Phase 0: health check only. Trading APIs arrive in later phases.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_PREFIX = process.env.NEXT_PUBLIC_API_PREFIX ?? "/api/v1";

export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_URL}${API_PREFIX}${normalized}`;
}

export async function fetchHealth(): Promise<{
  status: string;
  service: string;
  env: string;
  phase: number;
}> {
  const response = await fetch(apiUrl("/health"), { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json();
}
